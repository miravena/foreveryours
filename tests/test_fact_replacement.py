"""Fact replacement is right in both directions.

(b) DUPLICATE: a caregiver update ("groceries at 6 PM") must supersede the
earlier caregiver fact with the same subject ("groceries at 4 PM"), so only
one active grocery fact reaches the model.
(a) LEAK: when the senior privately corrects a caregiver-authored fact, the
caregiver panel may show the struck-through original but never the senior's
replacement words, unless the replacement itself passes
webapp._caregiver_panel_may_show() (disclosure attested).
"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from memory.store import MemoryItem, MemoryStore

OLD = "I'm dropping off groceries at 4 PM today"
NEW = "I'm dropping off groceries at 6 PM today"


class TestFactReplacement(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", Path(self.temp_dir.name) / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _store(self, session_id: str) -> MemoryStore:
        data_dir, _ = webapp._session_dirs(session_id)
        return MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir, timezone_str=webapp.SENIOR_TIMEZONE)

    def _briefed(self, panel: str) -> str:
        return panel.split("### Briefed memory", 1)[1]

    def _updated_session(self) -> str:
        session_id, _ = webapp.init_session()  # seeds DEMO_MEMO incl. the 4 PM line
        self.assertIn(OLD, [i.text for i in self._store(session_id).all()])
        webapp.save_caregiver_text_memo(NEW, session_id)
        return session_id

    def test_caregiver_update_supersedes_matching_fact(self):
        store = self._store(self._updated_session())
        active = [i for i in store.all() if i.status == "active" and "groceries" in i.text]
        self.assertEqual([i.text for i in active], [NEW])
        old = [i for i in store.all() if i.text == OLD]
        self.assertEqual(len(old), 1, old)
        self.assertEqual(old[0].status, "superseded")
        self.assertEqual(old[0].superseded_by, NEW)
        facts = store.senior_profile_facts()
        schedule = store.caregiver_schedule_updates()
        self.assertFalse(any("4 PM" in f for f in facts + schedule), (facts, schedule))
        self.assertTrue(any("6 PM" in f for f in schedule), schedule)

    def test_caregiver_update_is_idempotent(self):
        session_id = self._updated_session()
        before = [(i.text, i.status, i.superseded_by) for i in self._store(session_id).all()]
        webapp.save_caregiver_text_memo(NEW, session_id)
        after_store = self._store(session_id)
        after = [(i.text, i.status, i.superseded_by) for i in after_store.all()]
        self.assertEqual(after, before)
        active = [i for i in after_store.all() if i.status == "active" and "groceries" in i.text]
        self.assertEqual(len(active), 1, active)
        self.assertEqual(len([i for i in after_store.all() if i.status == "superseded"]), 1)

    def test_private_correction_text_hidden_from_panel(self):
        session_id, _ = webapp.init_session()
        store = self._store(session_id)
        store.add("Dad loves jazz", source="caregiver_memo")  # no-op: already seeded
        new_item = store.supersede(
            "Dad loves jazz", "I hate jazz now, it reminds me of my late wife", source="conversation_extract"
        )
        self.assertFalse(new_item.disclosure_attested)
        panel = webapp._format_caregiver_panel(session_id)
        self.assertNotIn("late wife", panel)
        self.assertNotIn("Replaced by", panel)
        self.assertIn("~~Dad loves jazz~~", self._briefed(panel))  # caregiver-authored: still shown

    def test_caregiver_replacement_text_shown_in_panel(self):
        session_id = self._updated_session()
        briefed = self._briefed(webapp._format_caregiver_panel(session_id))
        self.assertIn(f"~~{OLD}~~ → *Replaced by: {NEW}*", briefed)

    def test_seeds_never_supersede_each_other(self):
        session_id, _ = webapp.init_session()
        webapp.load_sample_family(session_id)
        superseded = [i.text for i in self._store(session_id).all() if i.status == "superseded"]
        self.assertEqual(superseded, [])

    def test_facts_saved_together_never_supersede_each_other(self):
        # Codex review: two reminders in ONE memo are additive, not a
        # correction, even though their subject keys match.
        session_id, _ = webapp.init_session()
        webapp.save_caregiver_text_memo("Blood pressure pill, 8 AM. Blood pressure pill, 8 PM.", session_id)
        store = self._store(session_id)
        pills = [(i.text, i.status) for i in store.all() if "pill" in i.text]
        self.assertEqual(pills, [("Blood pressure pill, 8 AM", "active"), ("Blood pressure pill, 8 PM", "active")])
        # A later "9 AM" matches both; which one it changes is ambiguous, so
        # neither is dropped (a missing reminder is worse than an extra one).
        webapp.save_caregiver_text_memo("Blood pressure pill, 9 AM", session_id)
        self.assertEqual(
            [i.text for i in self._store(session_id).all() if "pill" in i.text and i.status == "active"],
            ["Blood pressure pill, 8 AM", "Blood pressure pill, 8 PM", "Blood pressure pill, 9 AM"],
        )

    def test_reseeding_never_reverts_a_caregiver_update(self):
        # Codex review: with FY_SHARED_PROFILE=1 every new tab
        # re-runs the DEMO_MEMO pre-brief over the same household; it must
        # not bring the superseded 4 PM line back over the 6 PM update.
        with patch.object(webapp, "SHARED_PROFILE", True):
            session_id = self._updated_session()
            again, _ = webapp.init_session()
            self.assertEqual(again, session_id)
            webapp.load_sample_family(session_id)
            webapp.load_sample_family(session_id)
            store = self._store(session_id)
        active = [i.text for i in store.all() if i.status == "active" and "groceries" in i.text]
        self.assertEqual(active, [NEW])

    def test_restated_fact_still_superseded_by_update(self):
        # Codex review: a restatement differing only in case or
        # punctuation is the same fact, not a second one that makes the
        # update ambiguous.
        session_id, _ = webapp.init_session()
        webapp.save_caregiver_text_memo("I'm dropping off groceries at 4 pm today.", session_id)
        webapp.save_caregiver_text_memo(NEW, session_id)
        store = self._store(session_id)
        active = [i.text for i in store.all() if i.status == "active" and "groceries" in i.text]
        self.assertEqual(active, [NEW])
        self.assertFalse(any("4 PM" in f.upper() for f in store.senior_profile_facts() + store.caregiver_schedule_updates()))

    def test_expired_fact_does_not_make_update_ambiguous(self):
        # Codex review: an expired same-subject fact is not live,
        # so it neither blocks nor joins the supersede.
        session_id, _ = webapp.init_session()
        store = self._store(session_id)
        store.add("Blood pressure pill, 8 AM", source="caregiver_memo")
        # Written directly: add() would let either line supersede the other.
        store._items.append(MemoryItem("Blood pressure pill, 7 AM", source="caregiver_memo",
                                       scope="temporary", expires_at=time.time() - 1))
        store._flush()
        webapp.save_caregiver_text_memo("Blood pressure pill, 9 AM", session_id)
        store = self._store(session_id)
        status = {i.text: i.status for i in store.all() if "pill" in i.text}
        self.assertEqual(status["Blood pressure pill, 8 AM"], "superseded")
        self.assertEqual(status["Blood pressure pill, 9 AM"], "active")
        self.assertEqual([f for f in store.caregiver_schedule_updates() if "pill" in f], ["Blood pressure pill, 9 AM"])

    def test_cli_beat1_rerun_never_reverts_update(self):
        # Codex review: main.py beat1's canned fallback is a seed
        # too; re-running it must not bring 4 PM back over a 6 PM update.
        import io
        from contextlib import redirect_stdout

        import main
        data_dir = Path(self.temp_dir.name) / "cli"
        with patch.object(main, "DATA_DIR", data_dir), redirect_stdout(io.StringIO()):
            main.beat1_caregiver_memo()
            MemoryStore(main.DEFAULT_PROFILE_ID, data_dir).add(NEW, source="caregiver_memo")
            main.beat1_caregiver_memo()
        store = MemoryStore(main.DEFAULT_PROFILE_ID, data_dir)
        active = [i.text for i in store.all() if i.status == "active" and "groceries" in i.text]
        self.assertEqual(active, [NEW])

    def test_sample_family_never_replaces_a_caregiver_fact(self):
        # Codex review: the seed's "Blood pressure pill, 8 AM" must
        # not supersede the caregiver's own 9 AM reminder.
        session_id, _ = webapp.init_session()
        webapp.save_caregiver_text_memo("Blood pressure pill, 9 AM", session_id)
        webapp.load_sample_family(session_id)
        status = {i.text: i.status for i in self._store(session_id).all() if "pill" in i.text}
        self.assertEqual(status["Blood pressure pill, 9 AM"], "active")

    def test_equivalent_clock_formats_are_one_fact(self):
        # Codex review: "8 AM" and "8:00 am" are one reminder, so a
        # later 9 AM update replaces both instead of reading as ambiguous.
        session_id, _ = webapp.init_session()
        webapp.save_caregiver_text_memo("Blood pressure pill, 8 AM. Blood pressure pill, 8:00 am.", session_id)
        webapp.save_caregiver_text_memo("Blood pressure pill, 9 AM", session_id)
        active = [i.text for i in self._store(session_id).all() if "pill" in i.text and i.status == "active"]
        self.assertEqual(active, ["Blood pressure pill, 9 AM"])

    def test_restatement_never_supersedes_a_different_fact(self):
        # Codex P1: restating the morning reminder in another clock
        # format must not supersede the evening one.
        session_id, _ = webapp.init_session()
        webapp.save_caregiver_text_memo("Blood pressure pill, 8 AM. Blood pressure pill, 8 PM.", session_id)
        webapp.save_caregiver_text_memo("Blood pressure pill, 8:00 am", session_id)
        store = self._store(session_id)
        self.assertEqual([i.text for i in store.all() if "pill" in i.text and i.status == "superseded"], [])
        self.assertIn("Blood pressure pill, 8 PM", store.caregiver_schedule_updates())

    def test_number_that_names_the_subject_is_kept(self):
        # Codex P1: B12 and B6 are two different reminders.
        session_id, _ = webapp.init_session()
        webapp.save_caregiver_text_memo("Vitamin B12 reminder, 8 AM", session_id)
        webapp.save_caregiver_text_memo("Vitamin B6 reminder, 8 PM", session_id)
        updates = self._store(session_id).caregiver_schedule_updates()
        self.assertIn("Vitamin B12 reminder, 8 AM", updates)
        self.assertIn("Vitamin B6 reminder, 8 PM", updates)


if __name__ == "__main__":
    unittest.main()
