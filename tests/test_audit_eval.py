"""Offline tests for scripts/audit_eval.py (ADR-010). No key, no network."""
import collections
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "audit_eval_set.jsonl"

_spec = importlib.util.spec_from_file_location("audit_eval", ROOT / "scripts" / "audit_eval.py")
audit_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_eval)


def _run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = audit_eval.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def _score_line(stdout):
    return stdout.strip().splitlines()[-1]


class TestFixture(unittest.TestCase):
    def test_fixture_has_30_rows_and_all_five_categories(self):
        rows = audit_eval.load_fixture(FIXTURE)
        self.assertGreaterEqual(len(rows), 30)
        counts = collections.Counter(r["category"] for r in rows)
        for cat in audit_eval.CATEGORIES:
            self.assertGreaterEqual(counts[cat], 4, cat)
        self.assertTrue(all(isinstance(r["expect_flag"], bool) for r in rows))
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        unsafe = [r for r in rows if r.get("expect_status") == "UNSAFE"]
        self.assertGreaterEqual(len(unsafe), 3)
        # driving plans are a THINK guardrail, never an AUDIT flag
        self.assertFalse(any(r["expect_flag"] for r in rows if r["category"] == "driving"))


class TestScorer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_stub_none_fails_with_zero_recall(self):
        rc, out, err = _run("--auditor", "stub-none", "--out-dir", self.out)
        self.assertNotEqual(rc, 0)
        self.assertIn(" recall=0.00 ", _score_line(out))
        self.assertIn("RECALL_FLOOR", err)

    def test_stub_perfect_passes(self):
        rc, out, _ = _run("--auditor", "stub-perfect", "--out-dir", self.out)
        self.assertEqual(rc, 0)
        line = _score_line(out)
        self.assertTrue(line.startswith("model=stub-perfect n=43 recall=1.00 false_flags=0/"), line)
        self.assertIn(" unknown=0 calls=43 ", line)

    def test_cap_refuses_without_a_score_line(self):
        rc, out, err = _run("--auditor", "stub-perfect", "--out-dir", self.out, "--max-calls", "5")
        self.assertEqual(rc, 3)
        self.assertIn("cap reached: 5", err)
        self.assertFalse(any(l.startswith("model=") for l in out.splitlines()))
        # the five recorded rows are kept, so a resumed run makes only the rest
        rc, out, _ = _run("--auditor", "stub-perfect", "--out-dir", self.out)
        self.assertEqual(rc, 0)
        self.assertIn(" calls=38 ", _score_line(out))

    def test_second_run_makes_zero_calls_and_same_numbers(self):
        _, first, _ = _run("--auditor", "stub-perfect", "--out-dir", self.out)
        _, second, _ = _run("--auditor", "stub-perfect", "--out-dir", self.out)
        self.assertIn(" calls=43 ", _score_line(first))
        self.assertIn(" calls=0 ", _score_line(second))
        self.assertEqual(_score_line(first).replace("calls=43", "calls=0"), _score_line(second))

    def test_replay_creates_no_client(self):
        _run("--auditor", "stub-none", "--out-dir", self.out)
        recorded = Path(self.out) / "stub-none.jsonl"
        with patch("pipeline.audit.get_client", side_effect=AssertionError("client created")), \
                patch("pipeline.nebius_client.get_client", side_effect=AssertionError("client created")):
            rc, out, _ = _run("--replay", str(recorded))
        self.assertEqual(rc, 1)
        self.assertTrue(_score_line(out).startswith("model=stub-none n=43 recall=0.00 "))
        self.assertIn(" calls=0 ", _score_line(out))

    def test_live_path_retries_unknown_once_and_sums_usage(self):
        """A model answering garbage then SAFE: one retry, tokens from both attempts."""
        answers = iter(["no status word", "SAFE: fine"] + ["SAFE: fine"] * 100)

        class _Client:
            def __init__(self):
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

            def _create(self, **kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=next(answers)))],
                    usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
                )

        with patch("pipeline.audit.get_client", return_value=_Client()), \
                patch.dict("os.environ", {}, clear=False):
            rc, out, _ = _run("--model", "test/model", "--out-dir", self.out,
                              "--rate-in", "1", "--rate-out", "2")
        line = _score_line(out)
        self.assertEqual(rc, 1)  # all SAFE -> recall 0.00 below the floor
        self.assertIn(" calls=44 ", line)  # 43 rows + 1 retry
        self.assertIn(" unknown=0 ", line)
        self.assertIn(" prompt_tokens=4400 completion_tokens=440 ", line)
        self.assertIn(" est_cost_usd=0.005280", line)
        rec = json.loads((Path(self.out) / "test_model.jsonl").read_text().splitlines()[0])
        self.assertEqual([a["status"] for a in rec["attempts"]], ["UNKNOWN", "SAFE"])

    def test_unknown_twice_counts_as_unknown_not_flag(self):
        rows = [{"id": "x", "category": "fall", "transcript": "t", "reply": "r", "expect_flag": True}]
        records = {}
        calls = audit_eval.run_rows(rows, records, lambda row: ("UNKNOWN", "?", 0, 0),
                                    Path(self.out) / "u.jsonl", 200)
        self.assertEqual(calls, 2)
        line, _, _ = audit_eval.score("u", rows, records, calls, 0, 0)
        self.assertIn(" recall=0.00 ", line)
        self.assertIn(" unknown=1 ", line)


if __name__ == "__main__":
    unittest.main()
