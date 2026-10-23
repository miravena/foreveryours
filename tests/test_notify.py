"""Outbound caregiver notification (#201, ADR-014): message minimisation,
channel selection, rate limit, failure recording. Nothing here touches a real
network: SMTP goes to an in-process stub server on localhost, the webhook to a
fake opener."""
import email
import email.policy
import json
import os
import re
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import notify
from caregiver import CaregiverFlag, CaregiverFlags
from pipeline import orchestrator
from safety import fastpath

KEY_SHAPED = re.compile(r"\b(?:sk|hf|pk|nvapi)[-_][A-Za-z0-9_-]{6,}|\b[A-Za-z0-9]{32,}\b")
TRANSCRIPT = "I fell down by the old oak tree behind Maple Street and my knee hurts"


def _flag(text=None, severity="distress", told=True):
    return CaregiverFlag(
        text=text or fastpath.CAREGIVER_FLAG_TEXT["distress"], severity=severity,
        created_at=1_700_000_000.0, disclosed_to_senior=told,
    )


class _StubSmtp(socketserver.StreamRequestHandler):
    """Just enough SMTP to take one message."""

    def handle(self):
        w = lambda s: (self.wfile.write(s.encode() + b"\r\n"), self.wfile.flush())
        w("220 stub")
        data_mode, buf = False, []
        for raw in self.rfile:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    data_mode = False
                    self.server.messages.append("\n".join(buf))
                    w("250 queued")
                else:
                    buf.append(line)
                continue
            cmd = line.split(" ")[0].upper()
            if cmd in ("EHLO", "HELO"):
                w("250 stub")
            elif cmd == "DATA":
                data_mode = True
                w("354 go")
            elif cmd == "QUIT":
                w("221 bye")
                return
            else:
                w("250 ok")


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class TestMessage(unittest.TestCase):
    def test_body_has_only_the_allowed_fields(self):
        msg = notify.build_message(_flag(), "Sarah's household")
        body = msg.body
        self.assertIn(fastpath.CAREGIVER_FLAG_TEXT["distress"], body)
        self.assertIn("DISTRESS", body)
        self.assertIn("Senior told: yes", body)
        self.assertIn("Sarah's household", body)
        self.assertIn("2023-11-14", body)
        self.assertNotIn(TRANSCRIPT, body)

    def test_not_told_is_stated_as_not_yet_confirmed(self):
        self.assertIn("not yet confirmed", notify.build_message(_flag(told=False), "h").body)

    def test_key_shaped_strings_are_redacted_even_if_a_flag_text_carried_one(self):
        leaky = _flag(text="check now " + "sk" + "-abcdefghijklmnop1234 and " + "hf" + "_ABCDEFGHIJKLMNOP and " + "a" * 40)
        msg = notify.build_message(leaky, "h")
        for part in (msg.subject, msg.body):
            self.assertIsNone(KEY_SHAPED.search(part), part)

    def test_every_real_flag_text_builds_a_clean_body(self):
        for text in fastpath.CAREGIVER_FLAG_TEXT.values():
            body = notify.build_message(_flag(text=text), "h").body
            self.assertIsNone(KEY_SHAPED.search(body), body)


