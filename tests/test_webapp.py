"""Tests for webapp.py's per-session isolation (issues #11, #18).

A public demo link is shared by every judge at once, so one judge's flags,
memories and audio must never show up in another judge's tab, and must be
deleted when the session ends. Runs with no NEBIUS_API_KEY: the distress
phrase goes through the offline fast-path.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp


class TestWebappSessions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _turn(self, said: str, session_id: str):
        with patch.object(webapp.hear, "transcribe", return_value=said):
            return webapp.run_demo_turn("fake.wav", [], session_id)

    def test_new_session_is_prebriefed(self):
        session_id, panel = webapp.init_session()
        self.assertIn("Leo", panel)
        self.assertIn("jazz", panel)
        self.assertTrue((self.sessions_dir / session_id).is_dir())

    def test_flags_do_not_leak_between_sessions(self):
        judge_a, _ = webapp.init_session()
        judge_b, _ = webapp.init_session()
        self.assertNotEqual(judge_a, judge_b)

        self._turn("I fell down earlier and I'm scared", judge_a)

        self.assertIn("Dad was told", webapp._format_caregiver_panel(judge_a))
        self.assertIn("No flags yet", webapp._format_caregiver_panel(judge_b))

    def test_end_session_deletes_everything(self):
        session_id, _ = webapp.init_session()
        self._turn("I fell down earlier and I'm scared", session_id)
        webapp._end_session(session_id)
        self.assertFalse((self.sessions_dir / session_id).exists())

    def test_audio_from_previous_turn_is_removed(self):
        session_id, _ = webapp.init_session()
        _, audio_dir = webapp._session_dirs(session_id)
        audio_dir.mkdir(parents=True, exist_ok=True)
        old = audio_dir / "combined_old.wav"
        old.write_bytes(b"")
        self._turn("I fell down earlier and I'm scared", session_id)
        self.assertFalse(old.exists())

    def test_stale_sessions_are_swept(self):
        stale, _ = webapp.init_session()
        old = time.time() - webapp.SESSION_TTL_S - 60
        os.utime(self.sessions_dir / stale, (old, old))
        fresh, _ = webapp.init_session()
        self.assertFalse((self.sessions_dir / stale).exists())
        self.assertTrue((self.sessions_dir / fresh).exists())


if __name__ == "__main__":
    unittest.main()
