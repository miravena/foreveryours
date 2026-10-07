"""Tests for MemoryStore persistence, atomic writes, deduping, and semantic recall."""
import json
import tempfile
import unittest
from pathlib import Path

from memory.store import MemoryStore


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.profile_id = "test_profile"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_persistence_and_atomic_write(self):
        store1 = MemoryStore(self.profile_id, self.data_dir)
        item1 = store1.add("Dad loves jazz music", source="caregiver_memo")
        self.assertIsNotNone(item1)
        self.assertTrue(store1.path.exists())

        # Verify underlying JSON structure
        raw_data = json.loads(store1.path.read_text())
        self.assertEqual(len(raw_data), 1)
        self.assertEqual(raw_data[0]["text"], "Dad loves jazz music")

        # Verify new instance (simulating separate process run) reads persisted data
        store2 = MemoryStore(self.profile_id, self.data_dir)
        items = store2.all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text, "Dad loves jazz music")
        self.assertEqual(items[0].source, "caregiver_memo")

    def test_deduplication(self):
        store = MemoryStore(self.profile_id, self.data_dir)
        first = store.add("Grandson is Leo", source="caregiver_memo")
        self.assertIsNotNone(first)
        # Adding same text and source should return None and not duplicate
        second = store.add("Grandson is Leo", source="caregiver_memo")
        self.assertIsNone(second)
        self.assertEqual(len(store.all()), 1)

        # Same text with different source is allowed
        third = store.add("Grandson is Leo", source="conversation_extract")
        self.assertIsNotNone(third)
        self.assertEqual(len(store.all()), 2)

    def test_caregiver_context_isolation(self):
        store = MemoryStore(self.profile_id, self.data_dir)
        store.add("Avoid talking about driving", source="caregiver_note")
        store.add("Dad loves jazz", source="caregiver_memo")
        store.add("Loves blueberry pancakes", source="conversation_extract")

        cg_context = store.caregiver_context()
        self.assertEqual(len(cg_context), 2)
        sources = {item.source for item in cg_context}
        self.assertEqual(sources, {"caregiver_note", "caregiver_memo"})
        self.assertNotIn("conversation_extract", sources)

    def test_semantic_synonym_search(self):
        store = MemoryStore(self.profile_id, self.data_dir)
        # Conversation memory containing "grandson"
        store.add("My grandson Leo visited yesterday", source="conversation_extract")
        store.add("I used to love baking pies", source="conversation_extract")

        # Query using synonym "grandkid"
        results = store.search("Tell me about my grandkid")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("grandson Leo", results[0].text)

        # Query using synonym "grandchild"
        results_child = store.search("Where is my grandchild?")
        self.assertGreaterEqual(len(results_child), 1)
        self.assertIn("grandson Leo", results_child[0].text)

    def test_domain_synonym_car_driving(self):
        store = MemoryStore(self.profile_id, self.data_dir)
        store.add("Remember we sold the car last year", source="conversation_extract")

        # Query using synonym "driving"
        results = store.search("Can I go driving today?")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("sold the car", results[0].text)

    def test_stopword_pruning_prevents_false_positives(self):
        store = MemoryStore(self.profile_id, self.data_dir)
        store.add("The weather was sunny in Seattle", source="conversation_extract")
        store.add("I worked as a carpenter in Chicago", source="conversation_extract")

        # Query shares many stopwords ("what was the", "in") but key term is "carpenter"
        results = store.search("What was the job in the city?")
        # If no specific key terms match, should not return arbitrary stopword matches
        results_carpenter = store.search("Who was the carpenter?")
        self.assertEqual(len(results_carpenter), 1)
        self.assertIn("carpenter in Chicago", results_carpenter[0].text)

    def test_temporal_expiration_and_active_filtering(self):
        from memory.store import MemoryScope
        store = MemoryStore(self.profile_id, self.data_dir)
        now = 1000.0
        # Temporary 4 PM grocery delivery expiring at 1100
        store.add(
            "Sarah dropping groceries at 4 PM",
            source="caregiver_memo",
            scope=MemoryScope.TEMPORARY.value,
            expires_at=1100.0,
        )
        # Permanent biographical fact
        store.add("Dad loves jazz", source="caregiver_memo")

        # Before expiration: schedule updates include groceries
        active_schedule = store.caregiver_schedule_updates(now=1050.0)
        self.assertTrue(any("groceries" in s for s in active_schedule))

        # After expiration (t = 1200.0): groceries must be excluded!
        expired_schedule = store.caregiver_schedule_updates(now=1200.0)
        self.assertFalse(any("groceries" in s for s in expired_schedule))

        # Search should also exclude expired items
        store.add("Watched a baseball game yesterday", source="conversation_extract", expires_at=1100.0)
        hits_before = store.search("baseball", now=1050.0)
        self.assertEqual(len(hits_before), 1)
        hits_after = store.search("baseball", now=1200.0)
        self.assertEqual(len(hits_after), 0)

    def test_substring_time_words_do_not_force_temporary_scope(self):
        """Regression: 'am' matched as a substring of 'Liam'/'name' turned a
        permanent fact into a 24h-TTL one. Only whole time words should."""
        from memory.store import MemoryScope
        store = MemoryStore(self.profile_id, self.data_dir)
        store.add("His grandson's name is Liam", source="conversation_extract")
        store.add("Dad's family name is Amherst", source="conversation_extract")
        for item in store._items:
            self.assertEqual(item.scope, MemoryScope.PERMANENT.value, item.text)
            self.assertIsNone(item.expires_at, item.text)

        # Whole time words still trigger the TEMPORARY auto-scope.
        store.add("Sarah is visiting tomorrow", source="conversation_extract")
        tomorrow_item = next(i for i in store._items if "tomorrow" in i.text)
        self.assertEqual(tomorrow_item.scope, MemoryScope.TEMPORARY.value)
        self.assertIsNotNone(tomorrow_item.expires_at)

        # Regression (Codex review of #82): "4pm"/"10am" glued to a digit,
        # with no space, must still be caught as a clock marker.
        for t in ("Sarah is dropping by at 4pm", "Dad's appointment is at 10am"):
            store.add(t, source="conversation_extract")
            item = next(i for i in store._items if i.text == t)
            self.assertEqual(item.scope, MemoryScope.TEMPORARY.value, t)
            self.assertIsNotNone(item.expires_at, t)

    def test_caregiver_privacy_firewall(self):
        from memory.store import PrivacyLevel
        store = MemoryStore(self.profile_id, self.data_dir)
        store.add(
            "Planning surprise 80th birthday party next Saturday",
            source="caregiver_note",
            privacy=PrivacyLevel.CAREGIVER_ONLY.value,
        )
        store.add("Dad loves gardening", source="caregiver_memo")

        # Must NOT appear in senior profile facts
        facts = store.senior_profile_facts()
        self.assertFalse(any("surprise" in f.lower() for f in facts))
        self.assertTrue(any("gardening" in f.lower() for f in facts))

        # Must NOT appear in senior-facing schedule updates
        updates = store.caregiver_schedule_updates()
        self.assertFalse(any("surprise" in u.lower() for u in updates))

        # Must NOT appear in senior search
        search_hits = store.search("surprise party")
        self.assertEqual(len(search_hits), 0)

        # Must be preserved for caregiver coordination dashboard
        cg_all = store.caregiver_context(include_private=True)
        self.assertTrue(any("surprise" in c.text.lower() for c in cg_all))

    def test_contradictory_memory_supersede(self):
        store = MemoryStore(self.profile_id, self.data_dir)
        old_item = store.add("Dad loves jazz", source="caregiver_memo")
        new_item = store.supersede(
            "Dad loves jazz",
            "Senior no longer listens to jazz; prefers classical music",
            source="conversation_extract",
        )
        self.assertIsNotNone(new_item)
        self.assertEqual(old_item.status, "superseded")
        self.assertFalse(old_item.is_active())

        facts = store.senior_profile_facts()
        self.assertTrue(any("classical" in f.lower() for f in facts))
        self.assertFalse(any("Dad loves jazz" == f for f in facts))


