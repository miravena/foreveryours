"""Tests for webapp.py's per-session isolation (issues #11, #18).



A public demo link is shared by every judge at once, so one judge's flags,

memories and audio must never show up in another judge's tab, and must be

deleted when the session ends. Runs with no NEBIUS_API_KEY: the distress

phrase goes through the offline fast-path.

"""

import contextlib

import io

import os

import sys

import tempfile

import threading

import time

import unittest

import wave

from pathlib import Path

from unittest.mock import patch



import webapp
from memory.store import MemoryStore

# Gradio hands over uploads under the temp dir; webapp refuses audio paths outside it.
FAKE_UPLOAD = os.path.join(tempfile.gettempdir(), "fake.wav")

# Test prints (benchmarks, TTS fallbacks) go to a block-buffered stdout that is
# flushed only at exit, AFTER unittest's stderr summary, so
# `unittest discover tests 2>&1 | tail -1` never showed OK. Line-buffering keeps
# the two streams in order. Discovery imports this module before any test runs.
sys.stdout.reconfigure(line_buffering=True)





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

            return webapp.run_demo_turn(FAKE_UPLOAD, [], session_id)



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
        a reset conversation. Mid-demo means the browser still holds the
        conversation; with no history it is a first turn (#215)."""
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        with patch.object(webapp.hear, "transcribe", return_value=("Hello", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp.run_demo_turn(FAKE_UPLOAD, history, None)
        self.assertIn("reset after a period of inactivity", result[0])
        self.assertIsNotNone(result[5])  # a new session_id was minted

    def test_fresh_session_shows_no_reset_notice(self):
        """#215: the first turn of a fresh page has no session id and no
        history; nothing was reset, so the notice would be false."""
        with patch.object(webapp.hear, "transcribe", return_value=("Hello", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp.run_demo_turn(FAKE_UPLOAD, None, [], None)
        self.assertNotIn("reset after a period of inactivity", result[0])
        self.assertIsNotNone(result[5])

    def test_expired_session_with_history_shows_reset_notice(self):
        """#215: a session id lost while the browser still holds the
        conversation is a real expiry."""
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        with patch.object(webapp.hear, "transcribe", return_value=("Hello", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp.run_demo_turn(FAKE_UPLOAD, None, history, None)
        self.assertIn("reset after a period of inactivity", result[0])

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
        
        self.assertIn("HIGH PRIORITY SAFETY ALERT", panel)
        self.assertIn("CRISIS", panel)
        
        self.assertIn("Simulated caregiver alert:", strip)
        self.assertNotIn("No flags yet", panel)
        self.assertNotEqual(strip, "")

    def test_fast_path_flag_says_it_was_raised_by_safety_rules(self):
        session_id, _ = webapp.init_session()
        self._turn("I want to die", session_id)
        panel = webapp._format_caregiver_panel(session_id)
        self.assertIn("raised by: safety rules, before the model", panel)
        self.assertNotIn("raised by: Nemotron backstop", panel)

    def test_audit_flag_says_it_was_raised_by_the_backstop(self):
        from caregiver import CaregiverFlag

        flag = CaregiverFlag(text="x", severity="audit", disclosed_to_senior=True, source="audit")
        self.assertIn("raised by: Nemotron backstop, after the reply", webapp._flag_origin(flag))
        flag = CaregiverFlag(text="x", severity="confusion", disclosed_to_senior=True, source="perseveration")
        self.assertIn("raised by: repeated-question check", webapp._flag_origin(flag))

    def test_flag_without_source_renders_no_origin(self):
        from caregiver import CaregiverFlag

        flag = CaregiverFlag(text="x", severity="audit", disclosed_to_senior=True)
        self.assertEqual(webapp._flag_origin(flag), "")

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

    def test_session_sweeper_expires_orphan_without_new_visitor(self):
        # Must be a valid 32-hex session id: #150/#151 makes
        # the sweeper skip any entry whose name isn't one, so a non-hex name
        # here would no longer be swept and this test would be checking the
        # wrong thing.
        orphan = "aa00bb11cc22dd33ee44ff5500112233"
        root = self.sessions_dir / orphan
        root.mkdir(parents=True, exist_ok=True)
        old = time.time() - webapp.SESSION_TTL_S - 60
        os.utime(root, (old, old))

        stop = threading.Event()
        thread = webapp._start_session_sweeper(interval_s=0.01, stop_event=stop)
        self.assertIsNotNone(thread)
        for _ in range(100):
            if not root.exists():
                break
            time.sleep(0.01)
        stop.set()
        thread.join(timeout=2)
        self.assertFalse(root.exists())



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

        self.assertIn(webapp.SIMULATED_ALERT_CARD, panel)

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



    def test_memo_box_refuses_dosing_language(self):
        """#280: a dose instruction in a memo is refused, never stored, and the
        text stays in the box; a schedule reminder is saved as before."""
        session_id, _ = webapp.init_session()
        memo = "Dad's doctor said if his chest hurts he should take three extra aspirin and not bother anyone."
        panel, sess, kept = webapp.save_caregiver_text_memo(memo, session_id)
        self.assertEqual(sess, session_id)
        self.assertEqual(kept, memo)
        self.assertIn("Memo not saved", panel)
        self.assertNotIn("bother anyone", panel)
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)
        self.assertFalse(any("aspirin" in i.text for i in store.all()))
        # Review round 1: the wordings without "his", and the negated precaution.
        for bad in ("Double insulin tonight.", "Skip pills tonight.", "Give Dad extra insulin tonight.",
                    "Stop his blood pressure pills.",
                    # round 2
                    "Do not forget to double his insulin tonight.", "Give Dad more insulin tonight.",
                    # round 3
                    "Take three extra blood pressure pills tonight.", "Double his metformin tonight."):
            with self.subTest(bad=bad):
                self.assertIsNotNone(webapp.dosing_instruction(bad))
        for ok in ("Do not double his insulin.", "Never skip his pills.", "Dad takes 5 mg daily.",
                   "Bring an extra pillow tonight.", "Sarah is dropping off more groceries.",
                   "Dad has extra insulin in the fridge.", "Dad has two more pills left in the box."):
            with self.subTest(ok=ok):
                self.assertIsNone(webapp.dosing_instruction(ok))
        panel, _, cleared = webapp.save_caregiver_text_memo("Blood pressure pill at 8 AM.", session_id)
        self.assertEqual(cleared, "")
        self.assertIn("Blood pressure pill at 8 AM", panel)

    def test_high_priority_alert_banner_renders_on_distress(self):

        """High priority alert banner renders at the top of the caregiver panel on fall events."""

        session_id, _ = webapp.init_session()

        self._turn("I fell down earlier and I'm scared", session_id)

        panel = webapp._format_caregiver_panel(session_id)

        self.assertIn(webapp.SIMULATED_ALERT_CARD, panel)

        self.assertIn("Severity:** `DISTRESS`", panel)

        self.assertIn("Disclosure:** ✅ **Disclosed to Senior in conversation**", panel)



    def test_dual_input_prioritizes_text(self):

        session_id, _ = webapp.init_session()

        with patch.object(webapp.hear, "transcribe", return_value=("Audio transcript", {"wpm": 0.0, "avg_pause_s": 0.0})):

            # When both text and audio are provided, text_in takes precedence

            transcript_out, audio_out, history_state, panel, biomarkers, out_sess_id, out_text_in, out_audio_in = webapp.run_demo_turn(

                audio_in=FAKE_UPLOAD,

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
        from pipeline.intent import Intent
        for _ in range(3):
            # With no [URGENT] memo yet, a proactive tick in Quiet Mode must be
            # suppressed by the orchestrator before any LLM call. Force quiet mode
            # active (persistence is covered by MemoryStore's own tests) so this
            # webapp-level test is deterministic and fully offline, and stub the
            # LLM reply stream so no path can reach NEBIUS_API_KEY.
            with patch("memory.store.MemoryStore.is_quiet_mode_active", return_value=True), \
                 patch("pipeline.orchestrator.detect_intent", return_value=Intent.LOGISTICAL), \
                 patch("pipeline.orchestrator.think.stream_reply", return_value=iter(["Okay."])), \
                 patch("pipeline.orchestrator._speak_turn", return_value=("", [], 0.0)):
                res = webapp._run_demo_turn(None, None, [], session_id, is_proactive=True, trigger_type="silence")
            panel = res[0]
            self.assertIn("Blocked by Quiet Mode", panel)
            self.assertIn("ForeverYours initiated:", panel)
            self.assertNotIn("Dad said:", panel)
            history = res[2]
            self.assertEqual(len(history), 0)
        # The memo must read as a caregiver *schedule update* (contains a time/
        # errand marker) so caregiver_schedule_updates() surfaces it; only then
        # does the [URGENT] breakthrough fire during Quiet Mode.
        webapp.save_caregiver_text_memo("[URGENT] Doctor appointment this afternoon", session_id)
        with patch("memory.store.MemoryStore.is_quiet_mode_active", return_value=True), \
             patch("pipeline.orchestrator.think.stream_reply", return_value=iter(["Okay, I'll tell him."])), \
             patch("pipeline.orchestrator._speak_turn", return_value=("", [], 0.0)), \
             patch("pipeline.orchestrator.detect_intent", return_value=Intent.LOGISTICAL):
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
            result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("try again", result[0])
        self.assertIn("Acoustic Biomarkers", result[4])

    def test_whitespace_audio_transcript_returns_5_tuple(self):
        """Requirement 2.1: whitespace-only transcript -> consistent 5-tuple."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("   ", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("try again", result[0])
        self.assertIn("Acoustic Biomarkers", result[4])

    def test_empty_transcript_end_to_end_returns_8_tuple(self):
        """Requirement 2.2/2.3: run_demo_turn yields exactly 8 outputs (no Gradio mismatch),
        the 8th clearing audio_in so a stale sample clip isn't re-sent (#83, #80 2.B3)."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp.run_demo_turn(FAKE_UPLOAD, [], session_id)
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
            result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("daily request cap", result[0])
        self.assertIn("_Rate limited_", result[4])

    # --- The daily cap withholds only the paid THINK continuation ---
    #
    # At the cap, a fast-path utterance must still get the offline spoken
    # reply and the caregiver flag through BOTH handlers. stream_reply and
    # extract_memory_llm raise if touched, but run_turn's `except Exception`
    # would swallow that into a fallback, so each test also asserts the mocks
    # were never called, and that run_turn handed back no background thread.

    # (utterance, text the fast-path reply carries, text the caregiver flag carries)
    CAP_FAST_PATH_CASES = [
        ("I fell down earlier and I'm scared", "letting your family know", "URGENT"),
        ("I can't breathe", "letting your family know", "URGENT"),
        ("I want to die", "988", "URGENT CRISIS"),
        ("Where am I?", "take it slow", "Possible confusion"),
    ]

    def _cap_patches(self, utterance, rate_limit_ok=False):
        """The capped-session fixture shared by every test_cap_* test."""
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-key-for-cap-test"}))
        stack.enter_context(patch.object(
            webapp.hear, "transcribe", return_value=(utterance, {"wpm": 0.0, "avg_pause_s": 0.0})
        ))
        if rate_limit_ok is not None:
            stack.enter_context(patch.object(webapp, "_rate_limit_ok", return_value=rate_limit_ok))
        self.stream_reply_mock = stack.enter_context(patch(
            "pipeline.think.stream_reply", side_effect=AssertionError("THINK must not be called at the cap")
        ))
        self.extract_mock = stack.enter_context(patch(
            "pipeline.think.extract_memory_llm", side_effect=AssertionError("no hosted background work at the cap")
        ))
        self.turn_results = []
        real_run_turn = webapp.run_turn

        def recording_run_turn(*args, **kwargs):
            res = real_run_turn(*args, **kwargs)
            self.turn_results.append((kwargs.get("allow_hosted_call", True), res))
            return res

        stack.enter_context(patch.object(webapp, "run_turn", side_effect=recording_run_turn))
        self.remember_mock = stack.enter_context(patch.object(
            webapp, "_remember_background_thread", wraps=webapp._remember_background_thread
        ))
        return stack

    def _assert_no_hosted_work(self):
        self.stream_reply_mock.assert_not_called()
        self.extract_mock.assert_not_called()
        self.assertTrue(self.turn_results, "run_turn was never reached at the cap")
        for allowed, res in self.turn_results:
            self.assertFalse(allowed, "run_turn must get allow_hosted_call=False at the cap")
            self.assertIsNone(res.background_thread, "no AUDIT/extraction thread at the cap")

    def _assert_capped_fast_path_reply(self, result, session_id, reply_text, flag_text):
        self.assertEqual(len(result), 5)
        self.assertFalse(result[0].startswith("This demo has hit its daily request cap"))
        self.assertIn(reply_text, result[0])
        self.assertIsNotNone(result[1], "fast-path reply must carry audio at the cap")
        self.assertIn("daily request cap", result[0])
        self.assertIn("_Rate limited_", result[4])
        self.assertIn(flag_text, webapp._format_caregiver_panel(session_id))

    def test_cap_does_not_block_fast_path_nonstreaming(self):
        for utterance, reply_text, flag_text in self.CAP_FAST_PATH_CASES:
            with self.subTest(utterance=utterance):
                session_id, _ = webapp.init_session()
                with self._cap_patches(utterance):
                    result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
                    self._assert_no_hosted_work()
                    # The non-streaming handler registers only run_turn's own
                    # background thread, which must be None here.
                    for call in self.remember_mock.call_args_list:
                        self.assertIsNone(call.args[1])
                self._assert_capped_fast_path_reply(result, session_id, reply_text, flag_text)

    def test_cap_does_not_block_fast_path_streaming(self):
        for utterance, reply_text, flag_text in self.CAP_FAST_PATH_CASES:
            with self.subTest(utterance=utterance):
                session_id, _ = webapp.init_session()
                with self._cap_patches(utterance):
                    outputs = list(webapp.run_demo_turn_streaming(FAKE_UPLOAD, [], session_id))
                    self._assert_no_hosted_work()
                last = outputs[-1]
                # The reply audio rides its own CHUNK yield(s), once;
                # the final yield carries none, so check the delivered chunk.
                self.assertIsNone(last[1], "the final yield must not re-send the reply audio")
                delivered = [o[1] for o in outputs if isinstance(o[1], str)]
                spoken = (last[0], delivered[0] if delivered else None, *last[2:5])
                self._assert_capped_fast_path_reply(spoken, session_id, reply_text, flag_text)

    def test_cap_notice_does_not_claim_audio_when_speech_failed(self):
        """Codex P2 on the publish: a capped emergency whose TTS
        failed must not say the safety message "still played"."""
        utterance, reply_text, flag_text = self.CAP_FAST_PATH_CASES[0]
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                session_id, _ = webapp.init_session()
                # Non-streaming: no combined clip. Streaming: no
                # chunk is deliverable, so none reaches the browser.
                with self._cap_patches(utterance), \
                        patch.object(webapp, "_combine_audio_chunks", return_value=None), \
                        patch.object(webapp, "_chunk_readable", return_value=False):
                    if streaming:
                        result = list(webapp.run_demo_turn_streaming(FAKE_UPLOAD, [], session_id))[-1][:5]
                    else:
                        result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
                self.assertIsNone(result[1])
                self.assertIn("daily request cap", result[0])
                self.assertNotIn("still played", result[0])
                self.assertIn("speech was unavailable", result[0])
                self.assertIn(flag_text, webapp._format_caregiver_panel(session_id))

    def test_cap_notice_claims_only_what_happened(self):
        self.assertIn("still played", webapp._cap_notice(True, True))
        self.assertIn("family has been notified", webapp._cap_notice(True, True))
        self.assertNotIn("still played", webapp._cap_notice(False, True))
        self.assertNotIn("family has been notified", webapp._cap_notice(True, False))
        self.assertEqual(webapp.CAP_NOTICE, webapp._cap_notice(True, True))

    def test_cap_does_not_block_crisis_fast_path(self):
        """'I can't breathe' matches safety/fastpath.py's distress patterns on
        current main, so it is used as written (step 1)."""
        for utterance in ("I can't breathe", "I want to die"):
            with self.subTest(utterance=utterance):
                session_id, _ = webapp.init_session()
                with self._cap_patches(utterance):
                    result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
                    self._assert_no_hosted_work()
                self.assertIsNotNone(result[1])
                self.assertIn("URGENT", webapp._format_caregiver_panel(session_id))

    def test_cap_count_unchanged_by_emergency_turns(self):
        """Idempotency against the REAL counter: _rate_limit_ok is not patched."""
        import datetime
        import json
        from caregiver import CaregiverFlags

        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        data_dir.mkdir(parents=True, exist_ok=True)
        rate_file = data_dir / "rate_limit.json"
        today = datetime.date.today().isoformat()
        rate_file.write_text(json.dumps({today: webapp.MAX_DAILY_REQUESTS}), "utf-8")

        utterance = "I fell down earlier and I'm scared"
        for _ in range(2):
            with self._cap_patches(utterance, rate_limit_ok=None):
                result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
                self._assert_no_hosted_work()
            self.assertIsNotNone(result[1])
            self.assertIn("_Rate limited_", result[4])

        self.assertEqual(json.loads(rate_file.read_text("utf-8")), {today: webapp.MAX_DAILY_REQUESTS})
        flags = CaregiverFlags(webapp.DEFAULT_PROFILE_ID, data_dir).all()
        self.assertEqual(len(flags), 2)
        panel = webapp._format_caregiver_panel(session_id)
        self.assertEqual(panel.count(f"- **({flags[0].severity})** {flags[0].text}"), 2)

    def test_valid_distress_turn_preserved(self):
        """Requirement 3.1/3.4: a valid transcript still returns its 5-tuple with reply + audio."""
        session_id, _ = webapp.init_session()
        with patch.object(webapp.hear, "transcribe", return_value=("I fell down earlier and I'm scared", {"wpm": 0.0, "avg_pause_s": 0.0})):
            result = webapp._run_demo_turn(FAKE_UPLOAD, None, [], session_id)
        self.assertEqual(len(result), 5)
        self.assertIn("Dad said:", result[0])
        self.assertIsNotNone(result[1])
        self.assertIn("Acoustic Biomarkers", result[4])



def _make_wav(path: Path, seconds: float) -> Path:
    """A real 16 kHz mono 16-bit WAV of silence, `seconds` long."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * seconds))
    return path


class TestAudioInputGuard(unittest.TestCase):
    """A failed transcription, an oversized upload or an over-long
    recording gets a short retry-or-type-instead reply that keeps the session,
    and size/duration are refused BEFORE hear.transcribe runs. Every test
    submits a REAL file: a missing path deliberately skips the guard."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = Path(self.temp_dir.name)
        self.sessions_dir = self.tmp / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", self.tmp / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()
        self.sid, _ = webapp.init_session()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _store_count(self) -> int:
        data_dir, _ = webapp._session_dirs(self.sid)
        return len(MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir, timezone_str=webapp.SENIOR_TIMEZONE).all())

    @contextlib.contextmanager
    def _asr_failure(self):
        """transcribe raises; the handler's stderr log is captured and must name
        the exception type only, never its message (which can carry a path)."""
        err = io.StringIO()
        with patch.object(webapp.hear, "transcribe", side_effect=RuntimeError("/secret/path/one.wav: hosted ASR failed")) as m, \
                contextlib.redirect_stderr(err):
            yield m
        self.assertIn("[hear] transcription failed: RuntimeError", err.getvalue())
        self.assertNotIn("/secret/path", err.getvalue())


    def test_audio_path_outside_upload_dirs_is_refused_unread(self):
        # The path comes from the browser: one outside the temp/upload and
        # sample dirs gets the retry-or-type reply and is never opened.
        # The temp dir is pinned to an empty one: when the repo itself sits under
        # the real temp dir (scripts/smoke.sh's mktemp copy), webapp.py would
        # otherwise count as an upload and be probed.
        outside = os.path.abspath(webapp.__file__)
        env = {k: v for k, v in os.environ.items() if k != "GRADIO_TEMP_DIR"}
        with patch.object(webapp.tempfile, "gettempdir", return_value=str(self.tmp / "uploads")), \
                patch.dict(os.environ, env, clear=True), \
                patch.object(webapp.hear, "probe_duration") as probe, \
                patch.object(webapp.hear, "transcribe") as transcribe:
            transcript, _bio, refusal = webapp._guarded_transcribe(outside, True)
        self.assertIsNone(transcript)
        self.assertIn("type what Dad says", refusal)
        probe.assert_not_called()
        transcribe.assert_not_called()
    def test_transcription_failure_nonstreaming_returns_type_instead(self):
        wav = _make_wav(self.tmp / "one.wav", 1.0)
        with self._asr_failure() as m:
            result = webapp._run_demo_turn(str(wav), None, [], self.sid)
        m.assert_called_once()
        self.assertEqual(len(result), 5)
        self.assertIn("type", result[0].lower())
        self.assertIsNone(result[1])
        self.assertEqual(result[2], [])
        self.assertTrue((self.sessions_dir / self.sid).is_dir())

    def test_transcription_failure_streaming_returns_type_instead(self):
        wav = _make_wav(self.tmp / "one.wav", 1.0)
        with self._asr_failure() as m:
            outs = list(webapp.run_demo_turn_streaming(str(wav), [], self.sid))
        m.assert_called_once()
        last = outs[-1]
        self.assertEqual(len(last), 8)
        self.assertIn("type", last[0].lower())
        self.assertIsNone(last[1])
        self.assertEqual(last[5], self.sid)
        self.assertTrue((self.sessions_dir / self.sid).is_dir())

    def test_transcription_failure_caregiver_memo_keeps_panel_and_writes_nothing(self):
        wav = _make_wav(self.tmp / "memo.wav", 1.0)
        before = self._store_count()
        with self._asr_failure() as m:
            panel, sid2 = webapp.save_caregiver_voice_memo(str(wav), self.sid)
        m.assert_called_once()
        self.assertEqual(sid2, self.sid)
        self.assertIn("type", panel.lower())
        self.assertEqual(self._store_count(), before)

    def _run_all(self, path: Path) -> list[str]:
        nonstream = webapp._run_demo_turn(str(path), None, [], self.sid)
        self.assertEqual(len(nonstream), 5)
        self.assertIsNone(nonstream[1])
        last = list(webapp.run_demo_turn_streaming(str(path), [], self.sid))[-1]
        self.assertEqual(len(last), 8)
        self.assertEqual(last[5], self.sid)
        panel, sid2 = webapp.save_caregiver_voice_memo(str(path), self.sid)
        self.assertEqual(sid2, self.sid)
        return [nonstream[0], last[0], panel]

    def _assert_no_state(self, before: int):
        data_dir, _ = webapp._session_dirs(self.sid)
        self.assertEqual(self._store_count(), before)
        self.assertFalse((data_dir / "rate_limit.json").exists())

    def test_oversized_upload_refused_before_asr(self):
        big = self.tmp / "big.wav"
        big.write_bytes(b"\0" * 2048)
        before = self._store_count()
        with patch.object(webapp, "MAX_AUDIO_UPLOAD_BYTES", 1024), \
                patch.object(webapp.hear, "transcribe") as m:
            replies = self._run_all(big) + self._run_all(big)
        m.assert_not_called()
        for reply in replies:
            self.assertIn("too large", reply.lower())
        self._assert_no_state(before)

    def test_overlong_recording_refused_before_asr(self):
        long_wav = _make_wav(self.tmp / "long.wav", 3.0)
        before = self._store_count()
        with patch.object(webapp, "MAX_AUDIO_SECONDS", 2), \
                patch.object(webapp, "MAX_AUDIO_UPLOAD_BYTES", 10**8), \
                patch.object(webapp.hear, "transcribe") as m:
            replies = self._run_all(long_wav) + self._run_all(long_wav)
        m.assert_not_called()
        for reply in replies:
            self.assertIn("seconds", reply.lower())
        self._assert_no_state(before)

    def test_missing_or_empty_file_skips_guard_and_reaches_empty_transcript_branch(self):
        empty = self.tmp / "empty.wav"
        empty.write_bytes(b"")
        with patch.object(webapp, "MAX_AUDIO_UPLOAD_BYTES", 1), \
                patch.object(webapp, "MAX_AUDIO_SECONDS", 0), \
                patch.object(webapp.hear, "transcribe", return_value=("", {"wpm": 0.0, "avg_pause_s": 0.0})) as m:
            for path in (FAKE_UPLOAD, str(empty)):
                result = webapp._run_demo_turn(path, None, [], self.sid)
                self.assertEqual(len(result), 5)
                self.assertIn("Couldn't make out any speech or text", result[0])
        self.assertEqual(m.call_count, 2)


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
    def test_build_line_only_when_build_info_exists(self):
        # scripts/deploy_hf_space.py writes BUILD_INFO into the Space; a checkout has none.
        with tempfile.TemporaryDirectory() as tmp:
            info = Path(tmp) / "BUILD_INFO"
            self.assertEqual(webapp._build_line(info), "")
            info.write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")
            self.assertEqual(webapp._build_line(info), "Build: `0123456`")
            info.write_text("\n", encoding="utf-8")
            self.assertEqual(webapp._build_line(info), "")

    def test_model_footer_is_always_visible_and_names_the_think_model(self):
        from pipeline import speak, think

        defaults_only = {k: v for k, v in os.environ.items()
                         if k not in ("THINK_MODEL", "AUDIT_MODEL", "ASR_BACKEND", "TTS_BACKEND")}
        with patch.dict(os.environ, defaults_only, clear=True), \
                patch.object(speak, "_piper_available", return_value=True):
            demo = webapp.build_demo()
        footers = [
            b for b in demo.blocks.values()
            if "Safety backstop:" in str(getattr(b, "value", "")) and "Hearing:" in str(getattr(b, "value", ""))
        ]
        self.assertEqual(len(footers), 1)
        text = footers[0].value
        self.assertTrue(footers[0].visible)
        self.assertIn("Reply: NVIDIA Nemotron 3 Nano 30B on Nebius Token Factory", text)
        self.assertIn("Safety backstop: NVIDIA Nemotron 3 Super 120B on Nebius Token Factory", text)
        self.assertIn("Hearing: faster-whisper, on this app's server", text)
        self.assertIn("Voice: Piper, on this app's server", text)
        self.assertEqual(think.DEFAULT_THINK_MODEL, "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")

    def test_model_footer_follows_configured_models_and_backends(self):
        # The footer must name what actually runs, not the defaults: a
        # different reply model, hosted ASR, and the eSpeak fallback.
        env = {
            "THINK_MODEL": "meta-llama/Llama-3.3-70B-Instruct",
            "AUDIT_MODEL": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "ASR_BACKEND": "nebius",
            "ASR_NEBIUS_MODEL": "nvidia/parakeet-tdt-1.1b",
            "TTS_BACKEND": "espeak",
        }
        with patch.dict(os.environ, env):
            text = webapp._model_footer()
        self.assertIn("Reply: Llama-3.3-70B-Instruct on Nebius Token Factory", text)
        self.assertIn("Safety backstop: NVIDIA Nemotron 3 Nano 30B on Nebius Token Factory", text)
        self.assertIn("Hearing: parakeet-tdt-1.1b on Nebius Token Factory", text)
        self.assertNotIn("faster-whisper", text)
        self.assertNotIn("Piper", text)

    def test_audit_flag_names_the_configured_backstop_model(self):
        from caregiver import CaregiverFlag

        flag = CaregiverFlag(text="x", severity="audit", disclosed_to_senior=True, source="audit")
        with patch.dict(os.environ, {"AUDIT_MODEL": "meta-llama/Llama-3.3-70B-Instruct"}):
            origin = webapp._flag_origin(flag)
        self.assertEqual(origin, "raised by: Llama-3.3-70B-Instruct backstop, after the reply")

    def test_model_footer_voice_follows_the_speak_fallback_order(self):
        from pipeline import speak

        # Platform is passed in, not patched on the shared sys module: other
        # threads (Gradio, the session sweeper) read sys.platform too.
        with patch.object(speak, "_piper_available", return_value=False):
            self.assertIn("Voice: Windows System.Speech,", webapp._model_footer(platform="win32"))
        with patch.object(speak, "_piper_available", return_value=False), \
                patch.object(speak, "_get_espeak_cli", return_value="/usr/bin/espeak-ng"):
            self.assertIn("Voice: eSpeak NG,", webapp._model_footer(platform="linux"))

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


class _TurnHarness:
    """Shared setUp/tearDown and a blocking fake turn body for the
    concurrency tests. Same isolation as TestWebappSessions:
    SHARED_PROFILE=False and a temp SESSIONS root, so the per-session
    bookkeeping in run_demo_turn_streaming actually runs."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", Path(self.temp_dir.name) / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        self.entered = threading.Semaphore(0)
        self.release = threading.Event()
        self.threads: list[threading.Thread] = []
        self.errors: list[BaseException] = []

    def tearDown(self):
        # Never leave a worker parked on the event, whatever the test did.
        self.release.set()
        for t in self.threads:
            t.join(timeout=5)
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()
        self.assertFalse([t for t in self.threads if t.is_alive()], "a turn thread never finished")

    def _blocking_impl(self, *args, **kwargs):
        self.entered.release()
        if not self.release.wait(timeout=10):
            raise AssertionError("fake turn was never released")
        yield ("done",) + (None,) * 7

    def _start_turn(self, sid: str) -> threading.Thread:
        def run():
            try:
                list(webapp.run_demo_turn_streaming(None, "hi", [], sid, "Morning (Default)"))
            except BaseException as exc:  # noqa: BLE001 - re-raised in the test thread
                self.errors.append(exc)

        t = threading.Thread(target=run, daemon=True)
        self.threads.append(t)
        t.start()
        return t

    def _join_all(self):
        for t in self.threads:
            t.join(timeout=5)
            self.assertFalse(t.is_alive(), "turn thread did not finish")
        if self.errors:
            raise self.errors[0]


class TestTurnConcurrency(_TurnHarness, unittest.TestCase):
    """Gradio's default concurrency_limit of 1 queued every visitor's
    Send/Enter behind one slow ASR/Nebius/TTS turn. Turn listeners now share a
    bounded limit on concurrency_id "senior_turn", and a per-session lock keeps
    turns ordered within one session."""

    def test_turn_listeners_share_bounded_concurrency(self):
        demo = webapp.build_demo()
        # Every senior-turn producer has the same 8-output turn tuple:
        # run_btn.click, text_in.submit, the four proactive buttons and the two example chips (#239).
        turn_fns = [f for f in demo.fns.values() if len(f.outputs) == 8]
        self.assertEqual(len(turn_fns), 8, [getattr(f.fn, "__name__", f.fn) for f in turn_fns])
        for f in turn_fns:
            with self.subTest(fn=getattr(f.fn, "__name__", f.fn)):
                self.assertIsInstance(f.concurrency_limit, int)
                self.assertGreaterEqual(f.concurrency_limit, 2)
                self.assertEqual(f.concurrency_limit, webapp.TURN_CONCURRENCY)
                self.assertEqual(f.concurrency_id, "senior_turn")

    def test_same_session_turns_serialize(self):
        sid = webapp._new_session()
        with patch.object(webapp, "_run_demo_turn_streaming_impl", self._blocking_impl):
            self._start_turn(sid)
            self.assertTrue(self.entered.acquire(timeout=2), "first turn never started")
            self._start_turn(sid)
            # The second turn for the SAME session must wait while the first holds it.
            self.assertFalse(self.entered.acquire(timeout=0.5), "same-session turns overlapped")
            self.release.set()
            self.assertTrue(self.entered.acquire(timeout=2), "second turn never ran after the first finished")
            self._join_all()
        self.assertNotIn(sid, webapp._session_turn_locks)
        self.assertNotIn(sid, webapp._active_turns)

    def test_different_sessions_overlap(self):
        sid_a, sid_b = webapp._new_session(), webapp._new_session()
        with patch.object(webapp, "_run_demo_turn_streaming_impl", self._blocking_impl):
            self._start_turn(sid_a)
            self._start_turn(sid_b)
            # Both must be inside the turn body before either is released:
            # serialization is per session, never global.
            self.assertTrue(self.entered.acquire(timeout=2), "first session's turn never started")
            self.assertTrue(self.entered.acquire(timeout=2), "different sessions did not overlap")
            self.release.set()
            self._join_all()


class TestTurnLockHygiene(_TurnHarness, unittest.TestCase):
    """A browser disconnect frees the session
    lock, and FY_TURN_CONCURRENCY is validated."""

    def test_closing_suspended_turn_releases_session_lock(self):
        sid = webapp._new_session()

        def two_chunk_impl(*args, **kwargs):
            yield ("thinking",) + (None,) * 7
            yield ("done",) + (None,) * 7

        with patch.object(webapp, "_run_demo_turn_streaming_impl", two_chunk_impl):
            gen = webapp.run_demo_turn_streaming(None, "hi", [], sid, "Morning (Default)")
            next(gen)  # suspended mid-turn, holding the session lock
            self.assertTrue(webapp._session_turn_locks[sid].locked())
            gen.close()  # what Gradio does when the browser disconnects
            self.assertNotIn(sid, webapp._session_turn_locks)
            self.assertNotIn(sid, webapp._active_turns)
            # The next same-session turn proceeds instead of deadlocking.
            t = self._start_turn(sid)
            t.join(timeout=2)
            self.assertFalse(t.is_alive(), "next same-session turn blocked on a leaked lock")
            self._join_all()

    def test_turn_concurrency_setting_is_validated(self):
        self.assertEqual(webapp._parse_turn_concurrency(None), 4)
        self.assertEqual(webapp._parse_turn_concurrency("6"), 6)
        for bad in ("1", "0", "-3", "four", ""):
            with self.subTest(raw=bad):
                with self.assertRaisesRegex(ValueError, "FY_TURN_CONCURRENCY"):
                    webapp._parse_turn_concurrency(bad)


class TestPanelNotificationStates(unittest.TestCase):
    """#201: the caregiver panel says "notification sent", "notification failed"
    or, with the channel off, that the alert is simulated -- never "dispatched"."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_dir.cleanup)
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", Path(self.temp_dir.name) / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        webapp._request_log.clear()

    def _fall(self, notifier):
        session_id, _ = webapp.init_session()
        said = "I fell down earlier and I'm scared"
        with patch.object(webapp.hear, "transcribe", return_value=(said, {"wpm": 0.0, "avg_pause_s": 0.0})), \
             patch("notify.get_notifier", return_value=notifier):
            webapp.run_demo_turn(FAKE_UPLOAD, [], session_id)
        self._drain()
        return webapp._format_caregiver_panel(session_id)

    def _drain(self):
        """Wait for every notification thread this test started, so none
        outlives the test (a leaked daemon thread imports modules and writes
        files during other tests)."""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            live = [t for t in threading.enumerate() if t.name.startswith("fy-notify")]
            if not live:
                return
            for t in live:
                t.join(timeout=0.1)
        self.fail("notification threads still running")

    def test_slow_notifier_does_not_stall_the_next_turn_join(self):
        release = threading.Event()

        class Slow:
            def send(self, flag, household):
                release.wait(30)

        session_id, _ = webapp.init_session()
        said = "I fell down earlier and I'm scared"
        with patch.object(webapp.hear, "transcribe", return_value=(said, {"wpm": 0.0, "avg_pause_s": 0.0})), \
             patch("notify.get_notifier", return_value=Slow()):
            webapp.run_demo_turn(FAKE_UPLOAD, [], session_id)
            t0 = time.monotonic()
            webapp._join_previous_turn(session_id)
            self.assertLess(time.monotonic() - t0, 2)
        release.set()
        self._drain()

    def test_off_shows_no_notification_claim(self):
        import notify
        panel = self._fall(notify.NullNotifier())
        self.assertIn("HIGH PRIORITY SAFETY ALERT", panel)
        for claim in ("notified", "Notification failed", "dispatched", "DISPATCHED"):
            self.assertNotIn(claim, panel)

    def test_success_shows_notified(self):
        class Ok:
            def send(self, flag, household):
                return None
        panel = self._fall(Ok())
        self.assertIn("Notification sent to caregiver", panel)
        self.assertNotIn("Notification failed", panel)
        self.assertNotIn("imulated", panel)
        self.assertNotIn("ispatched", panel)

    def test_failure_shows_notification_failed(self):
        class Down:
            def send(self, flag, household):
                raise ConnectionRefusedError("nope")
        panel = self._fall(Down())
        self.assertIn("Notification failed", panel)
        self.assertNotIn("Notification sent", panel)

    def test_hosted_default_constructs_no_sender(self):
        import notify
        env = {"FY_NOTIFY_CHANNEL": "smtp", "FY_NOTIFY_TO": "x@example.com",
               "FY_NOTIFY_SMTP_HOST": "smtp.example.com", "SPACE_ID": "user/space"}
        with patch.dict(os.environ, env), patch("smtplib.SMTP") as smtp, \
             patch("smtplib.SMTP_SSL") as ssl, patch("urllib.request.urlopen") as urlopen:
            self.assertIsInstance(notify.get_notifier(), notify.NullNotifier)
            panel = self._fall_real_env()
        smtp.assert_not_called(); ssl.assert_not_called(); urlopen.assert_not_called()
        self.assertNotIn("Notification sent", panel)
        self.assertIn(webapp.SIMULATED_ALERT_STATUS, panel)

    def _fall_real_env(self):
        session_id, _ = webapp.init_session()
        said = "I fell down earlier and I'm scared"
        with patch.object(webapp.hear, "transcribe", return_value=(said, {"wpm": 0.0, "avg_pause_s": 0.0})):
            webapp.run_demo_turn(FAKE_UPLOAD, [], session_id)
        return webapp._format_caregiver_panel(session_id)


if __name__ == "__main__":

    unittest.main()
