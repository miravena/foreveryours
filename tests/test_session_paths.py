"""Session ids are checked before they become file paths (#147)."""
import os
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import webapp

# Gradio hands over uploads under the temp dir; webapp refuses audio paths outside it.
FAKE_UPLOAD = os.path.join(tempfile.gettempdir(), "fake.wav")


class TestSessionPaths(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.sessions_dir.mkdir()
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def test_valid_id_maps_under_sessions_dir(self):
        sid = "0123456789abcdef0123456789abcdef"
        data_dir, audio_dir = webapp._session_dirs(sid)
        root = Path(os.path.realpath(self.sessions_dir)) / sid
        self.assertEqual(data_dir, root / "data")
        self.assertEqual(audio_dir, root / "audio")

    def test_traversal_and_malformed_ids_are_rejected(self):
        for bad in ("../x", "..", "", "/etc", "ABCDEF0123456789ABCDEF0123456789",
                    "0123456789abcdef0123456789abcde", "0123456789abcdef0123456789abcdef/..",
                    None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                webapp._session_root(bad)

    def test_end_session_with_bad_id_deletes_nothing(self):
        victim = Path(self.temp_dir.name) / "victim"
        victim.mkdir()
        (victim / "keep.txt").write_text("x")
        webapp._end_session("../victim")  # must not raise
        self.assertTrue((victim / "keep.txt").exists())
        self.assertTrue(self.sessions_dir.exists())

    def test_shared_profile_is_unchanged(self):
        with patch.object(webapp, "SHARED_PROFILE", True):
            self.assertEqual(webapp._session_dirs(webapp.DEFAULT_PROFILE_ID),
                             (webapp.DATA_DIR, webapp.AUDIO_DIR))

    def test_shared_profile_public_turns_bypass_per_session_validation(self):
        with patch.object(webapp, "SHARED_PROFILE", True), \
             patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"), \
             patch.object(webapp, "AUDIO_DIR", Path(self.temp_dir.name) / "audio"), \
             patch.object(webapp, "run_turn") as mock_run_turn:
            from pipeline.orchestrator import TurnResult
            mock_run_turn.return_value = TurnResult("hello", "hello")

            ordinary = webapp.run_demo_turn(None, "hello", [], webapp.DEFAULT_PROFILE_ID)

        self.assertEqual(ordinary[5], webapp.DEFAULT_PROFILE_ID)

        # Exercise the real offline safety path as well as the ordinary
        # pipeline stub: shared mode must not reject "dad" before crisis
        # handling can run.
        with patch.object(webapp, "SHARED_PROFILE", True), \
             patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"), \
             patch.object(webapp, "AUDIO_DIR", Path(self.temp_dir.name) / "audio"):
            webapp.DATA_DIR.mkdir(parents=True, exist_ok=True)
            webapp.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            crisis = webapp.run_demo_turn(None, "I want to die", [], webapp.DEFAULT_PROFILE_ID)
            streaming = list(webapp.run_demo_turn_streaming(
                None, "I want to die", [], webapp.DEFAULT_PROFILE_ID
            ))

        self.assertIn("988", crisis[0])
        self.assertEqual(crisis[5], webapp.DEFAULT_PROFILE_ID)
        self.assertTrue(streaming)
        self.assertIn("988", streaming[-1][0])
        self.assertEqual(streaming[-1][5], webapp.DEFAULT_PROFILE_ID)
        self.assertEqual(mock_run_turn.call_count, 1)



class TestSweepKeepsActiveSessions(unittest.TestCase):
    """#146: the sweeper must not delete a household that is still in use."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _age(self, sid):
        old = time.time() - webapp.SESSION_TTL_S - 60
        os.utime(self.sessions_dir / sid, (old, old))

    def test_recent_memo_save_keeps_session(self):
        active, _ = webapp.init_session()
        orphan, _ = webapp.init_session()
        self._age(active)
        self._age(orphan)
        webapp.save_caregiver_text_memo("Dad has physio on Tuesday.", active)
        webapp._sweep_stale_sessions()
        self.assertTrue((self.sessions_dir / active).exists())
        self.assertFalse((self.sessions_dir / orphan).exists())

    def test_in_flight_background_thread_keeps_session(self):
        sid, _ = webapp.init_session()
        self._age(sid)
        release = threading.Event()
        worker = threading.Thread(target=release.wait, daemon=True)
        worker.start()
        webapp._remember_background_thread(sid, worker)
        try:
            webapp._sweep_stale_sessions()
            self.assertTrue((self.sessions_dir / sid).exists())
        finally:
            release.set()
            worker.join(timeout=2)
        webapp._sweep_stale_sessions()
        self.assertFalse((self.sessions_dir / sid).exists())
        with webapp._bg_threads_lock:
            webapp._bg_threads.pop(sid, None)


class TestSweepAndEndSessionRaceFree(unittest.TestCase):
    """#148, #150, #151: the sweeper and `_end_session` share one protocol
    (`_session_fs_lock`, `_active_turns`, a per-session list of live writer
    threads) so neither can race a touch/turn, follow a symlink alias, or
    sweep a stray non-session directory."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.sessions_dir.mkdir()
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _require(self, name):
        val = getattr(webapp, name, None)
        if val is None:
            self.fail(f"webapp.{name} does not exist (pre-fix code)")
        return val

    def _age(self, sid):
        old = time.time() - webapp.SESSION_TTL_S - 60
        os.utime(self.sessions_dir / sid, (old, old))

    def test_symlink_alias_with_valid_hex_name_survives_sweep_and_end_session(self):
        # The target is itself another real session UNDER sessions_dir, not an
        # external directory: `_session_root()` returns a realpath, and a
        # same-directory alias resolves to a path that still passes its
        # containment check (base/<other-real-id>), so the alias/target
        # distinction has to be made on the literal, unresolved entry -- an
        # external target would instead just fail `_session_root()`'s
        # containment check outright and prove nothing about that path.
        target_id = "99998888777766665555444433332222"
        target = self.sessions_dir / target_id
        target.mkdir()
        (target / "keep.txt").write_text("precious")
        alias = "11112222333344445555666677778888"
        (self.sessions_dir / alias).symlink_to(target, target_is_directory=True)

        # `target` is a fresh, ordinary session -- NOT aged, and SESSION_TTL_S
        # is left at its default (not patched to 0): a direct sweep of ITS OWN
        # entry would never reap it on TTL grounds either, which isolates the
        # alias-resolution bug (the thing under test) from ordinary
        # TTL-expiry sweeping of the target's own ordinary entry.
        webapp._sweep_stale_sessions()
        self.assertTrue(target.exists())
        self.assertTrue((target / "keep.txt").exists())

        webapp._end_session(alias)
        self.assertTrue(target.exists())
        self.assertTrue((target / "keep.txt").exists())

    def test_symlink_alias_to_an_external_directory_also_survives(self):
        # Belt-and-suspenders: an alias pointing OUTSIDE sessions_dir entirely
        # must also never be followed, even though `_session_root()` would
        # reject it anyway via the containment check.
        target = Path(self.temp_dir.name) / "other-household"
        target.mkdir()
        (target / "keep.txt").write_text("precious")
        alias = "aaaa2222333344445555666677778888"
        (self.sessions_dir / alias).symlink_to(target, target_is_directory=True)

        with patch.object(webapp, "SESSION_TTL_S", 0):
            webapp._sweep_stale_sessions()
            self.assertTrue(target.exists())
            self.assertTrue((target / "keep.txt").exists())

            webapp._end_session(alias)
            self.assertTrue(target.exists())
            self.assertTrue((target / "keep.txt").exists())

    def test_stray_non_hex_dir_survives_sweep_and_end_session(self):
        stray = self.sessions_dir / "not-a-session-id"
        stray.mkdir()
        (stray / "keep.txt").write_text("precious")
        old = time.time() - 999999
        os.utime(stray, (old, old))

        with patch.object(webapp, "SESSION_TTL_S", 0):
            webapp._sweep_stale_sessions()
            self.assertTrue(stray.exists())

            webapp._end_session("not-a-session-id")  # must not raise
            self.assertTrue(stray.exists())
            self.assertTrue((stray / "keep.txt").exists())

    def test_touch_race_keeps_session_alive_through_sweep(self):
        fs_lock = self._require("_session_fs_lock")
        sid, _ = webapp.init_session()
        root = self.sessions_dir / sid
        old = time.time() - 2 * 3600
        os.utime(root, (old, old))

        with patch.object(webapp, "SESSION_TTL_S", 3600):
            fs_lock.acquire()
            try:
                t = threading.Thread(target=webapp._sweep_stale_sessions)
                t.start()
                time.sleep(0.2)  # give the sweeper a chance to block on this entry
                os.utime(root, None)  # touch: mtime -> now, while the sweeper is still waiting on the lock
            finally:
                fs_lock.release()
            t.join(timeout=2)

        self.assertTrue(root.exists())

    def test_two_writers_one_slow_tracking_does_not_leak(self):
        self._require("_BG_JOIN_TIMEOUT_S")
        sid, _ = webapp.init_session()
        session_dir = self.sessions_dir / sid

        event_a = threading.Event()
        thread_a = threading.Thread(target=event_a.wait, daemon=True)
        thread_a.start()
        webapp._remember_background_thread(sid, thread_a)

        thread_b = threading.Thread(target=lambda: None)
        thread_b.start()
        thread_b.join(timeout=2)
        webapp._remember_background_thread(sid, thread_b)

        try:
            with patch.object(webapp, "SESSION_TTL_S", 0):
                webapp._sweep_stale_sessions()
                self.assertTrue(session_dir.exists(), "A still alive: sweep must not delete")
                webapp._end_session(sid)
                self.assertTrue(session_dir.exists(), "A still alive: _end_session must not delete")

                with patch.object(webapp, "_BG_JOIN_TIMEOUT_S", 0.1):
                    webapp._join_previous_turn(sid)  # times out: A is still blocked

                webapp._sweep_stale_sessions()
                self.assertTrue(session_dir.exists(), "join timeout must not drop A from tracking")
                webapp._end_session(sid)
                self.assertTrue(session_dir.exists())
        finally:
            event_a.set()
            thread_a.join(timeout=2)

        with patch.object(webapp, "SESSION_TTL_S", 0):
            webapp._sweep_stale_sessions()
        self.assertFalse(session_dir.exists(), "tracking leaked: session never got swept after A finished")

    def test_blocked_foreground_turn_survives_sweep_and_end_session(self):
        active_turns = self._require("_active_turns")
        sid, _ = webapp.init_session()
        session_dir = self.sessions_dir / sid

        block = threading.Event()
        release = threading.Event()

        def fake_run_turn(*a, **k):
            block.set()
            release.wait()
            return SimpleNamespace(
                reply_text="ok", audio_paths=[], caregiver_flag=None,
                is_fallback=False, background_thread=None,
            )

        with patch.object(webapp, "run_turn", side_effect=fake_run_turn), \
             patch.object(webapp, "SESSION_TTL_S", 0):
            worker = threading.Thread(target=webapp._run_demo_turn, args=(None, "hello", [], sid))
            worker.start()
            self.assertTrue(block.wait(timeout=2))

            webapp._sweep_stale_sessions()
            self.assertTrue(session_dir.exists())
            webapp._end_session(sid)
            self.assertTrue(session_dir.exists())

            release.set()
            worker.join(timeout=2)

        self.assertNotIn(sid, active_turns, "_active_turns entry must be cleaned up in finally")

    def test_two_overlapping_blocked_turns_one_released_still_survives_sweep(self):
        active_turns = self._require("_active_turns")
        sid, _ = webapp.init_session()
        session_dir = self.sessions_dir / sid

        pairs = queue.Queue()
        block1, release1 = threading.Event(), threading.Event()
        block2, release2 = threading.Event(), threading.Event()
        pairs.put((block1, release1))
        pairs.put((block2, release2))

        def fake_run_turn(*a, **k):
            block_evt, release_evt = pairs.get()
            block_evt.set()
            release_evt.wait()
            return SimpleNamespace(
                reply_text="ok", audio_paths=[], caregiver_flag=None,
                is_fallback=False, background_thread=None,
            )

        with patch.object(webapp, "run_turn", side_effect=fake_run_turn), \
             patch.object(webapp, "SESSION_TTL_S", 0):
            worker1 = threading.Thread(target=webapp._run_demo_turn, args=(None, "hello", [], sid))
            worker1.start()
            self.assertTrue(block1.wait(timeout=2))

            worker2 = threading.Thread(target=webapp._run_demo_turn, args=(None, "hello again", [], sid))
            worker2.start()
            self.assertTrue(block2.wait(timeout=2))

            self.assertEqual(active_turns.get(sid), 2)

            release1.set()
            worker1.join(timeout=2)

            webapp._sweep_stale_sessions()
            self.assertTrue(session_dir.exists(), "turn 2 still in progress: sweep must not delete")

            release2.set()
            worker2.join(timeout=2)

        self.assertNotIn(sid, active_turns)

    def test_streaming_disconnect_handoff_keeps_worker_then_writer_tracked(self):
        sid, _ = webapp.init_session()
        session_dir = self.sessions_dir / sid

        recorded = {}
        run_turn_block = threading.Event()
        run_turn_release = threading.Event()
        c_event = threading.Event()
        writer_c = threading.Thread(target=c_event.wait, daemon=True)

        def fake_run_turn(*a, **k):
            recorded["worker_thread"] = threading.current_thread()
            on_chunk = k.get("on_chunk")
            if on_chunk:
                on_chunk("Hello there.", Path(self.temp_dir.name) / "chunk0.wav")
            run_turn_block.set()
            run_turn_release.wait()
            writer_c.start()
            return SimpleNamespace(
                reply_text="Hello there.", audio_paths=[], caregiver_flag=None,
                is_fallback=False, background_thread=writer_c,
            )

        # The real worker thread webapp.py starts inside run_demo_turn_streaming
        # is not a daemon thread, so if an assertion below fails before we
        # release it, the interpreter would hang at exit waiting for it. Every
        # phase below releases its event(s) in `finally`, regardless of outcome.
        try:
            with patch.object(webapp, "run_turn", side_effect=fake_run_turn), \
                 patch.object(webapp, "_combine_audio_chunks", return_value=None), \
                 patch.object(webapp, "SESSION_TTL_S", 0):
                gen = webapp.run_demo_turn_streaming(None, "hello", [], sid)
                next(gen)  # "Companion is thinking..."
                next(gen)  # the chunk update -- blocks until fake_run_turn calls on_chunk
                self.assertTrue(run_turn_block.wait(timeout=2))

                gen.close()  # simulates the browser disconnecting mid-turn

                webapp._sweep_stale_sessions()
                self.assertTrue(session_dir.exists(), "worker thread still tracked and alive")
                webapp._end_session(sid)
                self.assertTrue(session_dir.exists())
        finally:
            run_turn_release.set()
            worker_thread = recorded.get("worker_thread")
            if worker_thread is not None:
                worker_thread.join(timeout=2)

        try:
            with patch.object(webapp, "SESSION_TTL_S", 0):
                webapp._sweep_stale_sessions()
                self.assertTrue(session_dir.exists(), "writer C still alive")
                webapp._end_session(sid)
                self.assertTrue(session_dir.exists())
        finally:
            c_event.set()
            writer_c.join(timeout=2)

        with patch.object(webapp, "SESSION_TTL_S", 0):
            webapp._sweep_stale_sessions()
        self.assertFalse(session_dir.exists(), "tracking leaked: session never got swept after C finished")

    def test_live_background_thread_blocks_end_session(self):
        sid, _ = webapp.init_session()
        session_dir = self.sessions_dir / sid
        ev = threading.Event()
        worker = threading.Thread(target=ev.wait, daemon=True)
        worker.start()
        webapp._remember_background_thread(sid, worker)
        try:
            webapp._end_session(sid)
            self.assertTrue(session_dir.exists())
        finally:
            ev.set()
            worker.join(timeout=2)
        webapp._end_session(sid)
        self.assertFalse(session_dir.exists())


class TestBadSessionIdNeverBlocksCrisisFastPath(unittest.TestCase):
    """#149: a malformed/foreign session id must never raise its way past
    the offline safety fast-path, and every read-only helper must degrade to
    its normal placeholder instead of raising."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.sessions_dir.mkdir()
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _assert_new_valid_session_id(self, new_sid):
        self.assertIsInstance(new_sid, str)
        self.assertRegex(new_sid, r"^[0-9a-f]{32}$")

    def _assert_nothing_written_outside_sessions_dir(self):
        self.assertFalse((self.sessions_dir.parent / "x").exists())
        self.assertEqual(sorted(p.name for p in self.sessions_dir.parent.iterdir()), ["sessions"])

    def test_run_demo_turn_with_bad_id_hits_crisis_fastpath(self):
        try:
            result = webapp.run_demo_turn(None, "I want to die", [], "../x")
        except Exception as exc:  # pre-fix: raises ValueError instead of running the turn (#149)
            self.fail(f"run_demo_turn raised on a malformed session id: {exc!r}")
        self.assertIn("988", result[0])
        self._assert_new_valid_session_id(result[5])
        self._assert_nothing_written_outside_sessions_dir()

    def test_run_demo_turn_streaming_with_bad_id_hits_crisis_fastpath(self):
        try:
            outputs = list(webapp.run_demo_turn_streaming(None, "I want to die", [], "../x"))
        except Exception as exc:
            self.fail(f"run_demo_turn_streaming raised on a malformed session id: {exc!r}")
        self.assertTrue(outputs)
        final = outputs[-1]
        self.assertIn("988", final[0])
        self._assert_new_valid_session_id(final[5])
        self._assert_nothing_written_outside_sessions_dir()

    def test_format_caregiver_panel_and_mobile_alert_strip_handle_bad_id(self):
        try:
            panel = webapp._format_caregiver_panel("../x")
        except Exception as exc:
            self.fail(f"_format_caregiver_panel raised on a malformed session id: {exc!r}")
        try:
            strip = webapp._format_mobile_alert_strip("../x")
        except Exception as exc:
            self.fail(f"_format_mobile_alert_strip raised on a malformed session id: {exc!r}")
        self.assertIsInstance(panel, str)
        self.assertIsInstance(strip, str)
        self._assert_nothing_written_outside_sessions_dir()

    def test_memo_savers_handle_bad_id_without_raising(self):
        try:
            text_result = webapp.save_caregiver_text_memo("Dad has physio Tuesday.", "../x")
        except Exception as exc:
            self.fail(f"save_caregiver_text_memo raised on a malformed session id: {exc!r}")
        self.assertIsInstance(text_result[0], str)
        self.assertEqual(text_result[2], "")

        try:
            with patch.object(webapp.hear, "transcribe", return_value="Dad has physio Tuesday."):
                voice_result = webapp.save_caregiver_voice_memo(FAKE_UPLOAD, "../x")
        except Exception as exc:
            self.fail(f"save_caregiver_voice_memo raised on a malformed session id: {exc!r}")
        self.assertIsInstance(voice_result[0], str)
        self._assert_nothing_written_outside_sessions_dir()


if __name__ == "__main__":
    unittest.main()
