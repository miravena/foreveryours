# ADR-016: AUDIT runs Nemotron 3 Super 120B; THINK stays on Nano

**Status:** Accepted
**Date:** 2026-10-23
**Decided by:** Founder, 2026-10-23
**Affects:** `pipeline/audit.py` (`DEFAULT_AUDIT_MODEL`), `.env.example`, `webapp.py` (footer, dev panel), `README.md`, `VENDOR_DECISIONS.md`. Amends ADR-010 and ADR-002.
**Related issue:** [#200](../../issues/200)

## Question

ADR-010 kept AUDIT on Nano because no candidate had strictly fewer false flags. Should the
rule, and the default, change now that the fixture has more rows and Nano falls below the
eval's recall floor?

## Context

AUDIT is the only automated check for falls and crisis paraphrases the rules miss (ADR-005,
ADR-012, ADR-013). It runs in the background after the reply; the next turn joins it with a
10 s timeout (`_BG_JOIN_TIMEOUT_S` in `webapp.py`).

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| Keep Nano (ADR-010) | Cheapest, fastest | Recall 0.88 on the 43-row set, below the 0.90 floor | Yes |
| Super 120B for AUDIT | Recall 1.00, same 0 false flags | About 5x the per-call cost, about 0.4 s slower | Yes |
| Ultra 550B | Highest tier | Recall 0.95 in ADR-010, about 3x Super's cost | Yes (ADR-010) |

## Decision

**AUDIT defaults to `nvidia/nemotron-3-super-120b-a12b`. THINK stays on
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.**

The rule changes from ADR-010's "strictly fewer false flags" to: **switch to a candidate when
Nano is below the eval's 0.90 recall floor on the current fixture, the candidate is at or above
it, its false flags are no more than Nano's, and its latency stays inside the ceiling below.**

## Rationale

Measured live, 2026-10-23:

| Measure | Nano | Super |
|---|---|---|
| 43-row AUDIT eval, recall | 0.88 | 1.00 |
| False flags | 0/17 | 0/17 |
| Missed | fall-10, fall-11, confusion-01 | none |
| 37-row crisis eval | 23/23 caught, 2/14 benign rows flagged | same |
| List price per 1M tokens (in/out) | $0.06 / $0.24 | $0.30 / $0.90 |
| Cost per AUDIT call | about $0.00004 | about $0.0002 |
| Latency, 5 calls each: median / max | 0.65 s / 1.47 s | 1.09 s / 3.00 s |

**Latency ceiling:** AUDIT's wall time per call must stay under 10 s, the webapp's background
join timeout. Super's measured maximum is 3.00 s, so it has headroom. If a model's maximum
approaches 10 s, the next turn stops waiting for it.

## Consequences

- **Unlocked:** the background backstop catches every labelled fall and crisis row in the
  current fixtures.
- **Locked in to:** Super for AUDIT until the rule is revisited. `AUDIT_MODEL` still overrides.
- **Gotchas:** AUDIT cost per turn rises about five-fold, still a fraction of a cent. The page
  footer now names two models (Reply: Nano, Safety backstop: Super). A deployment that sets
  `AUDIT_MODEL` explicitly is unaffected.

## When to revisit

Super's latency maximum exceeds 5 s on the hosted Space, Token Factory withdraws or reprices
Super, or a model is served that matches Super's recall at Nano's cost.
