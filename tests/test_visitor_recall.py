"""Live judge turns T01/T07 "Is anyone coming by today?" (#229).

The hosted model sometimes invented a visitor (the grandson at noon) or
dropped Sarah's time. The orchestrator now answers a visitor question from the
caregiver's visit updates itself, so the reply is the same every time and THINK
is never asked. These tests run offline with the hosted model stubbed to the
failing replies from the live runs.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline.intent import Intent, detect_intent, is_visitor_question
from pipeline.orchestrator import run_turn
from tests.test_offer_briefed_topic import _CapturingClient, _speak_joined

QUESTIONS = (
    "Is anyone coming by today?",
    "Is anybody coming over this afternoon?",
    "Is someone stopping by today?",
    "Who is coming today?",
    "Any visitors today?",
    "Is anybody dropping in?",
)


class TestVisitorQuestionDetector(unittest.TestCase):
    def test_visitor_questions(self):
        for q in QUESTIONS:
            with self.subTest(q=q):
                self.assertTrue(is_visitor_question(q))
                self.assertEqual(detect_intent(q), Intent.LOGISTICAL)

    def test_other_turns_are_not_visitor_questions(self):
        for q in ("What's my grandson's name?", "Is Sarah listening to us?", "What kind of music do I like?", "Who is my son?", ""):
            with self.subTest(q=q):
                self.assertFalse(is_visitor_question(q))


class TestVisitorAnswerIsGrounded(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        (root / "data").mkdir()
        (root / "audio").mkdir()
        self.audio_dir = root / "audio"
        self.store = MemoryStore("test_dad", root / "data")
        self.flags = CaregiverFlags("test_dad", root / "data")
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")
        self.store.add("I'm dropping off groceries at 4 PM today", source="caregiver_memo")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, transcript, bad_reply):
        client = _CapturingClient(bad_reply)
        with patch("pipeline.think.get_client", return_value=client), \
             patch("pipeline.orchestrator._speak_turn", side_effect=_speak_joined):
            res = run_turn(transcript=transcript, memory_store=self.store, flags=self.flags,
                           audio_out_dir=self.audio_dir, caregiver_name="Sarah")
        if res.background_thread:
            res.background_thread.join(timeout=10)
        return client, res

    def test_failing_live_replies_cannot_reach_the_senior(self):
        for bad in ("Your son Leo is stopping by around noon to visit.",
                    "Your family is planning to stop by this afternoon."):
            for q in QUESTIONS[:4]:
                with self.subTest(q=q, bad=bad):
                    client, res = self._run(q, bad)
                    self.assertIsNone(client.messages, "THINK should not be asked")
                    self.assertIn("Sarah is dropping off groceries at 4 PM today", res.reply_text)
                    self.assertNotIn("Leo", res.reply_text)
                    self.assertNotIn("noon", res.reply_text)

    def test_no_visit_update_falls_back_to_think(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            store = MemoryStore("empty_dad", root / "data")
            client = _CapturingClient("I don't have any visitors noted for today.")
            with patch("pipeline.think.get_client", return_value=client), \
                 patch("pipeline.orchestrator._speak_turn", side_effect=_speak_joined):
                run_turn(transcript=QUESTIONS[0], memory_store=store,
                         flags=CaregiverFlags("empty_dad", root / "data"),
                         audio_out_dir=self.audio_dir, caregiver_name="Sarah")
            self.assertIsNotNone(client.messages)


if __name__ == "__main__":
    unittest.main()
