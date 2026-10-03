# Roadmap to submission

Deadline: **2026-10-30, 10:00am PDT (17:00 UTC)**. This is the order we're actually working
in, and why — not a wishlist. If you only read one doc to know "what's next," read this one;
it links out to the GitHub Issue for anything that needs more than a paragraph.

> **Re-planned 2026-10-03** (27 days out). Three things changed the order:
> 1. **The hosted demo would go silent.** On Linux, espeak returns empty audio after about 19
>    sentences in one process ([#28](../../issues/28)). A hosted demo is one long-lived
>    process for every judge. This now blocks going live.
> 2. **Latency is probably a config switch, not a build.** Most of the 4.22s is Nemotron's
>    hidden reasoning tokens (PR #25). Turning reasoning off is a documented one-line switch
>    to test first; browser streaming becomes the fallback ([#17](../../issues/17)).
> 3. **Submit an early, editable Devpost draft.** A scored draft in hand beats a perfect entry
>    that misses the click. Proposed for ~10-20, not yet agreed ([#6](../../issues/6)).

## Critical path (in order)

```
1. Team Nebius key on hand                   <- 2nd key, so the deploy/tests/video don't
                                                depend on one person's personal credits
2. Fix silent TTS (#28) + narrow fast-path    <- Done (10-03); code unblocked
   "help me" false positives (#15)              for public Space deploy
3. Go live on HF Spaces (#11)                <- one command (scripts/deploy_hf_space.py);
                                                needs 1 (key)
4. Latency: reasoning off, re-measure (#17)  <- needs a live key; build browser streaming
                                                only if still > ~2s after this
5. Early Devpost draft submitted (#6, #20)    <- live URL + current video; editable until
                                                the deadline
6. Final video on the hosted URL (#5)         <- after 3, ideally after 4
7. Final Devpost text (#20, needs #14)        <- after 6; then re-submit the edit
```

## Milestones

| # | Milestone | Status | Depends on |
|---|---|---|---|
| M1 | Core pipeline fixes (fast-path continuation, disclosure honesty, audit fix, etc.) | **Done** (PR #7, merged 10-01) | — |
| M2 | PRD + implementation plan + this roadmap | **Done** (PR #8, merged 10-01; kept current since) | — |
| M3 | ASR backend decided | **Done**: local `faster-whisper` (see below) | — |
| M4 | Real voice I/O wired ([#9](../../issues/9)) | **Done** (PRs #23, #26). Voice *quality* is still the Design risk: local espeak is robotic. A better local voice can ride along with the #28 fix if it's cheap; otherwise it's a stretch goal. | M3 |
| M5 | Judge-accessible hosting ([#11](../../issues/11)) | **Ready to deploy, not live.** Nothing a judge can reach runs the app yet: Cloudflare Pages serves only the static `docs/index.html`. Deploy-ready for Spaces (per-visitor sessions, auto-deletion, sample clips, `scripts/deploy_hf_space.py`). Code blockers **[#28](../../issues/28)** and **[#15](../../issues/15)** resolved (10-03). Closes when a public URL answers. Keep the Space awake through judging, because free Spaces sleep and a cold first click can hang. | M10 |
| M6 | Live `NEBIUS_API_KEY` verification ([#1](../../issues/1)) | **Done** (PR #25: model inventory, beat2 live, 4.22s to first audio) | — |
| M7 | Day-2 recall demo ([#3](../../issues/3)) | **Done** (PR #22) | — |
| M7.5 | Sanity-check the name "ForeverYours" outside the team (can read as memorial/dating) | Open, low priority. Do it before the video is recorded, or keep the name by default. | — |
| M8 | Submission video recorded ([#5](../../issues/5)) | Open. A proof-of-concept terminal video exists (`video/output/`); the final one is recorded on the hosted URL. | M5 (ideally M11) |
| M9 | Devpost Representative + submission ([#6](../../issues/6)) | **Open — team decision pending.** Proposal: whoever is Representative submits an early, editable draft by ~10-20 (live URL + current video), then edits it up to the deadline. | M5 |
| M10 | Team Nebius key on hand | **In progress (10-03)**: second free-credit account being set up, so deploying, testing and recording don't depend on one person's personal credits | — |
| M11 | Perceived latency under ~2s ([#17](../../issues/17)) | Open. Step 1: `enable_thinking: false` on the THINK call, re-measure, and check reply quality against the #27 eldercare rules. Step 2 if needed: try `Nemotron-3_5-Lightning`. Step 3 only if still slow: stream sentence 1 to the browser. | M10 |
| M12 | Devpost text ([#20](../../issues/20)) | Draft exists (`docs/Project_Description.md`). Still needs the agreed [#14](../../issues/14) "why not ChatGPT voice mode" answer and the final links. | M5, M8 |

## Decided: ASR backend

**Local `faster-whisper`** (`ASR_BACKEND=whisper_local`). Token Factory returns 404 on
`/audio/transcriptions` (verified live, PR #25), so hosted NVIDIA ASR isn't available there.
Nebius + NVIDIA power THINK and AUDIT (both `NVIDIA-Nemotron-3-Nano-30B-A3B`), which meets the
sponsor-tech requirement. Earlier plan (NVIDIA-hosted ASR) superseded 2026-10-02.

## Judging requirements we're building against

Pulled directly from the hackathon's own rules page
([nebiusglobalaihackathon.devpost.com/rules](https://nebiusglobalaihackathon.devpost.com/rules)) —
not a hidden scoring strategy, just what's actually required, so nothing gets missed:

| Requirement | Status |
|---|---|
| Public repo, OSS license visible in GitHub's About section | **Done** (MIT, confirmed visible) |
| README with setup + running instructions | **Done** |
| Documentation of NVIDIA model + Nebius tool usage | **Done** — `README.md`'s Pipeline section |
| **A live/testable demo link, or a test build** — judges don't just watch the video | **Open — M5.** Decided: host it ourselves with our key configured, not rely on a judge getting their own key. See [#11](../../issues/11). |
| Demo video, <=3 minutes, shows the project functioning, uploaded to YouTube public | Open — M8 (proof-of-concept exists; final needs M5) |
| Runtime proof: a real call to Token Factory, or deployment on Nebius AI Cloud compute | **Done** — THINK + AUDIT call Token Factory at runtime (verified live, PR #25) |
| Written text description of features/functionality/tech used | **Draft exists** (`docs/Project_Description.md`) — M12 |
| One designated team Representative to submit | Open — M9, [#6](../../issues/6) |

## Self-judging

We don't have to wait for a real judge to find out we're weak on Design. See
[`docs/SELF_JUDGING.md`](SELF_JUDGING.md) — a rubric mirroring the real one, scored
independently by both of us against whatever mock submission exists at the time, logged so the
trend is visible. Run it after each real milestone (hosted, latency re-measured, video v1, text
drafted), not on a fixed schedule.

## Where stretch goals fit

Everything above is the critical path to a submittable entry. These are explicitly *not* on
it — pick them up only after the critical path is solid, and drop them without guilt if the
deadline gets close:

- A better TTS voice than espeak, if it isn't cheap enough to ride along with [#28](../../issues/28)
- NVIDIA NemoGuard as the AUDIT model (a second NVIDIA model for the tech score), if Token
  Factory lists it
- Hosting on a Nebius AI Cloud VM instead of / in addition to Spaces
- A caregiver-facing UI beyond the web page's caregiver column (see `PRD.md`'s non-goals — a
  full dashboard was deliberately cut once already; don't re-add it under time pressure)
- The early-memory-loss framing angle (optional/secondary, not required either way)
- Anything from `IMPLEMENTATION_PLAN.md`'s backlog not listed as a milestone above

Already done and no longer stretch: conversation history across turns (`webapp.py`,
`main.py chat`), an automated test suite (53 tests across 10 modules in `tests/`).

## How to follow this

This file is the single place tracking order/status — if you're picking up work, check here
first, then the linked GitHub Issue for detail. Update the status column in the same PR that
changes it; don't let this page and the Issues disagree.
