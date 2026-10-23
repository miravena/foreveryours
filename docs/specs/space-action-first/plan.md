# Plan: action first on the hosted page (#215)

## Goal

A judge who opens the Space reaches the product's moment inside 30 seconds without reading: one
line says what to try, the notices are one line each, the sample clips have human names, and no
internal label is on the page.

## Current state (check `main` first, not the Space)

Local `main` is ahead of the deployed build: the retention paragraph is already collapsed into
the accordion "How long your recordings and household data are kept" (`webapp.py` ~:2107-2112),
the "Beat 1 Onboarding" label is already gone, and the dev panels are `visible=DEV_MODE`. The
"Simulated Time of Day" dropdown sits inside the hidden "Clinical Configuration" accordion, so it
is not a judge-facing problem on `main`. What remains is below.

## Affected files

- `webapp.py` header (~:2096-2106): the first Markdown block becomes the title plus one bold line
  "Try this first: *I fell down earlier and I'm scared*" and one plain line "Talk or type as the
  senior on the left; the caregiver side on the right updates live." The two AI notices merge
  into one line: "This is an AI companion, not a person. Privacy notice." (link kept; the
  transparency wording required by `tests/test_retention_notice.py` and #66 B stays in the page;
  verify which test asserts which string before editing).
- `webapp.py` senior column (~:2146-2153): a `gr.Examples` on `text_in` with the single example
  "I fell down earlier and I'm scared" so one click fills the box (typed path first, as the
  Devpost testing instructions say); `SAMPLE_CLIP_LABELS` become plain names: "Dad asks what's
  happening today", "Dad talks about jazz", "Dad asks his grandson's name", "Dad says he fell and
  is scared".
- `webapp.py` reset notice (~:378 and its use): `_RESET_NOTICE` is shown only when a session
  really expired, never on the first turn of a fresh household (SELF_JUDGING.md Gaps).
- `tests/test_webapp.py`: `test_expired_session_shows_reset_notice` stays; add
  `test_fresh_session_shows_no_reset_notice`; the try-first line and the four labels are in
  the page; the AI-notice and recording-notice strings the existing tests assert are still present.
- `CHANGELOG.md`; `docs/DEVPOST_DRAFT.md` testing instructions if the wording changes.

## Steps

1. Read the tests that pin page copy (`grep -n "AI companion\|TRANSPARENCY\|recorded and turned" tests/`)
   and list which strings must survive.
2. Failing tests for the try-first line, the labels and the fresh-session reset notice.
3. Header, examples, labels, reset-notice condition.
4. Render the page headless at 1920x1080 (Playwright, Chromium from `~/.cache/ms-playwright`,
   `wait_until="load"` then a 15 s wait; the page never reaches `networkidle`) and attach the
   screenshot to the PR: the try-first line and the input must be above the fold.
5. Suite, Codex review, PR.

## Splitting across subagents

One subagent (fleet worker profile, medium), after `space-model-attribution` (#214) has landed on
`main`, because both touch the header region of `webapp.py`. It gets: this file, issue #215, the
2026-10-23 submission review (`docs/plans/SUBMISSION-REVIEW-2026-10-23.md`, "Hosted Space"
paragraph), `webapp.py` ~:370-380 and ~:2087-2200, `tests/test_webapp.py`,
`tests/test_retention_notice.py`. It returns: branch, the screenshot path, test names, suite
count, Codex result, PR link.

## Review

`scripts/openai_review.sh`. Copy changes only; the reviewer is asked to confirm no required
notice string was removed.
