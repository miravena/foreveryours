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
        # Multi-sentence endurance in a single process (proving zero silence / zero deadlock)
        sentences = iter([f"Sentence number {i} is speaking clearly." for i in range(5)])
        results = list(speak.speak_sentences(sentences, self.out_dir))
        self.assertEqual(len(results), 5)
        for text, path in results:
            self.assertTrue(path.exists(), f"Path {path} must exist on disk")
            self.assertGreater(path.stat().st_size, 500, f"Path {path} must contain real audio bytes")


if __name__ == "__main__":
    unittest.main()
