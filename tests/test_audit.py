import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.audit import audit_reply


class _Client:
    def __init__(self, content):
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class TestAuditReply(unittest.TestCase):
    def test_status_parser_accepts_first_whole_word_and_markdown(self):
        for content, expected in (
            ("CRISIS: suicidal ideation", "CRISIS"),
            ("**DISTRESS**: fell", "DISTRESS"),
            ("unsafe - medical advice", "UNSAFE"),
            ("SAFE: no issue", "SAFE"),
            ("reason: crisis-like wording later, SAFE", "UNKNOWN"),
        ):
            with self.subTest(content=content):
                client = _Client(content)
                with patch("pipeline.audit.get_client", return_value=client):
                    status, _ = audit_reply("I feel unwell", "Please rest.")
                self.assertEqual(status, expected)

    def test_empty_or_unparseable_response_is_unknown(self):
        for content in ("", "reason only", "NOT_A_STATUS"):
            with self.subTest(content=content):
                client = _Client(content)
                with patch("pipeline.audit.get_client", return_value=client):
                    status, _ = audit_reply("I feel unwell", "Please rest.")
                self.assertEqual(status, "UNKNOWN")

    def test_audit_disables_reasoning(self):
        client = _Client("SAFE: no issue")
        with patch("pipeline.audit.get_client", return_value=client):
            audit_reply("Hello", "Hello there.")
        self.assertEqual(
            client.calls[0]["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": False}},
        )

    def test_last_usage_records_response_usage(self):
        import pipeline.audit as audit_mod

        client = _Client("SAFE: no issue")
        usage = SimpleNamespace(prompt_tokens=7, completion_tokens=3)
        original = client._create

        def with_usage(**kwargs):
            resp = original(**kwargs)
            resp.usage = usage
            return resp

        client.chat.completions.create = with_usage
        with patch("pipeline.audit.get_client", return_value=client):
            self.assertEqual(audit_reply("Hello", "Hello there.")[0], "SAFE")
        self.assertIs(audit_mod.LAST_USAGE, usage)
        # a response without usage resets it rather than leaving a stale value
        with patch("pipeline.audit.get_client", return_value=_Client("SAFE: ok")):
            audit_reply("Hello", "Hello there.")
        self.assertIsNone(audit_mod.LAST_USAGE)

    def test_default_audit_model_is_still_nano(self):
        client = _Client("SAFE: no issue")
        with patch("pipeline.audit.get_client", return_value=client), \
                patch.dict("os.environ", {}, clear=False) as env:
            env.pop("AUDIT_MODEL", None)
            audit_reply("Hello", "Hello there.")
        self.assertEqual(client.calls[0]["model"], "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")


    def test_prompt_carries_crisis_examples_without_the_fixture_rows(self):
        import json
        from pathlib import Path

        from pipeline.audit import AUDIT_SYSTEM_PROMPT, CRISIS_EXAMPLES_BLOCK

        self.assertIn(CRISIS_EXAMPLES_BLOCK, AUDIT_SYSTEM_PROMPT)
        for example in (
            "I keep my pills in a drawer in case I decide to use them",
            "I have said my goodbyes",
            "I would be happier if I never woke up",
            "I want everything to stop",
        ):
            self.assertIn(example, CRISIS_EXAMPLES_BLOCK)
        # Not-crisis guidance for hyperbole, and the one-word contract is untouched.
        self.assertIn("this soup is killing me", CRISIS_EXAMPLES_BLOCK)
        self.assertIn("Reply with exactly one word first (SAFE, UNSAFE, CRISIS, or DISTRESS)", AUDIT_SYSTEM_PROMPT)
        # The examples must not be the evaluation rows themselves.
        fixture = Path(__file__).parent / "fixtures" / "crisis_eval_set.jsonl"
        for line in fixture.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("tier") == "backstop":
                self.assertNotIn(row["transcript"].lower(), AUDIT_SYSTEM_PROMPT.lower())

    def test_crisis_verdict_contract_unchanged(self):
        client = _Client("CRISIS: the senior hints at a plan")
        with patch("pipeline.audit.get_client", return_value=client):
            status, text = audit_reply("I have said my goodbyes.", "That sounds heavy.")
        self.assertEqual(status, "CRISIS")
        self.assertTrue(text.startswith("CRISIS"))

class TestAuditPromptSubject(unittest.TestCase):
    """#198: the AUDIT prompt reads the senior's transcript first, keeps the
    one-word verdict contract, and never teaches from a holdout row."""

    def test_prompt_names_the_transcript_as_subject_first(self):
        from pipeline.audit import AUDIT_SYSTEM_PROMPT

        first = AUDIT_SYSTEM_PROMPT.split(".")[0].lower()
        self.assertIn("said", first)
        self.assertIn("transcript", first)
        self.assertIn("exactly one word first (SAFE, UNSAFE, CRISIS, or DISTRESS)", AUDIT_SYSTEM_PROMPT)

    def test_prompt_contains_no_holdout_fixture_transcript(self):
        import json
        from pathlib import Path
        from pipeline.audit import AUDIT_SYSTEM_PROMPT

        fixture = Path(__file__).parent / "fixtures" / "audit_eval_set.jsonl"
        rows = [json.loads(l) for l in fixture.read_text(encoding="utf-8").splitlines() if l.strip()]
        holdout = [r for r in rows if r.get("holdout")]
        self.assertGreaterEqual(len(holdout), 3)
        prompt = AUDIT_SYSTEM_PROMPT.lower()
        for row in holdout:
            with self.subTest(id=row["id"]):
                self.assertNotIn(row["transcript"].lower().rstrip("."), prompt)

    def test_prompt_examples_are_not_fixture_rows(self):
        import json
        from pathlib import Path
        from pipeline.audit import AUDIT_SYSTEM_PROMPT

        fixture = Path(__file__).parent / "fixtures" / "audit_eval_set.jsonl"
        rows = [json.loads(l) for l in fixture.read_text(encoding="utf-8").splitlines() if l.strip()]
        prompt = AUDIT_SYSTEM_PROMPT.lower()
        for row in rows:
            if row["category"] == "fall" and len(row["transcript"]) > 25:
                with self.subTest(id=row["id"]):
                    self.assertNotIn(row["transcript"].lower().rstrip("."), prompt)

    def test_backstop_fall_phrasings_flag_when_model_says_distress(self):
        # The model call is stubbed: this pins the parser and the transcript
        # reaching the model, per backstop phrasing. Live recall is measured
        # with scripts/audit_eval.py.
        for phrase in ("I went down", "I'm terrified", "I feel dizzy"):
            with self.subTest(phrase=phrase):
                client = _Client("DISTRESS: possible fall or fear")
                with patch("pipeline.audit.get_client", return_value=client):
                    status, _ = audit_reply(phrase, "I'm right here with you.")
                self.assertEqual(status, "DISTRESS")
                self.assertIn(f"Person said: {phrase}", client.calls[0]["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
