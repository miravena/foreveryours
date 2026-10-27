# ADR-017: Host the judge demo on HF PRO with `cpu-basic` through the judging period

**Status:** Proposed
**Date:** 2026-10-27
**Decided by:** Account owner (the card and the PRO subscription are theirs); maintainers review
**Affects:** `.github/workflows/deploy-space.yml`, `scripts/deploy_hf_space.py`, `HOW_TO_WORK_HERE.md`, `README.md`
**Related issues:** [#252](../../issues/252), [#253](../../issues/253)

Supersedes the hosting part of [ADR-003](ADR-003-hosting.md) (free ZeroGPU as the host). The rest of
ADR-003 (Spaces, the Nebius secret, keep-awake) stands.

## Question

Where should the Space run so a judge who opens it between 2026-12-01 and 2026-12-15 gets a working
demo?

## Context

On 2026-10-27 the Space went down: four `deploy-space` runs in about 30 hours ended "not RUNNING after
900s", and the old container was replaced by a `RUNTIME_ERROR` Space with `hardware.current: null`.
The Space never got a machine. The analysis in #252 (and the incident write-up, PR #255) found this is
ZeroGPU scheduling on Hugging Face's side: 37 of 48 sampled free-account ZeroGPU Spaces that got past
the build had no hardware, and so did 6 of 11 PRO-owned ones, so PRO alone does not fix ZeroGPU.
Free hardware has no SLA and nothing alerts. The app is CPU-only; ZeroGPU was only ever a way to host
it without paying (ADR-003).

## Options considered

| Option | Cost to 2026-12-15 | Cons | Tried? |
|--------|--------------------|------|--------|
| Wait on free ZeroGPU | $0 | No SLA; the outage may recur during judging | Yes (outage) |
| **PRO + `cpu-basic`** | about $18 | Needs a card; Space stops if PRO is cancelled | No |
| PRO + `cpu-upgrade` ($0.03/h) | about $35 more | Dearer; PRO may be required anyway | No |
| Team org | about $40 | Moves the Space and changes the submitted URL | No |
| VM outside HF | about $70 | Hours of work; a backup link at best | No |

## Decision

**PRO plus `cpu-basic`, same Space and URL, kept up through the judging period (ends 2026-12-15
12:00 PT).** Because PRO bills monthly, keep it through 2026-12-27 at minimum, and optionally to the
winners announcement (about 2027-01-11). **Fallback: `cpu-upgrade` ($0.03/h)** if `cpu-basic` is too
slow or will not schedule.

The hardware is one setting: the repository variable `SPACE_HARDWARE` (default `cpu-basic`), read by
the deploy workflow and passed to `scripts/deploy_hf_space.py --hardware`. Moving to `cpu-upgrade`, or
back to `zero-a10g`, is editing that variable and re-running the workflow; no code change.
`app.py`'s `@spaces.GPU` marker only exists when the `spaces` package is installed, and the deploy adds
`spaces` to the Space's requirements only for `zero-*` hardware, so on CPU hardware it is absent and
the marker never registers. Switching back to ZeroGPU re-adds both.

The deploy now checks the account first. For `cpu-basic` / `cpu-upgrade` it stops with a clear message,
before any upload, if `whoami` shows the account is not PRO (and has no paid org), or `canPay` is
false, or the Hub rejects the hardware request (HTTP 400/402/403). That replaces a 900 s wait that
ends in an unhelpful "not RUNNING".

## Latency risk (approximate)

`cpu-basic` is 2 vCPU / 16 GB. ADR-003's 1.9 to 6.4 s per turn was taken on ZeroGPU, whose CPU share is
undocumented. To approximate, the app ran locally on a 4-core ARM (Neoverse-N1) host, pinned to 2 CPUs
(`taskset -c 0,1`) and unpinned, driven through the same streaming endpoint as the live judge check,
with the live Nebius models. Seconds from submit to first reply text / first audio chunk (audio is the
first yielded chunk path; a yield before it is only the "thinking" placeholder):

| Turn | 2 CPUs, text / audio | Unpinned, text / audio |
|------|----------------------|------------------------|
| typed 1 | 1.1 / 1.9 | 1.5 / 2.2 |
| typed 2 | 1.8 / 2.6 | 1.5 / 3.0 |
| sample clip (jazz) | 9.8 / 9.8 | 5.6 / 6.3 |

An earlier 2-CPU run of 5 typed turns (text only, first audio was not captured correctly) gave first
text of 2.2 to 3.5 s, and two clips gave 9.2 s and 4.6 s. The takeaway, with the caveat that this is
one noisy run on a shared host (load average about 3.7) and the Nebius round trip dominates typed
turns: typed turns are not CPU-bound, so 2 vCPU should not change them visibly; a spoken clip is
(local `faster-whisper` transcription), costing roughly 4 s more first-text on 2 CPUs, about 5 to 10 s
in total. Oracle is ARM and Hugging Face is x86, so the absolute numbers will differ. The decisive
measurement is one live judge check on the real Space after the switch. If clips feel slow there,
`cpu-upgrade` (8 vCPU) is the fallback. The measurement used 13 live reply turns, not the planned 10,
because the first audio detection was wrong and had to be redone.

## Consequences

- Cost about $18 to $27: PRO at $9/month for two to three months, `cpu-basic` itself is free for PRO.
- After PRO is cancelled the Space stops unless it is moved back to ZeroGPU; do not cancel before the
  keep-up date above.
- A failed deploy is still not rolled back (ADR-015's tag rollback applies); the early failure makes it
  visible in seconds.
- A merge of the change that wires this up redeploys, so it lands only once PRO is active.

## When to revisit

If `cpu-basic` misses the live judge check's latency, move to `cpu-upgrade`. If the account loses PRO,
move back to `zero-a10g` and accept the scheduling risk.
