"""Pins the webapp notice and privacy docs wording for audio/session retention
(GitHub #137, #143).

RULE: no text may promise deletion the instant the tab closes. Two separate
deletions exist and must both be named with honest timing: (a) the household
session directory, cleared through Gradio's own `gr.State` `delete_callback`
roughly an hour after the browser disconnects, or by the sweeper after
`SESSION_TTL_S` of inactivity if the close event never arrives; (b) recorded/
uploaded input audio, which lives in Gradio's own file cache
(`delete_cache=GRADIO_CACHE_SWEEP`) until the periodic sweep catches it, so up
to `GRADIO_CACHE_SWEEP[0] + GRADIO_CACHE_SWEEP[1]` seconds.

This file reads webapp.py's already-rendered Markdown text (via the existing
`build_demo()`, not a new symbol) and the two docs files as plain text, so it
exercises behaviour already present at commit 9f5a311 and fails with an
assertion -- not an import error -- when run against that commit.
"""
import math
import unittest
from pathlib import Path

import gradio as gr

import webapp

REPO_ROOT = Path(__file__).resolve().parent.parent


def _collect_markdown_text() -> str:
    demo = webapp.build_demo()
    try:
        texts = []
        for block in demo.blocks.values():
            if isinstance(block, gr.Markdown):
                value = getattr(block, "value", None)
                if isinstance(value, str):
                    texts.append(value)
        return "\n".join(texts)
    finally:
        demo.close()


class TestRetentionNoticeWording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notice_text = _collect_markdown_text()
        cls.privacy_md = (REPO_ROOT / "docs" / "PRIVACY.md").read_text()
        cls.safety_md = (REPO_ROOT / "docs" / "SAFETY_AND_PRIVACY.md").read_text()

    def test_no_immediate_deletion_claim(self):
        for label, text in (
            ("webapp notice", self.notice_text),
            ("docs/PRIVACY.md", self.privacy_md),
            ("docs/SAFETY_AND_PRIVACY.md", self.safety_md),
        ):
            self.assertNotIn(
                "deleted immediately",
                text.lower(),
                f"{label} claims immediate deletion, which the code does not do",
            )

    def test_no_bare_tab_close_deletion_promise(self):
        """'...deleted when you close this/the tab.' with nothing else is the
        exact false claim #137/#143 report -- the real deletion is delayed."""
        for label, text in (("webapp notice", self.notice_text),):
            self.assertNotRegex(
                text,
                r"deleted when you close (this|the) tab\.",
                msg=f"{label} promises bare tab-close deletion with no delay",
            )

    def test_webapp_notice_cites_session_ttl_minutes(self):
        ttl_minutes = webapp.SESSION_TTL_S // 60
        self.assertIn(
            str(ttl_minutes),
            self.notice_text,
            "webapp notice does not cite a minute figure derived from SESSION_TTL_S",
        )

    def test_webapp_notice_cites_cache_sweep_max_minutes(self):
        interval_s, max_age_s = webapp.GRADIO_CACHE_SWEEP
        cache_max_minutes = math.ceil((interval_s + max_age_s) / 60)
        self.assertIn(
            str(cache_max_minutes),
            self.notice_text,
            "webapp notice does not cite a minute figure derived from GRADIO_CACHE_SWEEP",
        )

    def test_privacy_md_names_both_mechanisms(self):
        text_lower = self.privacy_md.lower()
        self.assertIn("close", text_lower)
        self.assertRegex(
            text_lower,
            r"(hour|minute)",
            "docs/PRIVACY.md does not give any timing figure for deletion",
        )
        self.assertRegex(
            text_lower,
            r"cache",
            "docs/PRIVACY.md does not mention Gradio's separate input-audio cache",
        )

    def test_safety_and_privacy_md_names_both_mechanisms(self):
        text_lower = self.safety_md.lower()
        self.assertIn("session_ttl_s", text_lower)
        self.assertRegex(
            text_lower,
            r"cache",
            "docs/SAFETY_AND_PRIVACY.md does not mention Gradio's separate input-audio cache",
        )
        self.assertNotRegex(
            text_lower,
            r"deleted when the tab closes, or after",
            "docs/SAFETY_AND_PRIVACY.md omits the confirmed delay before the state-TTL "
            "deletion actually fires",
        )


if __name__ == "__main__":
    unittest.main()
