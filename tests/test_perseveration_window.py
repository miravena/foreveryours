"""Fixes #139: the perseveration/confusion flag must require a repeated
QUESTION inside a bounded time window, not just a repeated intent label.
Three distinct LOGISTICAL questions ("When is my appointment?" / "Are
groceries coming today?" / "What is planned tomorrow?") share one intent but
are not the same question, and must not flag.

These tests exercise only existing, already-shipped behaviour (run_turn with
a controlled `history`); they do not import any new symbol, so against
pre-fix code (commit 9f5a311) they FAIL on an assertion -- the
distinct-questions case gets a false flag -- rather than ERRORing on a
missing import.
"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline.orchestrator import run_turn
from safety.fastpath import FastPathResult

# The three paraphrases from the Issue: same LOGISTICAL intent, same subject
# ("appointment"), worded differently.
PARAPHRASES = [
    "When is my appointment?",
    "What time is my appointment?",
    "My appointment, when is it?",
]

# Three distinct LOGISTICAL questions sharing one intent label but not one
# subject -- the exact case #139 says must NOT flag.
DISTINCT_LOGISTICAL = [
    "When is my appointment?",
    "Are groceries coming today?",
    "What is planned tomorrow?",
]


def _history(questions, timestamps):
    """Builds a user-only history list; each entry gets the given 'ts' (or no
    'ts' key at all when the corresponding timestamp is None)."""
    entries = []
    for q, ts in zip(questions, timestamps):
        entry = {"role": "user", "content": q}
        if ts is not None:
            entry["ts"] = ts
        entries.append(entry)
    return entries


@patch("pipeline.orchestrator.fastpath.check", return_value=FastPathResult(False, "none", None, None, None))
@patch("pipeline.orchestrator._speak_turn", return_value=("spoken", [Path("reply.wav")], 0.1))
@patch("pipeline.orchestrator.think.stream_reply", return_value=iter(["Okay, dear."]))
class TestPerseverationWindow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        data_dir = Path(self.temp_dir.name) / "data"
        self.audio_dir = Path(self.temp_dir.name) / "audio"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore("test_dad", data_dir)
        self.flags = CaregiverFlags("test_dad", data_dir)

    def _run(self, transcript, history):
        res = run_turn(
            transcript,
            self.store,
            self.flags,
            self.audio_dir,
            caregiver_name="Sarah",
            history=history,
        )
        if res.background_thread:
            res.background_thread.join(timeout=10)
        return res

    def _perseveration_flags(self):
        return [f for f in self.flags.all() if "Perseveration" in f.text]

    def test_three_distinct_logistical_questions_do_not_flag(self, *_mocks):
        now = time.time()
        history = _history(DISTINCT_LOGISTICAL[:2], [now - 600, now - 300])
        res = self._run(DISTINCT_LOGISTICAL[2], history)

        self.assertEqual(self._perseveration_flags(), [])
        self.assertNotIn("make a note for your family", res.reply_text)

    def test_same_question_three_times_within_window_flags_and_discloses(self, *_mocks):
        # The literal same question, verbatim, three times.
        question = "What time is my appointment?"
        now = time.time()
        history = _history([question, question], [now - 600, now - 300])
        res = self._run(question, history)

        flagged = self._perseveration_flags()
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].disclosed_to_senior)
        self.assertIn("make a note for your family", res.reply_text)

    def test_oldest_repeat_older_than_window_does_not_flag(self, *_mocks):
        # Same literal question, but the oldest repeat is just past
        # PERSEVERATION_WINDOW_S (1800s); the most recent repeat is well
        # inside it.
        question = "What time is my appointment?"
        now = time.time()
        history = _history([question, question], [now - 1900, now - 300])
        res = self._run(question, history)

        self.assertEqual(self._perseveration_flags(), [])
        self.assertNotIn("make a note for your family", res.reply_text)

    def test_paraphrases_within_window_flag(self, *_mocks):
        now = time.time()
        history = _history(PARAPHRASES[:2], [now - 1200, now - 60])
        res = self._run(PARAPHRASES[2], history)

        flagged = self._perseveration_flags()
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].disclosed_to_senior)
        self.assertIn("make a note for your family", res.reply_text)

    def test_history_without_ts_does_not_flag(self, *_mocks):
        # No 'ts' key at all on either prior entry -- counts as outside the
        # window, erring toward no false confusion label.
        history = _history(PARAPHRASES[:2], [None, None])
        res = self._run(PARAPHRASES[2], history)

        self.assertEqual(self._perseveration_flags(), [])
        self.assertNotIn("make a note for your family", res.reply_text)


if __name__ == "__main__":
    unittest.main()
