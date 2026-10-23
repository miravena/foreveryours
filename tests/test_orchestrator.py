"""Tests for the end-to-end Orchestrator turn flow and offline degradation."""
import tempfile
import threading
import re
import unittest
from pathlib import Path

from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline.nebius_client import NebiusNotConfigured
from safety import fastpath
from pipeline import orchestrator
from pipeline.orchestrator import FALLBACK_REPLY_1, FALLBACK_REPLY_2, run_turn


class TestOrchestrator(unittest.TestCase):
    def test_crisis_disclosure_line_routes_self_harm_to_988_and_physical_danger_to_911(self):
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", orchestrator.CRISIS_DISCLOSURE_LINE) if x.strip()]
        hotline = [x for x in sentences if "988" in x]
        emergency = [x for x in sentences if "911" in x]
        self.assertEqual(len(hotline), 1, sentences)
        self.assertIn("hurt yourself", hotline[0])
        self.assertNotIn("911", hotline[0])
        self.assertEqual(len(emergency), 1, sentences)
        self.assertIn("physical danger", emergency[0])
        self.assertNotIn("988", emergency[0])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.profile_id = "test_dad"
        self.store = MemoryStore(self.profile_id, self.data_dir)
        self.flags = CaregiverFlags(self.profile_id, self.data_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_offline_fastpath_turn(self):
        # A distress turn must succeed completely even without NEBIUS_API_KEY
        transcript = "I fell down earlier and I'm scared"
        result = run_turn(
            transcript=transcript,
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        )

        self.assertEqual(result.transcript, transcript)
        self.assertIn("taking this seriously", result.reply_text)
        self.assertIn("letting your family know", result.reply_text.lower())
        self.assertGreaterEqual(len(result.audio_paths), 1)
        self.assertIsNotNone(result.time_to_first_audio_s)
        self.assertIsNotNone(result.caregiver_flag)
        self.assertIn("distress", result.caregiver_flag.lower())

        # Verify caregiver flag invariant: disclosed_to_senior must be True
        flag_items = self.flags.all()
        self.assertEqual(len(flag_items), 1)
        self.assertTrue(flag_items[0].disclosed_to_senior)
        self.assertEqual(flag_items[0].severity, "distress")

    def test_on_chunk_callback_fires_per_audio_chunk(self):
        # Issue #17: run_turn must invoke on_chunk(sentence, path) for each audio
        # chunk as it is produced, so a caller can pipeline playback. Uses the
        # offline fast-path so no NEBIUS_API_KEY is needed.
        seen = []
        result = run_turn(
            transcript="I fell down earlier and I'm scared",
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
            on_chunk=lambda sentence, path: seen.append(path),
        )
        if result.background_thread is not None:
            result.background_thread.join(timeout=10)
        # The fast-path immediate reply produced at least one chunk; every chunk
        # the callback saw must be one of the turn's audio paths, in order.
        self.assertGreaterEqual(len(seen), 1)
        for path in seen:
            self.assertIn(path, result.audio_paths)
        self.assertEqual(seen, result.audio_paths[: len(seen)])

    def test_default_on_chunk_none_preserves_behavior(self):
        # Regression: omitting on_chunk (default None) must not raise and must
        # still return audio paths, exactly as before.
        result = run_turn(
            transcript="I fell down earlier and I'm scared",
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        )
        if result.background_thread is not None:
            result.background_thread.join(timeout=10)
        self.assertGreaterEqual(len(result.audio_paths), 1)

    def test_non_fastpath_without_api_key_raises_gracefully(self):
        # When no API key is configured, non-distress conversational turns
        # raise NebiusNotConfigured so caller can provide clear guidance (fail loud, never fake).
        transcript = "Tell me about Miles Davis"
        try:
            run_turn(
                transcript=transcript,
                memory_store=self.store,
                flags=self.flags,
                audio_out_dir=self.audio_dir,
                caregiver_name="Sarah",
            )
        except NebiusNotConfigured:
            # Expected when NEBIUS_API_KEY is unset
            pass
        except Exception as exc:
            # If a key happened to be set, it's a valid completion
            if "NEBIUS_API_KEY" not in str(exc):
                self.fail(f"Unexpected exception: {exc}")

    def test_caregiver_sanitizer_rewrites_first_person(self):
        from pipeline.orchestrator import _sanitize_caregiver_update

        self.assertEqual(
            _sanitize_caregiver_update("I'm dropping off groceries at 4 PM today", "Sarah"),
            "Sarah is dropping off groceries at 4 PM today",
        )
        self.assertEqual(
            _sanitize_caregiver_update("I will visit around noon", "Leo"),
            "Leo will visit around noon",
        )

    def test_emotional_intent_gates_out_schedule_updates(self):
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("I'm dropping off groceries at 4 PM today", source="caregiver_memo")
        self.store.add("Avoid talking about driving", source="caregiver_memo")

        # Distress/sadness turn: should not throw schedule updates into memory
        transcript = "I fell down earlier and I'm scared"
        res = run_turn(
            transcript=transcript,
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        )
        for mem in res.memories_used:
            self.assertNotIn("groceries", mem.lower())
            self.assertNotIn("4 pm", mem.lower())
        if res.background_thread:
            res.background_thread.join(timeout=10)

    @patch("pipeline.think.stream_reply")
    def test_history_aware_anchor_rotation_suppresses_recent_anchor(self, mock_stream):
        mock_stream.return_value = iter(["Hello there."])
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")

        # Prior turn already talked about jazz
        history = [
            {"role": "user", "content": "I feel a bit down"},
            {"role": "assistant", "content": "I'm right here with you. Sometimes listening to jazz helps."},
        ]
        res = run_turn(
            transcript="I am still a bit lonely",
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
            history=history,
        )
        # Should rotate away from jazz to Leo or another unmentioned anchor
        for mem in res.memories_used:
            self.assertNotIn("jazz", mem.lower())
        if res.background_thread:
            res.background_thread.join(timeout=10)

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"])
    def test_general_appointments_question_hands_think_the_memo(self, mock_stream, mock_speak, mock_fast):
        # #189 (judge turns T09/T11): a general, plural "appointments" question
        # must reach THINK with the caregiver memo, not as a CASUAL turn with
        # no updates.
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        memo = "Dad has a check-up with Dr. Tan on Thursday at 10 AM."
        self.store.add(memo, source="caregiver_memo")
        with patch("pipeline.orchestrator.think.extract_new_memory", return_value=None):
            res = run_turn(
                "Do I have any appointments this week?",
                self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
            )
            if res.background_thread:
                res.background_thread.join(timeout=10)
        kwargs = mock_stream.call_args.kwargs
        self.assertIn(memo, kwargs["caregiver_updates"])
        self.assertEqual(kwargs["intent"], "LOGISTICAL")

    @patch("pipeline.think.stream_reply")
    def test_empty_reply_triggers_graceful_fallback(self, mock_stream):
        # When model returns empty tokens (e.g. token exhaustion during CoT),
        # orchestrator must trigger FALLBACK_REPLY_1 and synthesize audio (Zero-Silence Guarantee).
        mock_stream.return_value = iter([])  # empty completion
        transcript = "What do I have planned today?"
        res = run_turn(
            transcript=transcript,
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        )
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.reply_text, FALLBACK_REPLY_1)
        self.assertGreaterEqual(len(res.audio_paths), 1)
        self.assertEqual(res.audit_verdict, "skipped (fallback turn)")
        self.assertEqual(res.consecutive_errors, 1)

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"])
    def test_none_extraction_leaves_store_unchanged(self, mock_stream, mock_speak, mock_fast):
        # A correction/forget request offline yields None from extract_new_memory;
        # the orchestrator must then write nothing to the store.
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        self.store.add("His grandson is named Leo", source="caregiver_memo")
        before = [(i.text, i.status) if hasattr(i, "status") else i.text for i in self.store.all()]
        with patch("pipeline.orchestrator.think.extract_new_memory", return_value=None) as m:
            res = run_turn(
                "Please forget my grandson's name",
                self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
            )
            res.background_thread.join(timeout=10)
        # Other tests' leaked background threads may also hit the patch; match ours.
        self.assertIn("Please forget my grandson's name", [c.args[0] for c in m.call_args_list])
        after = [(i.text, i.status) if hasattr(i, "status") else i.text for i in self.store.all()]
        self.assertEqual(before, after)
        self.assertEqual(len(after), 1)
        self.assertIsNone(res.memory_saved)

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn")
    @patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"])
    def test_lifestyle_extraction_triggers_disclosure(self, mock_stream, mock_speak, mock_fast):
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        delivered = []
        spoken_texts = []

        def speak_side_effect(sentences, *_args, **kwargs):
            text = list(sentences)[0]
            spoken_texts.append(text)
            path = self.audio_dir / f"{len(mock_speak.call_args_list)}.wav"
            if kwargs.get("on_chunk"):
                kwargs["on_chunk"](text, path)
            return text, [path], 0.5

        mock_speak.side_effect = speak_side_effect
        
        with patch("pipeline.orchestrator.think.extract_new_memory", return_value="LIFESTYLE: SLEEP | Slept poorly due to back pain"):
            res = run_turn(
                "I barely slept last night, my back was killing me.",
                self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
                on_chunk=lambda sentence, path: delivered.append(path),
            )
            res.background_thread.join(timeout=10)
            
        # Verify the disclosure was spoken via _speak_turn
        # Note: _speak_turn is called twice (once for reply, once for disclosure)
        disclosures = [text for text in spoken_texts if "I'm making a quick note" in text]
                
        self.assertEqual(len(disclosures), 1)
        self.assertIn("Sarah", disclosures[0])
        self.assertIn("sleep", disclosures[0])
        
        # Verify it was added to memory with the LIFESTYLE scope
        items = self.store.all()
        lifestyle_items = [i for i in items if i.scope == "lifestyle"]
        self.assertEqual(len(lifestyle_items), 1)
        self.assertEqual(lifestyle_items[0].text, "Slept poorly due to back pain")
        self.assertEqual(len(delivered), 2)

    def test_run_turn_allow_hosted_call_false_skips_think(self):
        """At the daily request cap webapp passes allow_hosted_call=False.
        The offline fast-path still speaks and flags; THINK and the background
        AUDIT/extraction thread never run."""
        with patch("pipeline.think.stream_reply", side_effect=AssertionError("THINK must not be called at the cap")) as stream_mock, \
             patch("pipeline.think.extract_memory_llm", side_effect=AssertionError("no hosted background work at the cap")) as extract_mock:
            result = run_turn(
                "I fell down earlier and I'm scared",
                self.store,
                self.flags,
                self.audio_dir,
                caregiver_name="Sarah",
                allow_hosted_call=False,
            )
        stream_mock.assert_not_called()
        extract_mock.assert_not_called()
        self.assertIsNone(result.background_thread)
        self.assertIn("daily request cap", result.audit_verdict)
        self.assertTrue(result.audio_paths)
        self.assertIn("letting your family know", result.reply_text.lower())
        self.assertEqual(len(self.flags.all()), 1)
        self.assertFalse(result.is_fallback)

    def test_run_turn_allow_hosted_call_false_keeps_conflicts_pending(self):
        """A capped turn never reaches THINK, so a pending memory clarification
        must not be marked asked (Codex review)."""
        self.store.add_conflict("Leo is a grandson", "Leo is a nephew", "relationship unclear")
        with patch("pipeline.think.stream_reply", side_effect=AssertionError("THINK must not be called at the cap")):
            run_turn("I fell down earlier and I'm scared", self.store, self.flags, self.audio_dir, allow_hosted_call=False)
        self.assertEqual(len(self.store.get_pending_conflicts()), 1)

    def test_run_turn_allow_hosted_call_false_rejects_non_fast_path(self):
        """allow_hosted_call=False with nothing for the fast-path to say is a
        caller bug -- it must raise, never return a silent empty turn."""
        with patch("pipeline.think.stream_reply", side_effect=AssertionError("THINK must not be called")) as stream_mock:
            with self.assertRaises(ValueError):
                run_turn("Hello there", self.store, self.flags, self.audio_dir, allow_hosted_call=False)
        stream_mock.assert_not_called()
        self.assertEqual(self.flags.all(), [])

    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    def test_fastpath_flag_is_recorded_undisclosed_when_no_audio_is_synthesized(self, mock_speak):
        # An emergency is flagged whether or not TTS produced
        # audio; disclosed_to_senior is False because nothing was spoken.
        result = run_turn(
            "I fell down earlier and I'm scared",
            self.store,
            self.flags,
            self.audio_dir,
            caregiver_name="Sarah",
        )

        self.assertEqual(result.audio_paths, [])
        items = self.flags.all()
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].disclosed_to_senior)

    def test_fastpath_flag_is_on_disk_before_think_when_tts_hangs(self):
        # A hung in-process TTS engine is abandoned after
        # TTS_TIMEOUT_S and the undisclosed flag is already on disk when THINK
        # is entered; the immediate reply still comes back as text.
        import threading
        from unittest.mock import MagicMock

        from safety import fastpath

        release = threading.Event()
        self.addCleanup(release.set)
        engine = MagicMock()
        engine.runAndWait.side_effect = lambda: release.wait()
        seen_on_disk = []

        def think_entered(*args, **kwargs):
            seen_on_disk.extend(CaregiverFlags(self.profile_id, self.data_dir).all())
            raise NebiusNotConfigured("no key in tests")

        transcript = "I fell down earlier and I'm scared"
        with patch("pipeline.speak.TTS_TIMEOUT_S", 0.05), \
             patch("sys.platform", "linux"), \
             patch("pipeline.speak._get_piper_cli", return_value=None), \
             patch("pipeline.speak._get_espeak_cli", return_value=None), \
             patch("pipeline.speak._get_tts_engine", return_value=engine), \
             patch("pipeline.think.stream_reply", side_effect=think_entered):
            result = run_turn(transcript, self.store, self.flags, self.audio_dir, caregiver_name="Sarah")

        self.assertEqual(len(seen_on_disk), 1)
        self.assertFalse(seen_on_disk[0].disclosed_to_senior)
        self.assertEqual(result.audio_paths, [])
        self.assertIn(fastpath.check(transcript).immediate_reply, result.reply_text)
        self.assertEqual(len(self.flags.all()), 1)

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.think.stream_reply", return_value=["Reply"])
    def test_lifestyle_note_is_not_saved_without_delivered_disclosure(
        self, mock_stream, mock_speak, mock_fast
    ):
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)

        with patch(
            "pipeline.orchestrator.think.extract_new_memory",
            return_value="LIFESTYLE: SLEEP | Slept poorly",
        ):
            result = run_turn(
                "I barely slept last night.",
                self.store,
                self.flags,
                self.audio_dir,
                caregiver_name="Sarah",
            )
            result.background_thread.join(timeout=10)

        self.assertFalse(any(item.scope == "lifestyle" for item in self.store.all()))
        self.assertIn("Suppressed Lifestyle", result.memory_saved or "")

    @patch("pipeline.orchestrator.audit.audit_reply", return_value=("DISTRESS", "fell"))
    @patch("pipeline.orchestrator._speak_turn", side_effect=[
        ("Reply", [Path("reply.wav")], 0.5),
        ("I want to let Sarah know about something I just said.", [], None),
    ])
    @patch("pipeline.think.stream_reply", return_value=["Reply"])
    def test_audit_flag_stays_undisclosed_until_audio_is_delivered(
        self, mock_stream, mock_speak, mock_audit
    ):
        result = run_turn(
            "I feel unwell",
            self.store,
            self.flags,
            self.audio_dir,
            caregiver_name="Sarah",
        )
        result.background_thread.join(timeout=10)

        self.assertEqual(len(self.flags.all()), 1)
        self.assertFalse(self.flags.all()[0].disclosed_to_senior)

    def test_audit_flag_does_not_copy_verdict(self):
        # The AUDIT model's one-sentence reason must never reach the
        # caregiver panel. The flag says WHAT KIND of event happened, never
        # what the senior said or what the auditor wrote about it -- a reason
        # can carry health details, names or a bank PIN.
        from safety import fastpath

        verdict_text = "DISTRESS Senior said she fell and mentioned her bank PIN 1234"
        cases = [
            ("CRISIS", "crisis", "audit_crisis"),
            ("DISTRESS", "distress", "audit_distress"),
            ("UNSAFE", "audit", "audit_unsafe"),
        ]
        transcript = "I feel unwell"
        # The turn must NOT take the fast path, or the AUDIT branch never runs.
        self.assertFalse(fastpath.check(transcript).triggered)

        for status, severity, key in cases:
            with self.subTest(status=status):
                data_dir = Path(self.temp_dir.name) / status
                data_dir.mkdir(parents=True, exist_ok=True)
                audio_dir = Path(self.temp_dir.name) / f"audio-{status}"
                audio_dir.mkdir(parents=True, exist_ok=True)
                store = MemoryStore(self.profile_id, data_dir)
                flags = CaregiverFlags(self.profile_id, data_dir)

                with patch("pipeline.audit.audit_reply", return_value=(status, verdict_text)), \
                     patch("pipeline.orchestrator._speak_turn",
                           return_value=("Reply", [Path("reply.wav")], 0.5)), \
                     patch("pipeline.think.stream_reply", return_value=["Reply"]):
                    result = run_turn(
                        transcript=transcript,
                        memory_store=store,
                        flags=flags,
                        audio_out_dir=audio_dir,
                        caregiver_name="Sarah",
                    )
                    result.background_thread.join(timeout=10)

                flag_items = flags.all()
                # Exactly one flag per audited turn.
                self.assertEqual(len(flag_items), 1)
                flag = flag_items[0]
                self.assertEqual(flag.severity, severity)
                # The leak checks come FIRST so a regression fails on the leak
                # itself, not on a missing constant.
                self.assertNotIn("1234", flag.text)
                self.assertNotIn("PIN", flag.text)
                self.assertNotIn(verdict_text, flag.text)
                # ... and the flag is exactly the fixed text for this category.
                self.assertEqual(flag.text, fastpath.CAREGIVER_FLAG_TEXT[key])
                # The raw verdict still rides on the dev/biomarker surface.
                self.assertEqual(result.audit_verdict, verdict_text)

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [Path("reply.wav")], 0.5))
    @patch("pipeline.think.stream_reply", return_value=["Reply"])
    def test_quiet_mode_blocks_proactive_perseveration_before_flagging(
        self, mock_stream, mock_speak, mock_fast
    ):
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        self.store.set_quiet_mode(hours=4)
        history = [
            {"role": "user", "content": "What time is Sarah coming?"},
            {"role": "assistant", "content": "At 4 PM."},
            {"role": "user", "content": "When is Sarah visiting?"},
            {"role": "assistant", "content": "At 4 PM."},
        ]

        result = run_turn(
            "[PROACTIVE_TRIGGER]",
            self.store,
            self.flags,
            self.audio_dir,
            caregiver_name="Sarah",
            history=history,
            is_proactive=True,
        )

        self.assertTrue(result.is_fallback)
        self.assertEqual(self.flags.all(), [])

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"])
    def test_quiet_mode_hour_parsing(self, mock_stream, mock_speak, mock_fast):
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        
        # Test "8-10" becomes 10 (not 810)
        with patch("pipeline.orchestrator.think.extract_new_memory", return_value="QUIET_MODE: 8-10"):
            res = run_turn("I want to rest for 8-10 hours", self.store, self.flags, self.audio_dir, caregiver_name="Sarah")
            res.background_thread.join(timeout=10)
        self.assertIn("Activated Quiet Mode (10.0 hours)", res.memory_saved)

        # Test absurd value clamped to 24
        with patch("pipeline.orchestrator.think.extract_new_memory", return_value="QUIET_MODE: 1000"):
            res = run_turn("Sleep forever", self.store, self.flags, self.audio_dir, caregiver_name="Sarah")
            res.background_thread.join(timeout=10)
        self.assertIn("Activated Quiet Mode (24.0 hours)", res.memory_saved)
        
        # Test missing value uses default 4.0
        with patch("pipeline.orchestrator.think.extract_new_memory", return_value="QUIET_MODE: I am tired"):
            res = run_turn("I am tired", self.store, self.flags, self.audio_dir, caregiver_name="Sarah")
            res.background_thread.join(timeout=10)
        self.assertIn("Activated Quiet Mode (4.0 hours)", res.memory_saved)

    def test_quiet_mode_offline_suppression_and_breakthrough(self):
        # Activate quiet mode
        self.store.set_quiet_mode(hours=4.0)
        self.assertTrue(self.store.is_quiet_mode_active())
        
        # Proactive turn should be blocked
        res1 = run_turn("[PROACTIVE_TRIGGER]", self.store, self.flags, self.audio_dir, caregiver_name="Sarah", is_proactive=True)
        self.assertEqual(res1.audit_verdict, "Blocked by Quiet Mode")
        self.assertEqual(res1.audio_paths, [])
        self.assertEqual(res1.reply_text, "[Proactive turn suppressed by policy: Blocked by Quiet Mode]")
        self.assertTrue(res1.is_fallback)
        
        # Add a non-urgent schedule update
        self.store.add("Sarah is coming at 4 PM", source="caregiver_memo")
        res2 = run_turn("[PROACTIVE_TRIGGER]", self.store, self.flags, self.audio_dir, caregiver_name="Sarah", is_proactive=True)
        self.assertEqual(res2.audit_verdict, "Blocked by Quiet Mode")
        self.assertTrue(res2.is_fallback)
        
        # Add an [URGENT] schedule update
        self.store.add("[URGENT] Sarah is in the ER today", source="caregiver_memo")
        with patch("pipeline.orchestrator.think.stream_reply", return_value=["Oh no!"]):
            res3 = run_turn("[PROACTIVE_TRIGGER]", self.store, self.flags, self.audio_dir, caregiver_name="Sarah", is_proactive=True)
            
        self.assertNotEqual(res3.audit_verdict, "Blocked by Quiet Mode")
        self.assertIn("share something urgent", res3.reply_text)
        # Should only include the urgent update
        self.assertEqual(res3.memories_used, ["[URGENT] Sarah is in the ER today"])
        
        if res3.background_thread:
            res3.background_thread.join(timeout=10)

    @patch("pipeline.think.stream_reply")
    def test_progressive_circuit_breaker_on_consecutive_errors(self, mock_stream):
        # On 2nd consecutive error, circuit breaker trips: does NOT ask Dad to repeat!
        mock_stream.return_value = iter([])
        transcript = "What do I have planned today?"
        res = run_turn(
            transcript=transcript,
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
            consecutive_errors=1,
        )
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.reply_text, FALLBACK_REPLY_2)
        self.assertNotIn("say that one more time", res.reply_text)
        self.assertIn("trouble with my connection", res.reply_text)
        self.assertEqual(res.consecutive_errors, 2)

    @patch("pipeline.think.stream_reply")
    def test_network_exception_triggers_graceful_fallback(self, mock_stream):
        # When a network connection drops mid-turn, graceful fallback speaks to Dad
        mock_stream.side_effect = RuntimeError("Connection dropped")
        transcript = "How are you doing today?"
        res = run_turn(
            transcript=transcript,
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        )
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.reply_text, FALLBACK_REPLY_1)
        self.assertGreaterEqual(len(res.audio_paths), 1)

    @patch("pipeline.think.stream_reply")
    def test_zero_memory_default_on_factual_and_greetings(self, mock_stream):
        mock_stream.return_value = iter(["Hello, hope you have a great day!"])
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")
        self.store.add("Senior used to teach children", source="caregiver_memo")
        self.store.add("Sarah is dropping off groceries at 4 PM today", source="caregiver_memo")

        factual_queries = [
            "Good morning.",
            "What's 25 plus 17?",
            "Tell me a joke.",
            "What is the capital of France?",
            "How does rain form?",
        ]
        for query in factual_queries:
            with self.subTest(query=query):
                res = run_turn(
                    transcript=query,
                    memory_store=self.store,
                    flags=self.flags,
                    audio_out_dir=self.audio_dir,
                    caregiver_name="Sarah",
                )
                self.assertEqual(res.memories_used, [], f"Expected zero memories on factual query '{query}', got {res.memories_used}")

    @patch("pipeline.think.stream_reply")
    def test_zero_memory_allows_relevant_anchor(self, mock_stream):
        mock_stream.return_value = iter(["Jazz has such a comforting rhythm."])
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")

        res = run_turn(
            transcript="I was listening to some jazz earlier today.",
            memory_store=self.store,
            flags=self.flags,
            audio_out_dir=self.audio_dir,
            caregiver_name="Sarah",
        )
        self.assertEqual(len(res.memories_used), 1)
        self.assertIn("jazz", res.memories_used[0].lower())
        if res.background_thread:
            res.background_thread.join()

    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"])
    def test_perseveration_tracking_flags_loop(self, mock_stream, mock_speak, mock_fast):
        from safety.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        mock_speak.return_value = ("Reply", [self.audio_dir / "reply.wav"], 0.5)
        # Fixes #139: a repeat now also needs a 'ts' inside PERSEVERATION_WINDOW_S
        # on each prior entry (webapp.py adds this when it appends a user turn).
        import time as _time
        now = _time.time()
        history = [
            {"role": "user", "content": "What time is Sarah coming?", "ts": now - 600},
            {"role": "assistant", "content": "Sarah is coming at 4 PM."},
            {"role": "user", "content": "What time is Sarah coming?", "ts": now - 300},
            {"role": "assistant", "content": "She's visiting at 4 PM today."},
        ]
        # The 3rd time
        result = run_turn(
            "What time is Sarah coming?",
            self.store, 
            self.flags, 
            self.audio_dir, 
            history=history
        )
        if result.background_thread:
            result.background_thread.join(timeout=10)
        flag_items = self.flags.all()
        # Fixes #159: the flag text now describes the repeated QUESTION (per
        # the ticket's RULE #4: "Perseveration: the senior asked the same
        # question 3 times within N minutes."), not the old intent-only
        # wording -- this is a required, deliberate text change, not scope
        # creep; the "Perseveration" substring (and disclosed_to_senior)
        # checks below are the same assertions as before, applied to it.
        self.assertTrue(any("Perseveration" in f.text for f in flag_items))

        persev_flag = next(f for f in flag_items if "Perseveration" in f.text)
        self.assertTrue(persev_flag.disclosed_to_senior)
        
        # Verify the continuation note was passed to stream_reply
        call_args = mock_stream.call_args
        self.assertIn("Answer them gently and concisely", call_args.args[0])


