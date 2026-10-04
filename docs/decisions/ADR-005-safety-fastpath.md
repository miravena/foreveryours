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

- **Gotcha:** broad patterns false-positive. The bare `help me` pattern was narrowed to anchored or
  qualified forms (`help me`, `please help me`, `help me get up`, ...) so "help me remember..."
  does not trigger, and `fell(?!\s+asleep)` excludes "I fell asleep". Near-misses are covered in
  `tests/test_fastpath.py`. Remaining gaps are tracked on GitHub, not here.
- Every pattern change needs a test in `tests/test_fastpath.py` for both the trigger and the
  near-miss.

## When to revisit

False-positive/negative rates in testing justify a hybrid rule + model check.
