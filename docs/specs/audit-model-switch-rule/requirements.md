# PRD: AUDIT model switch rule (#200)

## Problem

ADR-010 measured AUDIT recall on true events at Nano 0.63, Super 120B 1.00 and Ultra 550B
0.95, all with 0 of 17 false flags, and kept Nano because the fixed rule requires strictly
fewer false flags and nothing beats zero. The rule predates the numbers and now blocks the one
change that catches the falls Nano misses. Per call: Nano 0.000023 USD, Super 0.00011, Ultra
0.00037. AUDIT is a background call, off the critical path.

## Users

The maintainers deciding the model; indirectly, every senior whose fall Nano misses.

## Scope

A decision recorded as an ADR; the `AUDIT_MODEL` default change if Super is chosen. Safe to
decide during judging; ships in `v1.1.0` unless #197's safety exception applies (a missed
emergency flag is exactly that exception, so the founder may choose to patch).

## Requirements

1. **The rule.** Restated as: switch when recall on true events improves and false flags do
   not increase, under a per-turn cost ceiling written in the ADR; or an explicit reason the
   old rule stands.
2. **If Super.** `AUDIT_MODEL` default in `pipeline/audit.py` and `.env.example` match; README
   Pipeline section and ADR-002 name the second model; per-turn cost in `VENDOR_DECISIONS.md`.
3. **Fresh numbers.** The eval re-runs after #193 so cached answers are keyed on content; under
   the 200-call cap; through `scripts/with_key.sh`.
4. **Latency proof.** AUDIT latency on the Space measured and shown not to reach the senior's
   first audio.
5. **Re-measure #198** against the chosen model before #198 closes.

## Acceptance criteria

The checkboxes on #200.

## Non-goals

Not the THINK model; Nano stays the reply model (ADR-002).

## Risks

- Super's latency delays the late disclosure of a backstop flag by seconds. Mitigation: measure
  it; the disclosure path already tolerates a slow AUDIT (`_BG_JOIN_TIMEOUT_S`).
- Cost at judge traffic. Mitigation: AUDIT is one call per turn; the daily cap bounds it.
