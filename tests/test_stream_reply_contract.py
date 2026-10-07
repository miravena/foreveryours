"""Issue #78: the orchestrator and think.stream_reply must agree on kwargs.

A blanket `except Exception` in run_turn once turned a TypeError (stream_reply
rejected `pending_conflicts`) into the canned fallback reply on every live turn,
and no keyless test could see it. These tests need no NEBIUS_API_KEY."""
import ast
import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from caregiver import CaregiverFlags
from memory.store import MemoryStore
from pipeline import orchestrator, think
from pipeline.orchestrator import FALLBACK_REPLY_1, FALLBACK_REPLY_2, run_turn


def _orchestrator_stream_reply_kwargs() -> set[str]:
    tree = ast.parse(Path(orchestrator.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "stream_reply"
        ):
            names.update(k.arg for k in node.keywords if k.arg)
    return names


class _StubClient:
    """Minimal OpenAI-style client: chat.completions.create(...) -> chunk iterator."""

    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=t))])
            for t in ("Hello there, dear. ", "It is lovely to hear from you.")
        )


class TestStreamReplyContract(unittest.TestCase):
    def test_orchestrator_kwargs_accepted_by_stream_reply(self):
        passed = _orchestrator_stream_reply_kwargs()
        self.assertIn("pending_conflicts", passed)  # guards the AST scan itself
        accepted = set(inspect.signature(think.stream_reply).parameters)
        self.assertEqual(passed - accepted, set(), "orchestrator passes kwargs stream_reply rejects")

    def test_run_turn_live_path_not_fallback_and_forwards_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, audio_dir = Path(tmp) / "data", Path(tmp) / "audio"
            data_dir.mkdir()
            audio_dir.mkdir()
            store = MemoryStore("t78", data_dir)
            flags = CaregiverFlags("t78", data_dir)
            store.add_conflict("grandson is Liam", "grandson is Leo", "names differ")
            client = _StubClient()
            real_build_prompt = think.build_prompt
            seen = {}

            def spy(*args, **kwargs):
                seen["pending_conflicts"] = kwargs.get("pending_conflicts")
                return real_build_prompt(*args, **kwargs)

            with patch.object(think, "get_client", return_value=client), \
                    patch.object(think, "build_prompt", side_effect=spy), \
                    patch.object(orchestrator.audit, "get_client", return_value=client):
                result = run_turn(
                    transcript="Tell me about my day",
                    memory_store=store,
                    flags=flags,
                    audio_out_dir=audio_dir,
                    caregiver_name="Sarah",
                )
                if result.background_thread is not None:
                    result.background_thread.join(timeout=10)

            self.assertFalse(result.is_fallback)
            self.assertNotIn(result.reply_text, (FALLBACK_REPLY_1, FALLBACK_REPLY_2))
            self.assertIn("lovely to hear", result.reply_text)
            self.assertTrue(client.calls, "stubbed client was never reached")
            self.assertEqual(
                seen["pending_conflicts"],
                [{"old_fact": "grandson is Liam", "new_fact": "grandson is Leo", "reason": "names differ"}],
            )

    def test_fallback_logs_exception_type_to_stderr(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as tmp:
            data_dir, audio_dir = Path(tmp) / "data", Path(tmp) / "audio"
            data_dir.mkdir()
            audio_dir.mkdir()
            err = io.StringIO()
            with patch.object(think, "stream_reply", side_effect=TypeError("boom-78")), \
                    contextlib.redirect_stderr(err):
                result = run_turn(
                    transcript="Tell me about my day",
                    memory_store=MemoryStore("t78", data_dir),
                    flags=CaregiverFlags("t78", data_dir),
                    audio_out_dir=audio_dir,
                )
            self.assertTrue(result.is_fallback)
            self.assertIn("TypeError", err.getvalue())
            self.assertIn("boom-78", err.getvalue())


if __name__ == "__main__":
    unittest.main()
