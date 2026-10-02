# Roadmap to submission

Deadline: **2026-10-30, 10:00am PDT (17:00 UTC)**. This is the order we're actually working
in, and why — not a wishlist. If you only read one doc to know "what's next," read this one;
it links out to the GitHub Issue for anything that needs more than a paragraph.

## Why this order (dependency chain, not preference)

```
ASR backend decision (DECIDED, see below)
  -> real voice I/O (#9)                     <- blocked on the decision above, now unblocked
  -> judge-accessible hosting (new issue)    <- independent of #9, can run in parallel
  -> live NEBIUS_API_KEY verification (#1)   <- independent, can run in parallel
  -> Day-2 recall demo (#3)                  <- independent, lower priority
  -> submission video (#5)                   <- needs #9 + hosting done first (can't film
                                                  a "voice companion" video on a text-only demo)
  -> Devpost Representative + submit (#6)    <- last, needs everything above
```

## Milestones

| # | Milestone | Status | Depends on |
|---|---|---|---|
| M1 | Core pipeline fixes (fast-path continuation, disclosure honesty, audit fix, etc.) | **Open PR [#7](../../pull/7)** — awaiting review | — |
| M2 | PRD + implementation plan + this roadmap | **Open PR [#8](../../pull/8)** — awaiting review | — |
| M3 | ASR backend decided | **Done**, see below | — |
| M4 | Real voice I/O wired ([#9](../../issues/9)) | **Done** (PR ready, verified with bundled samples + webapp). **Still worth prioritizing before the video (review finding, 2026-10-01):** voice *quality* is separate from voice *wiring* — local `pyttsx3`/`espeak` is working but robotic (already flagged as a Design-criterion risk in `VENDOR_DECISIONS.md`); prefer an NVIDIA-hosted TTS if Token Factory exposes one, before this is what a judge actually hears. | M3 |
| M5 | Judge-accessible hosting (host it ourselves, decided) | **Ready to deploy, not live yet (2026-10-02).** Nothing judge-reachable runs the app today: Cloudflare Pages serves only the static `docs/index.html` landing page. The app itself is deploy-ready for Spaces: per-visitor isolated sessions with auto-deletion (#18), a pre-briefed demo household, sample clips for judges without a mic, and `scripts/deploy_hf_space.py` (one command, needs an HF token + the Nebius key as a Space secret). Closes when a public URL answers. Earlier status said "Done" for the deploy files alone. **Caveat (review finding, 2026-10-01):** if the Spaces path is used, free-tier Spaces sleep when idle, so a judge's first click can hang on a cold start — plan to keep it awake through the actual judging window (upgraded/always-on hardware, or the Cloudflare/Tunnel path, which doesn't have this problem). | — |
| M6 | Live `NEBIUS_API_KEY` verification ([#1](../../issues/1)) | **Done** (PR #25: model inventory confirmed, beat2 live end to end, 4.22s to first audio, so the <2s target is not met on the LLM path yet; see #17) | — |
| M7 | Day-2 recall demo ([#3](../../issues/3)) | **Done** (PR #22 ready, persistence verified) | — |
| M7.5 | Sanity-check the name "ForeverYours" with someone outside the team (it can read as a memorial or dating brand, not a caregiving one — worth catching before it's on the video/Devpost page, not after) | Open | — |
| M8 | Submission video recorded ([#5](../../issues/5)) | Open | M4, M5 |
| M9 | Devpost Representative decided + submitted ([#6](../../issues/6)) | Open | everything above |

## Decided: ASR backend

> **Superseded 2026-10-02 (PR #25):** Token Factory returns 404 on `/audio/transcriptions`,
> so hosted NVIDIA ASR isn't available there. Shipping path is `ASR_BACKEND=whisper_local`
> (local `faster-whisper`); Nebius powers THINK + AUDIT. The original reasoning is kept below.

**NVIDIA-hosted ASR via Nebius Token Factory**, not local `faster-whisper`, for two reasons:
it leans into the sponsor stack the hackathon is judged on (same provider as THINK, and ASR
usage is more required-tech proof), and it keeps the latency story consistent with the rest of
the pipeline rather than mixing a local model into an otherwise-hosted path. The tradeoff —
losing full offline capability — is already covered: the fast-path (`safety/fastpath.py`) is
the one thing that must keep working with no key, and it doesn't touch ASR or THINK at all.
`faster-whisper` stays in the codebase as a fallback/dev convenience, not the primary path.
This unblocks [#9](../../issues/9).

## Judging requirements we're building against

Pulled directly from the hackathon's own rules page
([nebiusglobalaihackathon.devpost.com/rules](https://nebiusglobalaihackathon.devpost.com/rules)) —
not a hidden scoring strategy, just what's actually required, so nothing gets missed:

| Requirement | Status |
|---|---|
| Public repo, OSS license visible in GitHub's About section | **Done** (MIT, confirmed visible) |
| README with setup + running instructions | **Done** |
| Documentation of NVIDIA model + Nebius tool usage | **Done** — see `README.md`'s Pipeline section; keep it current as the ASR decision above gets implemented |
| **A live/testable demo link, or a test build** — judges don't just watch the video | **Open — M5 above.** We assumed video+repo was enough; it isn't, except for the Physical AI track, which we're not in. **Decided: host it ourselves** (our key already configured) rather than rely on a judge getting their own `NEBIUS_API_KEY` mid-review — too unreliable at hackathon judging speed/volume. README setup steps stay as a convenience, not the primary judging path. See [#11](../../issues/11). |
| Demo video, <=3 minutes, shows the project functioning, uploaded to YouTube public | Open — M8, needs M4+M5 first |
| Runtime proof: a real call to Token Factory, or deployment on Nebius AI Cloud compute | Partially done (THINK already calls Token Factory at runtime); hosting on Nebius AI Cloud compute for M5 would satisfy the "deployed on" half too — two requirements, one deployment decision |
| Written text description of features/functionality/tech used | Not written yet — needed for the Devpost submission form itself, separate from this repo |
| One designated team Representative to submit | Open — [#6](../../issues/6) |

## Self-judging

We don't have to wait for a real judge to find out we're weak on Design. See
[`docs/SELF_JUDGING.md`](SELF_JUDGING.md) — a rubric mirroring the real one, scored
independently by both of us against whatever mock submission exists at the time, logged so the
trend is visible. Run it after each real milestone (key live, hosted, video v1, text drafted),
not on a fixed schedule.

## Where stretch goals fit

Everything above is the critical path to a submittable entry. These are explicitly *not* on
it — pick them up only after M1–M9 are solid, and drop them without guilt if the deadline gets
close:

- Conversation history across turns (Implemented: session history in `webapp.py` and `main.py chat`)
- Automated verification test suite (Implemented: 22 tests in `tests/` covering fastpath, memory, speak, orchestrator)
- A caregiver-facing UI beyond the terminal panel (see `PRD.md`'s non-goals — a full dashboard
  was deliberately cut once already; don't re-add it under time pressure)
- The early-memory-loss framing angle (optional/secondary per the original pitch review, not
  required either way)
- Anything from `IMPLEMENTATION_PLAN.md`'s backlog not listed as a milestone above

## How to follow this

This file is the single place tracking order/status — if you're picking up work, check here
first, then the linked GitHub Issue for detail. Update the status column in the same PR that
changes it; don't let this page and the Issues disagree.