class TestDrivingAlternative(unittest.TestCase):
    """#192: a driving-intent reply always offers an alternative to driving."""

    def _run(self, transcript, reply):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "audio").mkdir()
            store = MemoryStore("p", d)
            flags = CaregiverFlags("p", d)
            with patch("pipeline.think.stream_reply", return_value=iter([reply])), \
                 patch("pipeline.think.extract_new_memory", return_value=None):
                res = run_turn(transcript, store, flags, d / "audio", caregiver_name="Sarah")
                if res.background_thread:
                    res.background_thread.join(timeout=10)
            return res.reply_text

    def test_declining_reply_gets_alternative_appended(self):
        out = self._run("I think I'll drive down to the shop myself this afternoon.",
                        "I'm glad you're feeling up to heading out. I can't drive for you, but Sarah mentioned it is best this way.")
        self.assertRegex(out, orchestrator._DRIVING_ALTERNATIVE_RE)
        self.assertIn("ask Sarah for a lift", out)

    def test_reply_with_alternative_is_untouched(self):
        reply = "Shall we ask Sarah for a lift instead?"
        self.assertEqual(self._run("I'll drive to the shop.", reply), reply)

    def test_non_driving_turn_is_untouched(self):
        reply = "That sounds like a good plan."
        self.assertEqual(self._run("Alright, I'll wait for Sarah then.", reply), reply)

    def test_intent_regex(self):
        for t in ("I think I'll drive down to the shop myself this afternoon.", "I'm going to drive to the bank"):
            self.assertTrue(orchestrator._DRIVING_INTENT_RE.search(t), t)
        for t in ("Alright, I'll wait for Sarah then.", "Dad used to drive a truck"):
            self.assertFalse(orchestrator._DRIVING_INTENT_RE.search(t), t)

    def test_past_or_negated_driving_is_untouched(self):
        reply = "You must miss those days on the road."
        for t in ("I used to drive a truck for forty years.", "I don't drive anymore, I gave it up."):
            self.assertEqual(self._run(t, reply), reply, t)


