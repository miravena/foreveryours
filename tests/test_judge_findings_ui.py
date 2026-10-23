"""Judge-facing UI text, asserted on the rendered Blocks config.

Judges could not find the caregiver side, could not tell the pre-briefed
household was fictional, and skimmed past unlabelled sample clips and a long
retention paragraph. Every check reads demo.get_config_file(), the same config
the browser receives, not webapp.py source.
"""
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from samples.generate_samples import SAMPLES

ACCORDION_LABEL = "Brief Dad companion (as Sarah, his daughter)"


class TestJudgeFindingsUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        demo = webapp.build_demo()
        try:
            cls.config = demo.get_config_file()
        finally:
            demo.close()
        cls.components = cls.config["components"]
        cls.by_id = {c["id"]: c for c in cls.components}
        cls.markdown = [
            str(c["props"].get("value", "")) for c in cls.components if c["type"] == "markdown"
        ]

    def _of_type(self, kind):
        return [c for c in self.components if c["type"] == kind]

    def _descendants(self, node):
        for child in node.get("children", []):
            yield child["id"]
            yield from self._descendants(child)

    def _find_layout(self, node, cid):
        if node["id"] == cid:
            return node
        for child in node.get("children", []):
            found = self._find_layout(child, cid)
            if found:
                return found
        return None

    def test_caregiver_accordion_renamed_and_open(self):
        found = [a for a in self._of_type("accordion") if a["props"].get("label") == ACCORDION_LABEL]
        self.assertEqual(len(found), 1)
        self.assertIs(found[0]["props"]["open"], True)

    def test_no_internal_beat_jargon_in_any_label(self):
        for c in self.components:
            self.assertNotIn("Beat 1", str(c["props"].get("label", "")), c["type"])

    def test_intro_points_at_the_caregiver_side_and_keeps_ai_notice(self):
        intro = [v for v in self.markdown if v.startswith("# ForeverYours")]
        self.assertEqual(len(intro), 1)
        self.assertIn("caregiver on the right", intro[0])
        self.assertIn("Artificial Intelligence (AI) companion, not a human", intro[0])

    def test_initial_caregiver_panel_labels_the_household_fictional(self):
        panel = [v for v in self.markdown if "Briefed memory" in v]
        self.assertEqual(len(panel), 1)
        self.assertIn("Sample household (fictional), pre-briefed by Sarah", panel[0])
        self.assertLess(panel[0].index("Sample household (fictional)"), panel[0].index("Briefed memory"))

    def test_about_household_sentence_is_grammatical(self):
        about = [v for v in self.markdown if v.startswith("Your tab is its own private demo household")]
        self.assertEqual(len(about), 1)
        self.assertIn(
            f"removed when the session cleanup timer runs (about {webapp._CLOSED_TAB_MIN} minutes "
            "after the tab closes)",
            about[0],
        )
        self.assertNotIn("removed about the session", about[0])

    def test_sample_clips_are_labelled_with_their_scripts(self):
        datasets = [d for d in self._of_type("dataset") if d["props"].get("label") == "No mic? Try a sample clip"]
        self.assertEqual(len(datasets), 1)
        expected = [f'"{SAMPLES[name]}"' for name in webapp.SAMPLE_CLIPS]
        self.assertEqual(datasets[0]["props"]["sample_labels"], expected)
        self.assertEqual(
            list(webapp.SAMPLE_CLIPS),
            ["senior_schedule.wav", "senior_jazz.wav", "senior_grandson.wav", "senior_distress.wav"],
        )
        self.assertIn("Is anyone coming by today?", expected[0])

    def test_retention_minutes_are_collapsed_but_still_rendered(self):
        found = [a for a in self._of_type("accordion") if "kept" in str(a["props"].get("label", ""))]
        self.assertEqual(len(found), 1)
        self.assertIs(found[0]["props"]["open"], False)
        node = self._find_layout(self.config["layout"], found[0]["id"])
        inside = " ".join(
            str(self.by_id[i]["props"].get("value", ""))
            for i in self._descendants(node)
            if self.by_id[i]["type"] == "markdown"
        )
        interval_s, max_age_s = webapp.GRADIO_CACHE_SWEEP
        for minutes in (
            webapp._CLOSED_TAB_MIN,
            webapp.SESSION_TTL_S // 60,
            interval_s // 60,
            max_age_s // 60,
            math.ceil((interval_s + max_age_s) / 60),
        ):
            self.assertIn(f"{minutes} minutes", inside)

    def test_recording_notice_above_mic_is_short(self):
        notice = [v for v in self.markdown if v.startswith("🎙️")]
        self.assertEqual(len(notice), 1)
        self.assertIn("recorded and turned into text", notice[0])
        self.assertIn("sent to Nebius Token Factory", notice[0])
        self.assertNotIn("cache", notice[0])
        self.assertNotIn("minutes", notice[0])

    def test_senior_left_caregiver_right_layout_unchanged(self):
        rows = [self._find_layout(self.config["layout"], r["id"]) for r in self._of_type("row")]
        first_row = min(rows, key=lambda r: r["id"])
        columns = [self.by_id[c["id"]] for c in first_row["children"]]
        self.assertEqual([c["type"] for c in columns], ["column", "column"])
        headings = []
        for col in first_row["children"]:
            first_md = next(
                self.by_id[i] for i in self._descendants(col) if self.by_id[i]["type"] == "markdown"
            )
            headings.append(first_md["props"]["value"])
        self.assertIn("Senior side", headings[0])
        self.assertIn("Caregiver side", headings[1])


class TestPanelAfterATurn(unittest.TestCase):
    """The label is part of every panel render, not only the initial value."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        for p in (
            patch.object(webapp, "SESSIONS_DIR", Path(tmp.name) / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(tmp.name) / "data"),
            patch.dict(os.environ, {"NEBIUS_API_KEY": ""}),
        ):
            p.start()
            self.addCleanup(p.stop)
        webapp._request_log.clear()

    def _assert_labelled(self, panel):
        self.assertIn("Sample household (fictional), pre-briefed by Sarah", panel)
        self.assertLess(panel.index("Sample household (fictional)"), panel.index("### Briefed memory"))

    def test_label_sits_above_briefed_memory_on_load_and_after_a_turn(self):
        session_id, panel = webapp.init_session()
        self._assert_labelled(panel)
        # The distress phrase takes the offline fast-path, so no key is needed.
        out = webapp.run_demo_turn(
            audio_in=None,
            text_in_or_history="I fell down earlier and I'm scared",
            history_or_session=[],
            session_id=session_id,
        )
        self._assert_labelled(out[3])


if __name__ == "__main__":
    unittest.main()
