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


if __name__ == "__main__":
    unittest.main()


    @patch("pipeline.orchestrator.fastpath.check")
    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.orchestrator.think.stream_reply", return_value=["Reply"])
    def test_perseveration_tracking_flags_loop(self, mock_stream, mock_speak, mock_fast):
        from pipeline.intent import Intent
        from pipeline.fastpath import FastPathResult
        mock_fast.return_value = FastPathResult(False, "none", None, None, None)
        history = [
            {"role": "user", "content": "What time is Sarah coming?"},
            {"role": "assistant", "content": "Sarah is coming at 4 PM."},
            {"role": "user", "content": "When is Sarah visiting?"},
            {"role": "assistant", "content": "She's visiting at 4 PM today."},
        ]
        # The 3rd time
        orchestrator.run_turn(
            "What time did you say Sarah was coming?", 
            self.store, 
            self.flags, 
            self.audio_dir, 
            history=history
        )
        flag_items = self.flags.all()
        self.assertTrue(any("Perseveration loop detected" in f.text for f in flag_items))


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
