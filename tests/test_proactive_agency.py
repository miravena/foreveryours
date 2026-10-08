import unittest
from pipeline.think import build_proactive_prompt

class TestProactiveAgency(unittest.TestCase):
    def test_proactive_policy_gate(self):
        """Verify the proactive prompt includes the strict anti-surveillance rule."""
        prompt_list = build_proactive_prompt(
            trigger_type="silence",
            facts=[],
            caregiver_updates=[]
        )
        prompt = prompt_list[0]["content"]
        self.assertIn("CRITICAL RULE: DO NOT tell the user that you are checking on them", prompt)
        self.assertIn("Never say 'you haven't spoken' or 'I am monitoring you'", prompt)

    def test_proactive_triggers(self):
        """Verify different triggers inject the correct instruction."""
        # Morning
        prompt = build_proactive_prompt("morning", [], [])[0]["content"]
        self.assertIn("Give a warm morning greeting", prompt)
        
        # Reminder
        prompt = build_proactive_prompt("reminder", [], [])[0]["content"]
        self.assertIn("Gently remind them of one of the caregiver updates", prompt)
        
        # Hobby
        prompt = build_proactive_prompt("hobby", [], [])[0]["content"]
        self.assertIn("Pick one of their permanent hobbies", prompt)
        
        # Silence
        prompt = build_proactive_prompt("silence", [], [])[0]["content"]
        self.assertIn("Give a generic, warm check-in", prompt)

if __name__ == '__main__':
    unittest.main()
