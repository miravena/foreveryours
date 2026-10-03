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

    def test_caregiver_panel_renders_phase3_memory_badges(self):
        from memory.store import MemoryScope, MemoryStore, PrivacyLevel
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        now = time.time()
        # 1. Temporary item with future expiration
        store.add(
            "Sarah dropping groceries at 4 PM",
            source="caregiver_memo",
            scope=MemoryScope.TEMPORARY.value,
            expires_at=now + 7200,
        )
        # 2. Private caregiver-only item
        store.add(
            "Planning surprise 80th birthday party",
            source="caregiver_note",
            privacy=PrivacyLevel.CAREGIVER_ONLY.value,
        )
        # 3. Superseded item
        store.supersede("Dad loves jazz", "Senior no longer listens to jazz; prefers classical")

        panel = webapp._format_caregiver_panel(session_id)
        self.assertIn("🟢 **[Permanent]**", panel)
        self.assertIn("🕒 **[Temporary — expires in", panel)
        self.assertIn("🔒 **[Caregiver Only — Hidden from Dad]**", panel)
        self.assertIn("🔄 _[Superseded]_", panel)

    def test_senior_text_input_turn_without_mic(self):
        """Dual-input mode: Senior types text directly without recording audio."""
        session_id, _ = webapp.init_session()
        # run_demo_turn(audio_in=None, text_in="I fell down earlier and I'm scared", history=[], session_id=session_id)
        out = webapp.run_demo_turn(
            audio_in=None,
            text_in_or_history="I fell down earlier and I'm scared",
            history_or_session=[],
            session_id=session_id,
        )
        transcript_and_reply, reply_audio, new_history, panel, sess, cleared_text = out
        self.assertIn("Dad said:** \"I fell down earlier and I'm scared\"", transcript_and_reply)
        self.assertIn("Companion replied:", transcript_and_reply)
        self.assertIn("Honest Safety Disclosure", transcript_and_reply)
        self.assertIsNotNone(reply_audio)
        self.assertEqual(cleared_text, "")
        # Check that high priority alert banner appears in the caregiver panel
        self.assertIn("🚨 **HIGH PRIORITY SAFETY ALERT DISPATCHED**", panel)
        self.assertIn("Disclosed to Senior in conversation", panel)

    def test_caregiver_text_memo_saves_and_updates_panel(self):
        """Caregiver text memo adds context and updates live panel badges."""
        session_id, _ = webapp.init_session()
        memo = "Dad loves chicken soup. Doctor appointment tomorrow at 2 PM."
        panel, sess, cleared = webapp.save_caregiver_text_memo(memo, session_id)
        self.assertEqual(sess, session_id)
        self.assertEqual(cleared, "")
        self.assertIn("Dad loves chicken soup", panel)
        self.assertIn("Doctor appointment tomorrow at 2 PM", panel)
        self.assertIn("🟢 **[Permanent]**", panel)

    def test_high_priority_alert_banner_renders_on_distress(self):
        """High priority alert banner renders at the top of the caregiver panel on fall events."""
        session_id, _ = webapp.init_session()
        self._turn("I fell down earlier and I'm scared", session_id)
        panel = webapp._format_caregiver_panel(session_id)
        self.assertTrue(panel.startswith("> 🚨 **HIGH PRIORITY SAFETY ALERT DISPATCHED**"))
        self.assertIn("Severity:** `DISTRESS`", panel)
        self.assertIn("Disclosure:** ✅ **Disclosed to Senior in conversation**", panel)


if __name__ == "__main__":
    unittest.main()

    def test_dual_input_prioritizes_text(self):
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value="Audio transcript"):
            # When both text and audio are provided, text_in takes precedence
            transcript_out, audio_out, history_state, panel, out_sess_id, out_text_in = webapp.run_demo_turn(
                audio_in="fake.wav",
                text_in_or_history="Text transcript",
                history_or_session=[],
                session_id=session_id
            )
            self.assertIn("Text transcript", transcript_out)
            self.assertNotIn("Audio transcript", transcript_out)
