"""Fixes #140: the caregiver panel is a privacy firewall, not a transcript.

`_format_caregiver_panel` (webapp.py) lists MemoryStore.all() under "Briefed
memory". That store also holds EMOTIONAL-scope memories extracted from the
senior's own words during conversation -- showing those to a caregiver is
exactly the surveillance #140 warns about. Caregiver-authored memos/notes
and disclosed safety flags are shown by design and must keep showing.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from caregiver import CaregiverFlags
from memory.store import MemoryScope, MemoryStore


class TestCaregiverPanelPrivacy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def test_emotional_memory_hidden_memo_and_flag_shown(self):
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        emotional_text = "I feel lonely since my wife died"
        store.add(
            emotional_text,
            source="conversation_extract",
            scope=MemoryScope.EMOTIONAL.value,
        )
        memo_text = "Sarah visits every Tuesday at 4pm"
        store.add(memo_text, source="caregiver_memo")

        flags = webapp.CaregiverFlags(webapp.DEFAULT_PROFILE_ID, data_dir)
        flag_text = "Dad mentioned feeling dizzy this morning"
        flags.add(flag_text, severity="info", disclosed_to_senior=True)

        panel = webapp._format_caregiver_panel(session_id)

        self.assertNotIn(emotional_text, panel)
        self.assertIn(memo_text, panel)
        self.assertIn(flag_text, panel)

    def test_emotional_state_tagged_text_hidden_even_off_emotional_scope(self):
        # Defence in depth: an item tagged [EMOTIONAL STATE] must stay
        # hidden even if its scope is something other than EMOTIONAL.
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        store.add(
            "[EMOTIONAL STATE]: Dad said he misses his late wife",
            source="conversation_extract",
            scope=MemoryScope.PERMANENT.value,
        )

        panel = webapp._format_caregiver_panel(session_id)
        self.assertNotIn("misses his late wife", panel)

    def test_decayed_emotional_memory_stays_hidden(self):
        # MemoryStore._decay_emotions() ages a 24h-expired EMOTIONAL item
        # into HISTORICAL scope, prefixing its still-private text with
        # "[PAST EMOTION - <date>]" instead of deleting it. Decaying scope
        # alone must not resurrect it in the caregiver panel (Codex review,
        # scripts/openai_review.sh).
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        emotional_text = "I feel lonely since my wife died"
        store.add(
            emotional_text,
            source="conversation_extract",
            scope=MemoryScope.EMOTIONAL.value,
            expires_at=1.0,  # already in the past
        )
        store._decay_emotions(now=2.0)
        item = next(i for i in store.all() if emotional_text in i.text)
        self.assertEqual(item.scope, MemoryScope.HISTORICAL.value)
        self.assertTrue(item.text.startswith("[PAST EMOTION"))

        panel = webapp._format_caregiver_panel(session_id)
        self.assertNotIn(emotional_text, panel)

    def test_correction_of_decayed_emotional_memory_stays_hidden(self):
        # MemoryStore.supersede() inherits scope from the item it replaces.
        # Correcting a decayed EMOTIONAL item (now HISTORICAL, text tagged
        # "[PAST EMOTION - ...]") must not drop that tag off the new fact,
        # or the correction -- itself drawn from the senior's own words --
        # would surface in the caregiver panel untagged (Codex review,
        # scripts/openai_review.sh).
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        original_text = "Angry with Sarah today"
        store.add(
            original_text,
            source="conversation_extract",
            scope=MemoryScope.EMOTIONAL.value,
            expires_at=1.0,
        )
        store._decay_emotions(now=2.0)
        decayed = next(i for i in store.all() if original_text in i.text)

        correction_text = "Angry with Sarah because she never visits"
        new_item = store.supersede(decayed.text, correction_text)
        self.assertEqual(new_item.scope, MemoryScope.HISTORICAL.value)
        self.assertTrue(new_item.text.startswith("[PAST EMOTION"))

        panel = webapp._format_caregiver_panel(session_id)
        self.assertNotIn(correction_text, panel)

    def test_unknown_scope_hidden_by_fallback(self):
        # Fallback: an item whose scope this code does not recognise must
        # not be shown just because it isn't explicitly EMOTIONAL.
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        store.add(
            "Some future, as-yet-unhandled scope value",
            source="conversation_extract",
            scope="some_future_scope",
        )

        panel = webapp._format_caregiver_panel(session_id)
        self.assertNotIn("Some future, as-yet-unhandled scope value", panel)

    def test_unknown_scope_hidden_even_for_caregiver_source(self):
        # The unknown-scope fallback must not be bypassed just because the
        # item's source is CAREGIVER_SOURCES -- a hand-edited data file or a
        # future code change could write a caregiver-sourced item with a
        # scope this code doesn't recognise, and the fail-closed guarantee
        # has to hold regardless of who (ostensibly) wrote the item
        # (review-arm finding: the unknown-scope fallback had this
        # uncovered exception).
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        store.add(
            "Caregiver note with a scope value this code has never seen",
            source="caregiver_memo",
            scope="some_future_scope",
        )

        panel = webapp._format_caregiver_panel(session_id)
        self.assertNotIn("Caregiver note with a scope value this code has never seen", panel)

    def test_senior_derived_facts_require_independent_disclosure_attestation(self):
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)

        private_text = "I feel lonely since my wife died"
        uncertain_text = "My grandson might move next year"
        misclassified_text = "ADD: I survived a traumatic war"
        store.add(private_text, source="conversation_extract")
        store.add(uncertain_text, source="conversation_extract", scope=MemoryScope.UNCERTAIN.value)
        store.add(misclassified_text, source="conversation_extract")
        authorized_text = "Dad sleeps poorly"
        store.add(
            authorized_text,
            source="conversation_extract",
            scope=MemoryScope.LIFESTYLE.value,
            disclosure_attested=True,
        )

        panel = webapp._format_caregiver_panel(session_id)

        self.assertNotIn(private_text, panel)
        self.assertNotIn(uncertain_text, panel)
        self.assertNotIn(misclassified_text, panel)
        self.assertIn(authorized_text, panel)


class TestMemoryConflictPrivacy(unittest.TestCase):
    """Fixes #165 (and duplicates #154, #156, #158, #160, #163, #166, #167):
    a private fact on either side of a memory conflict, or the reason given
    for it, must never reach the caregiver panel or survive on disk once the
    conflict closes."""

    PRIVATE_WORDS = ("lonely", "wife")

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _new_store_and_flags(self):
        session_id, _ = webapp.init_session()
        data_dir, _ = webapp._session_dirs(session_id)
        store = MemoryStore(webapp.DEFAULT_PROFILE_ID, data_dir)
        flags = CaregiverFlags(webapp.DEFAULT_PROFILE_ID, data_dir)
        return session_id, store, flags

    def _assert_panel_clean(self, session_id):
        try:
            panel = webapp._format_caregiver_panel(session_id)
        except Exception as exc:  # pre-fix code must FAIL, never ERROR
            self.fail(f"_format_caregiver_panel raised {exc!r}")
        for word in self.PRIVATE_WORDS:
            self.assertNotIn(word, panel)

    def _assert_disk_clean(self, store):
        try:
            raw = store.path.read_text()
        except Exception as exc:
            self.fail(f"reading store file raised {exc!r}")
        for word in self.PRIVATE_WORDS:
            self.assertNotIn(word, raw)

    def test_tagged_old_fact_hidden_through_full_lifecycle(self):
        session_id, store, flags = self._new_store_and_flags()
        try:
            store.add_conflict(
                "[EMOTIONAL STATE]: I feel lonely since my wife died",
                "I feel fine",
                "senior said they are lonely",
            )
        except Exception as exc:
            self.fail(f"add_conflict raised {exc!r}")
        self._assert_panel_clean(session_id)

        try:
            store.mark_conflicts_asked()
        except Exception as exc:
            self.fail(f"mark_conflicts_asked raised {exc!r}")
        self._assert_panel_clean(session_id)

        try:
            store.escalate_asked_conflicts(flags)
        except Exception as exc:
            self.fail(f"escalate_asked_conflicts raised {exc!r}")
        self._assert_panel_clean(session_id)
        self._assert_disk_clean(store)

    def test_untagged_old_fact_hidden_through_full_lifecycle(self):
        session_id, store, flags = self._new_store_and_flags()
        try:
            store.add_conflict(
                "I feel lonely since my wife died",
                "I feel fine",
                "senior said they are lonely",
            )
        except Exception as exc:
            self.fail(f"add_conflict raised {exc!r}")
        self._assert_panel_clean(session_id)

        store.mark_conflicts_asked()
        self._assert_panel_clean(session_id)

        store.escalate_asked_conflicts(flags)
        self._assert_panel_clean(session_id)
        self._assert_disk_clean(store)

    def test_private_text_only_in_new_fact_hidden_through_full_lifecycle(self):
        session_id, store, flags = self._new_store_and_flags()
        try:
            store.add_conflict(
                "Dad is doing fine",
                "I feel lonely since my wife died",
                "senior contradicted an earlier statement",
            )
        except Exception as exc:
            self.fail(f"add_conflict raised {exc!r}")
        self._assert_panel_clean(session_id)

        store.mark_conflicts_asked()
        self._assert_panel_clean(session_id)

        store.escalate_asked_conflicts(flags)
        self._assert_panel_clean(session_id)
        self._assert_disk_clean(store)

    def test_private_text_only_in_reason_hidden_through_full_lifecycle(self):
        session_id, store, flags = self._new_store_and_flags()
        try:
            store.add_conflict(
                "Dad said he is doing fine",
                "Dad said he is doing great",
                "I feel lonely since my wife died",
            )
        except Exception as exc:
            self.fail(f"add_conflict raised {exc!r}")
        self._assert_panel_clean(session_id)

        store.mark_conflicts_asked()
        self._assert_panel_clean(session_id)

        store.escalate_asked_conflicts(flags)
        self._assert_panel_clean(session_id)
        self._assert_disk_clean(store)

    def test_resolve_asked_conflicts_scrubs_disk(self):
        session_id, store, flags = self._new_store_and_flags()
        store.add_conflict(
            "I feel lonely since my wife died", "I feel fine", "senior said they are lonely"
        )
        store.mark_conflicts_asked()
        try:
            store.resolve_asked_conflicts()
        except Exception as exc:
            self.fail(f"resolve_asked_conflicts raised {exc!r}")
        self._assert_disk_clean(store)

    def test_clear_conflicts_scrubs_disk(self):
        session_id, store, flags = self._new_store_and_flags()
        store.add_conflict(
            "I feel lonely since my wife died", "I feel fine", "senior said they are lonely"
        )
        try:
            store.clear_conflicts()
        except Exception as exc:
            self.fail(f"clear_conflicts raised {exc!r}")
        self._assert_disk_clean(store)

    def test_escalation_cardinality_content_free_and_idempotent(self):
        session_id, store, flags = self._new_store_and_flags()
        store.add_conflict("Old fact A", "New fact A", "reason A")
        store.add_conflict("Old fact B", "New fact B", "reason B")
        store.mark_conflicts_asked()

        try:
            store.escalate_asked_conflicts(flags)
        except Exception as exc:
            self.fail(f"escalate_asked_conflicts raised {exc!r}")

        flag_items = flags.all()
        self.assertEqual(len(flag_items), 2)
        fixed_text = "Unresolved Memory Ambiguity: a memory question was asked and left unanswered."
        for flag in flag_items:
            self.assertEqual(flag.text, fixed_text)
            self.assertEqual(flag.severity, "info")
            self.assertFalse(flag.disclosed_to_senior)

        # Calling it again (nothing left in conflict_asked) must add no more.
        store.escalate_asked_conflicts(flags)
        self.assertEqual(len(flags.all()), 2)


if __name__ == "__main__":
    unittest.main()
