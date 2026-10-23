"""Guided interview mode (#206): the memo box's behaviour (pinned before the
shared save helper was extracted), the interview handlers, and the sweep.
Fully offline: no model call, no key."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from caregiver import DEFAULT_PROFILE_ID, INTERVIEW_QUESTIONS
from memory.store import MemoryStore


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

    def _store(self, session_id):
        data_dir, _ = webapp._session_dirs(session_id)
        return MemoryStore(DEFAULT_PROFILE_ID, data_dir)

    def _caregiver_items(self, session_id):
        return [i for i in self._store(session_id).all() if i.source == "caregiver_memo" and i.status == "active"]

    def _new_texts(self, session_id, before):
        """Active caregiver texts added since `before` (init_session pre-briefs a demo memo)."""
        return sorted(i.text for i in self._caregiver_items(session_id) if i.text not in before)

    def _bound(self, sid):
        return webapp._interview_new_state(webapp._interview_binding(sid))

    def _fresh(self):
        sid, _ = webapp.init_session()
        return sid, {i.text for i in self._caregiver_items(sid)}


class TestMemoBoxUnchanged(_SessionCase):
    """Regression for the helper extraction: the memo box saves, splits,
    supersedes, ignores empty text and refuses a swept session as before."""

    def test_memo_is_split_into_facts_and_returns_panel_id_and_empty_box(self):
        sid, before = self._fresh()
        panel, out_sid, box = webapp.save_caregiver_text_memo("Dad loves soup. Sarah calls at 8 PM.", sid)
        self.assertEqual(out_sid, sid)
        self.assertEqual(box, "")
        self.assertIn("Dad loves soup", panel)
        self.assertEqual(self._new_texts(sid, before), ["Dad loves soup", "Sarah calls at 8 PM"])

    def test_memo_update_supersedes_the_old_fact(self):
        sid, before = self._fresh()
        webapp.save_caregiver_text_memo("Blood pressure pill, 8 AM", sid)
        webapp.save_caregiver_text_memo("Blood pressure pill, 9 AM", sid)
        self.assertEqual(self._new_texts(sid, before), ["Blood pressure pill, 9 AM"])

    def test_blank_memo_writes_nothing(self):
        sid, before = self._fresh()
        webapp.save_caregiver_text_memo("   ", sid)
        self.assertEqual(self._new_texts(sid, before), [])

    def test_memo_box_still_does_not_validate_medical_content(self):
        # The plain memo box is out of scope for #206; only the interview validates.
        sid, before = self._fresh()
        webapp.save_caregiver_text_memo("Dad takes 5 mg daily", sid)
        self.assertEqual(self._new_texts(sid, before), ["Dad takes 5 mg daily"])

    def test_swept_session_is_refused_and_text_handed_back(self):
        sid, _ = webapp.init_session()
        webapp._end_session(sid)
        panel, new_sid, box = webapp.save_caregiver_text_memo("Dad loves soup.", sid)
        self.assertNotEqual(new_sid, sid)
        self.assertEqual(box, "Dad loves soup.")
        self.assertFalse((self.sessions_dir / sid).exists())


class TestInterviewHandlers(_SessionCase):
    def _confirm(self, answer, state, sid):
        return webapp.interview_confirm(answer, state, sid)

    def test_every_question_saves_in_its_declared_scope(self):
        sid, before = self._fresh()
        state = webapp._interview_new_state()
        for q in INTERVIEW_QUESTIONS:
            n = len(self._caregiver_items(sid))
            _panel, sid, state, _md, box = self._confirm(q["example"], state, sid)
            self.assertEqual(box, "")
            new = self._caregiver_items(sid)[n:]
            self.assertTrue(new, q["key"])
            self.assertEqual({i.scope for i in new}, {q["scope"]}, q["key"])
            self.assertTrue(all(i.privacy == "public" for i in new))
        self.assertEqual(state["answered"], [q["key"] for q in INTERVIEW_QUESTIONS])
        self.assertIn("5 of 5 answered, 0 skipped", webapp._render_interview(state))

    def test_bare_avoid_topics_become_guardrails(self):
        # Codex review: "Politics" answered to "topics to avoid" was saved as an
        # ordinary fact, so the companion could raise it. It must be a guardrail.
        sid, before = self._fresh()
        state = self._bound(sid)
        keys = [q["key"] for q in INTERVIEW_QUESTIONS]
        state["answered"] = keys[:keys.index("avoid")]
        self._confirm("Politics. His late wife.", state, sid)
        self.assertEqual(self._new_texts(sid, before),
                         ["Avoid talking about his late wife", "Avoid talking about politics"])
        guardrails = self._store(sid).caregiver_guardrails()
        self.assertTrue(any("politics" in g for g in guardrails), guardrails)
        self.assertTrue(any("late wife" in g for g in guardrails), guardrails)

    def test_avoid_answer_with_its_own_guardrail_word_is_kept(self):
        from caregiver import interview_answer_memo
        self.assertEqual(interview_answer_memo("avoid", "Never mention the fall"), "Never mention the fall.")
        self.assertEqual(interview_answer_memo("likes", "Politics"), "Politics")

    def test_answer_saves_exactly_as_a_typed_memo_would(self):
        a, _ = webapp.init_session()
        b, _ = webapp.init_session()
        text = "Dad loves jazz. He enjoys chicken soup."
        self._confirm(text, webapp._interview_new_state(), a)
        webapp.save_caregiver_text_memo(text, b)
        key = lambda sid: sorted((i.text, i.scope, i.privacy) for i in self._caregiver_items(sid))
        self.assertEqual(key(a), key(b))

    def test_interview_answer_supersedes_like_a_memo(self):
        sid, before = self._fresh()
        state = webapp._interview_new_state()
        webapp.save_caregiver_text_memo("Blood pressure pill, 8 AM", sid)
        state["answered"] = [q["key"] for q in INTERVIEW_QUESTIONS[:4]]  # next is "reminder"
        self._confirm("Blood pressure pill, 9 AM", state, sid)
        self.assertEqual(self._new_texts(sid, before), ["Blood pressure pill, 9 AM"])

    def test_refused_answer_is_shown_and_not_saved(self):
        sid, before = self._fresh()
        state = self._bound(sid)
        for bad in ("Dad takes 20 mg every morning", "He was diagnosed with something", "This pill treats his heart"):
            with self.subTest(bad=bad):
                _panel, sid, state, md, box = self._confirm(bad, state, sid)
                self.assertIn("Not saved", md)
                self.assertEqual(box, bad)  # kept for editing
                self.assertEqual(state, self._bound(sid))  # question still open
                self.assertEqual(self._new_texts(sid, before), [])
        self.assertIn("Question 1 of 5", md)

    def test_blank_answer_saves_nothing_and_does_not_advance(self):
        sid, before = self._fresh()
        _p, sid, state, md, _b = self._confirm("  ", webapp._interview_new_state(), sid)
        self.assertEqual(state["answered"], [])
        self.assertIn("Type an answer", md)
        self.assertEqual(self._new_texts(sid, before), [])

    def test_skip_saves_nothing_and_unskippable_cannot_be_skipped(self):
        sid, before = self._fresh()
        state, md = webapp.interview_skip(self._bound(sid), sid)  # question 1 is required
        self.assertEqual(state["skipped"], [])
        self.assertIn("can't be skipped", md)
        _p, sid, state, _m, _b = self._confirm("Sarah is his daughter.", state, sid)
        state, md = webapp.interview_skip(state, sid)
        self.assertEqual(state["skipped"], ["likes"])
        self.assertIn("1 of 5 answered, 1 skipped", md)
        self.assertEqual(self._new_texts(sid, before), ["Sarah is his daughter"])

    def test_resume_does_not_reask_answered_questions(self):
        sid, _ = webapp.init_session()
        _p, sid, state, _m, _b = self._confirm("Sarah is his daughter.", self._bound(sid), sid)
        state, _ = webapp.interview_skip(state, sid)
        # Leave and come back, including a state with a stale or hostile index.
        state["index"] = 0
        state, md = webapp.interview_next(state, sid)
        self.assertIn("Question 3 of 5", md)
        self.assertNotIn(INTERVIEW_QUESTIONS[0]["prompt"], md)
        self.assertNotIn(INTERVIEW_QUESTIONS[1]["prompt"], md)
        # Confirming now answers question 3, never question 1 again.
        _p, sid, state, _m, _b = self._confirm("He walks after breakfast.", state, sid)
        self.assertEqual(state["answered"], ["family", "routine"])

    def test_garbage_state_is_reset_safely(self):
        for junk in (None, "x", {"answered": "family"}, {"answered": [1, None, "nope"], "skipped": None}):
            with self.subTest(junk=junk):
                state, md = webapp.interview_next(junk)
                self.assertEqual(state, webapp._interview_new_state())
                self.assertIn("Question 1 of 5", md)

    def test_time_without_am_pm_is_still_temporary_for_the_schedule_question(self):
        sid, before = self._fresh()
        state = {"answered": [q["key"] for q in INTERVIEW_QUESTIONS[:4]], "skipped": [], "sid": webapp._interview_binding(sid)}
        self._confirm("Sarah visits at 15:00", state, sid)
        new = [i for i in self._caregiver_items(sid) if i.text not in before]
        self.assertEqual([(i.text, i.scope) for i in new], [("Sarah visits at 15:00", "temporary")])

    def test_refused_or_blank_answer_never_recreates_a_swept_household(self):
        for answer in ("Dad takes 20 mg", "  "):
            with self.subTest(answer=answer):
                sid, _ = webapp.init_session()
                webapp._end_session(sid)
                _p, new_sid, state, md, box = self._confirm(answer, webapp._interview_new_state(), sid)
                self.assertNotEqual(new_sid, sid)
                self.assertFalse((self.sessions_dir / sid).exists())
                self.assertEqual(box, answer)

    def test_state_from_a_swept_household_is_a_fresh_interview(self):
        for reset in ("memo", "voice", "sample"):
            with self.subTest(reset=reset):
                sid, _ = webapp.init_session()
                _p, sid, state, _m, _b = self._confirm("Sarah is his daughter.", self._bound(sid), sid)
                self.assertEqual(state["answered"], ["family"])
                webapp._end_session(sid)
                if reset == "memo":
                    new_sid = webapp.save_caregiver_text_memo("Dad loves soup.", sid)[1]
                elif reset == "voice":
                    new_sid = webapp.save_caregiver_voice_memo(os.path.join(tempfile.gettempdir(), "fake.wav"), sid)[1]
                else:
                    new_sid = webapp.load_sample_family(sid)[1]
                if reset != "sample":  # the loader recreates the household under the same id
                    self.assertNotEqual(new_sid, sid)
                state2, md = webapp.interview_next(state, new_sid)
                self.assertEqual(state2["answered"], [])
                self.assertIn("0 of 5 answered", md)
                self.assertIn("Question 1 of 5", md)
                refreshed, refreshed_md = webapp.interview_refresh(state, new_sid)
                self.assertEqual(refreshed["answered"], [])
                self.assertIn("0 of 5 answered", refreshed_md)

    def test_refresh_leaves_a_matching_state_alone(self):
        sid, _ = webapp.init_session()
        state = self._bound(sid)
        out_state, out_md = webapp.interview_refresh(state, sid)
        self.assertEqual(out_state, {"__type__": "update"})  # gr.skip(): nothing overwritten

    def test_refusal_notice_is_escaped_and_fits_every_question(self):
        sid, _ = webapp.init_session()
        evil = "<img src=x onerror=alert(1)> 20 mg"
        for q in INTERVIEW_QUESTIONS:
            state = {"answered": [k["key"] for k in INTERVIEW_QUESTIONS if k is not q], "skipped": [], "sid": webapp._interview_binding(sid)}
            _p, _s, _st, md, box = self._confirm(evil, state, sid)
            self.assertNotIn("<img", md)
            self.assertNotIn("reminders only", md)
            self.assertIn("Not saved", md)
            self.assertEqual(box, evil)
        _p, _s, _st, md, _b = self._confirm("He had a <b>diagnosis</b>", self._bound(sid), sid)
        self.assertNotIn("<b>", md)

    def test_swept_session_refuses_the_save_and_keeps_the_answer(self):
        sid, _ = webapp.init_session()
        webapp._end_session(sid)
        _p, new_sid, state, md, box = self._confirm("Sarah is his daughter.", webapp._interview_new_state(), sid)
        self.assertNotEqual(new_sid, sid)
        self.assertEqual(box, "Sarah is his daughter.")
        self.assertFalse((self.sessions_dir / sid).exists())
        self.assertEqual(state, self._bound(new_sid))

    def test_no_model_call_and_no_senior_turn(self):
        sid, _ = webapp.init_session()
        with patch.object(webapp, "run_turn", side_effect=AssertionError("senior turn")), \
                patch.dict(os.environ, {"NEBIUS_API_KEY": ""}):
            state = webapp._interview_new_state()
            for q in INTERVIEW_QUESTIONS:
                _p, sid, state, _m, _b = self._confirm(q["example"], state, sid)
        self.assertEqual(len(state["answered"]), 5)

    def test_end_session_removes_the_interview_memos(self):
        sid, before = self._fresh()
        state = webapp._interview_new_state()
        for q in INTERVIEW_QUESTIONS:
            _p, sid, state, _m, _b = self._confirm(q["example"], state, sid)
        root = self.sessions_dir / sid
        self.assertTrue((root / "data" / f"{DEFAULT_PROFILE_ID}.json").exists())
        webapp._end_session(sid)
        self.assertFalse(root.exists())

    def test_sweep_removes_aged_interview_session(self):
        sid, _ = webapp.init_session()
        self._confirm(INTERVIEW_QUESTIONS[0]["example"], webapp._interview_new_state(), sid)
        root = self.sessions_dir / sid
        stale = time.time() - webapp.SESSION_TTL_S - 60
        os.utime(root, (stale, stale))
        webapp._sweep_stale_sessions()
        self.assertFalse(root.exists())


class TestInterviewWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = webapp.build_demo().get_config_file()

    def _dep(self, api_name):
        deps = [d for d in self.config["dependencies"] if d["api_name"] == api_name]
        self.assertEqual(len(deps), 1, api_name)
        return deps[0]

    def test_handlers_are_wired_and_confirm_updates_the_caregiver_panel(self):
        for name in ("interview_next", "interview_skip", "interview_confirm"):
            self._dep(name)
        confirm = self._dep("interview_confirm")
        placeholder = webapp._format_caregiver_panel(None)
        panel = [c["id"] for c in self.config["components"] if c["type"] == "markdown" and c["props"].get("value") == placeholder]
        self.assertEqual(len(panel), 1)
        self.assertIn(panel[0], confirm["outputs"])

    def test_interview_lives_in_the_caregiver_column_not_the_senior_one(self):
        confirm = self._dep("interview_confirm")
        panel_id = confirm["outputs"][0]

        def chain(node, target, path=()):
            if node["id"] == target:
                return path
            for child in node.get("children", []):
                found = chain(child, target, path + (node["id"],))
                if found is not None:
                    return found
            return None

        layout = self.config["layout"]
        interview_btn = confirm["targets"][0][0]
        a, b = chain(layout, interview_btn), chain(layout, panel_id)
        # Same column as the caregiver panel: the deepest shared column is its parent.
        self.assertEqual(a[: len(b)], b)


if __name__ == "__main__":
    unittest.main()
