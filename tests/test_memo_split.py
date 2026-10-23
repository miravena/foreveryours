"""caregiver.split_memo_facts keeps abbreviations inside their fact.

A memo such as "Dad has a check-up with Dr. Tan on Thursday at 10 AM." used
to be stored as "Dad has a check-up with Dr" and "Tan on Thursday at 10 AM",
and the companion then said it had no appointments listed. Every memo path
(typed, dictated, demo seed, main.py beat1) goes through this one splitter.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from caregiver import split_memo_facts
from memory.store import MemoryStore


class AbbreviationStaysOneFactTests(unittest.TestCase):
    def assertOneFact(self, memo: str, abbreviation: str) -> None:
        facts = split_memo_facts(memo)
        self.assertEqual(len(facts), 1, facts)
        self.assertIn(abbreviation, facts[0])

    def test_dr(self):
        self.assertOneFact("Dad has a check-up with Dr. Tan on Thursday at 10 AM.", "Dr. Tan")

    def test_mr(self):
        self.assertOneFact("Mr. Lee from next door visits on Monday.", "Mr. Lee")

    def test_mrs(self):
        self.assertOneFact("Mrs. Chen brings lunch on Fridays.", "Mrs. Chen")

    def test_st(self):
        self.assertOneFact("Church is at St. Mary's on Sunday morning.", "St. Mary's")

    def test_am(self):
        self.assertOneFact("Lunch is at 11:30 a.m. on weekdays.", "11:30 a.m. on weekdays")

    def test_am_touching_the_clock_digit(self):
        self.assertOneFact("Walk at 9a.m. on weekdays.", "9a.m. on weekdays")
        self.assertEqual(split_memo_facts("Tea at 5p.m. Then bed."), ["Tea at 5p.m.", "Then bed"])

    def test_dose_unit(self):
        self.assertOneFact("Dad takes 5 mg. of his pill with breakfast.", "5 mg. of his pill")


class RealBoundariesStillSplitTests(unittest.TestCase):
    def test_unit_before_a_new_sentence_splits(self):
        self.assertEqual(split_memo_facts("Dad takes 5 mg. Mom visits."), ["Dad takes 5 mg", "Mom visits"])

    def test_meridiem_before_a_new_sentence_splits_and_keeps_its_period(self):
        self.assertEqual(split_memo_facts("Walk at 9 a.m. Then lunch."), ["Walk at 9 a.m.", "Then lunch"])

    def test_bang_question_newline_and_plain_periods_split(self):
        memo = "Dad loves jazz! Is Leo coming?\nAvoid talking about driving.I'm dropping off groceries at 4 PM today."
        self.assertEqual(
            split_memo_facts(memo),
            ["Dad loves jazz", "Is Leo coming", "Avoid talking about driving", "I'm dropping off groceries at 4 PM today"],
        )

    def test_decimal_is_not_a_boundary(self):
        self.assertEqual(split_memo_facts("Give 1.5 mg at noon."), ["Give 1.5 mg at noon"])

    def test_memo_without_a_break_is_stored_whole(self):
        self.assertEqual(split_memo_facts("Dad likes tea with Dr. Tan"), ["Dad likes tea with Dr. Tan"])
        self.assertEqual(split_memo_facts(""), [])
        self.assertEqual(split_memo_facts(None), [])


class TextMemoEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", root / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", root / "data"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _memo_texts(self, session_id: str) -> list[str]:
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)
        return [i.text for i in store.all() if i.source == "caregiver_memo"]

    def test_dr_tan_memo_is_one_stored_item_and_resave_adds_nothing(self):
        session_id, _ = webapp.init_session()
        before_save = self._memo_texts(session_id)
        memo = "Dad has a check-up with Dr. Tan on Thursday at 10 AM."
        webapp.save_caregiver_text_memo(memo, session_id)
        after_first = self._memo_texts(session_id)
        added = after_first[len(before_save):]
        self.assertEqual(added, ["Dad has a check-up with Dr. Tan on Thursday at 10 AM"])
        self.assertNotIn("Dad has a check-up with Dr", after_first)

        webapp.save_caregiver_text_memo(memo, session_id)  # idempotent re-save
        self.assertEqual(self._memo_texts(session_id), after_first)


if __name__ == "__main__":
    unittest.main()