class TestFromEnv(unittest.TestCase):
    def test_unset_is_null_and_constructs_no_sender(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("smtplib.SMTP") as smtp, patch("smtplib.SMTP_SSL") as ssl, \
             patch("urllib.request.urlopen") as urlopen:
            n = notify.from_env()
            self.assertIsInstance(n, notify.NullNotifier)
            n.send(_flag(), "h")
            smtp.assert_not_called(); ssl.assert_not_called(); urlopen.assert_not_called()

    def test_hosted_space_is_always_null_even_with_a_channel_set(self):
        env = {"FY_NOTIFY_CHANNEL": "smtp", "FY_NOTIFY_TO": "x@example.com", "SPACE_ID": "u/s"}
        with patch.dict(os.environ, env, clear=True):
            self.assertIsInstance(notify.from_env(), notify.NullNotifier)

    def test_channels_and_misconfiguration(self):
        with patch.dict(os.environ, {"FY_NOTIFY_CHANNEL": "smtp"}, clear=True):
            n = notify.from_env()
            self.assertIsInstance(n, notify.SmtpNotifier)
            with self.assertRaises(notify.ConfigError):
                n.send(_flag(), "h")
        with patch.dict(os.environ, {"FY_NOTIFY_CHANNEL": "webhook"}, clear=True):
            self.assertIsInstance(notify.from_env(), notify.WebhookNotifier)
        with patch.dict(os.environ, {"FY_NOTIFY_CHANNEL": "carrier-pigeon"}, clear=True):
            with self.assertRaises(notify.ConfigError):
                notify.from_env().send(_flag(), "h")


class TestSmtp(unittest.TestCase):
    def test_sends_one_message_to_a_stub_server(self):
        srv = _Server(("127.0.0.1", 0), _StubSmtp)
        srv.messages = []
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        n = notify.SmtpNotifier(host="127.0.0.1", port=srv.server_address[1], security="none",
                                to="sarah@example.com", sender="fy@example.com", household_label="Sarah's household")
        n.send(_flag(), "k")
        self.assertEqual(len(srv.messages), 1)
        parsed = email.message_from_string(srv.messages[0], policy=email.policy.default)
        text = "To: %s\n%s" % (parsed["To"], parsed.get_content())
        self.assertIn("To: sarah@example.com", text)
        self.assertIn(fastpath.CAREGIVER_FLAG_TEXT["distress"], text)
        self.assertNotIn("password", text.lower())

    def test_connection_failure_raises(self):
        n = notify.SmtpNotifier(host="127.0.0.1", port=1, security="none", to="a@example.com", timeout=1)
        with self.assertRaises(OSError):
            n.send(_flag(), "k")


class TestWebhook(unittest.TestCase):
    def test_posts_json_with_only_allowed_fields(self):
        seen = {}

        def opener(req, timeout=None):
            seen["url"], seen["data"], seen["timeout"] = req.full_url, req.data, timeout
            class R:
                status = 200
                def __enter__(s): return s
                def __exit__(s, *a): return False
            return R()

        n = notify.WebhookNotifier(url="http://127.0.0.1:9/hook", opener=opener, household_label="H")
        n.send(_flag(), "k")
        payload = json.loads(seen["data"])
        self.assertEqual(set(payload), {"text", "severity", "told", "household", "timestamp"})
        self.assertEqual(payload["severity"], "distress")
        self.assertTrue(payload["told"])

    def test_http_error_status_raises(self):
        class R:
            status = 500
            def __enter__(s): return s
            def __exit__(s, *a): return False
        n = notify.WebhookNotifier(url="http://127.0.0.1:9/hook", opener=lambda req, timeout=None: R())
        with self.assertRaises(notify.DeliveryError):
            n.send(_flag(), "k")

    def test_rejects_non_http_scheme(self):
        n = notify.WebhookNotifier(url="file:///etc/passwd", opener=lambda *a, **k: None)
        with self.assertRaises(notify.ConfigError):
            n.send(_flag(), "k")


class TestTransportSafety(unittest.TestCase):
    def test_starttls_and_ssl_use_a_verifying_context(self):
        import ssl
        for security in ("starttls", "ssl"):
            with self.subTest(security=security), patch("smtplib.SMTP") as plain, patch("smtplib.SMTP_SSL") as tls:
                n = notify.SmtpNotifier(host="h.example.com", user="u", password="p", to="a@example.com",
                                        security=security)
                n.send(_flag(), "k")
                if security == "ssl":
                    ctx = tls.call_args.kwargs["context"]
                else:
                    ctx = plain.return_value.__enter__.return_value.starttls.call_args.kwargs["context"]
                self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(ctx.check_hostname)

    def test_webhook_redirect_is_a_failure_not_a_silent_success(self):
        import http.server

        class H(http.server.BaseHTTPRequestHandler):
            hits = []
            def do_POST(self):
                H.hits.append(self.path)
                self.send_response(302); self.send_header("Location", "/elsewhere"); self.end_headers()
            def do_GET(self):
                H.hits.append("GET " + self.path)
                self.send_response(200); self.end_headers()
            def log_message(self, *a): pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        n = notify.WebhookNotifier(url=f"http://127.0.0.1:{srv.server_address[1]}/hook")
        with self.assertRaises(Exception) as ctx:
            n.send(_flag(), "k")
        self.assertEqual(type(ctx.exception).__name__, "HTTPError")
        self.assertEqual(H.hits, ["/hook"])


class TestRateLimit(unittest.TestCase):
    def test_cap_per_household_per_hour_then_refills(self):
        clock = [1000.0]
        sent = []
        n = notify.WebhookNotifier(url="http://127.0.0.1:9/h", max_per_hour=2, clock=lambda: clock[0],
                                   opener=lambda req, timeout=None: sent.append(1) or _Ok())
        n.send(_flag(), "a"); n.send(_flag(), "a")
        with self.assertRaises(notify.RateLimited):
            n.send(_flag(), "a")
        n.send(_flag(), "b")  # another household has its own budget
        self.assertEqual(len(sent), 3)
        clock[0] += 3601
        n.send(_flag(), "a")
        self.assertEqual(len(sent), 4)


class _Ok:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Boom:
    def send(self, flag, household):
        raise ConnectionRefusedError("sk" + "-abcdefghijklmnop leaked in message")


class _Rec:
    def __init__(self): self.calls = []
    def send(self, flag, household): self.calls.append((flag, household))


class TestNotifyFlagHelper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.flags = CaregiverFlags("p", Path(self.tmp.name))

    def test_success_is_recorded_on_the_flag_and_on_disk(self):
        rec = _Rec()
        flag = self.flags.add("x", severity="distress", disclosed_to_senior=True)
        orchestrator._notify_flag(self.flags, flag, rec)
        self.assertEqual(len(rec.calls), 1)
        self.assertIs(CaregiverFlags("p", Path(self.tmp.name)).all()[0].notified, True)

    def test_failure_records_type_name_only_and_never_raises(self):
        flag = self.flags.add("x", severity="distress", disclosed_to_senior=True)
        orchestrator._notify_flag(self.flags, flag, _Boom())
        stored = CaregiverFlags("p", Path(self.tmp.name)).all()[0]
        self.assertIs(stored.notified, False)
        self.assertEqual(stored.notify_error, "ConnectionRefusedError")
        self.assertNotIn("sk-", json.dumps(stored.__dict__))

    def test_off_leaves_the_flag_file_byte_identical(self):
        flag = self.flags.add("x", severity="distress", disclosed_to_senior=True)
        before = self.flags.path.read_bytes()
        orchestrator._notify_flag(self.flags, flag, notify.NullNotifier())
        self.assertEqual(self.flags.path.read_bytes(), before)
        self.assertNotIn(b"notif", before)

    def test_old_flag_files_still_load(self):
        self.flags.path.write_text(json.dumps([{"text": "t", "severity": "info", "created_at": 1.0,
                                                "disclosed_to_senior": False}]))
        f = CaregiverFlags("p", Path(self.tmp.name)).all()[0]
        self.assertIsNone(f.notified)

    def test_unknown_keys_in_a_flag_file_are_ignored_on_load(self):
        self.flags.path.write_text(json.dumps([{"text": "t", "severity": "info", "created_at": 1.0,
                                                "disclosed_to_senior": False, "from_the_future": 1}]))
        self.assertEqual(CaregiverFlags("p", Path(self.tmp.name)).all()[0].text, "t")

    def test_helper_survives_a_broken_flag_store(self):
        class Broken:
            path = Path("/nonexistent")
            def mark_notified(self, *a, **k): raise RuntimeError("disk")
        orchestrator._notify_flag(Broken(), _flag(), _Rec())  # must not raise


if __name__ == "__main__":
    unittest.main()
