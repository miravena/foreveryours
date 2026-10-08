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
            # #51: the most natural way a senior says this, plus dash variants
            # that ASR/LLM punctuation produces
            "Help me, I'm scared",
            "help me I'm scared",
            "I'm lying on the floor and it hurts",
            "  help  ",
            "  can someone help me  ",
            "help me? I'm scared",
            "help—I'm frightened",
            "help - I'm frightened",
            "Help – I'm frightened",
            # #55 Criterion 1: "cannot" must fire like "can't"
            "I cannot get up",
            "I cannot breathe",
            # #55 Criterion 2 (option A): a bare plea that is the whole message
            "help",
            "Help!",
            "Help!!",
            # #55 Criterion 3: on/hit the floor + a distress co-token, either order
            "I'm on the floor and I can't move",
            "I'm stuck on the floor",
            "I hit the floor and can't get up",
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
            # #51 Criterion 3: allowing "me" must not make task- or
            # memory-requests look like distress
            "help me remember Leo's birthday",
            "Help me pay the electricity bill, please",
            # #55 Criterion 2 near-misses: embedded "help" must stay silent
            "that was a big help!",
            "I need help with the crossword",
            # #55 Criterion 3 near-misses: benign floor use must stay silent
            "I'm on the floor watching telly",
            "I'm sitting on the floor doing a puzzle",
            "the baby is on the floor",
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

    def test_dashes_are_folded_before_matching(self):
        # #51: a dash between words is punctuation, not a word. Every dash
        # variant collapses to a space so no rule has to enumerate them.
        for dash in ("—", "–", "―", "‐", "‑", "−"):
            with self.subTest(dash=repr(dash)):
                self.assertEqual(fastpath._normalize(f"help{dash}I'm frightened"), "help i'm frightened")
        # ASCII hyphen and curly quotes still normalize as before
        self.assertEqual(fastpath._normalize("Help–I’m hurt"), "help i'm hurt")

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
