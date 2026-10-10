import unittest
from unittest.mock import patch
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



    def test_preflight_context_verification(self):
        """Verify that proactive turns are suppressed if required context is missing."""
        from pipeline.orchestrator import run_turn
        from memory.store import MemoryStore
        from caregiver import CaregiverFlags
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore('test', Path(td))
            flags = CaregiverFlags('test', Path(td))
            audio_dir = Path(td)
            
            # 1. Hobby trigger with NO permanent facts should skip
            res_hobby = run_turn("", store, flags, audio_dir, is_proactive=True, trigger_type="hobby")
            self.assertTrue(res_hobby.is_fallback)
            self.assertIn("suppressed by policy", res_hobby.reply_text)
            
            # 2. Reminder trigger with NO caregiver updates should skip
            res_reminder = run_turn("", store, flags, audio_dir, is_proactive=True, trigger_type="reminder")
            self.assertTrue(res_reminder.is_fallback)
            self.assertIn("suppressed by policy", res_reminder.reply_text)
            
            # 3. Silence trigger should still work even with no facts
            # Wait, silence will hit the LLM, we can't test it directly here without mocking. 
            # We'll just test the suppressions.

    def test_two_strike_suppression(self):
        """Verify that proactive turns are suppressed if the last two turns were from the assistant."""
        from pipeline.orchestrator import run_turn
        from memory.store import MemoryStore
        from caregiver import CaregiverFlags
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore('test', Path(td))
            flags = CaregiverFlags('test', Path(td))
            audio_dir = Path(td)
            
            history = [
                {"role": "assistant", "content": "Hello"},
                {"role": "assistant", "content": "Are you there?"}
            ]
            
            res = run_turn("", store, flags, audio_dir, history=history, is_proactive=True, trigger_type="silence")
            self.assertTrue(res.is_fallback)
            self.assertIn("Too many consecutive AI turns", res.reply_text)

    @patch("pipeline.orchestrator._speak_turn", return_value=("Reply", [], 0.5))
    @patch("pipeline.think.stream_reply", return_value=iter(["Reply"]))
    def test_reminder_dedup_only_suppresses_delivered_reminders(self, mock_stream, mock_speak):
        """#132: a reminder is suppressed only when that specific schedule item
        was actually delivered to the senior -- not because recent chit-chat
        happened to reuse a couple of its words."""
        from pipeline.orchestrator import run_turn
        from memory.store import MemoryStore
        from caregiver import CaregiverFlags
        import tempfile
        from pathlib import Path

        SUPPRESSION = "Reminder already delivered recently"

        # (a) NEVER delivered, but recent chit-chat happens to reuse two of the
        # item's words ("dropping", "groceries") in a totally unrelated story.
        # The old 2-of-N word bag suppressed on exactly this incidental overlap;
        # the delivery-aware check must NOT, because the specific reminder was
        # never actually spoken, so it still has to reach the senior.
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore('test', Path(td))
            flags = CaregiverFlags('test', Path(td))
            audio_dir = Path(td)
            store.add("Sarah is dropping off groceries at 4 PM", source="caregiver_memo")

            history = [{"role": "assistant", "content": "You were telling me about dropping your reading glasses, and how the corner shop ran out of your favourite groceries last week."}]
            res = run_turn("", store, flags, audio_dir, history=history, is_proactive=True, trigger_type="reminder")
            if res.background_thread:
                res.background_thread.join(timeout=10)
            self.assertNotIn(SUPPRESSION, res.reply_text)

        # (b) ACTUALLY delivered: the assistant already spoke this exact item ->
        # suppress so the senior isn't told the same reminder twice.
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore('test', Path(td))
            flags = CaregiverFlags('test', Path(td))
            audio_dir = Path(td)
            store.add("Sarah is dropping off groceries at 4 PM", source="caregiver_memo")

            history = [{"role": "assistant", "content": "Just so you know, Sarah is dropping off groceries at 4 PM today."}]
            res = run_turn("", store, flags, audio_dir, history=history, is_proactive=True, trigger_type="reminder")
            if res.background_thread:
                res.background_thread.join(timeout=10)
            self.assertTrue(res.is_fallback)
            self.assertIn(SUPPRESSION, res.reply_text)

if __name__ == '__main__':
    unittest.main()
