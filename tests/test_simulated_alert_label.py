"""The fall sample's caregiver alert is labelled as what it is.

With no outbound channel configured (the default, and always on the hosted
Space), `CaregiverFlags.add()` only writes a local flags file that the caregiver
panel polls: no caregiver device, e-mail or push is contacted. So the panel,
the mobile alert strip and the turn's disclosure note must call it a simulated
caregiver alert shown on this demo panel, and never claim a caregiver was
notified or an alert was dispatched. When a channel IS configured (#201), the
alert is real and must not be called simulated.

Runs offline: no NEBIUS_API_KEY, so the fall line goes through the fast-path.
"""
import os
import re
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp

FAKE_UPLOAD = os.path.join(tempfile.gettempdir(), "fake.wav")
FALL = "I fell down earlier and I'm scared"

# Built from fragments so a repo-wide grep for the old wording stays clean.
FORBIDDEN = re.compile(
    r"caregiver" + r"\s+notified" + r"|alert" + r"\s+dispatched",
    re.IGNORECASE,
)
SIMULATED = re.compile(r"simulated caregiver alert", re.IGNORECASE)
NOTIFY_ENV = ("FY_NOTIFY_CHANNEL", "SPACE_ID")


class _Harness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_dir.cleanup)
        env = {"NEBIUS_API_KEY": ""}
        self.patches = [
            patch.object(webapp, "SESSIONS_DIR", Path(self.temp_dir.name) / "sessions"),
            patch.object(webapp, "SHARED_PROFILE", False),
            patch.object(webapp, "DATA_DIR", Path(self.temp_dir.name) / "data"),
            patch.dict(os.environ, env),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        for key in NOTIFY_ENV:  # channel off, exactly as on the hosted Space
            os.environ.pop(key, None)
        webapp._request_log.clear()

    def _turn(self, said: str, session_id: str):
        with patch.object(webapp.hear, "transcribe", return_value=(said, {"wpm": 0.0, "avg_pause_s": 0.0})):
            return webapp.run_demo_turn(FAKE_UPLOAD, [], session_id)

    def _drain(self):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not [t for t in threading.enumerate() if t.name.startswith("fy-notify")]:
                return
            time.sleep(0.02)


class TestSimulatedAlertLabel(_Harness):
    def _assert_simulated(self, text: str, where: str):
        self.assertRegex(text, SIMULATED, f"{where} must say 'simulated caregiver alert'")
        self.assertNotRegex(text, FORBIDDEN, f"{where} must not claim a notification or dispatch")

    def test_fall_turn_labels_alert_simulated_everywhere(self):
        session_id, _ = webapp.init_session()
        transcript_and_reply = self._turn(FALL, session_id)[0]
        self._drain()
        panel = webapp._format_caregiver_panel(session_id)
        strip = webapp._format_mobile_alert_strip(session_id)
        self._assert_simulated(panel, "caregiver panel")
        self._assert_simulated(strip, "mobile alert strip")
        self._assert_simulated(transcript_and_reply, "turn disclosure note")
        self.assertRegex(panel, re.compile(r"this (demo )?panel", re.IGNORECASE),
                         "the panel must say where the simulated alert appears")

    def test_streaming_turn_disclosure_is_simulated(self):
        session_id, _ = webapp.init_session()
        outputs = list(webapp.run_demo_turn_streaming(None, FALL, [], session_id))
        self._drain()
        self._assert_simulated(outputs[-1][0], "streaming turn disclosure note")

    def test_configured_channel_is_not_called_simulated(self):
        class Ok:
            def send(self, flag, household):
                return None

        session_id, _ = webapp.init_session()
        with patch("notify.get_notifier", return_value=Ok()):
            transcript_and_reply = self._turn(FALL, session_id)[0]
            self._drain()
            panel = webapp._format_caregiver_panel(session_id)
            strip = webapp._format_mobile_alert_strip(session_id)
        for where, text in (("panel", panel), ("strip", strip), ("note", transcript_and_reply)):
            self.assertNotRegex(text, SIMULATED, f"{where}: a real send is not simulated")
            self.assertNotRegex(text, FORBIDDEN, where)


if __name__ == "__main__":
    unittest.main()
