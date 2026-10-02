"""Tests for THINK prompt generation, sentence chunking, and memory extraction."""
import unittest

from pipeline import think


class TestThink(unittest.TestCase):
    def test_build_prompt_structure(self):
        transcript = "Can you play some music?"
        facts = ["Loves Miles Davis", "Grandson is Leo"]
        guardrails = ["Avoid talking about driving"]
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hello, good to hear from you."},
        ]

        messages = think.build_prompt(transcript, facts, guardrails, history)
        self.assertEqual(messages[0]["role"], "system")
        system_content = messages[0]["content"]
        self.assertIn("SENIOR PROFILE & BELOVED ANCHORS", system_content)
        self.assertIn("- Loves Miles Davis", system_content)
        self.assertIn("- Grandson is Leo", system_content)
        self.assertIn("DO NOT RAISE (Safety Guardrails)", system_content)
        self.assertIn("- Avoid talking about driving", system_content)
        self.assertEqual(messages[1], history[0])
        self.assertEqual(messages[2], history[1])
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], transcript)

    def test_build_prompt_with_intent_and_caregiver_updates(self):
        transcript = "hello i feel so sad recently"
        facts = ["Dad loves jazz"]
        updates = ["Family member (Leo) is dropping off groceries at 4 PM today"]
        guardrails = ["Avoid talking about driving"]

        messages = think.build_prompt(
            transcript,
            facts,
            guardrails=guardrails,
            caregiver_updates=updates,
            intent="EMOTIONAL_SUPPORT",
        )
        system_content = messages[0]["content"]
        self.assertIn("CURRENT CONVERSATIONAL INTENT: EMOTIONAL_SUPPORT", system_content)
        self.assertIn("Validate their feelings first with warmth", system_content)
        self.assertIn("TODAY'S FAMILY / CAREGIVER UPDATES", system_content)
        self.assertIn("Family member (Leo) is dropping off groceries", system_content)
        self.assertIn("RELEVANCE DOES NOT IMPLY INSERTION", system_content)
        self.assertIn("DO NOT PRETEND TO HAVE A PHYSICAL BODY", system_content)

    def test_sentence_chunks_standard_punctuation(self):
        tokens = ["Hello ", "there! ", "How ", "are ", "you ", "doing ", "today? ", "I am well."]
        chunks = list(think.sentence_chunks(iter(tokens)))
        self.assertEqual(chunks, ["Hello there!", "How are you doing today?", "I am well."])

    def test_sentence_chunks_abbreviation_awareness(self):
        # "Dr. Smith" and "4 p.m." must NOT split mid-title or mid-time
        tokens = [
            "We have an appointment with Dr. ",
            "Smith at 4 ",
            "p.m. today. ",
            "Please bring your notes.",
        ]
        chunks = list(think.sentence_chunks(iter(tokens)))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], "We have an appointment with Dr. Smith at 4 p.m. today.")
        self.assertEqual(chunks[1], "Please bring your notes.")

    def test_durable_memory_extraction_rules(self):
        # Valid markers
        self.assertEqual(
            think.extract_new_memory("My favorite flavor is strawberry", "", use_llm=False),
            "My favorite flavor is strawberry",
        )
        self.assertEqual(
            think.extract_new_memory("I used to work as a teacher in Boston", "", use_llm=False),
            "I used to work as a teacher in Boston",
        )
        self.assertEqual(
            think.extract_new_memory("I love jazz so much", "", use_llm=False),
            "I love jazz so much",
        )
        self.assertEqual(
            think.extract_new_memory("My grandson will visit on Sunday", "", use_llm=False),
            "My grandson will visit on Sunday",
        )

        # Word boundary tests: should NOT trigger on partial substrings
        self.assertIsNone(think.extract_new_memory("This is my song playing", "", use_llm=False))
        self.assertIsNone(think.extract_new_memory("I likely will go to bed soon", "", use_llm=False))
        self.assertIsNone(think.extract_new_memory("How are you today?", "", use_llm=False))


if __name__ == "__main__":
    unittest.main()
