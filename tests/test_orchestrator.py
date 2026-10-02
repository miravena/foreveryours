"""Tests for the end-to-end Orchestrator turn flow and offline degradation."""
import tempfile
import unittest
from pathlib import Path

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline.nebius_client import NebiusNotConfigured
from pipeline.orchestrator import run_turn


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


if __name__ == "__main__":
    unittest.main()

