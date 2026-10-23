"""Tests for SPEAK sentence-by-sentence synthesis and audio file generation."""
import tempfile
import unittest
from pathlib import Path

from pipeline import speak


class TestSpeak(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_speak_sentences_generates_unique_paths(self):
        sentences = iter(["Hello there.", "How are you?"])
        results = list(speak.speak_sentences(sentences, self.out_dir))
        self.assertEqual(len(results), 2)
        sent1, path1 = results[0]
        sent2, path2 = results[1]
        self.assertEqual(sent1, "Hello there.")
        self.assertEqual(sent2, "How are you?")
        self.assertNotEqual(path1, path2)
        self.assertTrue(path1.exists(), f"Expected {path1} to exist")
        self.assertTrue(path2.exists(), f"Expected {path2} to exist")
        self.assertTrue(path1.name.endswith(".wav"))
        self.assertTrue(path2.name.endswith(".wav"))

    def test_espeak_cli_branch_on_linux(self):
        from unittest.mock import MagicMock, patch

        mock_subproc = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("subprocess.run", mock_subproc):
            sentences = iter(["Good morning.", "Here is your update."])
            results = list(speak.speak_sentences(sentences, self.out_dir))
            self.assertEqual(len(results), 2)
            self.assertEqual(mock_subproc.call_count, 2)
            # Verify espeak-ng was invoked with proper parameters (-s 150, -p 45, -w <out_path>, <text>)
            call1_args = mock_subproc.call_args_list[0][0][0]
            self.assertEqual(call1_args[0], "/usr/bin/espeak-ng")
            self.assertEqual(call1_args[1], "-s")
            self.assertEqual(call1_args[2], "150")
            self.assertEqual(call1_args[3], "-p")
            self.assertEqual(call1_args[4], "45")
            self.assertEqual(call1_args[5], "-w")
            self.assertEqual(call1_args[7], "Good morning.")

    def test_multi_sentence_endurance_no_silence(self):
        # Regression test for #28: on Linux, one long-lived in-process engine
        # started returning empty WAVs (44-byte header, no audio) after ~19
        # sentences, which would have gone silent mid-demo on a hosted server.
        # The fix is one clean espeak-ng subprocess per sentence (ADR-001), so
        # this runs a full 3x past the old failure point in a single process.
        # Keep the count well above 19 -- lowering it re-opens the bug.
        n_sentences = 60
        sentences = iter(
            [f"Sentence number {i} is speaking clearly." for i in range(n_sentences)]
        )
        results = list(speak.speak_sentences(sentences, self.out_dir))
        self.assertEqual(len(results), n_sentences)

        empty = []
        for i, (text, path) in enumerate(results):
            self.assertTrue(path.exists(), f"sentence {i}: path must exist on disk")
            size = path.stat().st_size
            if size <= 500:
                empty.append((i, size))
        self.assertEqual(
            empty, [],
            f"empty/near-empty WAVs at sentences {empty} -- #28-style silence regression",
        )


class TestPipelinedPlayer(unittest.TestCase):
    """Issue #17: playback overlaps synthesis, in order, and reports
    time-to-first-SOUND. Playback is always mocked -- no audio hardware."""

    def test_plays_all_chunks_in_order(self):
        from unittest.mock import patch

        played = []
        with patch("pipeline.speak.play_wav", side_effect=lambda p: played.append(p)):
            player = speak.PipelinedPlayer(play=True)
            for i in range(4):
                player.feed(f"s{i}", Path(f"chunk_{i}.wav"))
            player.close()
        self.assertEqual(played, [Path(f"chunk_{i}.wav") for i in range(4)])

    def test_play_false_is_inert(self):
        from unittest.mock import patch

        with patch("pipeline.speak.play_wav") as mock_play:
            player = speak.PipelinedPlayer(play=False)
            player.feed("s0", Path("chunk_0.wav"))
            player.close()
        mock_play.assert_not_called()
        self.assertIsNone(player.time_to_first_sound_s)

    def test_first_sound_time_is_recorded(self):
        from unittest.mock import patch

        with patch("pipeline.speak.play_wav"):
            player = speak.PipelinedPlayer(play=True)
            player.feed("s0", Path("chunk_0.wav"))
            player.close()
        self.assertIsNotNone(player.time_to_first_sound_s)
        self.assertGreaterEqual(player.time_to_first_sound_s, 0.0)

    def test_playback_overlaps_synthesis(self):
        """The first chunk must START playing before the LAST chunk is fed
        (i.e. while 'synthesis' of later chunks is still happening)."""
        import threading
        import time as _time
        from unittest.mock import patch

        play_started = threading.Event()

        def slow_play(_path):
            play_started.set()
            _time.sleep(0.05)

        with patch("pipeline.speak.play_wav", side_effect=slow_play):
            player = speak.PipelinedPlayer(play=True)
            player.feed("s0", Path("chunk_0.wav"))
            # Playback of chunk 0 should begin on the background thread without
            # waiting for us to feed chunk 1 -- prove it started before we feed more.
            self.assertTrue(play_started.wait(timeout=2.0), "playback did not start concurrently")
            player.feed("s1", Path("chunk_1.wav"))
            player.close()

class TestPiperTier(unittest.TestCase):
    """Issue #52: Piper offline neural voice is the PREFERRED tier when its CLI
    and voice model are both present, and the code falls through to the exact
    prior behavior when it is not (so `main` stays demo-able with no install)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)
        # A fake voice model: <name>.onnx with a sibling <name>.onnx.json.
        self.model = self.out_dir / "voice.onnx"
        self.model.write_bytes(b"fake-onnx")
        self.model.with_suffix(".onnx.json").write_text("{}")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_piper_branch_used_when_available(self):
        from unittest.mock import MagicMock, patch

        mock_subproc = MagicMock()
        with patch.dict("os.environ", {"TTS_PIPER_MODEL": str(self.model)}, clear=False), \
             patch("pipeline.speak._get_piper_cli", return_value="/usr/bin/piper"), \
             patch("subprocess.run", mock_subproc):
            results = list(speak.speak_sentences(iter(["Hello there."]), self.out_dir))
        self.assertEqual(len(results), 1)
        self.assertEqual(mock_subproc.call_count, 1)
        call = mock_subproc.call_args_list[0]
        argv = call[0][0]
        self.assertEqual(argv[0], "/usr/bin/piper")
        self.assertIn("-m", argv)
        self.assertIn("-f", argv)
        self.assertEqual(call.kwargs.get("input"), "Hello there.")

    def test_falls_back_when_piper_missing(self):
        from unittest.mock import MagicMock, patch

        mock_subproc = MagicMock()
        with patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value=None), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("subprocess.run", mock_subproc):
            results = list(speak.speak_sentences(iter(["Good morning."]), self.out_dir))
        self.assertEqual(len(results), 1)
        # Exactly the existing espeak-CLI invocation, unchanged.
        argv = mock_subproc.call_args_list[0][0][0]
        self.assertEqual(argv[0], "/usr/bin/espeak-ng")
        self.assertEqual(argv[1], "-s")
        self.assertEqual(argv[-1], "Good morning.")

    def test_tts_backend_espeak_forces_fallback(self):
        from unittest.mock import MagicMock, patch

        mock_subproc = MagicMock()
        with patch.dict("os.environ",
                        {"TTS_BACKEND": "espeak", "TTS_PIPER_MODEL": str(self.model)},
                        clear=False), \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value="/usr/bin/piper"), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("subprocess.run", mock_subproc):
            list(speak.speak_sentences(iter(["Forced fallback."]), self.out_dir))
        # Piper must be skipped; espeak must run.
        argv = mock_subproc.call_args_list[0][0][0]
        self.assertEqual(argv[0], "/usr/bin/espeak-ng")

    def test_piper_failure_falls_through(self):
        import subprocess as _sp
        from unittest.mock import patch

        def fake_run(argv, *args, **kwargs):
            if argv and argv[0] == "/usr/bin/piper":
                raise _sp.CalledProcessError(1, argv)
            return None  # espeak branch "succeeds"

        with patch.dict("os.environ", {"TTS_PIPER_MODEL": str(self.model)}, clear=False), \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value="/usr/bin/piper"), \
             patch("pipeline.speak._get_espeak_cli", return_value="/usr/bin/espeak-ng"), \
             patch("subprocess.run", side_effect=fake_run):
            # No exception should escape: it falls through to espeak.
            results = list(speak.speak_sentences(iter(["Recover please."]), self.out_dir))
        self.assertEqual(len(results), 1)


class TestTtsTimeoutBound(unittest.TestCase):
    """Every synthesis tier is bounded by TTS_TIMEOUT_S."""

    def test_timeout_env_parsing_rejects_non_finite_and_non_positive(self):
        for raw in (None, "", "abc", "0", "-3", "inf", "-inf", "nan"):
            self.assertEqual(speak._parse_tts_timeout(raw), 10.0, raw)
        self.assertEqual(speak._parse_tts_timeout("2.5"), 2.5)

    def test_reload_picks_up_env_loaded_after_import(self):
        from unittest.mock import patch

        with patch("pipeline.speak.TTS_TIMEOUT_S", speak.TTS_TIMEOUT_S), \
             patch.dict("os.environ", {"TTS_TIMEOUT_S": "3"}, clear=False):
            self.assertEqual(speak.reload_tts_timeout(), 3.0)
            self.assertEqual(speak.TTS_TIMEOUT_S, 3.0)

    def test_run_bounded_abandons_a_hung_call(self):
        import subprocess as _sp
        import threading
        from unittest.mock import patch

        release = threading.Event()
        self.addCleanup(release.set)
        with patch("pipeline.speak.TTS_TIMEOUT_S", 0.05):
            with self.assertRaises(_sp.TimeoutExpired):
                speak._run_bounded(release.wait, "fake")

    def test_run_bounded_reraises_worker_exception(self):
        def boom():
            raise OSError("driver missing")

        with self.assertRaises(OSError):
            speak._run_bounded(boom, "fake")
        self.assertEqual(speak._run_bounded(lambda: 7, "fake"), 7)

    def test_pyttsx3_tier_failure_yields_no_path(self):
        import sys as _sys
        from unittest.mock import MagicMock, patch

        engine = MagicMock()
        engine.runAndWait.side_effect = RuntimeError("engine died")
        with tempfile.TemporaryDirectory() as tmp, \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value=None), \
             patch("pipeline.speak._get_espeak_cli", return_value=None), \
             patch("pipeline.speak._get_tts_engine", return_value=engine):
            stdout_before = _sys.stdout
            with self.assertRaises(RuntimeError):
                list(speak.speak_sentences(iter(["Hello."]), Path(tmp)))
            self.assertIs(_sys.stdout, stdout_before)


class TestPyttsx3LockAfterTimeout(unittest.TestCase):
    """A pyttsx3 call abandoned at TTS_TIMEOUT_S
    must keep the engine lock until the engine really returns, so a later
    turn times out instead of entering the shared engine concurrently."""

    def _fake_engine(self, block: "threading.Event | None"):
        import threading
        from unittest.mock import MagicMock

        stats = {"calls": 0, "active": 0, "max_active": 0}
        guard = threading.Lock()

        def run_and_wait():
            with guard:
                stats["calls"] += 1
                stats["active"] += 1
                stats["max_active"] = max(stats["max_active"], stats["active"])
            try:
                if block is not None:
                    block.wait(5)
                else:
                    import time as _t
                    _t.sleep(0.02)
            finally:
                with guard:
                    stats["active"] -= 1

        engine = MagicMock()
        engine.runAndWait.side_effect = run_and_wait
        return engine, stats

    def _patches(self, timeout_s: float):
        from contextlib import ExitStack
        from unittest.mock import patch

        stack = ExitStack()
        stack.enter_context(patch("sys.platform", "linux"))
        stack.enter_context(patch("pipeline.speak._get_piper_cli", return_value=None))
        stack.enter_context(patch("pipeline.speak._get_espeak_cli", return_value=None))
        stack.enter_context(patch("pipeline.speak.TTS_TIMEOUT_S", timeout_s))
        return stack

    def _wait_unlocked(self, seconds: float = 3.0) -> bool:
        import time as _t

        end = _t.monotonic() + seconds
        while _t.monotonic() < end:
            if not speak._pyttsx3_lock.locked():
                return True
            _t.sleep(0.01)
        return False

    def test_abandoned_call_keeps_lock_and_next_call_never_enters_engine(self):
        import subprocess as _sp
        import threading

        release = threading.Event()
        self.addCleanup(lambda: (release.set(), self._wait_unlocked()))
        engine, stats = self._fake_engine(release)
        with tempfile.TemporaryDirectory() as tmp, self._patches(0.1):
            out = Path(tmp) / "a.wav"
            with self.assertRaises(_sp.TimeoutExpired):
                speak._synthesize_file("First.", out, engine)
            # The engine is still inside runAndWait, so the lock stays held.
            self.assertTrue(speak._pyttsx3_lock.locked())
            with self.assertRaises(_sp.TimeoutExpired):
                speak._synthesize_file("Second.", out, engine)
            self.assertEqual(stats["calls"], 1, "second call entered the hung engine")
            self.assertEqual(stats["max_active"], 1)

            # Once the hung engine returns, its thread frees the lock and the
            # tier works again.
            release.set()
            self.assertTrue(self._wait_unlocked(), "lock not released after engine returned")
            speak._synthesize_file("Third.", out, engine)
            self.assertEqual(stats["calls"], 2)
            self.assertEqual(stats["max_active"], 1)
            self.assertFalse(speak._pyttsx3_lock.locked())

    def test_concurrent_turns_take_turns_in_the_engine(self):
        import threading

        engine, stats = self._fake_engine(None)
        errors: list = []
        with tempfile.TemporaryDirectory() as tmp, self._patches(5.0):
            def turn(i):
                try:
                    speak._synthesize_file(f"Hi {i}.", Path(tmp) / f"{i}.wav", engine)
                except BaseException as exc:  # noqa: BLE001 - surfaced below
                    errors.append(exc)

            threads = [threading.Thread(target=turn, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
            self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(errors, [])
        self.assertEqual(stats["calls"], 4)
        self.assertEqual(stats["max_active"], 1)
        self.assertTrue(self._wait_unlocked())

    def test_stdout_restored_after_racing_turns(self):
        """Codex finding: the engine thread frees the engine lock before its
        caller restores stdout; a second turn in that gap must not capture the
        first turn's buffer as the stdout it later restores."""
        import sys as _sys
        import threading
        import time as _t
        from unittest.mock import MagicMock

        engine = MagicMock()
        # The engine returns at once; the caller is then slowed down between the
        # engine thread's lock release and its own redirect exit.
        engine.runAndWait.side_effect = lambda: None
        real_run_bounded = speak._run_bounded

        def slow_after_return(*args, **kwargs):
            result = real_run_bounded(*args, **kwargs)
            _t.sleep(0.05)
            return result

        stdout_before = _sys.stdout
        errors: list = []
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp, self._patches(5.0), \
             patch("pipeline.speak._run_bounded", side_effect=slow_after_return):
            def turn(i):
                try:
                    for j in range(3):
                        speak._synthesize_file(f"Hi {i}.", Path(tmp) / f"{i}-{j}.wav", engine)
                except BaseException as exc:  # noqa: BLE001 - surfaced below
                    errors.append(exc)

            threads = [threading.Thread(target=turn, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(20)
        self.assertEqual(errors, [])
        self.assertIs(_sys.stdout, stdout_before, "stdout left redirected after racing turns")

    def test_engine_error_still_releases_lock(self):
        from unittest.mock import MagicMock

        engine = MagicMock()
        engine.runAndWait.side_effect = RuntimeError("engine died")
        with tempfile.TemporaryDirectory() as tmp, self._patches(2.0):
            with self.assertRaises(RuntimeError):
                speak._synthesize_file("Hi.", Path(tmp) / "x.wav", engine)
        self.assertTrue(self._wait_unlocked())

    def test_on_done_runs_once_when_thread_cannot_start(self):
        from unittest.mock import patch

        calls = []
        with patch("threading.Thread.start", side_effect=RuntimeError("can't start new thread")):
            with self.assertRaises(RuntimeError):
                speak._run_bounded(lambda: 1, "fake", on_done=lambda: calls.append(1))
        self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()
