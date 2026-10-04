# ADR-002: THINK and AUDIT run NVIDIA Nemotron Nano 30B on Nebius

**Status:** Accepted
**Date:** 2026-10-01 (live-verified 2026-10-02, PR #25)
**Decided by:** Team
**Affects:** `pipeline/think.py`, `pipeline/audit.py`, cost, latency
**Related issue:** [#1](../../issues/1), [#17](../../issues/17)

## Question

Which model serves the THINK (reply) and AUDIT (honesty check) stages?

## Context

The hackathon requires Nebius + NVIDIA technology. Replies must feel fast, and AUDIT must not
double our cost.

## Decision

**`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` for both THINK and AUDIT**, via Nebius Token Factory
(`https://api.tokenfactory.nebius.com/v1`). Verified live (PR #25).

## Rationale

A mixture-of-experts model fits the latency target, satisfies the sponsor requirement, and
reusing it for AUDIT adds no extra model cost.

## Consequences

- **Gotcha:** hidden reasoning tokens dominated latency (4.22s to first audio). Sending
  `enable_thinking: false` (the default; `THINK_ENABLE_REASONING=true` turns reasoning back on)
  brought it to ~0.9s (PR #29) without quality loss.
- Both models are env-overridable (`THINK_MODEL`, `AUDIT_MODEL`), so a lighter Nemotron can be
  swapped in if latency regresses.

## When to revisit

Latency or quality regresses on the hosted instance, or the budget model changes.
