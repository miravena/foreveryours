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
| [M5 Judge-accessible hosting](../../milestone/2) **(MVP2)** | A public HF Spaces URL answers, with no false-positive distress alerts on the demo script ([ADR-003](decisions/ADR-003-hosting.md), [ADR-005](decisions/ADR-005-safety-fastpath.md)) | M10 |
| [M11 Latency under 2s](../../milestone/5) | Under ~2s to first audio, measured on the hosted instance (if still above, build browser streaming) | M5 |
| [M9 Representative + early draft](../../milestone/4) | Representative chosen; early editable Devpost draft with the live URL | M5 |
| [M8 Final demo video](../../milestone/3) | Video of at most 3 minutes, recorded on the hosted URL | M5, ideally M11 |
| [M12 Devpost text](../../milestone/6) | Final text with the video link | M8 |
| [M13 Final review and submit](../../milestone/8) | Review freeze, end-to-end check, submitted | M8, M12 |

Work completed before these milestones is recorded in [`CHANGELOG.md`](../CHANGELOG.md).

## Staging: MVP1 → MVP2 → MVP3

We deliver in three complete stages rather than one drop at the deadline. **A stage is a whole
product, not a pile of parts** — at every stage boundary there is a build a stranger could be
handed, a tagged release for it, and a demo that runs. That is what makes a missed estimate
survivable: the worst case is that the next stage starts later, sitting on a known-good version,
not that the deadline arrives with pieces that never met each other.

| Stage | What it gives a stranger | Built from |
|---|---|---|
| **MVP1 — runs** | `main.py` beats 1–4 and the web demo run offline on a laptop: hear, recall, speak, the safety fast-path, day-2 recall | [M4](../../milestone/1) and the work before it |
| **MVP2 — hosted** | A public URL that answers on its own: no false alert on the demo script, memory corrections hold, first audio under 2s | [M10](../../milestone/7), [M5](../../milestone/2), [M11](../../milestone/5) |
| **MVP3 — submittable** | Everything the judges actually open: representative, video, Devpost text, feedback, final review | [M9](../../milestone/4), [M8](../../milestone/3), [M12](../../milestone/6), [M13](../../milestone/8) |

**How we estimate against it.** The stage is the unit we promise and the Issue is the unit we do.
An Issue-level estimate only predicts that Issue, and a whole stage is too big to hold as one
number — so we check ourselves at stage boundaries, where the evidence is a running build rather
than a feeling. When an estimate runs long the answer is to cut inside the stage or move the
stage, never to let slices quietly accumulate toward the deadline.

**How we release against it.** Each stage ends the same way: rename `[Unreleased]` in the
changelog, tag `vX.Y.Z` on `main`, publish a GitHub Release
([`HOW_TO_WORK_HERE.md`](../HOW_TO_WORK_HERE.md) → *Releases*). The version lines are `v0.1.0`
for MVP1, `v0.2.0` for MVP2 and `v1.0.0` for MVP3, so every stage we reach is also a version we
can hand a judge or a partner — going back never means rebuilding.

## Decided: ASR backend

Local `faster-whisper`, because Token Factory has no audio-transcription endpoint (verified
live, PR #25). Full reasoning: [ADR-004](decisions/ADR-004-asr-backend.md).

## Judging requirements we're building against

Taken from the hackathon's own rules ([`HACKATHON_RULES.md`](HACKATHON_RULES.md), source
[nebiusglobalaihackathon.devpost.com/rules](https://nebiusglobalaihackathon.devpost.com/rules)),
so nothing gets missed. The right column says where each is tracked; it is not a status.

| Requirement | Tracked in |
|---|---|
| Public repo, OSS license visible in GitHub's About section | Static fact: MIT, `LICENSE` |
| README with setup + running instructions | `README.md` (reviewed in M13) |
| Documentation of NVIDIA model + Nebius tool usage | `README.md` "Pipeline" section; [ADR-002](decisions/ADR-002-think-audit-model.md) |
| **A live/testable demo link, or a test build.** Judges don't just watch the video. We host it ourselves with our key configured rather than rely on a judge getting their own | [M5](../../milestone/2), [#11](../../issues/11) |
| Demo video, under 3 minutes, showing the project functioning, public on YouTube, no third-party trademarks or copyrighted music | [M8](../../milestone/3), [#5](../../issues/5) |
| Runtime proof: a real call to Token Factory, or deployment on Nebius AI Cloud compute | Satisfied by THINK + AUDIT calling Token Factory at runtime (verified live, PR #25); re-check in M13 |
| Written text description of features/functionality/tech used | [M12](../../milestone/6), [#20](../../issues/20); draft in `docs/Project_Description.md` |
| One designated team Representative to submit | [M9](../../milestone/4), [#6](../../issues/6) |
| Demo stays **free and unrestricted until the Judging Period ends (2026-12-15)** | [M5](../../milestone/2), [#11](../../issues/11) |
| Feedback on Nebius Token Factory / AI Cloud and the NVIDIA tools used (also qualifies for the Most Valuable Feedback prize) | [M12](../../milestone/6), [#41](../../issues/41) |
| Identify the track (**Personal AI**) and, if the project predates the Submission Period, what was updated | Devpost form, checked in [M13](../../milestone/8) / [#37](../../issues/37) |

## How entries are judged

Full dated rules: [`HACKATHON_RULES.md`](HACKATHON_RULES.md) (snapshot 2026-10-04). Judging happens
after the deadline (2026-12-01 to 12-15), and **the 10-30 10:00 PDT cutoff is a hard submission
time**, not the judging time.

1. **Stage One, pass/fail:** the project reasonably fits the theme and reasonably applies the
   required APIs/SDKs. Our entry meets this by using Nebius Token Factory with an NVIDIA
   Nemotron model (see [ADR-002](decisions/ADR-002-think-audit-model.md)).
2. **Stage Two, four equally weighted criteria** (each is 25% of the score):

| Criterion | What the judges ask | Where we invest |
|---|---|---|
| Technological Implementation | How well it's built, and how effectively it uses Nebius model(s) and NVIDIA Nemotron | Pipeline, fast-path, tests/CI, ADRs |
| Design | A complete, coherent product experience, not just a technical proof of concept | The hosted web demo, voice quality, the split-screen disclosure beat ([#21](../../issues/21)) |
| Potential Impact | A credible, specific case for a real problem and audience, shown in the demo | `docs/PRD.md`, `docs/Project_Description.md`, the video |
| Quality of the Idea | A creative, non-obvious use of the models, and real understanding of the problem | Honest-disclosure design, caregiver briefing |

**Tie-break:** tied entries are compared on the first criterion above, then the next, so
Technological Implementation breaks ties first.

How we score ourselves against these, and the log of scores: [`SELF_JUDGING.md`](SELF_JUDGING.md).

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
