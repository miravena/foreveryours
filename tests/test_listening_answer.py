"""Live judge turns T05 "Is Sarah listening to us?" and T06 "Can Sarah hear what I tell you?".

The hosted model sometimes answers "Sarah can't hear our conversation, but she
does see safety flags if I send any": true, but without the "only" that rule 19
and the judge check require. The orchestrator now answers a listening question
itself with fixed text, as it does for "Is anyone coming by today?", so THINK is
never asked. The fast path still wins on a safety turn. Offline: the hosted
model is stubbed to the failing live reply.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline.intent import is_listening_question
from pipeline.orchestrator import _LISTENING_ANSWER, _listening_answer, run_turn
from tests.test_offer_briefed_topic import _CapturingClient, _speak_joined

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("live_judge_check", ROOT / "scripts" / "live_judge_check.py")
ljc = importlib.util.module_from_spec(_spec)
sys.modules["live_judge_check"] = ljc
_spec.loader.exec_module(ljc)

LIVE_FAILING_REPLY = "Sarah can't hear our conversation, but she does see safety flags if I send any."

POSITIVES = (
    "Is Sarah listening to us?",
    "Can Sarah hear what I tell you?",
    "is sarah listening",
    "Is Sarah always listening?",
    "Is anyone listening in?",
    "Is somebody listening in on us?",
    "Is my family listening?",
    "Is my daughter listening to our conversation?",
    "Can anyone hear us?",
    "Can Sarah hear me?",
    "Can Sarah see what I say?",
    "Can Sarah listen in?",
    "Does Sarah know what I tell you?",
    "Does Sarah hear everything I say?",
    "Is Sarah hearing this?",
    "Is Sarah watching me?",
    "Are you reporting to Sarah?",
    "Are you telling Sarah everything?",
    "Are you telling Sarah what I say?",
    # a different caregiver name: the detector is not tied to "Sarah"
    "Is Margaret listening to us?",
    "Can Priya hear what I tell you?",
    "Are you sharing what I say with Sarah?",
    "Is she listening in?",
)

# With the caregiver's name known (as in the app) the third party must be her,
# family, "anyone" or she/he/they: a company or device is a different question.
COMPANY_QUESTIONS = (
    "Is Google listening to us?",
    "Is Alexa listening?",
    "Can Nebius hear what I tell you?",
    "Are you sharing what I say with Nebius?",
    "Are you reporting to Nebius?",
    "Are you sending everything to the cloud?",
)

NEGATIVES = (
    "",
    "Don't tell Sarah about the biscuits",
    "Please don't tell Sarah what I said.",
    "Between you and me, I've been hiding chocolate biscuits in the sock drawer.",
    "Will you tell Sarah about the biscuits?",
    "Are you telling Sarah about the party?",
    "Are you listening?",
    "Can you hear me?",
    "Are you recording?",
    "Are you recording this for Sarah?",  # audio is kept briefly (docs/PRIVACY.md): THINK answers
    "Are you recording me?",
    "Does Sarah know what time it is?",
    "Does Sarah know about my appointment?",
    "Is Sarah coming today?",
    "Is anyone coming by today?",
    "Is Sarah watching the game?",
    "Is Sarah hearing aid fixed?",
    "Can Sarah see the garden?",
    "I like listening to jazz.",
    "What's my grandson's name?",
    "What kind of music do I like?",
)


class TestListeningQuestionDetector(unittest.TestCase):
    def test_listening_questions(self):
        for q in POSITIVES:
            with self.subTest(q=q):
                name = next((n for n in ("Margaret", "Priya") if n in q), "Sarah")
                self.assertTrue(is_listening_question(q, name))

    def test_listening_questions_without_a_known_name(self):
        for q in POSITIVES:
            if "Sarah" in q and q.startswith("Are you"):
                continue  # "Are you telling Sarah ..." needs the name (or a family word)
            with self.subTest(q=q):
                self.assertTrue(is_listening_question(q))

    def test_company_and_device_questions_are_not_listening_questions(self):
        for q in COMPANY_QUESTIONS:
            with self.subTest(q=q):
                self.assertFalse(is_listening_question(q, "Sarah"))

    def test_other_turns_are_not_listening_questions(self):
        for q in NEGATIVES:
            with self.subTest(q=q):
                self.assertFalse(is_listening_question(q))
                self.assertFalse(is_listening_question(q, "Sarah"))


class TestCannedTextMeetsTheJudgeCheck(unittest.TestCase):
    def test_canned_answer_passes_every_listening_check_for_t05_and_t06(self):
        for name in ("Sarah", "Margaret"):
            text = _listening_answer(f"Is {name} listening to us?", name)
            self.assertIn(name, text)
            turns = [t for g in ljc.build_groups() for t in g.turns if t.id in ("T05", "T06")]
            self.assertEqual(len(turns), 2)
            for turn in turns:
                for check in turn.checks:
                    if getattr(check, "target", None) != "reply":
                        continue
                    with self.subTest(name=name, turn=turn.id):
                        self.assertIsNone(check(text, {}, {}), text)

    def test_the_failing_live_reply_does_fail_the_check(self):
        # Guards the test itself: the check really does reject the model's wording.
        failures = [check(LIVE_FAILING_REPLY, {}, {}) for check in ljc.listening_checks()
                    if getattr(check, "target", None) == "reply"]
        self.assertTrue(any(failures), failures)

    def test_no_answer_for_other_turns(self):
        self.assertIsNone(_listening_answer("Is anyone coming by today?", "Sarah"))
        self.assertIsNone(_listening_answer("Don't tell Sarah about the biscuits", "Sarah"))


class TestListeningTurn(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        (root / "data").mkdir()
        (root / "audio").mkdir()
        self.audio_dir = root / "audio"
        self.store = MemoryStore("test_dad", root / "data")
        self.flags = CaregiverFlags("test_dad", root / "data")
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("I'm dropping off groceries at 4 PM today", source="caregiver_memo")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, transcript, reply=LIVE_FAILING_REPLY, history=None):
        client = _CapturingClient(reply)
        with patch("pipeline.think.get_client", return_value=client), \
             patch("pipeline.orchestrator._speak_turn", side_effect=_speak_joined):
            res = run_turn(transcript=transcript, memory_store=self.store, flags=self.flags,
                           audio_out_dir=self.audio_dir, caregiver_name="Sarah", history=history)
        if res.background_thread:
            res.background_thread.join(timeout=10)
        return client, res

    def test_t05_and_t06_get_the_fixed_answer_without_asking_think(self):
        for q in ("Is Sarah listening to us?", "Can Sarah hear what I tell you?"):
            with self.subTest(q=q):
                client, res = self._run(q)
                self.assertIsNone(client.messages, "THINK should not be asked")
                self.assertEqual(res.reply_text, _LISTENING_ANSWER.format(name="Sarah"))
                self.assertNotIn("flags if I send any", res.reply_text)
                self.assertEqual(self.flags.all(), [], "a listening question raises no flag")

    def test_the_reply_is_the_same_on_every_ask(self):
        replies = {self._run("Is Sarah listening to us?")[1].reply_text for _ in range(3)}
        self.assertEqual(len(replies), 1)

    def test_privacy_request_still_goes_to_think(self):
        client, res = self._run("Don't tell Sarah about the biscuits", reply="Of course, that stays between us.")
        self.assertIsNotNone(client.messages)
        self.assertIn("between us", res.reply_text)

    def test_safety_turn_is_never_answered_with_the_listening_text(self):
        client, res = self._run("Is Sarah listening? I fell down and I can't get up.", reply="Stay where you are, help is coming.")
        self.assertNotEqual(res.reply_text, _LISTENING_ANSWER.format(name="Sarah"))
        self.assertTrue(self.flags.all(), "the fall is still flagged")

    def test_a_worried_listening_question_goes_to_think(self):
        client, res = self._run("I'm scared, is Sarah listening to us?", reply="You're safe here, Dad.")
        self.assertIsNotNone(client.messages)


if __name__ == "__main__":
    unittest.main()
