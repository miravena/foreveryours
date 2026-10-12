"""Session ids are checked before they become file paths (#147)."""
import os
import tempfile
import threading
import time
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


if __name__ == "__main__":
    unittest.main()