class TestSupersedeInheritsProperties(unittest.TestCase):
    """Fixes #34: supersede() must preserve scope, privacy and expires_at."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.store = MemoryStore("test_dad", self.data_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_temporary_schedule_stays_temporary(self):
        """A 2-hour schedule update must remain temporary after correction."""
        import time
        expires = time.time() + 7200  # 2 hours from now
        self.store.add(
            "Groceries at 4 PM",
            source="caregiver_memo",
            scope="temporary",
            privacy="public",
            expires_at=expires,
        )
        new_item = self.store.supersede("Groceries at 4 PM", "Groceries at 5 PM", source="caregiver_memo")
        self.assertEqual(new_item.scope, "temporary")
        self.assertEqual(new_item.privacy, "public")
        self.assertEqual(new_item.expires_at, expires)

    def test_private_memory_stays_private(self):
        """A CAREGIVER_ONLY memory must stay private after supersession."""
        self.store.add(
            "Dad might need a walker",
            source="caregiver_memo",
            privacy="caregiver_only",
        )
        new_item = self.store.supersede("Dad might need a walker", "Dad needs a walker soon", source="caregiver_memo")
        self.assertEqual(new_item.privacy, "caregiver_only")

    def test_permanent_memory_defaults_preserved(self):
        """A normal permanent memory should stay permanent after supersession."""
        self.store.add("Dad loves jazz", source="caregiver_memo")
        new_item = self.store.supersede("Dad loves jazz", "Dad loves classical", source="caregiver_memo")
        self.assertEqual(new_item.scope, "permanent")
        self.assertEqual(new_item.privacy, "public")
        self.assertIsNone(new_item.expires_at)

    def test_chained_supersession_preserves(self):
        """Superseding a superseded memory still inherits from the latest active one."""
        import time
        expires = time.time() + 3600
        self.store.add("Meeting at 2 PM", source="caregiver_memo", scope="temporary", expires_at=expires)
        self.store.supersede("Meeting at 2 PM", "Meeting at 3 PM", source="caregiver_memo")
        new_item = self.store.supersede("Meeting at 3 PM", "Meeting at 4 PM", source="caregiver_memo")
        self.assertEqual(new_item.scope, "temporary")
        self.assertEqual(new_item.expires_at, expires)


if __name__ == "__main__":
    unittest.main()
