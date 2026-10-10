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

        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

        self.sessions_dir = Path(self.temp_dir.name) / "sessions"

        self.patches = [

            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),

            patch.object(webapp, "SHARED_PROFILE", False),

            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),

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

        with patch.object(webapp.hear, "transcribe", return_value=(said, {"wpm": 0.0, "avg_pause_s": 0.0})):

            return webapp.run_demo_turn("fake.wav", [], session_id)



    def test_ai_reminder_fires_on_turn_count_not_truncated_history(self):
        """#83 PR #85 Codex review: history is truncated to MAX_HISTORY_TURNS,
        so the periodic AI/recording reminder must count real turns from a
        persistent per-session counter, not len(history)."""
        from types import SimpleNamespace
        session_id, _ = webapp.init_session()
        fake_result = SimpleNamespace(
            reply_text="Good to hear from you.",
            audio_paths=[],
            caregiver_flag=False,
            is_fallback=False,
            background_thread=None,
        )
        with patch.object(webapp, "run_turn", return_value=fake_result):
            results = [self._turn(f"turn {i}", session_id) for i in range(webapp.REMINDER_EVERY_N_TURNS)]
        reminders = ["Reminder" in r[0] for r in results]
        self.assertEqual(reminders, [False] * (webapp.REMINDER_EVERY_N_TURNS - 1) + [True])

    def test_expired_session_shows_reset_notice(self):
        """#83, #80 3.C7: a turn with no session_id (State expired mid-demo)
        gets a fresh household and says so, instead of silently looking like
        a reset conversation."""
        with patch.object(webapp.hear, "transcribe", return_value=("Hello", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp.run_demo_turn("fake.wav", [], None)
        self.assertIn("reset after a period of inactivity", result[0])
        self.assertIsNotNone(result[5])  # a new session_id was minted

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

    def test_crisis_flag_renders_in_alerts(self):
        session_id, _ = webapp.init_session()
        self._turn("I want to die", session_id)
        
        panel = webapp._format_caregiver_panel(session_id)
        strip = webapp._format_mobile_alert_strip(session_id)
        
        self.assertIn("HIGH PRIORITY SAFETY ALERT DISPATCHED", panel)
        self.assertIn("CRISIS", panel)
        
        self.assertIn("Caregiver alert:", strip)
        self.assertNotIn("No flags yet", panel)
        self.assertNotEqual(strip, "")

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

        transcript_and_reply, reply_audio, new_history, panel, biomarkers, sess, cleared_text, cleared_audio = out

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

        self.assertIn("> 🚨 **HIGH PRIORITY SAFETY ALERT DISPATCHED**", panel)

        self.assertIn("Severity:** `DISTRESS`", panel)

        self.assertIn("Disclosure:** ✅ **Disclosed to Senior in conversation**", panel)



    def test_dual_input_prioritizes_text(self):

        session_id, _ = webapp.init_session()

        with patch.object(webapp.hear, "transcribe", return_value=("Audio transcript", {"wpm": 0.0, "avg_pause_s": 0.0})):

            # When both text and audio are provided, text_in takes precedence

            transcript_out, audio_out, history_state, panel, biomarkers, out_sess_id, out_text_in, out_audio_in = webapp.run_demo_turn(

                audio_in="fake.wav",

                text_in_or_history="Text transcript",

                history_or_session=[],

                session_id=session_id

            )

            self.assertIn("Text transcript", transcript_out)

            self.assertNotIn("Audio transcript", transcript_out)



    def test_quiet_mode_breakthrough_offline(self):
        """Issue #102: Offline webapp test: quiet on, three proactive ticks, then an [URGENT] memo; the next tick delivers the urgent line."""
        from memory.store import MemoryStore
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore("default", data_dir)
        store.set_quiet_mode(hours=4.0)
        for _ in range(3):
            res = webapp._run_demo_turn(None, None, [], session_id, is_proactive=True, trigger_type="silence")
            panel = res[0]
            self.assertIn("Blocked by Quiet Mode", panel)
            self.assertIn("ForeverYours initiated:", panel)
            self.assertNotIn("Dad said:", panel)
            history = res[2]
            self.assertEqual(len(history), 0)
        webapp.save_caregiver_text_memo("[URGENT] Please drink water", session_id)
        with patch("pipeline.orchestrator.think.generate_reply_stream", return_value=["Okay, I'll tell him."]), patch("pipeline.orchestrator._speak_turn", return_value=("", [], 0.0)):
            res = webapp._run_demo_turn(None, None, [], session_id, is_proactive=True, trigger_type="silence")
        panel = res[0]
        self.assertIn("share something urgent", panel)

class TestEmptyTranscriptArity(unittest.TestCase):
    """Regression tests for the empty/unintelligible-transcript arity bug.

    Every return path in webapp._run_demo_turn must yield a 5-tuple so that
    webapp.run_demo_turn produces exactly 7 values for Gradio's 7 declared
    outputs. The empty-transcript guard previously returned a 4-tuple, which
    crashed the demo with an output-count mismatch on blank/unintelligible
    input (a trivially reachable judge action).
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            # Issue #53: redirect the rate-limit counter into the temp dir so the
            # suite never spends the live demo's daily request quota.
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    # --- Property 1: Bug Condition (empty/unintelligible transcript) ---

    def test_empty_audio_transcript_returns_5_tuple(self):
        """Requirement 2.1/2.3: empty transcript -> consistent 5-tuple + message."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp._run_demo_turn("fake.wav", None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("try again", result[0])
        self.assertIn("Acoustic Biomarkers", result[4])

    def test_whitespace_audio_transcript_returns_5_tuple(self):
        """Requirement 2.1: whitespace-only transcript -> consistent 5-tuple."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("   ", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp._run_demo_turn("fake.wav", None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("try again", result[0])
        self.assertIn("Acoustic Biomarkers", result[4])

    def test_empty_transcript_end_to_end_returns_8_tuple(self):
        """Requirement 2.2/2.3: run_demo_turn yields exactly 8 outputs (no Gradio mismatch),
        the 8th clearing audio_in so a stale sample clip isn't re-sent (#83, #80 2.B3)."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp.run_demo_turn("fake.wav", [], session_id)
        self.assertEqual(len(result), 8)
        self.assertIn("try again", result[0])
        self.assertIsNone(result[7])

    # --- Property 2: Preservation (non-buggy paths unchanged) ---

    def test_no_input_path_preserved(self):
        """Requirement 3.2: neither audio nor text -> existing 5-tuple + message."""
        session_id, _ = webapp.init_session()
        result = webapp._run_demo_turn(None, None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("Record audio or type what Dad says first.", result[0])
        self.assertIn("_No audio detected_", result[4])

    def test_rate_limited_path_preserved(self):
        """Requirement 3.3: over the daily cap -> existing 5-tuple + rate-limit text.

        #81 A1: the cap only counts turns about to spend a Nebius call, so this
        needs a key present and a non-fast-path transcript to reach that check."""
        session_id, _ = webapp.init_session()
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-key-for-cap-test"}), \
             patch.object(webapp.hear, "transcribe", return_value=("Hello there", {"wpm": 0.0, "avg_pause_s": 0.0})), \
             patch.object(webapp, "_rate_limit_ok", return_value=False):
            result = webapp._run_demo_turn("fake.wav", None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("daily request cap", result[0])
        self.assertIn("_Rate limited_", result[4])

    def test_valid_distress_turn_preserved(self):
        """Requirement 3.1/3.4: a valid transcript still returns its 5-tuple with reply + audio."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("I fell down earlier and I'm scared", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp._run_demo_turn("fake.wav", None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("Dad said:", result[0])
        self.assertIsNotNone(result[1])
        self.assertIn("Acoustic Biomarkers", result[4])



class TestProactiveButtons(unittest.TestCase):
    """Issue #70: the proactive buttons call run_demo_turn(..., is_proactive=True).

    Runs the module-level handler the four buttons are wired to, offline, with
    run_turn stubbed so no API key is needed.
    """

    def setUp(self):
        # Issue #76: without this isolation, every run_demo_turn call in this
        # class wrote to the live data/rate_limit.json (DATA_DIR default),
        # tripping the real demo's daily cap on repeated suite runs -- same
        # root cause as #53, fixed for the other two turn-test classes but
        # missed here.
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _fake_result(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            reply_text="Good morning, Dad.",
            audio_paths=[],
            caregiver_flag=False,
            is_fallback=False,
            background_thread=None,
        )

    def test_run_demo_turn_accepts_is_proactive(self):
        session_id, _ = webapp.init_session()
        with patch.object(webapp, "run_turn", return_value=self._fake_result()) as rt:
            out = webapp.run_demo_turn(None, None, [], session_id, "Morning (Default)", is_proactive=True)
        self.assertEqual(len(out), 8)
        self.assertTrue(rt.call_args.kwargs["is_proactive"])
        self.assertIn("Good morning, Dad.", out[0])

    def test_proactive_turn_not_attributed_to_senior(self):
        """Issue #65: a proactive turn must render as assistant-initiated and
        must NOT print the internal trigger token as if Dad had said it."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp, "run_turn", return_value=self._fake_result()):
            out = webapp.run_proactive_turn([], session_id, "Morning (Default)", "morning")
        panel = out[0]
        self.assertIn("Good morning, Dad.", panel)
        self.assertIn("ForeverYours initiated:", panel)
        self.assertNotIn("Dad said:", panel)
        self.assertNotIn("[PROACTIVE_TRIGGER]", panel)

    def test_button_handler_returns_eight_outputs_for_each_time(self):
        for sim_time in ("Morning (Default)", "Sundowning (6 PM)", "Night (11 PM)"):
            session_id, _ = webapp.init_session()
            with patch.object(webapp, "run_turn", return_value=self._fake_result()) as rt:
                out = webapp.run_proactive_turn([], session_id, sim_time, "silence")
            self.assertEqual(len(out), 8)
            self.assertTrue(rt.call_args.kwargs["is_proactive"])
            self.assertEqual(out[5], session_id)


class TestBuildDemoCss(unittest.TestCase):
    def test_css_set_on_blocks_not_only_launch_kwargs(self):
        """#83 PR #85 Codex review: app.py (the hosted/Spaces entrypoint) calls
        build_demo() and never calls .launch(css=...) itself, so the mobile
        alert strip and footer rules must be set on the Blocks object -- Gradio
        stores a constructor-supplied css on `_deprecated_css` until a server
        actually renders /config (verified live for both entrypoints in the
        PR); checking it here catches a regression to launch()-only css."""
        demo = webapp.build_demo()
        self.assertIn(".mobile-alert-strip", demo._deprecated_css or "")
        self.assertIn("footer", demo._deprecated_css or "")


if __name__ == "__main__":

    unittest.main()

