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

if __name__ == "__main__":
    unittest.main()
