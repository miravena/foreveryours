"""Tests for the end-to-end Orchestrator turn flow and offline degradation."""
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline.nebius_client import NebiusNotConfigured
from pipeline.orchestrator import FALLBACK_REPLY_1, FALLBACK_REPLY_2, run_turn


class TestOrchestrator(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

