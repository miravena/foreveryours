#!/usr/bin/env python3
"""Browser smoke test for the ForeverYours web demo: click what a judge clicks.

Opens the Gradio app in headless Chromium (Playwright) and, in a fresh page (so a
fresh household) per step, drives the page the way a judge does: the "Try this first"
chip, each "No mic? Try a sample clip" button (which runs the local Whisper, so this
covers audio input too), a typed message plus Send, "Load sample family", a saved
text memo, the guided interview, and the fall phrase ending in the DISTRESS alert and
"Dad was told" on the caregiver panel. It waits on page state, never a fixed sleep,
saves one screenshot per step and prints PASS/FAIL per step. Exit code 1 if any step fails.

It is NOT part of the unittest suite or CI: it needs a running server and a browser.
Start the app yourself, then run this against it:

    .venv/bin/python webapp.py                         # terminal 1 (http://127.0.0.1:7860/)
    .venv/bin/python scripts/ui_smoke.py               # terminal 2, hosted model reachable
    .venv/bin/python scripts/ui_smoke.py --offline-ok  # terminal 2, app started without a key

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
TYPED = "Who is Sarah?"
MEMO = "Dad has a check-up with Dr. Tan on Thursday at 10 AM."
INTERVIEW_ANSWER = "Sarah is his daughter. His grandson Leo is nine. Rosa next door is his oldest friend."
CLIPS = (
    "Dad asks what's happening today",
    "Dad talks about jazz",
    "Dad asks his grandson's name",
    "Dad says he fell and is scared",
)

UNREACHABLE = "isn't reachable right now"  # the app's keyless-turn notice (webapp.py)
LOAD_TIMEOUT_MS = 90_000
TURN_TIMEOUT_MS = 240_000  # a turn can wait on local Whisper, a hosted model and TTS


class Smoke:
    def __init__(self, url: str, out: Path, offline_ok: bool, headed: bool):
        self.url, self.out, self.offline_ok, self.headed = url, out, offline_ok, headed
        self.results: list[tuple[str, bool, str]] = []

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

    def open_page(self, browser):
        page = browser.new_page(viewport={"width": 1400, "height": 1200})
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
        shot = self.out / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".png")
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
                    page.screenshot(path=str(shot), full_page=True)
                except PlaywrightError:
                    pass
                page.close()
        self.results.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else "") + f"  [{shot}]", flush=True)

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

    def run(self) -> int:
        self.out.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not self.headed)
            try:
                self.step("page loads: senior and caregiver side", browser, self.s_loads)
                self.step("chip: Try this first (fall phrase)", browser,
                          lambda pg: self.s_chip(pg, FALL, expect_alert=True))
                for label in CLIPS:
                    self.step(f"sample clip: {label}", browser,
                              lambda pg, label=label: self.s_chip(pg, label, expect_alert="fell" in label))
                self.step("type a message and Send", browser, self.s_typed)
                self.step("Load sample family", browser, self.s_sample_family)
                self.step("save a text memo", browser, self.s_memo)
                self.step("guided interview", browser, self.s_interview)
                self.step("fall: DISTRESS alert and Dad was told", browser, self.s_fall)
            finally:
                browser.close()
        failed = [r for r in self.results if not r[1]]
        print(f"\n{len(self.results) - len(failed)}/{len(self.results)} steps passed; screenshots in {self.out}")
        return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:7860/", help="the running app (default %(default)s)")
    ap.add_argument("--out", default="/tmp/ui-smoke/", help="screenshot directory (default %(default)s)")
    ap.add_argument("--offline-ok", action="store_true",
                    help="the app runs without a key: a step that needs the hosted model only needs some reply text")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    args = ap.parse_args(argv)
    return Smoke(args.url, Path(args.out), args.offline_ok, args.headed).run()


if __name__ == "__main__":
    sys.exit(main())
