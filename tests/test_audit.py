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


if __name__ == "__main__":
    unittest.main()
