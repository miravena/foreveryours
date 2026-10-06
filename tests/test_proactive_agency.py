import unittest
from unittest.mock import patch

from pipeline import think

class TestProactiveAgency(unittest.TestCase):
    def test_proactive_prompt_injection(self):
        # When is_proactive is True, the system prompt should contain the proactive block
        messages = think.build_prompt(
            transcript="[System: Initiate conversation]",
            facts=[],
            is_proactive=True
        )
        
        system_msg = messages[0]["content"]
        self.assertIn("[PROACTIVE INITIATION MODE]", system_msg)
        self.assertIn("CRITICAL RULE: DO NOT tell the user that you are checking on them", system_msg)
        
    def test_proactive_prompt_not_injected_normally(self):
        # When is_proactive is False, it should not be in the prompt
        messages = think.build_prompt(
            transcript="Hello",
            facts=[],
            is_proactive=False
        )
        
        system_msg = messages[0]["content"]
        self.assertNotIn("[PROACTIVE INITIATION MODE]", system_msg)

if __name__ == '__main__':
    unittest.main()
