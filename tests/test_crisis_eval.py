import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("crisis_eval", ROOT / "scripts" / "crisis_eval.py")
crisis_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crisis_eval)


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        rc = crisis_eval.main(list(argv))
    return rc, buf.getvalue().strip().splitlines()[-1]


class TestCrisisEval(unittest.TestCase):
    def test_regex_only_is_offline_and_clean(self):
        rc, line = run("--regex-only")
        self.assertEqual(rc, 0)
        self.assertIn("false_flags=0/", line)
        self.assertIn("missed=0", line)

    def test_stub_none_backstop_misses_the_backstop_rows(self):
        with tempfile.TemporaryDirectory() as d:
            rc, line = run("--auditor", "stub-none", "--out-dir", d)
        self.assertEqual(rc, 1)
        self.assertNotIn("missed=0", line)

    def test_stub_perfect_backstop_covers_everything(self):
        with tempfile.TemporaryDirectory() as d:
            rc, line = run("--auditor", "stub-perfect", "--out-dir", d)
        self.assertEqual(rc, 0)
        self.assertIn("missed=0", line)


if __name__ == "__main__":
    unittest.main()
