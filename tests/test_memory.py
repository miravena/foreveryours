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


if __name__ == "__main__":
    unittest.main()
