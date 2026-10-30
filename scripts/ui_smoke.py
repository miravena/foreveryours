#!/usr/bin/env python3
"""Browser smoke test for the ForeverYours web demo: click what a judge clicks.

Opens the Gradio app in headless Chromium (Playwright) and, in a fresh page (so a
fresh household) per step, drives the page the way a judge does: the "Try this first"
chip, each "No mic? Try a sample clip" button (which runs the local Whisper, so this
covers audio input too), a typed message plus Send, "Load sample family", a saved
text memo, the guided interview, and the fall phrase ending in the DISTRESS alert and
"Dad was told" on the caregiver panel. It also touches every other control a judge can reach:
the microphone Record button (with a fake microphone: Chromium plays a WAV file as the
mic), its Pause/Resume/Stop and device dropdown, the upload button, the recorded clip's
player controls and its clear (the X), the caregiver "Record Voice Memo" and "Type Note" tabs, every
accordion, the Enter key, and that the companion's reply audio element receives audio and
plays, and that a 2,001-character message or memo gets the polite refusal. It waits on page state, never a fixed sleep (the only timed waits are how long the fake
microphone records), saves one screenshot per step and size and prints PASS/FAIL per step.
Exit code 1 if any step fails.

It runs the whole suite at the desktop size and, with `--device`, with Playwright device
emulation for a phone (`pixel7`, `iphone14`, or `all`). Each size also gets a layout check
(horizontal overflow, controls off the screen, clipped text, overlapping controls) printed as
LAYOUT lines and listed at the end; layout findings are reported, they do not fail a step.
Emulation sets the viewport, pixel ratio, touch and user agent of Chromium (the only engine
installed here); it is not the real phone's browser.

It is NOT part of the unittest suite or CI: it needs a running server and a browser.
Start the app yourself, then run this against it:

    .venv/bin/python webapp.py                         # terminal 1 (http://127.0.0.1:7860/)
    .venv/bin/python scripts/ui_smoke.py               # terminal 2, hosted model reachable
    .venv/bin/python scripts/ui_smoke.py --offline-ok  # terminal 2, app started without a key
    .venv/bin/python scripts/ui_smoke.py --device all  # desktop, Pixel 7 and iPhone 14
    FY_DEV_MODE=1 .venv/bin/python webapp.py           # then add --dev-ui to try the dev-only controls

Needs the Python `playwright` package and a Chromium it can launch
(`pip install playwright`; `playwright install chromium` if none is installed).
Run it against a local server only, never against the public Space.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

FALL = "I fell down earlier and I'm scared"
TYPED = "What's my grandson's name?"  # the placeholder's own example
MEMO = "Dad has a check-up with Dr. Tan on Thursday at 10 AM."
INTERVIEW_ANSWER = "Sarah is his daughter. His grandson Leo is nine. Rosa next door is his oldest friend."
CLIPS = (
    "Dad asks what's happening today",
    "Dad talks about jazz",
    "Dad asks his grandson's name",
    "Dad says he fell and is scared",
)

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
MIC_WAV = SAMPLES / "senior_distress.wav"   # what the fake microphone "hears" on the senior side
MEMO_WAV = SAMPLES / "caregiver_memo.wav"   # ... and for the caregiver voice memo
UPLOAD_WAV = SAMPLES / "senior_jazz.wav"
DEVICES = {"desktop": None, "pixel7": "Pixel 7", "iphone14": "iPhone 14"}  # name -> playwright.devices key
RECORD_S = 6          # how long the fake microphone records (the only timed wait in this file)
LONG_CHARS = 2001     # one over the default input cap (FY_MAX_INPUT_CHARS / FY_MAX_MEMO_CHARS, 2000)
LONG_SENTENCE = "The garden was lovely today and the roses are out. "
MEMO_RECORD_S = 12    # caregiver_memo.wav is 11.3 s

# Logs the reply player's media events (play/playing/waiting/ended/...) into window.__ev, to
# tell "the audio element received audio and played" from "a player exists".
AUDIO_EVENTS_JS = """
window.__ev = [];
const log = (e) => window.__ev.push({t: Math.round(performance.now()), type: e.type, ct: e.target.currentTime,
  dur: e.target.duration, rs: e.target.readyState});
const hook = (a) => { if (a.__hooked) return; a.__hooked = true;
  for (const n of ['play','playing','pause','waiting','stalled','ended','error','canplay']) a.addEventListener(n, log); };
