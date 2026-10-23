"""Tests for CaregiverFlags and disclosure invariant enforcement."""
import tempfile
import unittest
from pathlib import Path

from caregiver import (
    INTERVIEW_QUESTIONS,
    SAMPLE_FAMILY,
    CaregiverFlags,
    split_memo_facts,
    validate_sample_profile,
)
from memory.store import MemoryScope, MemoryStore


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


class TestInterviewQuestions(unittest.TestCase):
    def test_five_questions_with_the_required_fields(self):
        self.assertEqual(len(INTERVIEW_QUESTIONS), 5)
        for q in INTERVIEW_QUESTIONS:
            self.assertEqual(set(q), {"key", "prompt", "scope", "skippable", "example"})
            self.assertTrue(q["prompt"].strip())
            self.assertIsInstance(q["skippable"], bool)
        self.assertEqual(len({q["key"] for q in INTERVIEW_QUESTIONS}), 5)

    def test_every_key_exists_in_sample_family_and_every_scope_is_known(self):
        groups = {g for g, _t, _p in SAMPLE_FAMILY["items"]}
        scopes = {s.value for s in MemoryScope}
        for q in INTERVIEW_QUESTIONS:
            self.assertIn(q["key"], groups)
            self.assertIn(q["scope"], scopes)

    def test_examples_pass_the_validator_and_save_in_the_declared_scope(self):
        for q in INTERVIEW_QUESTIONS:
            with self.subTest(key=q["key"]):
                validate_sample_profile(q["example"])
                with tempfile.TemporaryDirectory() as d:
                    store = MemoryStore("p", Path(d))
                    facts = split_memo_facts(q["example"])
                    for line in facts:
                        store.add(line, source="caregiver_memo", keep_texts=facts)
                    saved = store.all()
                    self.assertTrue(saved)
                    self.assertEqual({i.scope for i in saved}, {q["scope"]})

    def test_prompts_do_not_ask_for_medical_content(self):
        for q in INTERVIEW_QUESTIONS:
            self.assertNotRegex(q["prompt"].lower(), r"diagnos|condition|illness|dose|medical|symptom")


if __name__ == "__main__":
    unittest.main()
