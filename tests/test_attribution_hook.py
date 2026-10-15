"""Proves the shared attribution checker (scripts/check_attribution.sh) and the
commit-msg hook that delegates to it (.githooks/commit-msg).

Both always exit 0 (advisory only, ADR-007) and both print one "WARNING: ..."
line per problem on stderr. TestChecker drives the script directly; TestHook
drives the hook, which is what actually fires at commit time.

TestChecker's first test asserts the checker *is a file* before anything else,
so a missing checker (e.g. run against a pre-change revision) is an assertion
FAILURE, not a FileNotFoundError ERROR -- see the negative control in
AC2 of Office ticket #14357, run against commit 9f5a311.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_attribution.sh"
HOOK = REPO_ROOT / ".githooks" / "commit-msg"

GOOD_EMAIL = "287302999+elevenbaselab@users.noreply.github.com"

NEW_FORMAT = """\
fix: guard against empty audio

Why: a zero-length wav crashed the fast-path check.

Assisted-by: ClaudeCode:claude-sonnet-5-5
Assisted-meta: provider=Anthropic effort=medium
Cost-estimate: $0.85 (in 234, out 107K tokens, approximate)
"""

NEW_FORMAT_MERGE = """\
Merge branch 'wt/ticket-14357' (Fixes #146, #147: attribution format)

Assisted-by: ClaudeCode:claude-sonnet-5-5
Assisted-meta: provider=Anthropic effort=medium
Cost-estimate: $1.20 (approximate)
"""

MISSING_META = """\
fix: thing

Assisted-by: ClaudeCode:claude-sonnet-5-5
Cost-estimate: unknown
"""

# the shape of the 2026-10-12 commits fa241f1/891a431/46b59b1
NO_MODEL = """\
fix: thing

Assisted-by: ClaudeCode effort=medium
Assisted-meta: provider=Anthropic effort=medium
Cost-estimate: unknown
"""

# a trailing colon with nothing after it -- review-arm bounce #14357 round 2:
# the first draft of the checker treated "harness:" as a valid "harness:model".
EMPTY_MODEL = """\
fix: thing

Assisted-by: ClaudeCode:
Assisted-meta: provider=Anthropic effort=medium
Cost-estimate: unknown
"""

NO_COST = """\
fix: thing

Assisted-by: ClaudeCode:claude-sonnet-5-5
Assisted-meta: provider=Anthropic effort=medium
"""


def _write_msg(tmp_dir, text):
    path = Path(tmp_dir) / "MSG"
    path.write_text(text)
    return path


def _run_checker(tmp_dir, text, email=GOOD_EMAIL):
    msgfile = _write_msg(tmp_dir, text)
    result = subprocess.run(
        ["sh", str(CHECKER), str(msgfile), email],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result


def _run_hook(tmp_dir, text, email=GOOD_EMAIL):
    msgfile = _write_msg(tmp_dir, text)
    env = dict(os.environ)
    env["GIT_AUTHOR_EMAIL"] = email
    result = subprocess.run(
        ["sh", str(HOOK), str(msgfile)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    return result


class TestChecker(unittest.TestCase):
    def test_checker_script_exists(self):
        # Assertion, not a bare file-open: a missing checker must FAIL, never ERROR.
        self.assertTrue(CHECKER.is_file(), f"{CHECKER} is missing")

    def test_new_format_gives_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_checker(tmp, NEW_FORMAT)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("WARNING", result.stderr)

    def test_new_format_merge_commit_gives_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_checker(tmp, NEW_FORMAT_MERGE)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("WARNING", result.stderr)

    def test_missing_assisted_meta_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_checker(tmp, MISSING_META)
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)
        self.assertIn("Assisted-meta", result.stderr)

    def test_no_model_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_checker(tmp, NO_MODEL)
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)
        self.assertIn(":<model>", result.stderr)

    def test_empty_model_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_checker(tmp, EMPTY_MODEL)
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)
        self.assertIn(":<model>", result.stderr)

    def test_no_cost_estimate_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_checker(tmp, NO_COST)
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)
        self.assertIn("Cost-estimate", result.stderr)


class TestHook(unittest.TestCase):
    """.githooks/commit-msg exists at every revision in this history, so these
    run it directly rather than guarding its existence first."""

    def test_hook_exists(self):
        self.assertTrue(HOOK.is_file(), f"{HOOK} is missing")

    def test_hook_always_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_hook(tmp, NO_MODEL)
        self.assertEqual(result.returncode, 0)

    def test_hook_warns_on_no_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_hook(tmp, NO_MODEL)
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)
        self.assertIn(":<model>", result.stderr)

    def test_hook_warns_on_empty_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_hook(tmp, EMPTY_MODEL)
        self.assertEqual(result.returncode, 0)
        self.assertIn("WARNING", result.stderr)
        self.assertIn(":<model>", result.stderr)

    def test_hook_new_format_gives_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_hook(tmp, NEW_FORMAT)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("WARNING", result.stderr)


if __name__ == "__main__":
    unittest.main()
