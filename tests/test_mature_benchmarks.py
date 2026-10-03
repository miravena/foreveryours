"""Quantitative Adversarial Benchmarks for ForeverYours (Phase 3).

Measures objective metrics rather than subjective 10/10 scores:
1. Unnecessary Personalization Rate (Zero-Memory Benchmark): Target 0.0% across 20 factual/unrelated queries
2. False Positive Safety Escalation Rate: Target 0.0% on benign fatigue/nap/autumn phrases
3. Temporal Expiration Compliance: Target 100.0% on time-bound memories
4. Caregiver Privacy Firewall Leakage Rate: Target 0.0% on CAREGIVER_ONLY notes
5. Contradictory Memory Evolution Accuracy: Target 100.0% on superseded memories
"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryScope, MemoryStore, PrivacyLevel
from pipeline.orchestrator import run_turn
from safety import fastpath


class TestMatureBenchmarks(unittest.TestCase):
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

    @patch("pipeline.think.stream_reply")
    def test_unnecessary_personalization_rate_benchmark(self, mock_stream):
        """Benchmark 1: Unnecessary Personalization Rate on 20 completely ordinary queries.
        Target: 0.0% (Zero forced personalization).
        """
        mock_stream.return_value = iter(["Here is the answer."])

        # Pre-load senior's rich memory profile (7 diverse facts and 1 schedule note)
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")
        self.store.add("Senior used to be a high school teacher", source="caregiver_memo")
        self.store.add("Loves homemade chicken soup", source="caregiver_memo")
        self.store.add("Senior enjoys gardening and flowers", source="caregiver_memo")
        self.store.add("Daughter Sarah visits on weekends", source="caregiver_memo")
        self.store.add("Avoid talking about driving", source="caregiver_memo")
        self.store.add("Sarah is dropping off groceries at 4 PM today", source="caregiver_memo")

        ordinary_queries = [
            "What time is it?",
            "What's 25 plus 17?",
            "Tell me a joke.",
            "What's the capital of France?",
            "What day is it?",
            "How does rain form?",
            "What is 10 divided by 2?",
            "How far is the moon?",
            "What is water made of?",
            "Can you define the word empathy?",
            "Why is the sky blue?",
            "What does photosynthesis mean?",
            "What year was the telescope invented?",
            "How many hours are in a day?",
            "Good morning.",
            "Good afternoon.",
            "Hello there.",
            "How is the weather today?",
            "What colors make green?",
            "How many inches are in a foot?",
        ]

        unnecessary_personalizations = 0
        total_queries = len(ordinary_queries)

        for query in ordinary_queries:
            res = run_turn(
                transcript=query,
                memory_store=self.store,
                flags=self.flags,
                audio_out_dir=self.audio_dir,
                caregiver_name="Sarah",
            )
            if len(res.memories_used) > 0:
                unnecessary_personalizations += 1

        rate = (unnecessary_personalizations / total_queries) * 100.0
        print(f"\n[BENCHMARK 1] Unnecessary Personalization Rate: {rate:.1f}% ({unnecessary_personalizations}/{total_queries})")
        self.assertEqual(
            unnecessary_personalizations,
            0,
            f"Expected 0.0% Unnecessary Personalization Rate, got {rate:.1f}%",
        )

    def test_false_positive_safety_escalation_rate(self):
        """Benchmark 2: False Positive Safety Alert Rate on benign fatigue / nap / seasonal speech.
        Target: 0.0% (Zero false panic alerts sent to caregiver).
        """
        benign_queries = [
            "I'm exhausted after gardening",
            "I'm tired after a long day",
            "I fell asleep in my chair earlier",
            "I took a nice long nap",
            "I love the crisp fall weather",
            "The autumn leaves are falling outside",
            "Today was an awful day at the grocery store",
            "I'm a little worn out today",
            "I'm feeling quite sleepy",
            "I rested on the sofa all afternoon",
            "Help me remember my grandson's name",
            "Can you help me understand today's schedule?",
            "Help me find my reading glasses",
            "Can you help me with this puzzle?",
            "I think I'm falling asleep in front of the TV",
        ]

        false_alarms = 0
        total_cases = len(benign_queries)

        for phrase in benign_queries:
            res = fastpath.check(phrase)
            if res.triggered:
                false_alarms += 1

        rate = (false_alarms / total_cases) * 100.0
        print(f"\n[BENCHMARK 2] False Positive Safety Escalation Rate: {rate:.1f}% ({false_alarms}/{total_cases})")
        self.assertEqual(
            false_alarms,
            0,
            f"Expected 0.0% False Positive Safety Escalation Rate, got {rate:.1f}%",
        )

    def test_temporal_expiration_compliance(self):
        """Benchmark 3: Temporal Expiration Compliance Rate.
        Target: 100.0% (Expired events must never be retrieved as current).
        """
        base_time = 1700000000.0
        # Schedule item expiring in 2 hours
        self.store.add(
            "Sarah dropping groceries at 4 PM",
            source="caregiver_memo",
            scope=MemoryScope.TEMPORARY.value,
            expires_at=base_time + 7200.0,
        )
        # Permanent item
        self.store.add("Dad loves jazz", source="caregiver_memo")

        # Check 1: 1 hour in (active)
        t_active = base_time + 3600.0
        active_updates = self.store.caregiver_schedule_updates(now=t_active)
        self.assertIn("Sarah dropping groceries at 4 PM", active_updates)

        # Check 2: 3 hours in (expired)
        t_expired = base_time + 10800.0
        expired_updates = self.store.caregiver_schedule_updates(now=t_expired)
        self.assertNotIn("Sarah dropping groceries at 4 PM", expired_updates)

        # Permanent fact remains active
        facts = self.store.senior_profile_facts(now=t_expired)
        self.assertIn("Dad loves jazz", facts)

        print("\n[BENCHMARK 3] Temporal Expiration Compliance: 100.0% (Passed)")

    def test_caregiver_privacy_firewall_leakage_rate(self):
        """Benchmark 4: Caregiver Privacy Firewall Leakage Rate.
        Target: 0.0% (Private caregiver notes strictly withheld from senior turns).
        """
        self.store.add(
            "Planning surprise 80th birthday party with extended family next weekend",
            source="caregiver_note",
            privacy=PrivacyLevel.CAREGIVER_ONLY.value,
        )
        self.store.add("Senior used to be a high school teacher", source="caregiver_memo")

        # Senior profile facts check
        facts = self.store.senior_profile_facts()
        leaked_in_facts = any("surprise" in f.lower() for f in facts)

        # Senior schedule updates check
        updates = self.store.caregiver_schedule_updates()
        leaked_in_updates = any("surprise" in u.lower() for u in updates)

        # Senior memory search check
        searched = self.store.search("surprise birthday party")
        leaked_in_search = len(searched) > 0

        total_checks = 3
        leaks = sum([leaked_in_facts, leaked_in_updates, leaked_in_search])
        rate = (leaks / total_checks) * 100.0

        print(f"\n[BENCHMARK 4] Caregiver Privacy Leakage Rate: {rate:.1f}% ({leaks}/{total_checks})")
        self.assertEqual(leaks, 0, f"Expected 0.0% Privacy Leakage Rate, got {rate:.1f}%")

    def test_contradictory_memory_evolution_accuracy(self):
        """Benchmark 5: Contradictory Memory Evolution Accuracy.
        Target: 100.0% (Superseded preferences properly updated without conflicting recall).
        """
        old_item = self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.supersede(
            "Dad loves jazz",
            "Senior no longer listens to jazz; prefers classical music",
            source="conversation_extract",
        )

        self.assertEqual(old_item.status, "superseded")
        self.assertFalse(old_item.is_active())

        active_facts = self.store.senior_profile_facts()
        has_new = any("classical" in f.lower() for f in active_facts)
        has_old = any(f == "Dad loves jazz" for f in active_facts)

        self.assertTrue(has_new, "Expected new preference in active facts")
        self.assertFalse(has_old, "Expected old superseded preference to be excluded")

        print("\n[BENCHMARK 5] Contradictory Memory Evolution Accuracy: 100.0% (Passed)")


if __name__ == "__main__":
    unittest.main()
