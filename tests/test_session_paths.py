"""Session ids are checked before they become file paths (#147)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp


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


if __name__ == "__main__":
    unittest.main()