if __name__ == "__main__":
    unittest.main()


class _RecordingNotifier:
    def __init__(self, error=None):
        self.error, self.sent = error, []

    def send(self, flag, household):
        self.sent.append((flag.severity, flag.text, flag.disclosed_to_senior))
        if self.error:
            raise self.error


class TestOutboundNotification(unittest.TestCase):
    """#201: one notification per flag, after it is persisted, off by default."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        self.data_dir.mkdir(parents=True)
        self.audio_dir.mkdir(parents=True)
        self.profile_id = "test_dad"
        self.store = MemoryStore(self.profile_id, self.data_dir)
        self.flags = CaregiverFlags(self.profile_id, self.data_dir)

    def _fast(self, notifier):
        with patch("notify.get_notifier", return_value=notifier):
            result = run_turn("I fell down earlier and I'm scared", self.store, self.flags,
                              self.audio_dir, caregiver_name="Sarah")
            for t in result.notify_threads:
                t.join(timeout=10)
        return result

    def test_fastpath_flag_is_notified_once_and_recorded(self):
        n = _RecordingNotifier()
        self._fast(n)
        self.assertEqual(len(n.sent), 1)
        self.assertEqual(n.sent[0][0], "distress")
        stored = CaregiverFlags(self.profile_id, self.data_dir).all()
        self.assertEqual(len(stored), 1)
        self.assertIs(stored[0].notified, True)

    def test_fastpath_send_failure_is_recorded_not_raised(self):
        self._fast(_RecordingNotifier(error=TimeoutError("secret detail")))
        stored = CaregiverFlags(self.profile_id, self.data_dir).all()[0]
        self.assertIs(stored.notified, False)
        self.assertEqual(stored.notify_error, "TimeoutError")

    def test_off_by_default_leaves_the_flag_file_unchanged(self):
        import notify
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(notify.get_notifier(), notify.NullNotifier)
            result = run_turn("I fell down earlier and I'm scared", self.store, self.flags,
                              self.audio_dir, caregiver_name="Sarah")
        self.assertIsNone(result.background_thread)
        self.assertNotIn("notif", self.flags.path.read_text())

    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [Path("reply.wav")], 0.5))
    @patch("pipeline.think.stream_reply", return_value=["Reply"])
    def test_audit_flag_is_notified(self, mock_stream, mock_speak):
        n = _RecordingNotifier()
        with patch("pipeline.audit.audit_reply", return_value=("CRISIS", "x")), \
             patch("notify.get_notifier", return_value=n):
            result = run_turn("I feel unwell", self.store, self.flags, self.audio_dir, caregiver_name="Sarah")
            result.background_thread.join(timeout=10)
            for t in result.notify_threads:
                t.join(timeout=10)
        self.assertEqual([x[0] for x in n.sent], ["crisis"])
        self.assertIs(CaregiverFlags(self.profile_id, self.data_dir).all()[0].notified, True)

    def test_fastpath_without_a_streaming_consumer_is_not_attested_as_told(self):
        import notify
        seen = []

        class Spy:
            def send(self, flag, household):
                seen.append(notify.build_message(flag, "h").body)

        self._fast(Spy())
        # Synthesized audio but no on_chunk consumer: delivery is unattested.
        self.assertIn("Senior told: not yet confirmed", seen[0])
        self.assertTrue(CaregiverFlags(self.profile_id, self.data_dir).all()[0].disclosed_to_senior)

    def test_fastpath_with_an_accepting_consumer_is_attested_as_told(self):
        import notify
        seen = []

        class Spy:
            def send(self, flag, household):
                seen.append(notify.build_message(flag, "h").body)

        with patch("notify.get_notifier", return_value=Spy()):
            result = run_turn("I fell down earlier and I'm scared", self.store, self.flags,
                              self.audio_dir, caregiver_name="Sarah", on_chunk=lambda s, p: None)
            for t in result.notify_threads:
                t.join(timeout=10)
        self.assertIn("Senior told: yes", seen[0])

    def test_fastpath_with_a_refusing_consumer_is_not_attested(self):
        import notify
        seen = []

        class Spy:
            def send(self, flag, household):
                seen.append(notify.build_message(flag, "h").body)

        with patch("notify.get_notifier", return_value=Spy()):
            result = run_turn("I fell down earlier and I'm scared", self.store, self.flags,
                              self.audio_dir, caregiver_name="Sarah", on_chunk=lambda s, p: False)
            for t in result.notify_threads:
                t.join(timeout=10)
        self.assertIn("not yet confirmed", seen[0])

    def test_slow_notifier_does_not_delay_the_turn_or_its_background_thread(self):
        import time as _time
        release = threading.Event()

        class Slow:
            def send(self, flag, household):
                release.wait(30)

        with patch("notify.get_notifier", return_value=Slow()):
            t0 = _time.monotonic()
            result = run_turn("I fell down earlier and I'm scared", self.store, self.flags,
                              self.audio_dir, caregiver_name="Sarah")
            self.assertLess(_time.monotonic() - t0, 5)
            self.assertIsNone(result.background_thread)  # nothing the next turn would join
            self.assertEqual(len(result.notify_threads), 1)
        release.set()
        for t in result.notify_threads:
            t.join(timeout=10)

    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [Path("reply.wav")], 0.5))
    @patch("pipeline.think.stream_reply", return_value=["Reply"])
    def test_audit_background_thread_does_not_wait_for_a_slow_send(self, mock_stream, mock_speak):
        import time as _time
        release = threading.Event()

        class Slow:
            def send(self, flag, household):
                release.wait(30)

        with patch("pipeline.audit.audit_reply", return_value=("DISTRESS", "x")), \
             patch("notify.get_notifier", return_value=Slow()):
            result = run_turn("I feel unwell", self.store, self.flags, self.audio_dir, caregiver_name="Sarah")
            t0 = _time.monotonic()
            result.background_thread.join(timeout=10)
            self.assertFalse(result.background_thread.is_alive())
            self.assertLess(_time.monotonic() - t0, 5)
        release.set()
        for t in result.notify_threads:
            t.join(timeout=10)

    def test_send_past_the_deadline_is_recorded_as_a_failure(self):
        release = threading.Event()

        class Hung:
            def send(self, flag, household):
                release.wait(30)

        flag = self.flags.add("x", severity="distress", disclosed_to_senior=True)
        with patch("pipeline.orchestrator.NOTIFY_DEADLINE_S", 0.2):
            orchestrator._notify_flag(self.flags, flag, Hung())
        release.set()
        stored = CaregiverFlags(self.profile_id, self.data_dir).all()[0]
        self.assertIs(stored.notified, False)
        self.assertEqual(stored.notify_error, "TimeoutError")

    def test_message_never_carries_the_transcript(self):
        import notify
        captured = []

        class Spy:
            def send(self, flag, household):
                captured.append(notify.build_message(flag, "h").body)

        self._fast(Spy())
        self.assertEqual(len(captured), 1)
        for fragment in ("fell down", "scared", "earlier"):
            self.assertNotIn(fragment, captured[0].lower())


class TestCrisisCarryAndOne988(unittest.TestCase):
    """#199 / #191: a backstop CRISIS verdict is carried into the next turn and
    the 988 line is given once across the turns, never twice in one reply."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.data_dir = root / "data"
        self.audio_dir = root / "audio"
        self.data_dir.mkdir()
        self.audio_dir.mkdir()
        self.store = MemoryStore("t199", self.data_dir)
        self.flags = CaregiverFlags("t199", self.data_dir)
        self.spoken = []

        def fake_speak_turn(sentences, audio_out_dir, on_chunk=None):
            # Deliver each chunk through on_chunk like the real _speak_turn;
            # only chunks the consumer accepted count as spoken (heard).
            parts = list(sentences)
            for part in parts:
                ack = on_chunk(part, Path("x.wav")) if on_chunk is not None else None
                if ack is not False:
                    self.spoken.append(part)
            return " ".join(parts), [Path("x.wav")], 0.1

        patcher = patch("pipeline.orchestrator._speak_turn", side_effect=fake_speak_turn)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _turn(self, transcript, think_sentences, audit=("SAFE", "ok"), accept=True):
        captured = {}

        def fake_stream(think_input, *a, **k):
            captured["think_input"] = think_input
            return iter(think_sentences)

        with patch("pipeline.think.stream_reply", side_effect=fake_stream), \
             patch("pipeline.think.sentence_chunks", side_effect=lambda it: it), \
             patch("pipeline.audit.audit_reply", return_value=audit), \
             patch("pipeline.think.extract_new_memory", return_value=None):
            result = run_turn(
                transcript, self.store, self.flags, self.audio_dir, caregiver_name="Sarah",
                on_chunk=(lambda s, p: True) if accept else None,
            )
            if result.background_thread is not None:
                result.background_thread.join(timeout=10)
        return result, captured

    def test_backstop_crisis_then_neutral_turn_gives_988_once(self):
        crisis_text = "I have said my goodbyes."
        self.assertFalse(fastpath.check(crisis_text).triggered)
        r1, _ = self._turn(crisis_text, ["That sounds heavy."], audit=("CRISIS", "plan"))
        r2, cap2 = self._turn(
            "What is the weather like?",
            ["I am here with you.", "You can call 988 any time.", "Shall we have some tea?"],
        )
        all_spoken = " ".join(self.spoken)
        self.assertEqual(all_spoken.count("988"), 1, all_spoken)
        self.assertNotIn("988", r2.reply_text)
        self.assertIn("Shall we have some tea?", r2.reply_text)
        # THINK was told the 988 line and the family notice were already given.
        self.assertIn("already", cap2["think_input"])
        self.assertIn("do not mention 988", cap2["think_input"].lower())

    def test_marker_is_one_turn_only(self):
        self._turn("I have said my goodbyes.", ["That sounds heavy."], audit=("CRISIS", "plan"))
        self._turn("What is the weather like?", ["Mild today."])
        _, cap3 = self._turn("And tomorrow?", ["Mild again."])
        self.assertNotIn("audit flagged", cap3["think_input"])

    def test_undelivered_disclosure_lets_next_turn_offer_988_once(self):
        # No on_chunk consumer: the disclosure line is never attested as heard.
        self._turn("I have said my goodbyes.", ["That sounds heavy."], audit=("CRISIS", "plan"), accept=False)
        r2, cap2 = self._turn(
            "What is the weather like?",
            ["Please call or text 988.", "Also, you can call 988 any time."],
        )
        self.assertIn("exactly once", cap2["think_input"])
        self.assertIn("family", cap2["think_input"])
        self.assertEqual(r2.reply_text.count("988"), 1, r2.reply_text)

    def test_fastpath_crisis_reply_never_repeats_988_from_think(self):
        # #191: the canned fast-path line carries 988; THINK must not add a second.
        r, _ = self._turn(
            "Sometimes I feel like everyone would be better off without me.",
            ["I am so glad you told me.", "Please do call 988 tonight.", "I am here."],
        )
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)
        self.assertIn("I am here.", r.reply_text)

    def test_fastpath_crisis_continuation_never_repeats_hotline_or_apology(self):
        # Live judge run: THINK's continuation repeated "Please call or text 988"
        # and the apology after the canned fast-path line. The orchestrator drops
        # both before they are spoken; the fast-path line keeps its own.
        r, cap = self._turn(
            "I want to die",
            [
                "I am so sorry you are feeling this way.",
                "Please call or text 988 to speak with someone who can help right now.",
                "I'm right here with you.",
                "Would you tell me what has been weighing on you?",
            ],
        )
        fast = fastpath.check("I want to die")
        self.assertTrue(r.reply_text.startswith(fast.immediate_reply), r.reply_text)
        continuation = r.reply_text[len(fast.immediate_reply):]
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)
        self.assertEqual(r.reply_text.lower().count("sorry"), 1, r.reply_text)
        self.assertNotIn("988", continuation)
        self.assertNotIn("sorry", continuation.lower())
        self.assertIn("I'm right here with you.", continuation)
        self.assertIn("weighing on you", continuation)
        # Nothing spoken repeats them either.
        spoken = " ".join(self.spoken)
        self.assertEqual(spoken.count("988"), 1, self.spoken)
        self.assertEqual(spoken.lower().count("sorry"), 1, self.spoken)
        # The prompt rule rides along with the note.
        self.assertIn("do NOT apologize or say sorry again", cap["think_input"])

    def test_fastpath_crisis_continuation_of_only_repeats_gets_a_gentle_line(self):
        r, _ = self._turn(
            "I want to die",
            ["I'm so sorry.", "Please call or text 988."],
        )
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)
        self.assertEqual(r.reply_text.lower().count("sorry"), 1, r.reply_text)
        self.assertIn("I'm here with you.", r.reply_text)

    def test_apology_clause_removed_but_safety_advice_in_the_sentence_kept(self):
        r, _ = self._turn(
            "I want to die",
            ["You don't need to apologize; please put the pills down and move away from them."],
        )
        self.assertIn("Please put the pills down and move away from them.", r.reply_text)
        self.assertNotIn("apologize", r.reply_text)

    def test_fastpath_audio_failed_think_988_survives_its_apology_clause(self):
        # The canned line was not spoken, so THINK's 988 is the only spoken one:
        # removing the apology must not take the hotline with it.
        fast = fastpath.check("I want to die")

        def speak(sentences, audio_out_dir, on_chunk=None):
            parts = list(sentences)
            if parts == [fast.immediate_reply]:
                raise RuntimeError("tts down")
            for part in parts:
                self.spoken.append(part)
            return " ".join(parts), [Path("x.wav")], 0.1

        with patch("pipeline.orchestrator._speak_turn", side_effect=speak):
            r, cap = self._turn("I want to die", ["I'm sorry you're hurting; please call or text 988 now."])
        self.assertEqual(self.spoken, ["Please call or text 988 now."])
        self.assertNotIn("sorry", " ".join(self.spoken).lower())
        # THINK is told its 988 is needed, overriding the "already given" note.
        self.assertIn(orchestrator.CRISIS_FASTPATH_AUDIO_FAILED_NOTE, cap["think_input"])

    def test_spoken_fastpath_crisis_line_sends_no_audio_failed_note(self):
        _, cap = self._turn("I want to die", ["I'm right here with you."])
        self.assertNotIn(orchestrator.CRISIS_FASTPATH_AUDIO_FAILED_NOTE, cap["think_input"])

    def test_strip_apology_never_loses_a_safety_instruction(self):
        cases = {
            "I'm sorry, call 911.": "Call 911.",
            "I'm sorry, don't jump!": "Don't jump!",
            "I'm sorry, don't overdose.": "Don't overdose.",
            "I'm so sorry, stop!": "Stop!",
            "I'm so sorry, dear.": "",
            "I'm sorry you're hurting\u2014don't jump.": "Don't jump.",
            "I'm sorry you're hurting don't jump.": "I'm sorry you're hurting don't jump.",
            "I am so sorry you are feeling this way.": "",
            "I'm sorry to hear that, but I'm right here.": "I'm right here.",
            "I'm sorry you're hurting but please put the pills down and move away from them.":
                "Please put the pills down and move away from them.",
            "Sorry - if you are in danger call 911 right now!": "If you are in danger call 911 right now!",
            "I'm sorry, but I'm right here with you.": "I'm right here with you.",
            "I am so sorry you are feeling this way, Dad.": "",
            "I'm so sorry.": "",
            # A safety word only inside the apology clause: keep the sentence whole.
            "I'm so sorry you're in danger.": "I'm so sorry you're in danger.",
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence):
                self.assertEqual(orchestrator._strip_apology(sentence), expected)

    def test_apology_kept_outside_a_fastpath_crisis_turn(self):
        r, _ = self._turn("Tell me about jazz", ["Sorry, I missed that.", "Jazz is lovely."])
        self.assertIn("Sorry, I missed that.", r.reply_text)

    def test_audit_disclosure_skips_988_when_the_reply_already_gave_it(self):
        r1, _ = self._turn(
            "I have said my goodbyes.", ["Please call or text 988 right now."], audit=("CRISIS", "plan")
        )
        self.assertEqual(" ".join(self.spoken).count("988"), 1, self.spoken)
        self.assertTrue(any("letting Sarah know" in s for s in self.spoken))

    def test_reply_988_without_attested_delivery_is_not_carried_as_given(self):
        # Codex review: a generated 988 the consumer never accepted is no evidence.
        self._turn("I have said my goodbyes.", ["Please call or text 988."],
                   audit=("CRISIS", "plan"), accept=False)
        _, cap2 = self._turn("What is the weather like?", ["Mild today."])
        self.assertIn("exactly once", cap2["think_input"])

    def test_refused_988_chunk_is_not_recorded_as_heard(self):
        # Final Codex review (P1): THINK's 988 sentence is refused by the
        # consumer while the disclosure is accepted. The 988 was never heard,
        # so the disclosure must give it and the carry must not suppress it.
        def selective(sentence, path):
            return "988" not in sentence or "letting" in sentence
        captured = {}
        def fake_stream(think_input, *a, **k):
            return iter(["Please call or text 988 right now."])
        with patch("pipeline.think.stream_reply", side_effect=fake_stream), \
             patch("pipeline.think.sentence_chunks", side_effect=lambda it: it), \
             patch("pipeline.audit.audit_reply", return_value=("CRISIS", "plan")), \
             patch("pipeline.think.extract_new_memory", return_value=None):
            r = run_turn("I have said my goodbyes.", self.store, self.flags, self.audio_dir,
                         caregiver_name="Sarah", on_chunk=selective)
            if r.background_thread is not None:
                r.background_thread.join(timeout=10)
        disclosure = [s for s in self.spoken if "letting Sarah know" in s]
        self.assertTrue(disclosure)
        self.assertIn("988", disclosure[0])
        # The 988 was heard through the accepted disclosure, so the carry now
        # (correctly) records it as given.
        _, cap2 = self._turn("What is the weather like?", ["Mild today."])
        self.assertIn("do not mention 988", cap2["think_input"].lower())

    def test_unrelated_refused_chunk_does_not_unhear_an_accepted_988(self):
        # Codex P2 on the fix: only the 988 chunk's own acceptance matters.
        def selective(sentence, path):
            return "tea" not in sentence
        with patch("pipeline.think.stream_reply",
                   side_effect=lambda *a, **k: iter(["Please call 988.", "Shall we have tea?"])), \
             patch("pipeline.think.sentence_chunks", side_effect=lambda it: it), \
             patch("pipeline.audit.audit_reply", return_value=("CRISIS", "plan")), \
             patch("pipeline.think.extract_new_memory", return_value=None):
            r = run_turn("I have said my goodbyes.", self.store, self.flags, self.audio_dir,
                         caregiver_name="Sarah", on_chunk=selective)
            if r.background_thread is not None:
                r.background_thread.join(timeout=10)
        self.assertEqual(" ".join(self.spoken).count("988"), 1, self.spoken)

    def test_consecutive_backstop_crises_give_988_once(self):
        # Final Codex review (P2): a second CRISIS verdict right after an
        # attested one must not add 988 again in its disclosure.
        self._turn("I have said my goodbyes.", ["That sounds heavy."], audit=("CRISIS", "plan"))
        self._turn("I just want everything to stop.", ["I am here with you."], audit=("CRISIS", "plan"))
        all_spoken = " ".join(self.spoken)
        self.assertEqual(all_spoken.count("988"), 1, all_spoken)
        _, cap3 = self._turn("Are you still there?", ["I am."])
        self.assertIn("do not mention 988", cap3["think_input"].lower())

    def test_two_mentions_in_one_allowed_sentence_become_one(self):
        r, _ = self._turn("I feel low today.", ["Call 988 now, or text 988 if talking is hard."])
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)

    def test_fastpath_line_never_spoken_leaves_think_free_to_say_988(self):
        # Review: budget 0 only when the canned crisis line was actually spoken.
        calls = {"n": 0}

        def flaky(sentences, audio_out_dir, on_chunk=None):
            parts = list(sentences)
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("tts down")
            return " ".join(parts), [Path("x.wav")], 0.1

        with patch("pipeline.orchestrator._speak_turn", side_effect=flaky):
            r, _ = self._turn("I want to die.", ["Please call 988 now."])
        self.assertIn("Please call 988 now.", r.reply_text)

    def test_carry_survives_a_failed_think_turn(self):
        self._turn("I have said my goodbyes.", ["That sounds heavy."], audit=("CRISIS", "plan"), accept=False)
        with patch("pipeline.think.stream_reply", side_effect=RuntimeError("boom")):
            r2 = run_turn("What is the weather like?", self.store, self.flags, self.audio_dir, caregiver_name="Sarah")
        self.assertTrue(r2.is_fallback)
        _, cap3 = self._turn("Hello again", ["Hello."])
        self.assertIn("exactly once", cap3["think_input"])

    def test_reply_that_is_only_the_repeated_988_gets_a_crisis_aware_line(self):
        self._turn("I have said my goodbyes.", ["That sounds heavy."], audit=("CRISIS", "plan"))
        r2, _ = self._turn("What is the weather like?", ["Please call 988 now."])
        self.assertFalse(r2.is_fallback)
        self.assertIn("How are you feeling right now?", r2.reply_text)
        self.assertNotIn("drifted", r2.reply_text)
        self.assertNotIn("988", r2.reply_text)

    def test_dropped_988_keeps_911_advice(self):
        r, _ = self._turn("I want to die.", ["If you are in danger call 911 or 988.", "I am here."])
        self.assertIn("911", r.reply_text)
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)  # the canned line only

    def test_room_and_price_numbers_are_not_the_hotline(self):
        r, _ = self._turn("I want to die.", ["Call the desk about room 988.", "It costs $988 a year."])
        self.assertIn("room 988", r.reply_text)
        self.assertIn("$988", r.reply_text)

    def test_spelled_out_hotline_counts(self):
        r, _ = self._turn("I want to die.", ["You can call nine eight eight any time.", "I am here."])
        self.assertNotIn("nine eight eight", r.reply_text)

    def test_detector_counts_any_988_unless_ruled_out(self):
        from pipeline.orchestrator import _hotline_match

        for text in ("988 is there for you.", "988 is available.", "Contact 988.", "Use 988 now.",
                     "You can also try 988.", "The number is 988.", "Nine eight eight is free.",
                     "Dial 9-8-8.", "Try 9 8 8 tonight.", "Please call or text 988."):
            with self.subTest(text=text):
                self.assertIsNotNone(_hotline_match(text))
        for text in ("Call the desk about room 988.", "It costs $988 a year.", "Up 988% on last year.",
                     "That was in the year 988.", "He walked 988 steps.", "See page 988.",
                     "Flat 988 is on the left.", "Call 19885 now."):
            with self.subTest(text=text):
                self.assertIsNone(_hotline_match(text))

    def test_context_free_988_sentences_are_given_once_end_to_end(self):
        r, _ = self._turn("I feel low today.", ["Please call 988 now.", "988 is always there for you."])
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)
        r, _ = self._turn("I want to die.", ["Try 9-8-8 tonight.", "988 is available.", "I am here."])
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)  # canned line only
        self.assertNotIn("9-8-8", r.reply_text)
        self.assertIn("I am here.", r.reply_text)

    def test_audit_disclosure_skips_988_for_a_context_free_reply_mention(self):
        self._turn("I have said my goodbyes.", ["988 is there for you."], audit=("CRISIS", "plan"))
        self.assertEqual(" ".join(self.spoken).count("988"), 1, self.spoken)

    def test_think_988_guard_is_per_reply_on_ordinary_turns(self):
        r, _ = self._turn("I feel low today.", ["Call 988 if it gets worse.", "Call 988 any time."])
        self.assertEqual(r.reply_text.count("988"), 1, r.reply_text)


