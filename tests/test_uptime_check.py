"""uptime_check: probe, two-try rule, and the Issue open / adopt / throttle / close rules.

HTTP and ``gh`` are replaced with fakes; nothing here touches the network.
"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import uptime_check as u  # noqa: E402

NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)


def fake_get(stage="RUNNING", cfg=200, runtime_code=200):
    def get(url, timeout=0):
        if url == u.RUNTIME_URL:
            return runtime_code, json.dumps({"stage": stage})
        return cfg, ""
    return get


class FakeGH(u.GitHub):
    def __init__(self, issue=None, dry_run=False):
        super().__init__("o/r", dry_run)
        self.issue, self.calls = issue, []

    def open_outage(self):
        return self.issue

    def _gh(self, *args):
        self.calls.append(args)
        return ""

    def _write(self, what):
        ok = super()._write(what)
        return False if not ok else self._noop_label(what)

    def _noop_label(self, what):
        # label creation shells out through _run, not _gh; record and skip
        if what.startswith("ensure label"):
            self.calls.append(("label",))
            return False
        return True


class OpenOutageTests(unittest.TestCase):
    def test_paginated_comments_with_bracket_text(self):
        issues = json.dumps([{"number": 5, "body": "", "createdAt": "2026-10-27T00:00:00Z"}])
        page1 = json.dumps([{"created_at": "2026-10-27T01:00:00Z", "body": "[Space][demo]"}])
        page2 = json.dumps([{"created_at": "2026-10-27T02:00:00Z", "body": u.MARKER + " x"}])
        gh = u.GitHub("o/r")
        gh._gh = lambda *a: issues if a[0] == "issue" else page1 + "\n" + page2
        self.assertEqual(gh.open_outage()["last_comment"], "2026-10-27T02:00:00Z")


class ProbeTests(unittest.TestCase):
    def test_up(self):
        self.assertTrue(u.probe(fake_get())["up"])

    def test_stage_not_running(self):
        r = u.probe(fake_get(stage="APP_STARTING"))
        self.assertFalse(r["up"])
        self.assertEqual(r["stage"], "APP_STARTING")

    def test_config_not_200(self):
        self.assertFalse(u.probe(fake_get(cfg=503))["up"])
        self.assertFalse(u.probe(fake_get(cfg=0))["up"])

    def test_runtime_api_error(self):
        r = u.probe(fake_get(runtime_code=500))
        self.assertFalse(r["up"])
        self.assertEqual(r["stage"], "RUNTIME_API_500")


class CheckTests(unittest.TestCase):
    def test_second_try_rescues_cold_start(self):
        seq = iter([("APP_STARTING", 0), ("RUNNING", 200)])
        state = {}

        def get(url, timeout=0):
            if url == u.RUNTIME_URL:
                state["s"], state["c"] = next(seq)
                return 200, json.dumps({"stage": state["s"]})
            return state["c"], ""
        slept = []
        r = u.check(get, sleep=slept.append, gap=7)
        self.assertTrue(r["up"])
        self.assertEqual(slept, [7])

    def test_two_failures_is_down(self):
        r = u.check(fake_get(stage="RUNTIME_ERROR"), sleep=lambda s: None)
        self.assertFalse(r["up"])

    def test_healthy_does_not_sleep(self):
        u.check(fake_get(), sleep=lambda s: self.fail("slept"))


DOWN = {"up": False, "stage": "APP_STARTING", "config": 0}
UP = {"up": True, "stage": "RUNNING", "config": 200}


class ActTests(unittest.TestCase):
    def test_down_opens_issue_with_assignees_and_label(self):
        gh = FakeGH()
        u.act(DOWN, gh, NOW)
        create = [c for c in gh.calls if c[0] == "issue" and c[1] == "create"][0]
        self.assertIn("elevenbaselab,SirTehTarik", create)
        self.assertIn("outage", create)
        title = create[create.index("--title") + 1]
        self.assertIn("Live demo down: APP_STARTING since 2026-10-27T12:00:00Z", title)
        self.assertIn(("label",), gh.calls)

    def test_down_adopts_open_issue_and_comments_first_time(self):
        gh = FakeGH({"number": 252, "body": "", "createdAt": "2026-10-27T00:20:00Z",
                     "last_comment": None})
        u.act(DOWN, gh, NOW)
        self.assertFalse([c for c in gh.calls if c[1] == "create"])
        self.assertTrue([c for c in gh.calls if c[:2] == ("issue", "comment")])

    def test_down_throttles_comments_to_six_hours(self):
        recent = u.iso(NOW - timedelta(hours=5, minutes=59))
        gh = FakeGH({"number": 9, "body": "", "createdAt": recent, "last_comment": recent})
        msg = u.act(DOWN, gh, NOW)
        self.assertEqual(gh.calls, [])
        self.assertIn("already open", msg)
        old = u.iso(NOW - timedelta(hours=6, minutes=1))
        gh = FakeGH({"number": 9, "body": "", "createdAt": old, "last_comment": old})
        u.act(DOWN, gh, NOW)
        self.assertTrue([c for c in gh.calls if c[:2] == ("issue", "comment")])

    def test_recovery_comments_duration_and_closes(self):
        since = u.iso(NOW - timedelta(hours=2, minutes=5))
        gh = FakeGH({"number": 9, "body": f"<!-- down-since: {since} -->",
                     "createdAt": "2026-01-01T00:00:00Z", "last_comment": None})
        u.act(UP, gh, NOW)
        comment = [c for c in gh.calls if c[:2] == ("issue", "comment")][0]
        self.assertIn("down for 2 h 5 min", comment[comment.index("--body") + 1])
        self.assertTrue([c for c in gh.calls if c[:2] == ("issue", "close")])

    def test_recovery_of_adopted_issue_uses_created_at(self):
        gh = FakeGH({"number": 252, "body": "no marker",
                     "createdAt": u.iso(NOW - timedelta(minutes=90)), "last_comment": None})
        u.act(UP, gh, NOW)
        comment = [c for c in gh.calls if c[:2] == ("issue", "comment")][0]
        self.assertIn("down for 1 h 30 min", comment[comment.index("--body") + 1])

    def test_up_without_issue_does_nothing(self):
        gh = FakeGH()
        u.act(UP, gh, NOW)
        self.assertEqual(gh.calls, [])

    def test_dry_run_writes_nothing(self):
        gh = FakeGH(dry_run=True)
        msg = u.act(DOWN, gh, NOW)
        self.assertEqual(gh.calls, [])
        self.assertIn("would open", msg)


if __name__ == "__main__":
    unittest.main()
