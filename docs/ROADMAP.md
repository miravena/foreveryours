# Roadmap to submission

Deadline: **2026-10-30, 10:00am PDT (17:00 UTC)**.

> **One source of truth.** This is one small repo with two workers, so work *state* lives in
> exactly one place: **GitHub**. [Milestones](../../milestones) hold the order and due dates,
> Issues hold scope, owner and acceptance criteria, and *blocked by* relationships hold the
> dependencies. This page is the **plan and the reasoning** (what the milestones are, why in
> this order, what the judges require). It deliberately has no status or date columns, because
> a copy of GitHub's state is a second tracker that drifts. To see what is open, blocked or due:
> [milestones, sorted by due date](../../milestones) · [open Issues](../../issues).

## Why this order

1. **The hosted demo must not go silent.** On Linux, espeak returned empty audio after about 19
   sentences in one process ([#28](../../issues/28)); a hosted demo is one long-lived process
   for every judge, so this gates going live. Fix: [ADR-001](decisions/ADR-001-tts-backend.md).
2. **Latency is mostly a config switch.** Most of the original 4.22s was Nemotron's hidden
   reasoning tokens (PR #25); turning reasoning off was tested first, with browser streaming
   as the fallback ([#17](../../issues/17), [ADR-002](decisions/ADR-002-think-audit-model.md)).
3. **Submit an early, editable Devpost draft.** A scored draft in hand beats a perfect entry
   that misses the click ([#6](../../issues/6)).
4. **Leave review time.** The last milestone reserves days before the deadline for an
   end-to-end check, so nothing is first seen on submission day.

## Milestones (plan; live dates and status are on GitHub)

Order is by due date on the [milestones page](../../milestones). "Depends on" is the plan; the
enforced version is each Issue's *blocked by* relationship.

| Milestone | Done means | Depends on |
|---|---|---|
| [M10 Team Nebius key](../../milestone/7) | A second Nebius key is on hand, so deploying, testing and recording don't depend on one person's credits | - |
| [M4 Voice I/O + memory quality](../../milestone/1) | Real voice I/O wired; recall handles word inflections | - |
| [M5 Judge-accessible hosting](../../milestone/2) **(MVP)** | A public HF Spaces URL answers, with the "help me" fast-path fixed ([ADR-003](decisions/ADR-003-hosting.md), [ADR-005](decisions/ADR-005-safety-fastpath.md)) | M10 |
| [M11 Latency under 2s](../../milestone/5) | Under ~2s to first audio, measured on the hosted instance (if still above, build browser streaming) | M5 |
| [M9 Representative + early draft](../../milestone/4) | Representative chosen; early editable Devpost draft with the live URL | M5 |
| [M8 Final demo video](../../milestone/3) | Video of at most 3 minutes, recorded on the hosted URL | M5, ideally M11 |
| [M12 Devpost text](../../milestone/6) | Final text with the video link | M8 |
| [M13 Final review and submit](../../milestone/8) | Review freeze, end-to-end check, submitted | M8, M12 |

Earlier milestones M1-M3, M6, M7 are done; see [`CHANGELOG.md`](../CHANGELOG.md).

## Decided: ASR backend

Local `faster-whisper`, because Token Factory has no audio-transcription endpoint (verified
live, PR #25). Full reasoning: [ADR-004](decisions/ADR-004-asr-backend.md).

## Judging requirements we're building against

Pulled from the hackathon's own rules page
([nebiusglobalaihackathon.devpost.com/rules](https://nebiusglobalaihackathon.devpost.com/rules)),
so nothing gets missed. The right column says where each is tracked; it is not a status.

| Requirement | Tracked in |
|---|---|
| Public repo, OSS license visible in GitHub's About section | Static fact: MIT, `LICENSE` |
| README with setup + running instructions | `README.md` (reviewed in M13) |
| Documentation of NVIDIA model + Nebius tool usage | `README.md` "Pipeline" section; [ADR-002](decisions/ADR-002-think-audit-model.md) |
| **A live/testable demo link, or a test build.** Judges don't just watch the video. We host it ourselves with our key configured rather than rely on a judge getting their own | [M5](../../milestone/2), [#11](../../issues/11) |
| Demo video, at most 3 minutes, showing the project functioning, public on YouTube | [M8](../../milestone/3), [#5](../../issues/5) |
| Runtime proof: a real call to Token Factory, or deployment on Nebius AI Cloud compute | Satisfied by THINK + AUDIT calling Token Factory at runtime (verified live, PR #25); re-check in M13 |
| Written text description of features/functionality/tech used | [M12](../../milestone/6), [#20](../../issues/20); draft in `docs/Project_Description.md` |
| One designated team Representative to submit | [M9](../../milestone/4), [#6](../../issues/6) |

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

## How to follow this

- **What should I work on / what is blocked / when is it due?** GitHub: the
  [milestones page](../../milestones), then the Issue and its *blocked by* section.
- **Why this order, what do the judges need?** This page.
- **Why did we choose X?** [`decisions/`](decisions/README.md).
- **What happened last session?** [`WORK_LOG.md`](WORK_LOG.md).

If the plan changes (a milestone is added or reordered), change the milestone on GitHub first,
then update the table above in the same commit. Never write status or dates on this page.
