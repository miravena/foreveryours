"""The TTS_TIMEOUT_S bound holds even when the pyttsx3 engine
lock is busy.

The pyttsx3 last-resort tier shares one cached engine across turns, guarded by
``pipeline.speak._pyttsx3_lock``. Waiting for that lock is part of the
synthesis budget: a turn that cannot get the engine within TTS_TIMEOUT_S gets
``subprocess.TimeoutExpired``, so a fast-path emergency still saves its
caregiver flag within the bound instead of queueing behind a hung engine.

Every call under test runs in a helper thread with a hard join cap, so a
regression fails the test instead of hanging the suite.
"""
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline import speak
from pipeline.orchestrator import run_turn
from safety import fastpath

FALL_PHRASE = "I fell down earlier and I'm scared"
TIMEOUT = 0.05   # TTS_TIMEOUT_S under test
SLACK = 0.25     # thread start + scheduling; far below a second bound
HARD_CAP = 3.0   # a call still running after this is treated as hung


def _call_capped(fn):
    """Run fn() in a daemon thread; return (outcome, elapsed_s).

    outcome is ("value", v), ("error", exc) or ("hung", None)."""
    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - reported to the test
            box["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    start = time.monotonic()
    worker.start()
    worker.join(HARD_CAP)
    elapsed = time.monotonic() - start
    if worker.is_alive():
        return ("hung", None), elapsed
    if "error" in box:
        return ("error", box["error"]), elapsed
    return ("value", box.get("value")), elapsed


class _Pyttsx3TierCase(unittest.TestCase):
    """Only the pyttsx3 tier is available: no Piper, no espeak, not Windows."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        for target, value in (
            ("pipeline.speak.TTS_TIMEOUT_S", TIMEOUT),
            ("sys.platform", "linux"),
            ("pipeline.speak._get_piper_cli", MagicMock(return_value=None)),
            ("pipeline.speak._get_espeak_cli", MagicMock(return_value=None)),
        ):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def _hold_engine_lock(self):
        """Simulate another turn that owns the shared engine."""
        self.assertTrue(speak._pyttsx3_lock.acquire(timeout=1.0), "lock already stuck")
        self.addCleanup(speak._pyttsx3_lock.release)

    def _assert_bounded_timeout(self, outcome, elapsed):
        kind, value = outcome
        self.assertNotEqual(kind, "hung", "pyttsx3 tier waited on the engine lock without a bound")
        self.assertEqual(kind, "error", f"expected TimeoutExpired, got {outcome!r}")
        self.assertIsInstance(value, subprocess.TimeoutExpired)
        self.assertLess(elapsed, TIMEOUT + SLACK, f"took {elapsed:.3f}s against a {TIMEOUT}s bound")


class Pyttsx3LockWaitIsBoundedTests(_Pyttsx3TierCase):
    def test_busy_engine_lock_times_out_within_tts_timeout(self):
        engine = MagicMock()
        self._hold_engine_lock()
        out = Path(self.temp_dir.name) / "reply.wav"
        outcome, elapsed = _call_capped(lambda: speak._synthesize_file("Hello.", out, engine))
        self._assert_bounded_timeout(outcome, elapsed)
        engine.runAndWait.assert_not_called()

    def test_hung_engine_is_not_reentered_and_next_caller_is_bounded(self):
        release = threading.Event()
        self.addCleanup(release.set)
        engine = MagicMock()
        engine.runAndWait.side_effect = lambda: release.wait()
        out = Path(self.temp_dir.name) / "reply.wav"

        first, first_elapsed = _call_capped(lambda: speak._synthesize_file("One.", out, engine))
        self._assert_bounded_timeout(first, first_elapsed)
        second, second_elapsed = _call_capped(lambda: speak._synthesize_file("Two.", out, engine))
        self._assert_bounded_timeout(second, second_elapsed)
        self.assertEqual(engine.runAndWait.call_count, 1, "abandoned engine was called again")


class FastPathFlagUnderEngineContentionTests(_Pyttsx3TierCase):
    def setUp(self):
        super().setUp()
        data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        data_dir.mkdir()
        self.audio_dir.mkdir()
        self.store = MemoryStore("test_dad", data_dir)
        self.flags = CaregiverFlags("test_dad", data_dir)
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("NEBIUS_API_KEY", None)  # THINK fails fast, offline
        engine_patch = patch("pipeline.speak._get_tts_engine", return_value=MagicMock())
        engine_patch.start()
        self.addCleanup(engine_patch.stop)

    def test_flag_saved_undisclosed_within_bound_while_engine_is_busy(self):
        fast = fastpath.check(FALL_PHRASE)
        self.assertTrue(fast.triggered)
        self._hold_engine_lock()

        outcome, elapsed = _call_capped(lambda: run_turn(
            transcript=FALL_PHRASE,
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        ))
        kind, result = outcome
        self.assertNotEqual(kind, "hung", "run_turn queued behind a busy TTS engine")
        self.assertEqual(kind, "value", f"run_turn raised {result!r}")
        # One tier is tried (pyttsx3), so one bound applies; THINK fails fast offline.
        self.assertLess(elapsed, TIMEOUT + SLACK, f"turn took {elapsed:.3f}s against a {TIMEOUT}s bound")
        items = self.flags.all()
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].disclosed_to_senior)
        self.assertIn(fast.immediate_reply, result.reply_text)
        self.assertEqual(result.audio_paths, [])


if __name__ == "__main__":
    unittest.main()
