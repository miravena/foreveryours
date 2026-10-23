"""#201: with no real channel (hosted Space, or channel unset) the caregiver
panel previews the exact message the caregiver would get, labelled not sent."""
import os
import unittest
from unittest.mock import patch

import notify
import webapp
from caregiver import CaregiverFlags, DEFAULT_PROFILE_ID
from tests.test_simulated_alert_label import _Harness, FALL


class TestNotifyPreview(_Harness):
    def _panel(self, said=FALL):
        session_id, _ = webapp.init_session()
        note = self._turn(said, session_id)[0]
        self._drain()
        data_dir, _ = webapp._session_dirs(session_id)
        flag = [f for f in CaregiverFlags(DEFAULT_PROFILE_ID, data_dir).all()][-1]
        return webapp._format_caregiver_panel(session_id), note, flag

    def _quoted(self, flag):
        body = notify.build_message(flag).body
        return "\n".join(f"> {l}".rstrip() for l in body.split("\n"))

    def test_preview_local_no_channel(self):
        panel, note, flag = self._panel()
        self.assertIn("Preview — the message Sarah would receive:", panel)
        self.assertIn(self._quoted(flag), panel)
        self.assertIn("Not sent: no notification channel is set up", panel)
        self.assertIn("Sarah would be notified", note)
        self.assertIn("nothing is sent", note)

    def test_preview_on_space(self):
        os.environ["SPACE_ID"] = "x/y"
        os.environ["FY_NOTIFY_CHANNEL"] = "webhook"
        panel, note, flag = self._panel()
        self.assertIn(self._quoted(flag), panel)
        self.assertIn("Not sent: notifications are off in this demo", panel)

    def test_preview_uses_configured_household_label(self):
        os.environ["FY_NOTIFY_HOUSEHOLD_LABEL"] = "Dad at home"
        self.addCleanup(os.environ.pop, "FY_NOTIFY_HOUSEHOLD_LABEL", None)
        panel, _, _ = self._panel()
        self.assertIn("> Household: Dad at home", panel)

    def test_no_transcript_in_preview(self):
        panel, _, _ = self._panel("I fell down earlier and I'm scared, my secret is zebra-quartz-77")
        self.assertNotIn("zebra-quartz-77", panel)

    def test_no_preview_with_channel(self):
        class Ok:
            def send(self, flag, household):
                return None
        with patch("notify.get_notifier", return_value=Ok()):
            panel, note, _ = self._panel()
        self.assertNotIn("Preview —", panel)
        self.assertNotIn("Not sent", panel)
        self.assertNotIn("nothing is sent", note)

    def test_no_preview_without_flag(self):
        session_id, _ = webapp.init_session()
        self.assertNotIn("Preview —", webapp._format_caregiver_panel(session_id))


if __name__ == "__main__":
    unittest.main()
