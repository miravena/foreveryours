# Memory Lifecycle Patches Plan

## Objective
Address the three memory lifecycle loopholes:
1. Rigid Emotional Categorization
2. Certainty Escalation
3. Complete Deletion of Emotions

## Changes Required

### 1. `pipeline/think.py` (Prompt Engineering for Loophole 1)
- Add rule to `EXTRACTION_SYSTEM_PROMPT`: "For profound life events (death, trauma, major diagnosis), use standard fact extraction (which makes it PERMANENT). ONLY use EMOTION for fleeting, temporary moods."
- Add few-shot `[SCENARIO H]`: "My dog passed away today." -> `My dog passed away recently`.

### 2. `memory/store.py` (Historical Archiving & Prefix Stripping for Loopholes 2 & 3)
- **Prefix Stripping**: Update `supersede()` and `delete()` to strip `[UNVERIFIED/UNCERTAIN]: ` and `[EMOTIONAL STATE]: ` from `old_text` before searching.
- **Historical Archiving**: Add a `_decay_emotions(self, now: float)` method. This will iterate over `_items`. If an item is `EMOTIONAL` and its `expires_at` is reached, it will mutate the item:
  - `item.scope = MemoryScope.HISTORICAL.value`
  - `item.text = f"[PAST EMOTION]: {item.text}"`
  - `item.expires_at = None`
  - `item.status = "active"`
  - Call `self._flush()`
  This method will be called at the top of `senior_profile_facts()` and `search()`.

### 3. Verification
- `test_mature_benchmarks.py`:
  - **Benchmark 16**: Test that "My dog died" is extracted as a permanent fact, not an emotion.
  - **Benchmark 17**: Test that an expired emotion is retrieved by `search()` as `[PAST EMOTION]`.
  - **Benchmark 18**: Test `SUPERSEDE` correctly strips the prefix and upgrades an `UNCERTAIN` fact.

### 4. Review
- Write `docs/specs/lifecycle-patches/review.md` evaluating the success and identifying any remaining gaps.
