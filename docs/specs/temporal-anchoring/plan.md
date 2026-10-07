# Temporal Anchoring Plan

## Objective
Eliminate semantic search time-hallucinations by explicitly appending creation dates to `[PAST EMOTION]` items when they decay.

## Changes Required

### 1. `memory/store.py`
- Modify `_decay_emotions()`:
  - Add `import datetime`
  - Instead of `i.text = f"[PAST EMOTION]: {i.text}"`, format the string dynamically using `i.created_at`.
  - Example output: `[PAST EMOTION - Oct 04, 2026]: Angry at the dog`

### 2. Verification (`tests/test_mature_benchmarks.py`)
- **Benchmark 19**: Test that when an emotion is added and manually expired, it produces the exact timestamp string using the mocked clock, and the retrieved context contains the formatted date string.

### 3. Review
- Write `docs/specs/temporal-anchoring/review.md` evaluating if any loopholes remain.