new MutationObserver(() => document.querySelectorAll('audio').forEach(hook)).observe(document, {childList: true, subtree: true});
setInterval(() => document.querySelectorAll('audio').forEach(hook), 200);
"""

# One pass over what the page shows: returns a list of short findings.
LAYOUT_JS = """
() => {
  const out = [], vw = window.innerWidth;
  const label = (e) => ((e.getAttribute('aria-label') || e.innerText || e.getAttribute('placeholder') || e.className || e.tagName)
    + '').trim().replace(/\\s+/g, ' ').slice(0, 40);
  if (document.documentElement.scrollWidth > vw + 1)
    out.push(`horizontal scroll: page is ${document.documentElement.scrollWidth}px wide in a ${vw}px viewport`);
  const shown = (e) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05; };
  const ctl = [...document.querySelectorAll('button, a[href], input, textarea, select, audio')].filter(shown);
  for (const e of ctl) { const r = e.getBoundingClientRect();
    if (r.left < -1 || r.right > vw + 1) out.push(`off-screen: "${label(e)}" spans ${Math.round(r.left)}..${Math.round(r.right)} of ${vw}px`); }
  for (const e of document.querySelectorAll('button, label, p, h1, h2, h3, span, li, a')) {
    if (!shown(e) || !e.innerText || !e.innerText.trim()) continue;
    const cs = getComputedStyle(e);
    if (e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0 && cs.overflowX !== 'visible' && !['inline'].includes(cs.display))
      out.push(`clipped text: "${label(e)}" is ${e.scrollWidth}px of text in ${e.clientWidth}px`); }
  const boxes = ctl.filter(e => e.tagName !== 'AUDIO').map(e => [e, e.getBoundingClientRect()]);
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, ra] = boxes[i], [b, rb] = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (w > 4 && h > 4 && w * h > 0.25 * Math.min(ra.width * ra.height, rb.width * rb.height))
      out.push(`overlap: "${label(a)}" and "${label(b)}" share ${Math.round(w)}x${Math.round(h)}px`); }
  return out.slice(0, 12);
}
"""

UNREACHABLE = "isn't reachable right now"  # the app's keyless-turn notice (webapp.py)
LOAD_TIMEOUT_MS = 90_000
TURN_TIMEOUT_MS = 240_000  # a turn can wait on local Whisper, a hosted model and TTS


class Smoke:
    def __init__(self, url: str, out: Path, offline_ok: bool, headed: bool, device: str = "desktop", dev_ui: bool = False,
                 only: tuple[str, ...] = ()):
        self.url, self.out, self.offline_ok, self.headed = url, out, offline_ok, headed
        self.device, self.dev_ui, self.only = device, dev_ui, only
        self.results: list[tuple[str, bool, str]] = []
        self.layout: dict[str, list[str]] = {}   # finding -> steps that showed it
        self.pw = None
        self.contexts: dict = {}

    # ---- page text helpers (the app has no element ids; its labels are the contract) ----

    @staticmethod
    def body(page) -> str:
        return page.inner_text("body")

    @classmethod
    def caregiver(cls, page) -> str:
        """Text of the caregiver column: everything after its heading."""
        text = cls.body(page)
        return text.split("Caregiver side (live)", 1)[1] if "Caregiver side (live)" in text else ""

    @classmethod
    def transcript(cls, page) -> str:
        """The conversation block: from 'Dad said:' to the reply player's label."""
        text = cls.body(page)
        start = text.find("Dad said:")
        if start < 0:
            return ""
        end = text.find("Companion's reply", start)
        return text[start:end if end > 0 else None].strip()

    @staticmethod
    def wait_for(page, predicate, what: str, timeout_ms: int = TURN_TIMEOUT_MS):
        """Poll page state until predicate() is truthy; no fixed sleeps."""
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            page.wait_for_timeout(250)
        raise AssertionError(f"timed out after {timeout_ms // 1000}s waiting for {what}")

    def context_options(self) -> dict:
        key = DEVICES[self.device]
        if key is None:
            return {"viewport": {"width": 1400, "height": 1200}}
        opts = dict(self.pw.devices[key])
        opts.pop("default_browser_type", None)  # Chromium is the only engine installed here
        return opts

    def open_page(self, browser):
        # A new context per page: a fresh household, nothing shared between steps.
        ctx = browser.new_context(permissions=["microphone"], **self.context_options())
        ctx.add_init_script(AUDIO_EVENTS_JS)
        page = ctx.new_page()
        page.fy_ctx = ctx
        page.fy_net = []  # every streamed-reply response, for the audio-delivery check
        page.on("response", lambda r: page.fy_net.append(r) if "/stream/" in r.url else None)
        page.set_default_timeout(LOAD_TIMEOUT_MS)
        page.goto(self.url, wait_until="domcontentloaded")
        page.get_by_role("button", name="Send", exact=True).wait_for()
        # The household is created by the page-load event; wait until the panel shows it.
        self.wait_for(page, lambda: "Briefed memory" in self.caregiver(page)
                      and "Setting up your demo household" not in self.caregiver(page),
                      "the caregiver panel to finish loading", LOAD_TIMEOUT_MS)
        return page

    def wait_reply(self, page, expect_turns: int = 1) -> str:
        """Wait for the turn to finish and return the transcript.

        A real turn shows "Companion replied:" and the panel counts the conversation. With no
        key the app instead shows a notice that the live model is unreachable (the fast-path
        still answers a fall offline): that counts as the reply only under --offline-ok, and
        fails at once otherwise instead of waiting out the timeout.
        """
        def done():
            t = self.transcript(page)
            counted = re.search(r"Today:\s*(\d+) conversation", self.caregiver(page))
            if "Companion replied:" in t and counted and int(counted.group(1)) >= expect_turns:
                return t
            if UNREACHABLE in t:
                return t
            return None
        transcript = self.wait_for(page, done, "the companion's reply on the transcript")
        if "Companion replied:" not in transcript:
            assert self.offline_ok, "the hosted model is unreachable (no key?); rerun with --offline-ok to accept that"
            return transcript
        reply = transcript.split("Companion replied:", 1)[1].strip().strip('"').strip()
        assert reply, "the companion's reply is empty"
        return transcript

    # ---- steps ----

    def step(self, name: str, browser, fn):
        shot_dir = self.out / self.device
        shot_dir.mkdir(parents=True, exist_ok=True)
        shot = shot_dir / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".png")
        page = None
        try:
            page = self.open_page(browser)
            detail = fn(page) or ""
            ok = True
        except (AssertionError, PlaywrightTimeout, PlaywrightError) as exc:
            ok, detail = False, str(exc).strip().splitlines()[0][:300] if str(exc).strip() else repr(exc)
        finally:
            if page is not None:
                try:
                    for finding in page.evaluate(LAYOUT_JS):
                        self.layout.setdefault(finding, []).append(name)
                        print(f"LAYOUT  [{self.device}] {name}: {finding}", flush=True)
                except PlaywrightError:
                    pass
                try:
                    page.screenshot(path=str(shot), full_page=True)
                except PlaywrightError:
                    pass
                page.fy_ctx.close()
        self.results.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  [{self.device}] {name}" + (f"  -- {detail}" if detail else "") + f"  [{shot}]", flush=True)

    def s_loads(self, page):
        body = self.body(page)
        assert "Senior side" in body and "Caregiver side (live)" in body, "a side is missing"
        for label in ("Send", "Load sample family", "Save Text Memo"):
            assert page.get_by_role("button", name=label).first.is_visible(), f"button {label!r} not visible"
        assert page.get_by_label("Type (as the senior)").is_visible(), "the Type box is not visible"
        assert "What ForeverYours has told you" in self.caregiver(page), "caregiver panel did not render"
        assert "Calm" in self.caregiver(page), "a fresh household should start calm"

    def s_chip(self, page, label: str, expect_alert: bool = False):
        page.get_by_role("button", name=label, exact=True).click()
        transcript = self.wait_reply(page)
        if expect_alert:
            self.wait_for(page, lambda: "DISTRESS" in self.caregiver(page), "the DISTRESS alert", 60_000)
        said = transcript.split("Companion replied:", 1)[0].split("\n\n", 1)[0]
        assert re.search(r'Dad said:\s*"\s*\S', said), f"nothing was heard/typed as Dad: {said!r}"
        return f"reply {len(transcript)} chars"

    def s_typed(self, page):
        page.get_by_label("Type (as the senior)").fill(TYPED)
        page.get_by_role("button", name="Send", exact=True).click()
        transcript = self.wait_reply(page)
        assert TYPED in transcript, f"the typed message is not in the transcript: {transcript[:120]!r}"
        self.wait_for(page, lambda: page.get_by_label("Type (as the senior)").input_value() == "",
                      "the Type box to clear after Send", 30_000)

    def s_sample_family(self, page):
        assert "Fictional sample household" not in self.caregiver(page), "sample card shown before the click"
        page.get_by_role("button", name="Load sample family").click()
        self.wait_for(page, lambda: "Fictional sample household" in self.caregiver(page),
                      "the fictional sample household card", 60_000)

    def s_memo(self, page):
        box = page.get_by_label("Write context memo")
        box.fill(MEMO)
        page.get_by_role("button", name="Save Text Memo").click()
        self.wait_for(page, lambda: "Dr. Tan" in self.caregiver(page),
                      "the memo on the caregiver panel", 60_000)
        self.wait_for(page, lambda: box.input_value() == "", "the memo box to clear", 30_000)

    def s_interview(self, page):
        header = page.get_by_role("button", name=re.compile(r"Guided interview"))
        if header.count() == 0 or not header.first.is_visible():
            raise AssertionError("the guided interview is not on the page")
        header.first.click()
        page.get_by_role("button", name="Start / resume").click()
        self.wait_for(page, lambda: "Question 1 of 5" in self.body(page), "question 1 of 5", 30_000)
        page.get_by_label("Your answer").fill(INTERVIEW_ANSWER)
        page.get_by_role("button", name="Confirm answer").click()
        self.wait_for(page, lambda: "Question 2 of 5" in self.body(page) and "1 of 5 answered" in self.body(page),
                      "question 2 after confirming answer 1", 60_000)
        self.wait_for(page, lambda: "Rosa next door" in self.caregiver(page),
                      "the interview answer in Briefed memory", 60_000)
        page.get_by_role("button", name="Skip", exact=True).click()
        self.wait_for(page, lambda: "Question 3 of 5" in self.body(page) and "1 skipped" in self.body(page),
                      "question 3 after skipping question 2", 30_000)

    def s_fall(self, page):
        page.get_by_label("Type (as the senior)").fill(FALL)
        page.get_by_role("button", name="Send", exact=True).click()
        self.wait_reply(page)
        panel = self.wait_for(
            page, lambda: (lambda c: c if "DISTRESS" in c and "Dad was told" in c else None)(self.caregiver(page)),
            "DISTRESS and 'Dad was told' on the caregiver panel", 60_000)
        assert "HIGH PRIORITY SAFETY ALERT" in panel, "no safety alert card on the caregiver panel"

    # ---- steps added for every other control ----

    @staticmethod
    def visible(page, locator) -> bool:
        try:
            return locator.first.is_visible()
        except PlaywrightError:
            return False

    def record_with_fake_mic(self, page, seconds: int = RECORD_S, pause: bool = False, memo: bool = False):
        """Record / (Pause / Resume) / Stop on the senior recorder (the caregiver memo's with memo=True).

        Chromium feeds the fake microphone from the WAV given at launch; the recording length is
        the one thing here that is a plain timed wait.
        """
        pick = (lambda loc: loc.last) if memo else (lambda loc: loc.first)  # the memo recorder is the second on the page
        pick(page.locator("button.record-button:visible")).click()
        pick(page.locator("button.stop-button:visible")).wait_for()
        if pause:
            page.wait_for_timeout(1000)
            page.get_by_role("button", name="pause", exact=True).click()
            page.get_by_role("button", name="Resume", exact=True).wait_for()
            page.get_by_role("button", name="Resume", exact=True).click()
            page.get_by_role("button", name="pause", exact=True).wait_for()
        page.wait_for_timeout(seconds * 1000)
        pick(page.locator("button.stop-button:visible")).click()
        pick(page.get_by_role("button", name="Play", exact=True)).wait_for()

    def send_and_read(self, page) -> str:
        page.get_by_role("button", name="Send", exact=True).click()
        transcript = self.wait_reply(page)
        said = transcript.split("Companion replied:", 1)[0].split("\n\n", 1)[0]
        assert re.search(r'Dad said:\s*"\s*\S', said), f"nothing was heard as Dad: {said!r}"
        return transcript

    def s_mic_record(self, page):
        self.record_with_fake_mic(page, pause=True)
        transcript = self.send_and_read(page)
        assert self.wait_for(page, lambda: not self.visible(page, page.get_by_role("button", name="Play", exact=True)),
                             "the recorded clip to clear after Send", 30_000) is not None
        if "fell" in transcript.lower():
            self.wait_for(page, lambda: "DISTRESS" in self.caregiver(page), "the DISTRESS alert", 60_000)
        return f"Dad said: {transcript.split('Companion replied:', 1)[0][:70].strip()!r}"

    def s_mic_devices(self, page):
        select = page.locator("select.mic-select")
        names = select.locator("option").all_inner_texts()
        assert len(names) >= 2, f"the device dropdown lists {names!r}, wanted at least two devices"
        for i, name in enumerate(names):
            select.select_option(index=i)
            assert select.locator("option:checked").inner_text() == name, f"{name!r} was not selected"
            self.record_with_fake_mic(page, seconds=3)
            page.get_by_role("button", name="Clear", exact=True).first.click()
            self.wait_for(page, lambda: self.visible(page, page.locator("button.record-button:visible")),
                          "the Record button after Clear", 15_000)
        return "devices: " + " | ".join(names)

    def s_player_controls(self, page):
        """The recorded clip's own player: play, speed, skip, volume, reset, trim, download."""
        self.record_with_fake_mic(page, seconds=4)
        page.get_by_role("button", name="Play", exact=True).click()
        page.get_by_role("button", name="Pause", exact=True).wait_for()
        speed = page.get_by_role("button", name=re.compile("Adjust playback speed")).first
        before = speed.get_attribute("aria-label")
        speed.click()
        after = self.wait_for(page, lambda: (lambda a: a if a != before else None)(speed.get_attribute("aria-label")),
                              "the speed button to change", 5000)
        page.get_by_role("button", name=re.compile("Skip backwards")).click()
        page.get_by_role("button", name=re.compile("Skip forward")).click()
        page.get_by_role("button", name="Adjust volume").click()
        assert page.locator(".volume-slider").first.is_visible(), "the volume slider did not open"
        page.get_by_role("button", name="Pause", exact=True).click()
        page.get_by_role("button", name="Play", exact=True).wait_for()
        page.get_by_role("button", name="Reset audio").click()
        page.get_by_role("button", name="Trim audio to selection").click()
        page.get_by_role("button", name="Cancel", exact=True).wait_for()
        page.get_by_role("button", name="Cancel", exact=True).click()
        page.get_by_role("button", name="Trim audio to selection").wait_for()
        with page.expect_download() as dl:
            page.get_by_role("button", name="Download").first.click()
        return f"speed {before!r} -> {after!r}; downloaded {dl.value.suggested_filename!r}"

    def choose_upload(self, page, path: Path):
        page.get_by_role("button", name="Upload file", exact=True).first.click()
        page.locator("input[type=file]:visible, input[type=file]").first.set_input_files(str(path))
        page.get_by_role("button", name="Play", exact=True).first.wait_for()

    def s_upload(self, page):
        self.choose_upload(page, UPLOAD_WAV)
        transcript = self.send_and_read(page)
        return f"Dad said: {transcript.split('Companion replied:', 1)[0][:70].strip()!r}"

    def s_upload_bad(self, page):
        bad = Path(self.out) / "not-audio.wav"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"this is text, not audio\n" * 40)
        page.get_by_role("button", name="Upload file", exact=True).first.click()
        page.locator("input[type=file]").first.set_input_files(str(bad))
        page.wait_for_timeout(1500)  # the widget may reject the file at once or accept it for Send to refuse
        page.get_by_role("button", name="Send", exact=True).click()
        def refused():
            t = self.body(page)
            return next((m for m in ("Couldn't make out", "couldn't", "Record audio or type", "not a supported", "unsupported",
                                     "Error", "error", "isn't reachable", "unexpected error") if m in t), None)
        what = self.wait_for(page, refused, "a notice for a file that is not audio", 60_000)
        assert "Traceback" not in self.body(page), "a traceback reached the page"
        return f"notice: {what!r}"

    def s_clear(self, page):
        self.choose_upload(page, UPLOAD_WAV)
        page.get_by_role("button", name="Clear", exact=True).first.click()
        self.wait_for(page, lambda: not self.visible(page, page.get_by_role("button", name="Play", exact=True)),
                      "the clip to disappear after the X", 15_000)
        page.get_by_role("button", name="Send", exact=True).click()
        self.wait_for(page, lambda: "Record audio or type what Dad says first" in self.body(page),
                      "the 'nothing to send' notice after clearing", 30_000)

    def s_accordions(self, page):
        cases = (
            ("How long your recordings and household data are kept", r"minutes after you close this tab"),
            ("About this demo household", r"Nobody else on this link sees it"),
            ("Brief Dad companion", r"Write context memo"),
            ("Guided interview", r"Start / resume"),
        )
        detail = []
        for title, probe in cases:
            header = page.get_by_role("button", name=re.compile(re.escape(title))).first
            body = page.get_by_text(re.compile(probe)).first
            first = body.is_visible()
            header.click()
            self.wait_for(page, lambda: body.is_visible() != first, f"{title!r} to toggle", 8000)
            header.click()
            self.wait_for(page, lambda: body.is_visible() == first, f"{title!r} to toggle back", 8000)
            detail.append(f"{title.split(' ')[0]} {'open' if first else 'closed'} at start")
        return "; ".join(detail)

    def s_enter_sends(self, page):
        box = page.get_by_label("Type (as the senior)")
        box.fill(TYPED)
        box.press("Enter")
        transcript = self.wait_reply(page)
        assert TYPED in transcript, f"Enter did not send the typed message: {transcript[:120]!r}"

    def s_reply_audio(self, page):
        """The fall reply is spoken offline too, so this works with or without a key."""
        page.get_by_label("Type (as the senior)").fill(FALL)
        page.get_by_role("button", name="Send", exact=True).click()
        self.wait_reply(page)
        def playing():
            state = page.evaluate("""() => [...document.querySelectorAll('audio')].map(a =>
                ({dur: a.duration, ct: a.currentTime, rs: a.readyState, ended: a.ended}))""")
            return next((a for a in state if a["dur"] and a["dur"] > 0 and a["rs"] > 0 and (a["ct"] > 0 or a["ended"])), None)
        audio = self.wait_for(page, playing, "the reply audio element to receive audio and play", 60_000)
        self.wait_for(page, lambda: page.evaluate("window.__ev.some(e => e.type === 'ended')"),
                      "the reply audio to play to its end", 60_000)
        events = page.evaluate("window.__ev")
        first = next((e["t"] for e in events if e["type"] == "playing"), None)
        stalls = []
        waiting = None
        for e in events:
            if e["type"] == "waiting" and first is not None and e["t"] > first:
                waiting = e
            elif e["type"] == "playing" and waiting is not None:
                stalls.append(f"{e['t'] - waiting['t']} ms at {waiting['ct']:.1f} s")
                waiting = None
        segs = [r for r in page.fy_net if ".aac" in r.url]
        got = sum(len(r.body()) for r in segs)
        assert segs and got > 0, "no streamed audio segment reached the browser"
        assert all(r.status == 200 for r in segs), "a streamed audio segment was refused"
        return (f"{len(segs)} segment(s), {got} bytes, element {audio['dur']:.1f} s long, played to the end"
                + (f"; STALLED mid-reply: {', '.join(stalls)}" if stalls else "; no stall"))

    def s_too_long(self, page):
        """A 2,001-character typed message gets the polite refusal, no reply and no counted turn (#37)."""
        text = (LONG_SENTENCE * 100)[:LONG_CHARS]
        assert len(text) == LONG_CHARS
        box = page.get_by_label("Type (as the senior)")
        box.fill(text)
        page.get_by_role("button", name="Send", exact=True).click()
        self.wait_for(page, lambda: "That is a lot to take in at once" in self.body(page),
                      "the polite too-long refusal", 60_000)
        body = self.body(page)
        assert f"({LONG_CHARS} characters; the limit is 2000)" in body, "the refusal does not state the length and the limit"
        assert "Nothing was sent" in body, "the refusal does not say nothing was sent"
        assert "Companion replied:" not in body, "a companion reply appeared for an over-long message"
        assert page.get_by_role("button", name="Play", exact=True).count() == 0 or not self.visible(page, page.get_by_role("button", name="Play", exact=True)), \
            "a reply player appeared"
        assert "Traceback" not in body, "a traceback reached the page"
        assert not re.search(r"Today:\s*[1-9]\d* conversation", self.caregiver(page)), "the refused message was counted as a conversation"
        assert box.input_value() == text, "the typed text was not handed back into the box"

    def s_memo_too_long(self, page):
        """A 2,001-character text memo is refused and nothing is saved."""
        text = (LONG_SENTENCE * 100)[:LONG_CHARS]
        box = page.get_by_label("Write context memo")
        box.fill(text)
        page.get_by_role("button", name="Save Text Memo").click()
        self.wait_for(page, lambda: "too long to save" in self.body(page), "the polite too-long memo refusal", 60_000)
        assert "Nothing was saved" in self.body(page), "the refusal does not say nothing was saved"
        assert "garden was lovely" not in self.caregiver(page), "the refused memo reached Briefed memory"

    def s_memo_tabs(self, page):
        note, voice = page.get_by_role("tab", name="Type Note"), page.get_by_role("tab", name="Record Voice Memo")
        box = page.get_by_label("Write context memo")
        assert box.is_visible(), "Type Note is not the first tab"
        voice.click()
        self.wait_for(page, lambda: not box.is_visible() and self.visible(page, page.get_by_role("button", name="Save Voice Memo")),
                      "the Record Voice Memo tab", 8000)
        note.click()
        self.wait_for(page, lambda: box.is_visible(), "the Type Note tab again", 8000)
        box.fill(MEMO)
        box.press("Shift+Enter")  # a two-line box: Shift+Enter submits, as Gradio's textbox does
        self.wait_for(page, lambda: "Dr. Tan" in self.caregiver(page), "the memo saved with Shift+Enter", 60_000)

    def memo_items(self, page) -> int:
        return self.caregiver(page).count("caregiver_memo")

    def s_memo_voice(self, page):
        before = self.memo_items(page)
        page.get_by_role("tab", name="Record Voice Memo").click()
        self.record_with_fake_mic(page, seconds=MEMO_RECORD_S, memo=True)
        page.get_by_role("button", name="Save Voice Memo").click()
        self.wait_memo_saved(page, before)
        return f"memory items {before} -> {self.memo_items(page)}"

    def wait_memo_saved(self, page, before: int):
        """Wait for the saved voice memo in Briefed memory; a refusal notice fails at once, with its text."""
        def saved():
            if self.memo_items(page) > before:
                return True
            notice = re.search(r"⚠️[^\n]*", self.caregiver(page))
            assert not notice, f"the voice memo was refused: {notice.group(0)[:200]!r}"
            return False
        self.wait_for(page, saved, "the voice memo to appear in Briefed memory", 120_000)

    def s_memo_upload(self, page):
        before = self.memo_items(page)
        page.get_by_role("tab", name="Record Voice Memo").click()
        page.get_by_role("button", name="Upload file", exact=True).last.click()  # the memo widget opens in record mode
        page.locator("input[type=file]").last.set_input_files(str(MEMO_WAV))
        page.get_by_role("button", name="Play", exact=True).last.wait_for()
        page.get_by_role("button", name="Save Voice Memo").click()
        self.wait_memo_saved(page, before)
        return f"memory items {before} -> {self.memo_items(page)}"

    def s_links(self, page):
        found = {}
        for name in ("Privacy notice", "Safety & privacy design"):
            link = page.get_by_role("link", name=name).first
            href = link.get_attribute("href") or ""
            assert href.startswith("http"), f"{name!r} has no http link: {href!r}"
            found[name] = href
        return "not followed (external); " + ", ".join(f"{k} -> {v}" for k, v in found.items())

    def s_dev_controls_absent(self, page):
        for label in ("Simulated Time of Day", "Clinical Configuration", "Morning Greeting", "Silence Check-in"):
            assert page.get_by_text(label).count() == 0 or not page.get_by_text(label).first.is_visible(), \
                f"{label!r} is visible on the hosted UI"
        return "time-of-day dropdown and proactive buttons are hidden unless FY_DEV_MODE=1"

    def s_dev_controls(self, page):
        page.get_by_role("button", name=re.compile("Clinical Configuration")).click()
        drop = page.get_by_label("Simulated Time of Day")
        drop.click()
        options = page.get_by_role("option").all_inner_texts()
        assert len(options) == 3, f"time-of-day options: {options!r}"
        page.get_by_role("option", name=re.compile("Evening")).click()
        assert "Evening" in drop.input_value(), "the Evening option was not chosen"
        page.get_by_role("button", name=re.compile("Simulate Proactive Triggers")).click()
        for label in ("Morning Greeting", "Caregiver Reminder", "Hobby Engagement", "Silence Check-in"):
            page.get_by_role("button", name=label, exact=True).click()
            t = self.wait_for(page, lambda: ("ForeverYours initiated" in self.body(page) or UNREACHABLE in self.body(page)) and self.body(page), label)
            page.reload(wait_until="domcontentloaded")
            self.wait_for(page, lambda: "Briefed memory" in self.caregiver(page), "reload", LOAD_TIMEOUT_MS)
            page.get_by_role("button", name=re.compile("Simulate Proactive Triggers")).click()
        return "options: " + " | ".join(options)

    def steps(self):
        """(name, fn, microphone file) in run order; the file is what the fake microphone plays."""
        yield ("page loads: senior and caregiver side", self.s_loads, MIC_WAV)
        yield ("chip: Try this first (fall phrase)", lambda pg: self.s_chip(pg, FALL, expect_alert=True), MIC_WAV)
        for label in CLIPS:
            yield (f"sample clip: {label}", lambda pg, label=label: self.s_chip(pg, label, expect_alert="fell" in label), MIC_WAV)
        yield ("type a message and Send", self.s_typed, MIC_WAV)
        yield ("Load sample family", self.s_sample_family, MIC_WAV)
        yield ("save a text memo", self.s_memo, MIC_WAV)
        yield ("guided interview", self.s_interview, MIC_WAV)
        yield ("fall: DISTRESS alert and Dad was told", self.s_fall, MIC_WAV)
        # ---- every other control ----
        yield ("accordions: open and close each", self.s_accordions, MIC_WAV)
        yield ("Enter key sends the typed message", self.s_enter_sends, MIC_WAV)
        yield ("reply audio element receives audio and plays", self.s_reply_audio, MIC_WAV)
        yield ("mic: Record, Pause, Resume, Stop, Send", self.s_mic_record, MIC_WAV)
        yield ("mic: device dropdown, each device records", self.s_mic_devices, MIC_WAV)
        yield ("recorded clip: player controls", self.s_player_controls, MIC_WAV)
        yield ("upload button, Send", self.s_upload, MIC_WAV)
        yield ("upload a file that is not audio", self.s_upload_bad, MIC_WAV)
        yield ("X clears the audio input", self.s_clear, MIC_WAV)
        yield ("guardrail: 2,001-character message is refused", self.s_too_long, MIC_WAV)
        yield ("guardrail: 2,001-character memo is refused", self.s_memo_too_long, MIC_WAV)
        yield ("caregiver tabs and Shift+Enter memo", self.s_memo_tabs, MIC_WAV)
        yield ("caregiver Record Voice Memo (fake mic)", self.s_memo_voice, MEMO_WAV)
        yield ("caregiver voice memo upload", self.s_memo_upload, MIC_WAV)
        yield ("links have targets", self.s_links, MIC_WAV)
        if self.dev_ui:
            yield ("dev-only: time-of-day dropdown and proactive buttons", self.s_dev_controls, MIC_WAV)
        else:
            yield ("dev-only controls are hidden on the hosted UI", self.s_dev_controls_absent, MIC_WAV)

    def run(self) -> int:
        self.out.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            self.pw = p
            browsers: dict[Path, object] = {}
            try:
                for name, fn, wav in self.steps():
                    if self.only and not any(o.lower() in name.lower() for o in self.only):
                        continue
                    if wav not in browsers:
                        browsers[wav] = p.chromium.launch(
                            headless=not self.headed,
                            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                  f"--use-file-for-fake-audio-capture={wav}", "--autoplay-policy=no-user-gesture-required"])
                    self.step(name, browsers[wav], fn)
            finally:
                for b in browsers.values():
                    b.close()
        failed = [r for r in self.results if not r[1]]
        print(f"\n[{self.device}] {len(self.results) - len(failed)}/{len(self.results)} steps passed; screenshots in {self.out / self.device}")
        if self.layout:
            print(f"[{self.device}] {len(self.layout)} layout finding(s):")
            for finding, where in self.layout.items():
                print(f"  - {finding}  (steps: {len(where)}, first: {where[0]})")
        return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:7860/", help="the running app (default %(default)s)")
    ap.add_argument("--out", default="/tmp/ui-smoke/", help="screenshot directory (default %(default)s)")
    ap.add_argument("--offline-ok", action="store_true",
                    help="the app runs without a key: a step that needs the hosted model only needs some reply text")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--device", default="desktop", choices=[*DEVICES, "all"],
                    help="viewport to emulate (default %(default)s); 'all' runs desktop, pixel7 and iphone14 in turn")
    ap.add_argument("--only", action="append", default=[], metavar="TEXT",
                    help="run only the steps whose name contains TEXT (repeatable)")
    ap.add_argument("--dev-ui", action="store_true",
                    help="the app was started with FY_DEV_MODE=1: try the time-of-day dropdown and proactive buttons")
    args = ap.parse_args(argv)
    code = 0
    for device in (DEVICES if args.device == "all" else [args.device]):
        code |= Smoke(args.url, Path(args.out), args.offline_ok, args.headed, device, args.dev_ui, tuple(args.only)).run()
    return code


if __name__ == "__main__":
    sys.exit(main())
