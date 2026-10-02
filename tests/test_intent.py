import unittest
from pipeline.intent import Intent, detect_intent


class TestIntentDetection(unittest.TestCase):
    def test_emotional_support_detection(self):
        phrases = [
            "hello i feel so sad recently",
            "I'm feeling very lonely today",
            "I miss my late wife so much",
            "I am scared and anxious",
            "I've been feeling down and blue",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_intent(phrase), Intent.EMOTIONAL_SUPPORT)

    def test_logistical_detection(self):
        phrases = [
            "what things do i have to do today",
            "what am i doing today",
            "what do i have planned today",
            "what is on my agenda today",
            "what time are my groceries arriving",
            "when is my daughter coming today",
            "what is on my schedule for today",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_intent(phrase), Intent.LOGISTICAL)

    def test_memory_request_detection(self):
        phrases = [
            "what is my grandson's name",
            "what do you remember about my family",
            "do you know my son's name",
            "tell me about my wife",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_intent(phrase), Intent.MEMORY_REQUEST)

    def test_mixed_intent_detection(self):
        phrases = [
            "I feel sad today, is my daughter coming at four?",
            "I am feeling lonely, what time are the groceries arriving?",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_intent(phrase), Intent.MIXED)

    def test_casual_intent_detection(self):
        phrases = [
            "good morning, nice weather outside",
            "I like listening to Miles Davis",
            "Hello there",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_intent(phrase), Intent.CASUAL)


if __name__ == "__main__":
    unittest.main()
