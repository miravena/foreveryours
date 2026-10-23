"""one-click "Load sample family".

A judge clicks one button before saying anything and the caregiver panel
shows a labelled-fictional senior with family, likes, a daily routine and
caregiver-entered medication REMINDER times (plain schedule items, never
dosing advice); the senior's reply prompt carries a seeded reminder; the
session-end path and the inactivity sweep delete the seed with everything
else. Fully offline: the LLM stream and TTS are stubbed.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from caregiver import (
    DEFAULT_CAREGIVER_NAME,
    DEFAULT_PROFILE_ID,
    SAMPLE_FAMILY,
    SAMPLE_FAMILY_LABEL,
    sample_family_texts,
    validate_sample_profile,
)
from memory.store import MemoryStore, PrivacyLevel

REMINDER_LINE = "Blood pressure pill, 8 AM"


def _texts(group: str) -> list[str]:
    return [t for g, t, _p in SAMPLE_FAMILY["items"] if g == group]


class TestSampleSeedAndValidator(unittest.TestCase):
    """caregiver.py: the seed itself and validate_sample_profile."""

    def test_seed_passes_validator_and_names_persona_family_likes_routine_reminder(self):
        validate_sample_profile(SAMPLE_FAMILY["items"])  # must not raise
        self.assertTrue(SAMPLE_FAMILY["senior_name"])
        self.assertIn(SAMPLE_FAMILY["senior_name"], _texts("persona")[0])
        self.assertGreaterEqual(len(_texts("family")), 2)
        self.assertGreaterEqual(len(_texts("likes")), 1)
        self.assertGreaterEqual(len(_texts("routine")), 3)
        reminders = _texts("reminder")
        self.assertIn(REMINDER_LINE, reminders)
        # Every reminder is a time-of-day schedule item ("..., 8 AM").
        for r in reminders:
            self.assertRegex(r, r"\d{1,2}(:\d{2})?\s*(AM|PM)$")
        self.assertEqual(SAMPLE_FAMILY["caregiver_name"], DEFAULT_CAREGIVER_NAME)
        self.assertEqual(sample_family_texts(), [t for _g, t, _p in SAMPLE_FAMILY["items"]])

    def test_seed_covers_meals_walk_and_visits(self):
        routine = " ".join(_texts("routine")).lower()
        for meal in ("breakfast", "lunch", "dinner"):
            self.assertIn(meal, routine)
        self.assertIn("walk", routine)
        self.assertIn("visit", routine)

    def test_identity_facts_carry_no_schedule_words(self):
        """openai_review: a family/persona/likes line that also
        says "every evening" or "visits on Saturday afternoons" is claimed by
        MemoryStore.caregiver_schedule_updates() and dropped from
        senior_profile_facts(), so "Who is my daughter?" would get nothing.
        Identity stays identity; visits and calls are routine items."""
        import re
        schedule_word = re.compile(
            r"\b(am|pm|today|tomorrow|tonight|afternoon|morning|evening|o'clock|groceries|appointment|doctor|dropping\s+off|visiting|visit)\b",
            re.IGNORECASE,
        )
        for group in ("persona", "family", "likes", "avoid"):
            for text in _texts(group):
                self.assertIsNone(schedule_word.search(text), text)

    def test_validator_accepts_allowed_examples(self):
        validate_sample_profile("Blood pressure pill, 8 AM")
        validate_sample_profile(["Blood pressure pill, 8 AM", "Evening walk, 6 PM"])
        validate_sample_profile([{"text": "Evening walk, 6 PM"}])

    def test_validator_refuses_dosing(self):
        for text in ("Take 20 mg at 8 AM", "Dose: 1 pill", "Take 2 tablets at breakfast", "5 ml of syrup"):
            with self.assertRaises(ValueError, msg=text) as ctx:
                validate_sample_profile([text])
            self.assertIn("dosing", str(ctx.exception))

    def test_validator_refuses_diagnosis(self):
        for text in ("Pill for your hypertension 8 AM", "Diagnosed with arthritis", "Pill for your blood pressure, 8 AM"):
            with self.assertRaises(ValueError, msg=text) as ctx:
                validate_sample_profile([text])
            self.assertIn("diagnosis", str(ctx.exception))

    def test_validator_refuses_clinical_claim(self):
        for text in ("This treats high blood pressure", "Eases the symptoms by noon", "This will cure his cough"):
            with self.assertRaises(ValueError, msg=text) as ctx:
                validate_sample_profile([text])
            self.assertIn("clinical claim", str(ctx.exception))

    def test_validator_refuses_combined_dosing_and_diagnosis_line(self):
        with self.assertRaises(ValueError):
            validate_sample_profile(["Take 2 tablets of 20 mg lisinopril for your hypertension at 8 AM"])


class _SessionCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.sessions_dir = Path(self.temp_dir.name) / "sessions"
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", self.sessions_dir),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()
        webapp._request_log.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def _store(self, session_id: str) -> MemoryStore:
        data_dir, _ = webapp._session_dirs(session_id)
        return MemoryStore(DEFAULT_PROFILE_ID, data_dir)


class TestLoadSampleFamily(_SessionCase):
    """webapp.load_sample_family + _format_caregiver_panel."""

    def test_panel_shows_fictional_label_and_reminder_line_before_any_utterance(self):
        session_id, panel_before = webapp.init_session()
        self.assertNotIn("Fictional sample data", panel_before)
        panel, returned_id = webapp.load_sample_family(session_id)
        self.assertEqual(returned_id, session_id)
        self.assertIn("Fictional sample data", panel)
        self.assertIn(SAMPLE_FAMILY_LABEL, panel)
        self.assertIn(REMINDER_LINE, panel)
        self.assertIn("8 AM", panel)
        # The reminder is a plain schedule line attributed to the caregiver by name.
        self.assertIn(f"{REMINDER_LINE} _(reminder set by {DEFAULT_CAREGIVER_NAME})_", panel)
        for word in ("mg", "dose", "tablet", "diagnos", "treat"):
            self.assertNotIn(word, panel.lower().replace("medical/safety", ""))
        # Persona, family, likes, routine all visible.
        self.assertIn(SAMPLE_FAMILY["senior_name"], panel)
        self.assertIn("Leo", panel)
        self.assertIn("jazz", panel)
        self.assertIn("Evening walk, 6 PM", panel)
        # Live poll of the same session shows the same card (reads from disk).
        self.assertIn("Fictional sample data", webapp._format_caregiver_panel(session_id))

    def test_panel_lists_each_seed_fact_once(self):
        session_id, _ = webapp.init_session()
        panel, _ = webapp.load_sample_family(session_id)
        for text in sample_family_texts():
            self.assertEqual(panel.count(text), 1, text)

    def test_panel_on_none_session_creates_one(self):
        panel, session_id = webapp.load_sample_family(None)
        self.assertTrue(session_id)
        self.assertIn("Fictional sample data", panel)

    def test_second_click_is_idempotent(self):
        session_id, _ = webapp.init_session()
        webapp.load_sample_family(session_id)
        count_after_first = len(self._store(session_id).all())
        panel2, _ = webapp.load_sample_family(session_id)
        self.assertEqual(len(self._store(session_id).all()), count_after_first)
        self.assertEqual(panel2.count(REMINDER_LINE), 1)

    def test_seed_items_are_caregiver_sourced_with_declared_privacy(self):
        session_id, _ = webapp.init_session()
        webapp.load_sample_family(session_id)
        by_text = {i.text: i for i in self._store(session_id).all()}
        for _group, text, privacy in SAMPLE_FAMILY["items"]:
            self.assertIn(text, by_text)
            self.assertEqual(by_text[text].source, "caregiver_memo")
            expected = PrivacyLevel.CAREGIVER_ONLY.value if privacy == "caregiver_only" else PrivacyLevel.PUBLIC_TO_SENIOR.value
            self.assertEqual(by_text[text].privacy, expected, text)

    def test_loader_validates_before_writing_anything(self):
        session_id, _ = webapp.init_session()
        baseline = [i.text for i in self._store(session_id).all()]
        bad_seed = dict(SAMPLE_FAMILY)
        bad_seed["items"] = (
            ("routine", "Evening walk, 6 PM", "public"),
            ("reminder", "Take 2 tablets of 20 mg at 8 AM", "public"),
        )
        with patch.object(webapp, "SAMPLE_FAMILY", bad_seed):
            with self.assertRaises(ValueError):
                webapp.load_sample_family(session_id)
        self.assertEqual([i.text for i in self._store(session_id).all()], baseline)
        self.assertNotIn("Fictional sample data", webapp._format_caregiver_panel(session_id))

    def test_fresh_session_shows_no_sample_profile(self):
        seeded, _ = webapp.init_session()
        webapp.load_sample_family(seeded)
        fresh = webapp._new_session()
        self.assertNotEqual(fresh, seeded)
        panel = webapp._format_caregiver_panel(fresh)
        self.assertNotIn("Fictional sample data", panel)
        self.assertNotIn(REMINDER_LINE, panel)

    def test_two_simultaneous_sessions_stay_isolated(self):
        a, _ = webapp.init_session()
        b, _ = webapp.init_session()
        webapp.load_sample_family(a)
        self.assertIn("Fictional sample data", webapp._format_caregiver_panel(a))
        self.assertNotIn("Fictional sample data", webapp._format_caregiver_panel(b))
        self.assertNotIn(REMINDER_LINE, [i.text for i in self._store(b).all()])
        webapp._end_session(a)
        self.assertFalse((self.sessions_dir / a).exists())
        self.assertTrue((self.sessions_dir / b).exists())


class TestSeniorSideRecall(_SessionCase):
    def test_senior_context_contains_seeded_reminder(self):
        """The reply prompt built for the senior's next turn carries the
        seeded reminder via memory_store.caregiver_schedule_updates (no live
        model: think.stream_reply and TTS are stubbed)."""
        session_id, _ = webapp.init_session()
        webapp.load_sample_family(session_id)
        store = self._store(session_id)
        self.assertIn(REMINDER_LINE, store.caregiver_schedule_updates())
        self.assertIn("Evening walk, 6 PM", store.caregiver_schedule_updates())
        facts = store.senior_profile_facts()
        self.assertIn(_texts("persona")[0], facts)
        for text in _texts("family") + _texts("likes"):
            self.assertIn(text, facts, "identity fact must be recallable, not swallowed as a schedule item")
        self.assertTrue(any("daughter" in f.lower() for f in facts))
        self.assertFalse(any("daughter" in u.lower() for u in store.caregiver_schedule_updates()))
        captured = {}

        def fake_stream(transcript, facts, **kwargs):
            captured["transcript"] = transcript
            captured["facts"] = facts
            captured.update(kwargs)
            return iter(["Your blood pressure pill is at 8 AM, Walter."])

        with patch("pipeline.orchestrator.think.stream_reply", side_effect=fake_stream), \
             patch("pipeline.orchestrator._speak_turn", return_value=("", [], 0.0)), \
             patch.object(webapp.hear, "transcribe", return_value=("What time is my pill today?", {"wpm": 0.0, "avg_pause_s": 0.0})):
            webapp.run_demo_turn("fake.wav", [], session_id)
        self.assertEqual(captured.get("transcript"), "What time is my pill today?")
        self.assertIn(REMINDER_LINE, captured.get("caregiver_updates") or [])
        # The caregiver-only health note never reaches the senior's prompt.
        private = [t for _g, t, p in SAMPLE_FAMILY["items"] if p == "caregiver_only"]
        prompt_blob = " ".join((captured.get("caregiver_updates") or []) + list(captured.get("facts") or []))
        for text in private:
            self.assertNotIn(text, prompt_blob)


class TestResetAndSweep(_SessionCase):
    def test_end_session_removes_seeded_dir(self):
        session_id, _ = webapp.init_session()
        webapp.load_sample_family(session_id)
        root = self.sessions_dir / session_id
        self.assertTrue((root / "data" / f"{DEFAULT_PROFILE_ID}.json").exists())
        webapp._end_session(session_id)
        self.assertFalse(root.exists())

    def test_sweep_removes_aged_seeded_dir(self):
        session_id, _ = webapp.init_session()
        webapp.load_sample_family(session_id)
        root = self.sessions_dir / session_id
        stale = time.time() - webapp.SESSION_TTL_S - 60
        os.utime(root, (stale, stale))
        webapp._sweep_stale_sessions()
        self.assertFalse(root.exists())
        # And the next visitor starts clean.
        fresh = webapp._new_session()
        self.assertNotIn("Fictional sample data", webapp._format_caregiver_panel(fresh))


class TestBuildDemoWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = webapp.build_demo().get_config_file()
        cls.components = {c["id"]: c for c in cls.config["components"]}

    def _find(self, type_, **props):
        hits = [
            c for c in self.config["components"]
            if c["type"] == type_ and all(c["props"].get(k) == v for k, v in props.items())
        ]
        self.assertEqual(len(hits), 1, (type_, props, len(hits)))
        return hits[0]

    def _parent_of(self, target_id):
        def walk(node, parent):
            if node["id"] == target_id:
                return parent
            for child in node.get("children", []):
                found = walk(child, node)
                if found is not None:
                    return found
            return None
        return walk(self.config["layout"], None)

    def _panel_id(self):
        # The caregiver panel is the Markdown whose initial value is the
        # no-session placeholder and which init_session writes to.
        placeholder = webapp._format_caregiver_panel(None)
        md = [c for c in self.config["components"] if c["type"] == "markdown" and c["props"].get("value") == placeholder]
        self.assertEqual(len(md), 1)
        return md[0]["id"]

    def test_button_exists_in_build_demo(self):
        self._find("button", value="Load sample family")

    def test_click_is_wired_with_session_state_in_and_caregiver_panel_out(self):
        btn = self._find("button", value="Load sample family")
        deps = [d for d in self.config["dependencies"] if any(t[0] == btn["id"] and t[1] == "click" for t in d["targets"])]
        self.assertEqual(len(deps), 1)
        dep = deps[0]
        self.assertEqual(dep["api_name"], "load_sample_family")
        state_ids = {c["id"] for c in self.config["components"] if c["type"] == "state"}
        self.assertTrue(set(dep["inputs"]) & state_ids, "session-id gr.State must be an input")
        self.assertIn(self._panel_id(), dep["outputs"])
        # The session state is also an output so a None session gets its new id back.
        self.assertTrue(set(dep["outputs"]) & state_ids)

    def test_button_sits_in_caregiver_column_and_split_screen_is_unchanged(self):
        btn = self._find("button", value="Load sample family")
        panel_id = self._panel_id()
        btn_parent = self._parent_of(btn["id"])
        self.assertIsNotNone(btn_parent)
        self.assertEqual(btn_parent["id"], self._parent_of(panel_id)["id"], "button must live in the caregiver column")
        self.assertEqual(self.components[btn_parent["id"]]["type"], "column")
        # The hero split-screen: exactly one top-level Row with exactly two Columns.
        top_rows = [n for n in self.config["layout"]["children"] if self.components[n["id"]]["type"] == "row"]
        self.assertEqual(len(top_rows), 1)
        cols = [n for n in top_rows[0]["children"] if self.components[n["id"]]["type"] == "column"]
        self.assertEqual(len(cols), 2)
        self.assertEqual(cols[1]["id"], btn_parent["id"], "caregiver column is the right-hand column")
        # Order inside the caregiver column: panel, then the button, then the memo accordion.
        child_ids = [n["id"] for n in btn_parent["children"]]
        accordion_ids = [i for i in child_ids if self.components[i]["type"] == "accordion"]
        self.assertLess(child_ids.index(panel_id), child_ids.index(btn["id"]))
        self.assertLess(child_ids.index(btn["id"]), child_ids.index(accordion_ids[0]))


if __name__ == "__main__":
    unittest.main()
