"""Tests for safety fast-path triggers, invariants, and normalization."""
import unittest

from safety import fastpath


class TestFastPath(unittest.TestCase):
    def test_distress_triggers(self):
        cases = [
            "I fell down earlier and I'm scared",
            "Help me, I can't get up",
            "I have bad chest pain",
            "My chest hurts so much",
            "I'm dizzy and nauseous",
            "Call 911 right now",
            "I am bleeding from my hand",
            "Help me!",
            "Please help me",
            "Someone help me!",
            "Help me up",
            "Call for help",
            "Help, I'm scared",
            "help I am so scared",
            "Help! I'm terrified",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger fast-path")
                self.assertEqual(res.severity, "distress")
                self.assertIsNotNone(res.immediate_reply)
                self.assertIn("notifying their family", res.continuation_note)
                self.assertIn("URGENT: possible distress", res.caregiver_flag)

    def test_conversational_help_requests_do_not_trigger(self):
        # Issue #15: conversational help requests must NOT trigger emergency distress
        cases = [
            "Can you help me remember my grandson's name?",
            "Help me understand what time Sarah is coming",
            "Help me find my reading glasses",
            "Help me choose what music to listen to",
            "Can you help me with this puzzle?",
            "Could you help me look for my coat?",
            "I think I'm falling asleep in front of the TV",
            "I'm scared of thunderstorms",
            "Does that help? I'm scared of the dark",
            "That helps, I'm scared less now",
            "Help me understand why I'm scared of storms",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.triggered, f"Conversational request '{phrase}' should not trigger emergency distress")
                self.assertEqual(res.severity, "none")
                self.assertIsNone(res.caregiver_flag)

    def test_unicode_curly_quotes_normalization(self):
        # Curly apostrophes from phone keyboard or ASR
        res = fastpath.check("I’m dizzy")
        self.assertTrue(res.triggered)
        self.assertEqual(res.severity, "distress")

    def test_confusion_triggers(self):
        cases = [
            "Where am I right now?",
            "I don't know where I am",
            "I don't know what day it is",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertTrue(res.triggered, f"Expected '{phrase}' to trigger confusion")
                self.assertEqual(res.severity, "confusion")
                self.assertIn("You're safe", res.immediate_reply)
                self.assertIn("Possible confusion", res.caregiver_flag)

    def test_neutral_phrases_do_not_trigger(self):
        cases = [
            "I really love jazz music",
            "What is my grandson's name?",
            "It is sunny outside today",
            "Let's talk about Miles Davis",
            "I had a nice breakfast this morning",
            "I fell asleep in my chair earlier",
            "I'm exhausted after gardening",
            "I love the fall weather",
            "Today was an awful day",
            "I'm tired after a long walk",
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                res = fastpath.check(phrase)
                self.assertFalse(res.triggered, f"Neutral phrase '{phrase}' should not trigger")
                self.assertEqual(res.severity, "none")
                self.assertIsNone(res.immediate_reply)
                self.assertIsNone(res.continuation_note)
                self.assertIsNone(res.caregiver_flag)


if __name__ == "__main__":
    unittest.main()
