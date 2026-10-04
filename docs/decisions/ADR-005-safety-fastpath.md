# ADR-005: Safety fast-path is deterministic rules, not a model

**Status:** Accepted
**Date:** 2026-10-01
**Decided by:** Team
**Affects:** `safety/fastpath.py`
**Related issue:** [#15](../../issues/15), [#33](../../issues/33)

## Question

How do we detect distress ("I fell", "help me") fast and safely?

## Decision

**Rule-based regex**, checked before any model call.

## Rationale

Deterministic, under 50ms, no hallucination risk, and it can speak a reassurance immediately.

## Consequences

- **Gotcha:** broad patterns false-positive. PR #29 tightened "I fell" vs "I fell asleep";
  bare `\bhelp me\b` still false-triggers on "help me remember..." (open: #15 / #33).
- Every pattern change needs a test in `tests/test_fastpath.py` for both the trigger and the
  near-miss.

## When to revisit

False-positive/negative rates in testing justify a hybrid rule + model check.
