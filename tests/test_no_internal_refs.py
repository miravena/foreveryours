"""The repo is public: no internal tracker ids in tracked files.

GitHub refs are `#N` with 1-3 digits. The fleet's own task ids are 4-6 digits and
mean nothing to a reader here (GitHub even links them to issues that do not exist),
so code, tests and docs cite GitHub issues only. The pre-push hook applies the same
rule to commit messages. CSS/HTML/SVG are skipped: `#166534` there is a colour.
"""
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Built from pieces so this file does not match itself.
_WORD = "off" + "ice"
PATTERN = re.compile(
    r"\b" + _WORD + r" ?#\d+"            # an internal-tracker prefix with any id
    r"|\bticket #\d{4,}"                 # "ticket #12345"
    r"|(?<![\w&#/])#\d{4,6}\b",          # a bare 4-6 digit id
    re.IGNORECASE,
)
SELF = pathlib.Path(__file__).resolve()  # its own examples are ids on purpose
SKIP_SUFFIXES = {".html", ".css", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".wav", ".mp3", ".onnx", ".bin"}


def tracked_files():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return [ROOT / f for f in out.stdout.splitlines()]


class NoInternalRefsTest(unittest.TestCase):
    def test_tracked_files_cite_github_issues_only(self):
        files = tracked_files()
        if files is None:
            self.skipTest("not a git checkout")
        hits = []
        for path in files:
            if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file() or path.resolve() == SELF:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if PATTERN.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:120]}")
        self.assertEqual(hits, [], "internal tracker ids in a public repo:\n" + "\n".join(hits))

    def test_pattern_catches_ids_and_spares_github_refs(self):
        self.assertTrue(PATTERN.search(_WORD.title() + " #23238: fix"))
        self.assertTrue(PATTERN.search("see (#23235)"))
        self.assertTrue(PATTERN.search("Ticket #16084 round 4"))
        self.assertFalse(PATTERN.search("Fixes #159: fall flag"))
        self.assertFalse(PATTERN.search("(#148, #83)"))
        self.assertFalse(PATTERN.search("issues/1234#issuecomment-5678"))


if __name__ == "__main__":
    unittest.main()
