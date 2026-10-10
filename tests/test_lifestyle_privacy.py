import json
import tempfile
import time
import unittest
from pathlib import Path

from memory.store import MemoryScope, MemoryStore


class TestLifestylePrivacy(unittest.TestCase):
    def test_lifestyle_requires_disclosure_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore("dad", Path(tmp))
            with self.assertRaises(ValueError):
                store.add("slept poorly", source="conversation_extract", scope="lifestyle")

    def test_lifestyle_defaults_to_seven_day_ttl_and_is_excluded_from_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore("dad", Path(tmp))
            item = store.add(
                "slept poorly",
                source="conversation_extract",
                scope="lifestyle",
                disclosure_attested=True,
            )
            self.assertIsNotNone(item)
            self.assertAlmostEqual(item.expires_at, time.time() + 7 * 24 * 3600, delta=5)
            self.assertEqual(store.search("slept poorly"), [])

    def test_legacy_expired_lifestyle_is_scrubbed_on_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dad.json"
            path.write_text(json.dumps([{
                "text": "private health detail",
                "source": "conversation_extract",
                "created_at": time.time() - 8 * 24 * 3600,
                "scope": "lifestyle",
                "privacy": "public",
                "expires_at": None,
                "status": "active",
                "superseded_by": None,
            }]))
            store = MemoryStore("dad", Path(tmp))
            self.assertNotIn("private health detail", path.read_text())
            self.assertFalse(any(
                item.scope == MemoryScope.LIFESTYLE.value and item.text == "private health detail"
                for item in store.all()
            ))


if __name__ == "__main__":
    unittest.main()
