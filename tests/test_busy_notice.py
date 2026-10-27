"""The page shows one plain busy notice, not a stack of parse-error toasts (#246).

When the hosting proxy answers a Gradio API request with an HTML error page,
the Gradio client toasts "Could not parse server response" once per failed
request and the reply's voice never loads. webapp.BUSY_NOTICE_HEAD is the
script that replaces that with one banner. These tests check it is wired into
the served page and run the script itself under Node with a stub browser
(skipped when Node is not installed).
"""

import json
import shutil
import subprocess
import unittest
import urllib.request

import webapp


class BusyNoticeWiringTest(unittest.TestCase):
    def test_script_carries_the_plain_message(self):
        self.assertIn(json.dumps(webapp.BUSY_MESSAGE), webapp.BUSY_NOTICE_HEAD)
        self.assertTrue(webapp.BUSY_NOTICE_HEAD.startswith("<script>"))
        self.assertNotIn("__MSG__", webapp.BUSY_NOTICE_HEAD)
        self.assertNotIn("__HIDE_MS__", webapp.BUSY_NOTICE_HEAD)

    def test_served_page_config_carries_the_script(self):
        # app.py (the hosted entrypoint) calls build_demo() then launch(), so
        # the head must survive that path, like PAGE_CSS does.
        demo = webapp.build_demo()
        try:
            _, local_url, _ = demo.launch(prevent_thread_lock=True, server_name="127.0.0.1",
                                          quiet=True, show_error=False)
            with urllib.request.urlopen(local_url.rstrip("/") + "/config", timeout=20) as resp:
                config = json.load(resp)
        finally:
            demo.close()
        self.assertIn(webapp.BUSY_NOTICE_HEAD, config.get("head") or "")


HARNESS = r"""
const results = {};
const timers = [];
function el(tag) {
  return { tag, style: {}, attrs: {}, children: [], textContent: "",
           setAttribute(k, v) { this.attrs[k] = v; },
           appendChild(c) { this.children.push(c); return c; },
           querySelectorAll() { return []; } };
}
const parseToast = el("div"); parseToast.textContent = "Error Could not parse server response: SyntaxError: Unexpected token '<'";
const busyToast = el("div"); busyToast.textContent = "Error This application is currently busy. Please try again.";
const realToast = el("div"); realToast.textContent = "Error Something else went wrong";
const body = el("body");
const document = { body, createElement: el, documentElement: body, addEventListener() {},
                   querySelectorAll(sel) { return sel.includes("toast-body") ? [parseToast, busyToast, realToast] : []; } };
class Headers { constructor(h) { this.h = {}; for (const k in (h || {})) this.h[k.toLowerCase()] = h[k]; }
                get(k) { return this.h[k.toLowerCase()] || null; } }
class Response { constructor(body, init) { this.body = body; this.status = init.status;
                 this.headers = new Headers(init.headers); } }
let next;
const xhrs = [];
class XMLHttpRequest {
  constructor() { this.listeners = {}; this.status = 0; this.ct = null; xhrs.push(this); }
  open(m, u) {}
  send() {}
  addEventListener(n, f) { (this.listeners[n] = this.listeners[n] || []).push(f); }
  getResponseHeader() { return this.ct; }
  fire(n) { (this.listeners[n] || []).forEach(f => f()); }
}
const window = {
  fetch: () => Promise.resolve(next), Response, XMLHttpRequest,
  setTimeout(f, ms) { timers.push({ f, ms }); return timers.length; }, clearTimeout(id) { if (timers[id - 1]) timers[id - 1].f = null; },
};
__SCRIPT__
const banner = () => body.children.find(c => c.attrs.role === "status");
(async () => {
  next = { status: 200, headers: new Headers({ "content-type": "application/json" }) };
  const ok = await window.fetch("https://x.hf.space/gradio_api/queue/join", {});
  results.json_passthrough = ok === next;
  results.banner_after_json = !!banner();

  next = { status: 503, headers: new Headers({ "content-type": "text/html" }) };
  const other = await window.fetch("https://x.hf.space/some/page", {});
  results.non_api_passthrough = other === next;
  results.banner_after_non_api = !!banner();

  next = { status: 429, headers: new Headers({ "content-type": "text/html; charset=utf-8" }) };
  const rewritten = await window.fetch("https://x.hf.space/gradio_api/queue/join", {});
  results.rewritten_status = rewritten.status;
  results.rewritten_body = JSON.parse(rewritten.body);
  results.rewritten_ct = rewritten.headers.get("content-type");
  results.banner_text = banner().textContent;
  results.banner_display = banner().style.display;
  results.parse_toast_hidden = parseToast.style.display === "none";
  results.busy_toast_hidden = busyToast.style.display === "none";
  results.real_toast_kept = realToast.style.display !== "none";

  next = { status: 502, headers: new Headers({ "content-type": "text/html" }) };
  await window.fetch("https://x.hf.space/gradio_api/queue/join", {});
  await window.fetch("https://x.hf.space/gradio_api/queue/join", {});
  results.banner_count = body.children.filter(c => c.attrs.role === "status").length;

  const live = timers.filter(t => t.f);
  results.live_timers = live.length;
  results.hide_ms = live[0].ms;
  live[0].f();
  results.banner_after_timeout = banner().style.display;

  const aborted = new window.XMLHttpRequest(); aborted.open("GET", "https://x.hf.space/gradio_api/stream/a/b/playlist.m3u8"); aborted.send();
  aborted.fire("abort"); aborted.fire("loadend");
  results.banner_after_abort = banner().style.display;

  const failed = new window.XMLHttpRequest(); failed.open("GET", "https://x.hf.space/gradio_api/stream/a/b/playlist.m3u8"); failed.send();
  failed.status = 503; failed.ct = "text/html"; failed.fire("loadend");
  results.banner_after_audio_fail = banner().style.display;

  console.log(JSON.stringify(results));
})();
"""


