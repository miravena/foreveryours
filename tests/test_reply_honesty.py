"""Replies say only what the app knows (#278, #279).

#279: the companion never says the caregiver is on her way or will check on
Dad (T15: "She's on her way to check on you now"), and on a turn that raised
no safety flag it never promises to pass a message to the family (T13:
"Great, I'll let Sarah know we're all set"). #278: asked about appointments
with one in the notes, a reply never opens with "I don't see any
appointments". These run offline with THINK stubbed to the live replies.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline import think
from pipeline.orchestrator import (
    appointment_readout,
    claims_caregiver_arriving,
    denies_noted_appointment,
    promises_family_message,
    run_turn,
)
from tests.test_offer_briefed_topic import _CapturingClient


def _speak_joined(sentences, audio_out_dir, on_chunk=None):
    """Speaks every sentence and reports audio, so a disclosure counts as told."""
    texts = [s for s in sentences if s and s.strip()]
    return " ".join(texts), ([Path(audio_out_dir) / "s.wav"] if texts else []), 0.5

MEMO_TAN = "Dad has a check-up with Dr. Tan on Thursday at 10 AM."


class TestArrivalClaims(unittest.TestCase):
    def test_invented_arrivals_are_caught(self):
        for s in ("She's on her way to check on you now.",
                  "She’s on her way to check on you now.",
                  "Sarah is coming over right now.",
                  "Help is on the way.",
                  "She'll be there soon.",
                  "Sarah will check on you later.",
                  "Your family is rushing over.",
                  # Codex review round 2: emergency words do not make it true
                  "Sarah is on her way with emergency help.",
                  # round 6: a hedged first mention does not shield a later claim
                  "I can't say when Sarah will check on you, but she's on her way.",
                  # round 7: a trailing question does not shield the claim
                  "She's on her way, are you hurt?",
                  # round 8: a condition before a ";" does not shield a later claim
                  "If you are hurt, call 911; Sarah is on her way."):
            with self.subTest(s=s):
                self.assertTrue(claims_caregiver_arriving(s, "Sarah"))

    def test_grounded_visits_and_confirmations_are_kept(self):
        for s in ("That sounds like a good plan. She'll be along at 4 PM with the groceries.",
                  "Sarah is dropping off groceries at 4 PM today.",
                  "If you call Sarah, she can be there soon.",
                  "I did let Sarah know about your fall.",
                  "Sarah can't hear our conversation.",
                  "I'm on my way to understanding you better.",
                  # Codex review: the honest "not confirmed" answer is kept
                  "Sarah isn't on her way.",
                  "I don't know if she's on her way, so please call 911 if you're hurt.",
                  "I let her know, but I can't say when she'll check on you.",
                  # Codex review round 2: advice and questions are not claims
                  "Please ask Sarah to check on you.",
                  "Would you like Sarah to check on you later?"):
            with self.subTest(s=s):
                self.assertFalse(claims_caregiver_arriving(s, "Sarah"))

    def test_uses_the_configured_caregiver_name(self):
        self.assertTrue(claims_caregiver_arriving("Maria is coming over now.", "Maria"))


class TestMessagePromises(unittest.TestCase):
    def test_promises_are_caught(self):
        for s in ("Great, I'll let Sarah know we're all set.",
                  "I'll let Sarah know you'll be waiting for her.",
                  "I’ll let her know.",
                  "Shall I tell her?",
                  "I can pass that on to Sarah.",
                  "Let me tell your family.",
                  "I will make sure Sarah knows.",
                  "Would you like me to call Sarah?"):
            with self.subTest(s=s):
                self.assertTrue(promises_family_message(s, "Sarah"))

    def test_refusals_and_suggestions_are_kept(self):
        for s in ("I won't tell Sarah.",
                  "I can't call Sarah, but you can.",
                  "Why don't you give Sarah a call later?",
                  "I did let Sarah know.",
                  "Sarah can't hear our chats; she only gets a safety flag.",
                  "I'll let you rest now.",
                  "You could tell Sarah when she arrives."):
            with self.subTest(s=s):
                self.assertFalse(promises_family_message(s, "Sarah"))


class TestAppointmentDenial(unittest.TestCase):
    def test_denials_of_a_noted_appointment(self):
        for s in ("I don't see any appointments listed for this week.",
                  "I don't have a confirmed time for that appointment noted.",
                  "There are no appointments this week.",
                  # Codex review: naming the day or doctor does not make it true
                  "There are no appointments on Thursday.",
                  "I don't have a confirmed time for your appointment with Dr. Tan."):
            with self.subTest(s=s):
                self.assertTrue(denies_noted_appointment(s, [MEMO_TAN]))

    def test_a_denial_that_carries_the_appointment_is_kept(self):
        s = "I don't see any appointments listed for this week besides the Thursday check-up with Dr. Tan at 10 AM."
        self.assertFalse(denies_noted_appointment(s, [MEMO_TAN]))

    def test_no_appointment_in_the_notes_keeps_the_honest_answer(self):
        self.assertFalse(denies_noted_appointment("I don't see any appointments listed.", []))

    def test_time_denial_kept_when_the_note_has_no_time(self):
        self.assertFalse(denies_noted_appointment("I don't have a time noted for that.",
                                                  ["Dad has a check-up with Dr. Tan next week."]))

    def test_readout_speaks_to_dad(self):
        self.assertEqual(appointment_readout([MEMO_TAN], "Sarah"),
                         "Sarah mentioned you have a check-up with Dr. Tan on Thursday at 10 AM.")


class _TurnCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        (root / "data").mkdir()
        (root / "audio").mkdir()
        self.audio_dir = root / "audio"
        self.store = MemoryStore("test_dad", root / "data")
        self.flags = CaregiverFlags("test_dad", root / "data")
        self.store.add("Dad loves jazz", source="caregiver_memo")
        self.store.add("His grandson is named Leo", source="caregiver_memo")
        self.store.add("I'm dropping off groceries at 4 PM today", source="caregiver_memo")

    def turn(self, transcript, reply, **kwargs):
        client = _CapturingClient(reply)
        with patch("pipeline.think.get_client", return_value=client), \
             patch("pipeline.orchestrator._speak_turn", side_effect=_speak_joined):
            res = run_turn(transcript=transcript, memory_store=self.store, flags=self.flags,
                           audio_out_dir=self.audio_dir, caregiver_name="Sarah", **kwargs)
        if res.background_thread:
            res.background_thread.join(timeout=10)
        return client, res


class TestT13T15InRunTurn(_TurnCase):
    def test_t13_message_promise_is_dropped_and_the_visit_kept(self):
        _, res = self.turn("Alright, I'll wait for Sarah then.",
                           "Great, I'll let Sarah know we're all set. She'll be along at 4 PM with the groceries.")
        self.assertNotIn("let Sarah know", res.reply_text)
        self.assertIn("4 PM", res.reply_text)

    def test_t13_promise_only_gets_the_honest_line(self):
        _, res = self.turn("Alright, I'll wait for Sarah then.", "I'll let Sarah know you'll be waiting for her.")
        self.assertNotIn("let Sarah know", res.reply_text)
        self.assertIn("can't pass messages", res.reply_text)

    def test_t15_on_her_way_is_dropped_and_the_confirmation_kept(self):
        _, first = self.turn("I fell down earlier and I'm scared.", "I'm right here with you.")
        self.assertTrue(first.session_flags)
        _, res = self.turn("Did you tell Sarah about my fall?",
                           "Yes, I let Sarah know about your fall. She's on her way to check on you now.",
                           session_flags=first.session_flags)
        self.assertIn("I let Sarah know about your fall", res.reply_text)
        self.assertNotIn("on her way", res.reply_text)
        self.assertNotIn("check on you", res.reply_text)

    def test_fall_turn_drops_on_her_way_and_keeps_its_disclosure(self):
        _, res = self.turn("I fell down earlier and I'm scared.",
                           "I'll let Sarah know you're scared. She's on her way.")
        self.assertNotIn("on her way", res.reply_text)
        # A safety turn may still say the family is being told.
        self.assertIn("I'll let Sarah know you're scared", res.reply_text)


class TestDrivingFallback(_TurnCase):
    def test_a_dropped_promise_on_a_driving_turn_gets_only_the_lift_offer(self):
        # Live T12 on v1.0.1: "Would you like me to ask Sarah for a lift
        # instead? I can't pass messages on to Sarah myself, ..."
        _, res = self.turn("I think I'll drive down to the shop myself this afternoon.",
                           "I'll let Sarah know you're heading out.")
        self.assertNotIn("can't pass messages", res.reply_text)
        self.assertNotIn("me to ask", res.reply_text)
        self.assertIn("lift", res.reply_text)


class TestEmergencyWordingInRunTurn(_TurnCase):
    def test_emergency_words_do_not_keep_an_arrival_claim(self):
        _, res = self.turn("I fell down earlier and I'm scared.",
                           "Sarah is on her way with emergency help. Please call 911 if you are hurt.")
        self.assertNotIn("on her way", res.reply_text)
        self.assertIn("call 911", res.reply_text)

    def test_other_safety_advice_in_the_sentence_is_kept(self):
        _, res = self.turn("I fell down earlier and I'm scared.", "She's on her way, don't move your neck.")
        self.assertNotIn("on her way", res.reply_text)
        self.assertIn("Don't move your neck.", res.reply_text)

    def test_one_sentence_with_claim_and_911_keeps_only_the_advice(self):
        _, res = self.turn("I fell down earlier and I'm scared.",
                           "She's on her way to check on you; please call 911 if you are hurt.")
        self.assertNotIn("on her way", res.reply_text)
        self.assertIn("call 911", res.reply_text)


class TestArrivalClauseWithAdvice(unittest.TestCase):
    def test_the_claim_goes_and_the_911_advice_stays(self):
        from pipeline.orchestrator import strip_arrival_clauses
        self.assertEqual(strip_arrival_clauses("She's on her way to check on you; please call 911.", "Sarah"),
                         "Please call 911.")
        self.assertEqual(strip_arrival_clauses("Call 911 now, and Sarah is on her way.", "Sarah"), "Call 911 now.")
        # round 6: a "because" clause is cut on its own
        self.assertEqual(strip_arrival_clauses("Don't move your neck because Sarah is on her way.", "Sarah"),
                         "Don't move your neck.")
        # Codex review round 4: a clause holding both becomes plain advice
        self.assertEqual(strip_arrival_clauses("Sarah is on her way to help you call 911.", "Sarah"),
                         "If you need help right now, please call 911.")

    def test_appointment_belt_follows_the_question(self):
        from pipeline.orchestrator import appointment_updates
        self.assertEqual(appointment_updates([MEMO_TAN], "Do I have any appointments this week?"), [MEMO_TAN])
        self.assertEqual(appointment_updates([MEMO_TAN], "Do I have any appointments on Friday?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "Do I have any appointments today?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "Any appointments tomorrow?"), [])
        # round 8: a capitalised opener is not a name
        self.assertEqual(appointment_updates([MEMO_TAN], "Any appointments this week?"), [MEMO_TAN])
        self.assertEqual(appointment_updates([MEMO_TAN], "Please remind me about my appointment with Dr. Tan"),
                         [MEMO_TAN])
        # round 7: a next-week note does not answer "this week"
        later = "Dad has a check-up with Dr. Tan next week."
        self.assertEqual(appointment_updates([later], "Do I have any appointments this week?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "Any appointments next week?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "What time is my dentist appointment?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "What time is my appointment with Dr. Lee?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "What time is my appointment with dr. lee?"), [])
        self.assertEqual(appointment_updates([MEMO_TAN], "when do i see doctor tan?"), [MEMO_TAN])
        self.assertEqual(appointment_updates([MEMO_TAN], "What time is my appointment with Dr. Tan?"), [MEMO_TAN])


class TestT09InRunTurn(_TurnCase):
    def setUp(self):
        super().setUp()
        self.store.add(MEMO_TAN, source="caregiver_memo")

    def test_t09_denial_is_dropped_and_the_memo_read(self):
        _, res = self.turn("Do I have any appointments this week?",
                           "I don't see any appointments listed for this week. "
                           "Sarah mentioned she'll be dropping off groceries at 4 PM today.")
        self.assertNotIn("don't see any appointments", res.reply_text)
        self.assertIn("Dr. Tan on Thursday at 10 AM", res.reply_text)

    def test_t10_denial_before_the_answer_is_dropped_once(self):
        _, res = self.turn("What time is my appointment with Dr. Tan?",
                           "I don't have a confirmed time for that appointment noted. "
                           "Sarah mentioned you have a check-up with Dr. Tan on Thursday at 10 AM.")
        self.assertNotIn("confirmed time", res.reply_text)
        self.assertEqual(res.reply_text.count("10 AM"), 1)

    def test_an_unrelated_thursday_does_not_stand_in_for_the_appointment(self):
        _, res = self.turn("Do I have any appointments this week?",
                           "I don't see any appointments listed. Sarah is dropping off groceries on Thursday.")
        self.assertIn("Dr. Tan on Thursday at 10 AM", res.reply_text)

    def test_an_unrelated_ten_am_does_not_stand_in_for_the_appointment(self):
        _, res = self.turn("Do I have any appointments this week?",
                           "I don't see any appointments listed. Sarah is bringing groceries at 10 AM.")
        self.assertIn("Dr. Tan on Thursday at 10 AM", res.reply_text)

    def test_a_good_answer_is_left_alone(self):
        good = "You have a check-up with Dr. Tan on Thursday at 10 AM."
        _, res = self.turn("Do I have any appointments this week?", good)
        self.assertEqual(res.reply_text, good)


class TestPrompt(unittest.TestCase):
    def test_rule_26_is_in_the_system_prompt(self):
        self.assertIn("26. NO INVENTED CAREGIVER ACTIONS OR MESSAGES", think.SYSTEM_PROMPT)
        self.assertIn("on her way", think.SYSTEM_PROMPT)

    def test_updates_header_says_later_days_count(self):
        messages = think.build_prompt("Do I have any appointments this week?", [],
                                      caregiver_updates=[MEMO_TAN])
        self.assertIn("UPCOMING APPOINTMENTS", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
