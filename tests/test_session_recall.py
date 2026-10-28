"""Fixes #230: "What did I just tell you?" must reach THINK with the previous
turn's disclosure in the context it is given, while the disclosure stays off
the caregiver panel."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import webapp
from pipeline import think
from tests.test_late_disclosure import LateDisclosureHarness

DISCLOSURE = "Between you and me, I've been hiding chocolate biscuits in the sock drawer."


class TestSessionRecall(LateDisclosureHarness):
    extract_result = None

    def _turn(self, text, history, sid, prompts):
        real_build = think.build_prompt

        def spy_stream(transcript, facts, **kw):
            msgs = real_build(transcript, facts, **kw)
            prompts.append(msgs)
            return iter(["Okay."])

        with patch("pipeline.orchestrator.think.stream_reply", side_effect=spy_stream), \
             patch("pipeline.orchestrator.audit.audit_reply", return_value=("SAFE", "")):
            outs = list(webapp.run_demo_turn_streaming(None, text, history, sid))
        webapp._join_previous_turn(outs[-1][5])
        return outs[-1]

    def test_t19_think_context_contains_t18_disclosure(self):
        prompts: list = []
        last = self._turn(DISCLOSURE, [], None, prompts)
        history, sid = last[2], last[5]
        last = self._turn("What did I just tell you?", history, sid, prompts)
        msgs = prompts[-1]
        convo = [m for m in msgs if m["role"] != "system"]
        self.assertIn("sock drawer", " ".join(m["content"] for m in convo))
        # THINK is pointed at the disclosure and told the rules do not forbid recalling it
        final_user = msgs[-1]["content"]
        self.assertIn("sock drawer", final_user)
        self.assertIn("THIS CONVERSATION IS NOT A STORED MEMORY", msgs[0]["content"])
        # privacy: nothing about it on the caregiver panel
        self.assertNotIn("biscuit", str(last[3]).lower())
        self.assertNotIn("sock drawer", str(last[3]).lower())





class TestRecallNote(unittest.TestCase):
    def test_only_recall_questions_get_a_note(self):
        from pipeline.orchestrator import _session_recall_note
        hist = [{"role": "user", "content": DISCLOSURE}, {"role": "assistant", "content": "Ah."}]
        for q in ("What did I just tell you?", "what did I say earlier", "Do you remember what I told you?"):
            self.assertIn("sock drawer", _session_recall_note(q, hist) or "", q)
        self.assertIsNone(_session_recall_note("How is the weather?", hist))
        self.assertIsNone(_session_recall_note("What did I just tell you?", []))
