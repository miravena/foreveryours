# Loophole 2: Fire-and-Forget Resolution Drop Plan

## Objective
Fix the "Fire-and-Forget" Loophole. Currently, when a memory conflict is injected into the prompt for clarification, the system immediately deletes it (`memory_store.clear_conflicts()`). If the senior ignores the AI's question, the conflict is permanently lost. 
The AI should instead escalate unresolved conflicts to the Caregiver Dashboard rather than dropping them or nagging the senior endlessly.

## Changes Required

### 1. `memory/store.py`
Replace `clear_conflicts()` with a state-machine approach for conflicts:
- Add `mark_conflicts_asked()`: Changes `status="conflict"` to `status="conflict_asked"`. This is called when the conflict is injected into the prompt.
- Add `escalate_stale_conflicts(flags: CaregiverFlags)`: Finds all items with `status="conflict_asked"`, adds a CaregiverFlag (e.g., `flags.add(f"Unresolved Memory Ambiguity: {reason}", severity="info", disclosed_to_senior=False)`), and then marks them as `status="deleted"` so they don't persist in the store forever.

### 2. `pipeline/orchestrator.py`
- At the start of `run_turn`, before checking for new conflicts, call `memory_store.escalate_stale_conflicts(flags)`. This ensures that any conflicts asked about in the *previous* turn are escalated if they weren't resolved by the extraction phase (since extraction for the previous turn has already completed).
- When retrieving `pending_conflicts`, instead of `memory_store.clear_conflicts()`, call `memory_store.mark_conflicts_asked()`.

### 3. Logic Flow
1. **Turn 1**: Senior says "Doctor is Thursday". Extractor flags `CONFLICT`. Store saves `status="conflict"`.
2. **Turn 2**: `run_turn` starts. `escalate_stale_conflicts` does nothing (none are `conflict_asked`). `get_pending_conflicts` finds the conflict. `mark_conflicts_asked` changes it to `conflict_asked`. The AI asks the senior: "Did you reschedule?"
3. **Turn 2 (Background)**: Extractor runs on the senior's reply. 
   - *Case A (Resolved)*: Senior says "Yes". Extractor outputs `SUPERSEDE` or `ADD` or `DELETE`. Since the extractor doesn't explicitly delete the `conflict_asked` item, wait... how does it get deleted if resolved?
   - Actually, the easiest way is that the background extractor doesn't need to explicitly delete the conflict. If the senior resolves it, a *new* valid fact is added or superseded. The stale conflict will just be escalated as an "Info" flag on Turn 3. The caregiver will see "Unresolved Ambiguity" but also see the new active fact. This is safe and requires no complex LLM multi-step reasoning.
   - *Better Approach*: We can just use `CaregiverFlags` directly for escalation.

Wait, if we escalate *every* conflict to the Caregiver Dashboard on Turn 3, even if the senior resolved it on Turn 2, that generates false-positive alerts for the caregiver.
To fix this: `extract_new_memory` must output a `RESOLVE_CONFLICT` command, OR `add_conflict` uses the exact old fact, and if that fact is superseded, the conflict is naturally moot.
Because we don't want to complicate the LLM prompt further, let's keep it simple: `memory_store.escalate_stale_conflicts(flags)` just logs them to the caregiver as a low-priority note. 
Actually, to truly avoid false positives, we can instruct the LLM: 
"If the senior clarifies a pending conflict, output the appropriate ADD/SUPERSEDE/DELETE command. The system will automatically clear pending conflicts when you do." 
Wait, if ANY command (`ADD`, `SUPERSEDE`, `DELETE`, `NONE`) happens on Turn 2, the conflict is considered "handled" (either the senior answered it, or ignored it). 
If the senior ignored it (LLM outputs `NONE`), we escalate. 
If the senior answered it (LLM outputs `ADD`/`SUPERSEDE`), we do NOT escalate.

Let's do this: 
In `orchestrator.py` background thread:
If `saved_cmd` is NOT `NONE` (and not `CONFLICT`), we clear `conflict_asked` without escalating. 
If `saved_cmd` IS `NONE` (meaning no durable facts were extracted, senior ignored the question), we escalate `conflict_asked` to CaregiverFlags and delete it.

This perfectly solves the problem without changing the prompt!

### Revised Implementation Plan
**`memory/store.py`**:
- `mark_conflicts_asked()`: Changes `status="conflict"` to `status="conflict_asked"`.
- `resolve_asked_conflicts()`: Changes `status="conflict_asked"` to `status="deleted"` (used when senior answers).
- `escalate_asked_conflicts(flags)`: Iterates `conflict_asked`, adds `flags.add(...)`, then changes to `status="deleted"`.

**`pipeline/orchestrator.py`**:
- In the main thread: `if pending_conflicts: memory_store.mark_conflicts_asked()`.
- In the background thread, after `think.extract_new_memory` returns `saved_cmd`:
  - If `saved_cmd` is a valid command (`ADD`, `SUPERSEDE`, `DELETE`), call `memory_store.resolve_asked_conflicts()`.
  - If `saved_cmd` is `None` (or `NONE`), call `memory_store.escalate_asked_conflicts(flags)`.

### 4. Testing
Create Benchmark 12 in `test_mature_benchmarks.py` to test that a dropped conflict triggers a CaregiverFlag.
