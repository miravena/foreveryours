# ADR-005: Safety fast-path plus asynchronous model backstop

**Status:** Accepted
**Date:** 2026-10-01
**Decided by:** Team
**Affects:** `safety/fastpath.py`
**Related issue:** [#15](../../issues/15), [#33](../../issues/33), [#105](../../issues/105)

## Question

How do we detect distress ("I fell", "help me") fast and safely?

## Decision

**Rule-based regex**, checked before any model call, with an asynchronous AUDIT
model backstop for transcript phrasing the rules cannot cover.

## Rationale

Deterministic, under 50ms, no hallucination risk, and it can speak a reassurance immediately.

## Consequences

- **Gotcha:** broad patterns false-positive. The bare `help me` pattern was narrowed to anchored or
  qualified forms (`help me`, `please help me`, `help me get up`, ...) so "help me remember..."
  does not trigger, and `fell(?!\s+asleep)` excludes "I fell asleep". Near-misses are covered in
  `tests/test_fastpath.py`. Remaining gaps are tracked on GitHub, not here.
- Every pattern change needs a test in `tests/test_fastpath.py` for both the trigger and the
  near-miss.
- **Crisis tier:** direct suicidal language (`I am suicidal`, `I want to end it all`, `I do not
  want to live`, and equivalent phrases) takes precedence over distress. Benign idioms such as
  `to die for`, `tired I could die`, and `laughing so hard` are removed only as matched spans;
  genuine crisis text elsewhere in the same clause remains detectable. Newline-separated ASR
  fragments are normalized before matching.

## Model backstop amendment

The AUDIT pass reads the senior transcript as well as the companion reply and
can return `CRISIS`, `DISTRESS`, `UNSAFE`, or `SAFE`. It runs after speech has
started, so it does not replace the immediate fast-path reassurance or add
latency to first audio. `CRISIS` and `DISTRESS` flags receive a spoken
follow-up before persistence; a failed or unparseable audit is recorded as
`unknown`, never as `SAFE`.

## When to revisit

False-positive/negative rates in live evaluation justify changing the model,
prompt, or graded severity policy. The deterministic fast-path remains the
first safety layer.
