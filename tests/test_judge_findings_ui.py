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

    def test_sample_clips_carry_plain_names(self):
        """#215: the chips read as what Dad does, not as the clip's script."""
        datasets = [d for d in self._of_type("dataset") if d["props"].get("label") == "No mic? Try a sample clip"]
        self.assertEqual(len(datasets), 1)
        self.assertEqual(
            datasets[0]["props"]["sample_labels"],
            [
                "Dad asks what's happening today",
                "Dad talks about jazz",
                "Dad asks his grandson's name",
                "Dad says he fell and is scared",
            ],
        )
        # #239: a clip chip also blanks the Type box, so typed text cannot win over it.
        self.assertTrue(all(row[1] == "" for row in datasets[0]["props"]["samples"]))
        self.assertEqual(
            list(webapp.SAMPLE_CLIPS),
            ["senior_schedule.wav", "senior_jazz.wav", "senior_grandson.wav", "senior_distress.wav"],
        )

    def test_try_first_line_is_in_the_header(self):
        intro = [v for v in self.markdown if v.startswith("# ForeverYours")][0]
        self.assertIn("Try this first: *I fell down earlier and I'm scared*", intro)

    def test_try_first_example_fills_the_type_box(self):
        datasets = [d for d in self._of_type("dataset") if d["props"].get("label") == "Try this first"]
        self.assertEqual(len(datasets), 1)
        self.assertEqual(datasets[0]["props"]["samples"], [["I fell down earlier and I'm scared"]])
        comps = datasets[0]["props"]["components"]
        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0]["name"], "textbox")

    def test_example_chips_run_the_send_turn(self):
        """#239: each chip fills its input, then runs the same turn as Send."""
        deps = self.config["dependencies"]
        send = [d for d in deps if (d["targets"][0][1] == "click" and d["api_name"] == "run_demo_turn_streaming")]
        self.assertEqual(len(send), 1)
        send = send[0]
        labels = ("Try this first", "No mic? Try a sample clip")
        for label in labels:
            ds = [d for d in self._of_type("dataset") if d["props"].get("label") == label][0]
            fill = [d for d in deps if d["targets"][0] == [ds["id"], "click"] or tuple(d["targets"][0]) == (ds["id"], "click")]
            self.assertEqual(len(fill), 1, label)
            chained = [d for d in deps if d.get("trigger_after") == fill[0]["id"]]
            self.assertEqual(len(chained), 1, label)
            self.assertEqual(chained[0]["inputs"], send["inputs"])
            self.assertEqual(chained[0]["outputs"], send["outputs"])
            self.assertTrue(chained[0]["api_name"].startswith("run_demo_turn_streaming"))

    def test_transparency_notice_is_one_line_with_privacy_link(self):
        notice = [v for v in self.markdown if "TRANSPARENCY NOTICE" in v]
        self.assertEqual(len(notice), 1)
        line = [l for l in notice[0].split("\n") if "TRANSPARENCY NOTICE" in l]
        self.assertEqual(len(line), 1)
        self.assertIn("Privacy notice", line[0])
        self.assertIn(webapp.PRIVACY_NOTICE_URL, line[0])

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
