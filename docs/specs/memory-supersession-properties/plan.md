# Plan: Memory Supersession Temporal Integrity (Issue #34)

## Goal
Fix `supersede()` in `memory/store.py` so that when a memory is updated, it retains its original temporal expiration (`expires_at`) and privacy scope (`scope`, `privacy`).

## Current vs Expected Behavior
*   **Current:** When a temporary memory (e.g., a schedule expiring in 2 hours) is superseded, a new `MemoryItem` is created with default parameters (permanent, public). The temporary property is silently lost.
*   **Expected:** The new superseded memory should inherit the `scope`, `privacy`, and `expires_at` attributes from the original memory item to maintain strict caregiver intent and time bounds.

## Changes
*   **`memory/store.py`**: Update the `supersede` method to retrieve `scope`, `privacy`, and `expires_at` from the old memory item, and pass them to the constructor of the new `MemoryItem`.
*   **`tests/test_memory.py`**: Add `TestSupersedeInheritsProperties` to verify that temporary schedules stay temporary, private memos stay private, and chained supersessions correctly carry the properties forward.

## Verification
*   Run the full test suite (`pytest tests/test_memory.py`) to confirm zero regressions and verify the newly introduced assertions pass.
