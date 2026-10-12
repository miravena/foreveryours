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


if __name__ == "__main__":
    unittest.main()
