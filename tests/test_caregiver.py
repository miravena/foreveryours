"""Tests for CaregiverFlags and disclosure invariant enforcement."""
import tempfile
import unittest
from pathlib import Path

from caregiver import CaregiverFlags


class TestCaregiverFlags(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.profile_id = "test_dad"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_disclosure_argument_is_mandatory(self):
        flags = CaregiverFlags(self.profile_id, self.data_dir)
        # Calling add without disclosed_to_senior must fail at type/argument level
        with self.assertRaises(TypeError):
            flags.add("Fell down", severity="urgent")  # type: ignore

    def test_add_and_persistence(self):
        flags1 = CaregiverFlags(self.profile_id, self.data_dir)
        flag1 = flags1.add(
            "URGENT: possible distress — 'I fell down'",
            severity="distress",
            disclosed_to_senior=True,
        )
        self.assertEqual(flag1.severity, "distress")
        self.assertTrue(flag1.disclosed_to_senior)
        self.assertTrue(flags1.path.exists())

        # Load from disk in a fresh instance
        flags2 = CaregiverFlags(self.profile_id, self.data_dir)
        loaded = flags2.all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].text, flag1.text)
        self.assertEqual(loaded[0].severity, "distress")
        self.assertTrue(loaded[0].disclosed_to_senior)


if __name__ == "__main__":
    unittest.main()
