# ADR-003: Host the judge demo on Hugging Face Spaces

**Status:** Accepted (hosting on free ZeroGPU superseded by [ADR-017](ADR-017-judging-period-hosting.md) once it is accepted)
**Date:** 2026-10-01
**Decided by:** Team
**Affects:** `app.py`, `webapp.py`, `scripts/deploy_hf_space.py`
**Related issue:** [#11](../../issues/11)

## Question

Where do we run the app so judges can use it without their own key?

## Context

Devpost needs a live link or test build. Cloudflare Pages serves only the static landing page.

## Decision

**Hugging Face Spaces (Gradio)**, deployed with `scripts/deploy_hf_space.py`, using our own
Nebius key configured as a Space secret.

## Rationale

Free tier, Gradio-native, handles long-lived model calls. Per-visitor sessions with
auto-deletion (PR #26) keep visitors isolated and honor the no-retention privacy claim.

## Consequences

- **Gotcha:** free Spaces sleep after ~48h idle, and the sleep time cannot be configured
  (Hugging Face [Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview)); judging
  runs 2026-12-01 to 2026-12-15, five weeks after the last commit, so an un-kept Space will have
  slept long before the first judge arrives (#81 A2).
  **Keep-awake:** a daily request from any always-on machine (oracle), from deploy through
  2026-12-15:
  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' https://<user>-<space>.hf.space/
  ```
  Scheduled once a day; a non-200 means the Space needs attention before the next judge hits it.
- Needs a team Nebius key so deploying does not depend on one person's credits.
- **2026 policy change (checked 2026-10-20):** Hugging Face now requires PRO (personal) or
  Team/Enterprise (org) to run a Gradio Space on `cpu-basic`; a free account gets a 403
  "cpu-basic quota limit" instead. Free accounts with a verified email that are older than
  30 days may still host 2 ZeroGPU Spaces ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview),
  [ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)). We deploy with
  `--hardware zero-a10g` first: `app.py` defines one never-called `@spaces.GPU` function
  because ZeroGPU will not boot without one. That is a community workaround, not documented
  usage, so if the Space fails to boot or misbehaves by 2026-10-24 we switch to PRO
  ($9/month) on `cpu-basic`, which keeps the same Space URL.
- **Deployed 2026-10-21** at <https://huggingface.co/spaces/elevenbaselab/foreveryours> on `zero-a10g` (free account), from `main`
  2a3af03. Upload to running took about 2 minutes. One-off timings on that revision, through the
  public API from a client outside Hugging Face, end to end:
  - caregiver memo saved: 0.3 s;
  - senior voice clip (`samples/senior_jazz.wav`), transcription, reply and spoken audio: 3.8 s;
  - distress turn with spoken disclosure and caregiver flag: 6.4 s;
  - typed recall turn: 1.9 s.

  These are single runs, not a benchmark. Browser time-to-first-audio is not measured yet.
  Keep-awake runs twice a day (03:23 and 15:23 UTC) until 2026-12-16.
- The Nebius key must keep enough credit through 2026-12-15; without it the Space falls
  back to the offline fast-path only.

## Concurrency (2026-10-22)

Gradio's default `concurrency_limit` of 1 meant one visitor's slow ASR/Nebius/TTS turn queued
every other visitor's Send and Enter, including an emergency phrase (Codex review 2026-10-22,
robustness finding #6). The six senior-turn listeners (Send, Enter and the four
proactive buttons) now share `concurrency_id="senior_turn"` with
`concurrency_limit=FY_TURN_CONCURRENCY`, **default 4**, validated as an integer >= 2 at startup.
One shared id means the bound counts all turn producers together. Why 4: THINK (Nebius) is
network-bound and overlaps freely, but local faster-whisper ASR and Piper TTS are CPU-bound on a
small Space (`cpu-basic` is 2 vCPU, and our ZeroGPU Space never calls the GPU), so four
simultaneous CPU turns is the most we allow before they starve the typed offline safety
fast-path; a hackathon judging panel is a handful of simultaneous visitors anyway. Unbounded is
refused because the daily cap and audio limits assume a bounded number of in-flight turns.
Within one session, turns stay strictly ordered: `run_demo_turn_streaming` holds a per-session
lock (`_session_turn_locks`, created and deleted with the session's `_active_turns` count) for
the whole turn, so a second Send from the same tab waits for the first and is never dropped or
run twice; a browser disconnect releases it. Caregiver memo handlers keep Gradio's default.

**Revisit when** the Space moves off a 2 vCPU tier, or the judging panel regularly exceeds about
four simultaneous visitors.

## When to revisit

Spaces cold-starts or resource limits break the demo, or we get a better free host.
