"""Concurrent writers on one household profile.

Two writers on the same profile (a turn's background AUDIT/extraction thread,
the next turn, a caregiver memo save) used to load their own snapshot of
`dad.json` / `dad.flags.json` and flush it whole, so the last flush silently
dropped the other's items; both flushes also shared one fixed `.tmp` name.
And a memo save did not count as an active session operation, so a session
deleted under it (tab close / sweeper) was recreated holding only the
caregiver's private memo.

Tests (a), (d), (e) and (h) fail on main before the fix; the rest pin the
shape of the fix (unique temp files, nested transactions, cleanup on a
failed replace). Standard library only; run with the repo's .venv python
(webapp imports gradio).
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import DEFAULT_PROFILE_ID, CaregiverFlags
from memory.store import MemoryStore

import webapp

MEMO = "Dr. Patel visits Tuesday."


def _files_containing(root: Path, needle: str) -> list[Path]:
    return [
        p for p in root.rglob("*")
        if p.is_file() and needle in p.read_text(errors="ignore")
    ]


class TestProfileWriteRaces(unittest.TestCase):
    def setUp(self):
        # Same isolation as tests/test_webapp.py::TestProactiveButtons.
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.d = Path(self.temp_dir.name) / "profile"
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp_dir.cleanup()

    # (a)
    def test_two_stores_do_not_lose_each_others_items(self):
        a = MemoryStore(DEFAULT_PROFILE_ID, self.d)
        b = MemoryStore(DEFAULT_PROFILE_ID, self.d)
        a.add("alpha fact", source="caregiver_memo")
        b.add("beta fact", source="caregiver_memo")
        texts = [i.text for i in MemoryStore(DEFAULT_PROFILE_ID, self.d).all()]
        self.assertIn("alpha fact", texts)
        self.assertIn("beta fact", texts)

    # (b)
    def test_two_flag_stores_do_not_lose_each_others_flags(self):
        a = CaregiverFlags(DEFAULT_PROFILE_ID, self.d)
        b = CaregiverFlags(DEFAULT_PROFILE_ID, self.d)
        a.add("Dad sounded frightened.", severity="distress", disclosed_to_senior=False)
        b.add("Dad mentioned chest pain.", severity="distress", disclosed_to_senior=False)
        texts = [f.text for f in CaregiverFlags(DEFAULT_PROFILE_ID, self.d).all()]
        self.assertIn("Dad sounded frightened.", texts)
        self.assertIn("Dad mentioned chest pain.", texts)

    # (c)
    def test_concurrent_adds_from_threads_keep_every_item(self):
        for run in range(3):
            d = self.d / f"run{run}"
            n_threads, n_adds = 8, 5
            barrier = threading.Barrier(n_threads)
            errors: list[BaseException] = []

            def worker(t: int) -> None:
                try:
                    barrier.wait(timeout=10)
                    for i in range(n_adds):
                        MemoryStore(DEFAULT_PROFILE_ID, d).add(
                            f"fact {t}-{i}", source="caregiver_memo"
                        )
                except BaseException as exc:  # collected, asserted below
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
            for th in threads:
                th.start()
            for th in threads:
                th.join(timeout=30)
            self.assertFalse(any(th.is_alive() for th in threads), f"run {run}: thread hung")
            self.assertEqual(errors, [], f"run {run}")
            texts = {i.text for i in MemoryStore(DEFAULT_PROFILE_ID, d).all()}
            expected = {f"fact {t}-{i}" for t in range(n_threads) for i in range(n_adds)}
            self.assertEqual(len(expected), 40)
            self.assertEqual(expected - texts, set(), f"run {run}: lost items")
            self.assertEqual(list(d.glob("*.tmp")), [], f"run {run}: temp leftovers")

    # (d)
    def test_memo_save_after_end_session_is_refused(self):
        sid = webapp._new_session()
        webapp._end_session(sid)
        self.assertFalse((self.sessions_dir / sid).exists())
        panel, new_sid, box = webapp.save_caregiver_text_memo(MEMO, sid)
        self.assertFalse((self.sessions_dir / sid).exists(), "deleted household was recreated")
        self.assertNotEqual(new_sid, sid)
        self.assertTrue((self.sessions_dir / new_sid).is_dir())
        self.assertEqual(box, MEMO, "the typed memo must be handed back, not dropped")
        self.assertTrue(
            panel.startswith("_Your demo household was reset after a period of inactivity._"),
            panel[:120],
        )
        self.assertEqual(_files_containing(self.sessions_dir, "Dr. Patel"), [])

    # (e)
    def test_memo_save_counts_as_active(self):
        sid = webapp._new_session()
        entered = threading.Event()
        release = threading.Event()
        real_add = MemoryStore.add

        def blocking_add(store, *args, **kwargs):
            entered.set()
            release.wait(10)
            return real_add(store, *args, **kwargs)

        errors: list[BaseException] = []

        def save() -> None:
            try:
                webapp.save_caregiver_text_memo("Blocked memo fact.", sid)
            except BaseException as exc:
                errors.append(exc)

        with patch.object(webapp.MemoryStore, "add", blocking_add):
            worker = threading.Thread(target=save)
            worker.start()
            try:
                self.assertTrue(entered.wait(5), "memo save never reached store.add")
                self.assertTrue(webapp._is_session_busy(sid), "memo save is not an active operation")
                webapp._end_session(sid)
                self.assertTrue((self.sessions_dir / sid).is_dir(), "_end_session deleted a household mid-save")
            finally:
                # Always unblock and join, so a failing assertion above still
                # terminates instead of hanging on the blocked worker.
                release.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertFalse(webapp._is_session_busy(sid))
        webapp._end_session(sid)
        self.assertFalse((self.sessions_dir / sid).exists())

    # (f)
    def test_flush_uses_unique_temp_file_per_write(self):
        import memory.profile_io as profile_io

        real_replace = os.replace
        for cls, name, add in (
            (MemoryStore, "dad.json", lambda s, n: s.add(f"fact {n}", source="caregiver_memo")),
            (CaregiverFlags, "dad.flags.json",
             lambda s, n: s.add(f"flag {n}", severity="info", disclosed_to_senior=False)),
        ):
            with self.subTest(cls=cls.__name__):
                d = self.d / cls.__name__
                sources: list[str] = []

                def recorder(src, dst, *a, **kw):
                    sources.append(str(src))
                    return real_replace(src, dst, *a, **kw)

                with patch.object(profile_io.os, "replace", recorder):
                    add(cls(DEFAULT_PROFILE_ID, d), 1)
                    add(cls(DEFAULT_PROFILE_ID, d), 2)
                self.assertEqual(len(sources), 2, sources)
                self.assertNotEqual(sources[0], sources[1])
                pattern = re.compile(re.escape(name) + r"\..+\.tmp$")
                for src in sources:
                    self.assertEqual(Path(src).parent, d)
                    self.assertRegex(Path(src).name, pattern)
                self.assertEqual(list(d.glob("*.tmp")), [])

    # (g)
    def test_quiet_mode_renews_under_transaction(self):
        store = MemoryStore(DEFAULT_PROFILE_ID, self.d)
        store.set_quiet_mode(hours=1)
        store.set_quiet_mode(hours=2)
        fresh = MemoryStore(DEFAULT_PROFILE_ID, self.d)
        quiet = [i for i in fresh.all() if i.text == "[QUIET_MODE]" and i.status == "active"]
        self.assertEqual(len(quiet), 1, quiet)
        self.assertAlmostEqual(quiet[0].expires_at, time.time() + 7200, delta=5)

    # (h)
    def test_voice_memo_save_after_end_session_is_refused(self):
        sid = webapp._new_session()
        webapp._end_session(sid)
        audio = Path(self.temp_dir.name) / "memo.wav"  # never created: probes are skipped
        with patch.object(webapp.hear, "transcribe", return_value=MEMO):
            panel, new_sid = webapp.save_caregiver_voice_memo(str(audio), sid)
        self.assertFalse((self.sessions_dir / sid).exists(), "deleted household was recreated")
        self.assertNotEqual(new_sid, sid)
        self.assertTrue(
            panel.startswith("_Your demo household was reset after a period of inactivity._"),
            panel[:120],
        )
        self.assertEqual(_files_containing(self.sessions_dir, "Dr. Patel"), [])

    # (i)
    def test_failed_replace_cleans_temp_and_propagates(self):
        import memory.profile_io as profile_io

        MemoryStore(DEFAULT_PROFILE_ID, self.d).add("existing fact", source="caregiver_memo")
        path = self.d / "dad.json"
        before = path.read_bytes()
        with patch.object(profile_io.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError) as ctx:
                MemoryStore(DEFAULT_PROFILE_ID, self.d).add("x", source="caregiver_memo")
        self.assertIn("disk full", str(ctx.exception))
        self.assertEqual(list(self.d.glob("*.tmp")), [])
        self.assertEqual(path.read_bytes(), before)

        # The profile lock was released: a later writer (from another thread,
        # so a leaked RLock owned by this one would block it) still succeeds.
        done = threading.Event()

        def later() -> None:
            MemoryStore(DEFAULT_PROFILE_ID, self.d).add("x", source="caregiver_memo")
            done.set()

        th = threading.Thread(target=later)
        th.start()
        th.join(10)
        self.assertTrue(done.is_set(), "profile lock was not released after the failed replace")
        texts = [i.text for i in MemoryStore(DEFAULT_PROFILE_ID, self.d).all()]
        self.assertIn("x", texts)
        self.assertIn("existing fact", texts)


if __name__ == "__main__":
    unittest.main()