class TestWordsMatchShortInflections(unittest.TestCase):
    """Fixes #32: _words_match must handle short-word inflections (3-4 chars)."""

    def test_dog_dogs(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("dog", "dogs"))

    def test_dogs_dog(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("dogs", "dog"))

    def test_walk_walked(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("walk", "walked"))

    def test_walk_walking(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("walk", "walking"))

    def test_cat_cats(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("cat", "cats"))

    def test_car_cart_no_match(self):
        """'car' and 'cart' share a prefix but 't' is not a valid inflection suffix."""
        from pipeline.orchestrator import _words_match
        self.assertFalse(_words_match("car", "cart"))

    def test_run_runs(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("run", "runs"))

    def test_exact_short_match(self):
        from pipeline.orchestrator import _words_match
        self.assertTrue(_words_match("dog", "dog"))

    def test_unrelated_short_words(self):
        from pipeline.orchestrator import _words_match
        self.assertFalse(_words_match("dog", "fog"))

    def test_find_matching_facts_short_words(self):
        """End-to-end: 'I like the dogs' should match 'Senior loves walking the dog'."""
        from pipeline.orchestrator import _find_matching_facts
        facts = ["Senior loves walking the dog"]
        result = _find_matching_facts("I like the dogs", facts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "Senior loves walking the dog")
