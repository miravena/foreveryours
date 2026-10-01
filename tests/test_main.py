"""Tests for main.py CLI demo beats and helpers."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main
from caregiver import CaregiverFlags
from memory.store import MemoryStore


class TestMain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        self.patch_data = patch.object(main, "DATA_DIR", self.data_dir)
        self.patch_audio = patch.object(main, "AUDIO_DIR", self.audio_dir)
        self.patch_data.start()
        self.patch_audio.start()

    def tearDown(self):
        self.patch_data.stop()
        self.patch_audio.stop()
        self.temp_dir.cleanup()

    def test_beat1_saves_caregiver_memo(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main.beat1_caregiver_memo()
        out = buf.getvalue()
        self.assertIn("Caregiver memo saved", out)

        store = MemoryStore(main.DEFAULT_PROFILE_ID, self.data_dir)
        items = store.all()
        self.assertGreaterEqual(len(items), 3)
        texts = [i.text for i in items]
        self.assertTrue(any("jazz" in t.lower() for t in texts))

    def test_day2_recall_check(self):
        # First write memo via beat1
        main.beat1_caregiver_memo()

        buf = io.StringIO()
        with redirect_stdout(buf):
            main.day2_recall_check()
        out = buf.getvalue()
        self.assertIn("Persistence confirmed", out)
        self.assertIn("fact(s) recalled from a prior run", out)

    def test_beat3_distress_with_no_play(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main.beat3_worrying_remark("I fell down earlier and I'm scared", play=False)
        out = buf.getvalue()
        self.assertIn("Senior said:", out)
        self.assertIn("taking this seriously", out)


if __name__ == "__main__":
    unittest.main()