@unittest.skipUnless(shutil.which("node"), "node not installed")
class BusyNoticeBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = webapp.BUSY_NOTICE_HEAD[len("<script>"):-len("</script>")]
        out = subprocess.run(["node", "-e", HARNESS.replace("__SCRIPT__", script)],
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        cls.r = json.loads(out.stdout.strip().splitlines()[-1])

    def test_json_and_non_api_responses_pass_through_untouched(self):
        self.assertTrue(self.r["json_passthrough"])
        self.assertTrue(self.r["non_api_passthrough"])
        self.assertFalse(self.r["banner_after_json"])
        self.assertFalse(self.r["banner_after_non_api"])

    def test_html_api_answer_becomes_a_json_busy_error(self):
        self.assertEqual(self.r["rewritten_status"], 429)
        self.assertEqual(self.r["rewritten_body"]["error"], webapp.BUSY_MESSAGE)
        self.assertEqual(self.r["rewritten_ct"], "application/json")

    def test_one_banner_with_the_plain_message(self):
        self.assertEqual(self.r["banner_text"], webapp.BUSY_MESSAGE)
        self.assertEqual(self.r["banner_display"], "block")
        self.assertEqual(self.r["banner_count"], 1)

    def test_parse_error_toasts_hidden_other_toasts_kept(self):
        self.assertTrue(self.r["parse_toast_hidden"])
        self.assertTrue(self.r["busy_toast_hidden"])
        self.assertTrue(self.r["real_toast_kept"])

    def test_banner_clears_after_the_last_failure(self):
        self.assertEqual(self.r["live_timers"], 1)
        self.assertEqual(self.r["hide_ms"], webapp.BUSY_NOTICE_HIDE_MS)
        self.assertEqual(self.r["banner_after_timeout"], "none")

    def test_failed_reply_audio_shows_the_banner_but_an_abort_does_not(self):
        self.assertEqual(self.r["banner_after_abort"], "none")
        self.assertEqual(self.r["banner_after_audio_fail"], "block")


if __name__ == "__main__":
    unittest.main()
