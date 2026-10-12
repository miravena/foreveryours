"""Issue #71: time-to-first-sound must never be reported for audio that never
actually played. Exercises PipelinedPlayer + play_wav end to end with
subprocess.run mocked (no real audio hardware), through only the public
surface that already exists on main -- no new symbols are imported here, so
on pre-fix code these tests FAIL (wrong value) rather than ERROR (missing
attribute)."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import speak


class TestFirstSoundHonesty(unittest.TestCase):
    def _run_player(self, run_effect):
        """Feed one chunk through a real PipelinedPlayer with subprocess.run
        behaving as `run_effect`, and return the player after close()."""
        with patch("sys.platform", "linux"), \
             patch("subprocess.run", side_effect=run_effect):
            player = speak.PipelinedPlayer(play=True)
            player.feed("hello", Path("chunk_0.wav"))
            player.close()
        return player

    def test_missing_player_stays_none(self):
        # No aplay binary at all -- subprocess.run raises FileNotFoundError,
        # exactly what Python raises when the executable doesn't exist.
        player = self._run_player(FileNotFoundError())
        self.assertIsNone(
            player.time_to_first_sound_s,
            "no audio player was available, so no sound was ever heard -- "
            "ttfs must stay None, not report a fake near-zero reading",
        )

    def test_failing_player_stays_none(self):
        # aplay exists but exits non-zero (e.g. no audio device) -- nothing
        # was actually heard either.
        player = self._run_player(
            subprocess.CalledProcessError(1, ["aplay", "chunk_0.wav"])
        )
        self.assertIsNone(
            player.time_to_first_sound_s,
            "playback failed, so no sound was ever heard -- ttfs must stay "
            "None, not report a fake near-zero reading",
        )

    def test_successful_playback_records_a_float(self):
        # aplay runs and exits 0 -- playback genuinely completed.
        player = self._run_player(lambda *a, **k: subprocess.CompletedProcess(a, 0))
        self.assertIsInstance(player.time_to_first_sound_s, float)
        self.assertGreaterEqual(player.time_to_first_sound_s, 0.0)

    def test_play_wav_return_value_matches_outcome(self):
        """play_wav itself (not just the player) must report success/failure
        via its return value, since PipelinedPlayer relies on it."""
        with patch("sys.platform", "linux"):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                self.assertFalse(speak.play_wav(Path("chunk_0.wav")))
            with patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["aplay"]),
            ):
                self.assertFalse(speak.play_wav(Path("chunk_0.wav")))
            with patch(
                "subprocess.run",
                side_effect=lambda *a, **k: subprocess.CompletedProcess(a, 0),
            ):
                self.assertTrue(speak.play_wav(Path("chunk_0.wav")))


if __name__ == "__main__":
    unittest.main()
