# Plan: Memory Recall Short Word Inflections (Issue #32)

## Goal
Fix `_words_match` in `pipeline/orchestrator.py` so that short-word inflections (e.g., "dog" and "dogs", "walk" and "walked") are correctly matched during memory recall.

## Current vs Expected Behavior
*   **Current:** `_words_match` requires both words to be >= 5 characters for substring matching. Short words fall back to exact matching. This causes the system to miss memories when pluralization or past tense is used on short words.
*   **Expected:** Short words (3-4 characters) should allow specific common English suffixes (`s`, `d`, `es`, `ed`, `ing`) for a match, ensuring relevant memories are recalled without false positives (e.g., "car" should not match "cart").

## Changes
*   **`pipeline/orchestrator.py`**: Update `_words_match()` to add safe inflection matching for words >= 3 characters.
*   **`tests/test_orchestrator.py`**: Add `TestWordsMatchShortInflections` to verify "dog"/"dogs" and "walk"/"walked" matching, and to ensure "car"/"cart" does not falsely match. Add an end-to-end `_find_matching_facts` test.

## Verification
*   Run the full test suite (`pytest tests/test_orchestrator.py`) to confirm zero regressions and that all new tests pass.
