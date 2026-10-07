# Caregiver Conflict Resolution Plan

## Objective
Fix "Loophole 4: Blindness to Caregiver Conflicts". Ensure that the background memory extraction agent can detect and flag when the Senior's statement contradicts a schedule update or memo provided by the Caregiver.

## Context
Currently, `extract_memory_llm` only looks at `active_facts` (which are explicitly filtered by `senior_profile_facts()` to exclude Caregiver items). If a caregiver notes that a doctor appointment is on Monday, and the senior says it's on Thursday, the extraction LLM has no idea the Caregiver said Monday, and will blindly extract Thursday as a new active fact.

## Changes Required

### 1. Extractor Prompt Update (`pipeline/think.py`)
Update `EXTRACTION_SYSTEM_PROMPT` to acknowledge Caregiver Notes:
- Add an instruction: "If the senior's statement contradicts a CAREGIVER NOTE, output a CONFLICT command (e.g. CONFLICT: Caregiver says doctor is Monday | Senior says doctor is Thursday | Source conflict)."

### 2. Function Signature Updates (`pipeline/think.py`)
Modify `extract_memory_llm` and `extract_new_memory` to accept a new parameter: `caregiver_updates: list[str] | None = None`.
- In `extract_memory_llm`, append these updates to the user prompt block (e.g., `\n\nACTIVE CAREGIVER NOTES:\n...`).

### 3. Orchestrator Integration (`pipeline/orchestrator.py`)
In `run_turn`, `filtered_schedule` already holds the active caregiver updates for the current turn.
Pass `filtered_schedule` to `extract_new_memory`:
```python
saved_cmd = think.extract_new_memory(transcript, reply_text, active_facts, caregiver_updates=filtered_schedule)
```

### 4. Testing (`tests/test_mature_benchmarks.py`)
Create Benchmark 11: `test_caregiver_conflict_resolution`.
- Preload a caregiver memo: "Doctor appointment is tomorrow at 10 AM".
- Senior transcript: "My doctor appointment is next Thursday."
- Verify that `extract_memory_llm` returns a `CONFLICT` command rather than blindly `ADD`ing Thursday.

## Risks & Mitigations
- **Risk:** The LLM might try to `SUPERSEDE` the caregiver note instead of flagging a `CONFLICT`.
  **Mitigation:** `SUPERSEDE` rule states it can only be used on facts "EXACTLY listed in the ACTIVE PROFILE FACTS". Since caregiver notes will be in a separate `ACTIVE CAREGIVER NOTES` block, the LLM should default to `CONFLICT`. We will explicitly state in the prompt rules not to supersede caregiver notes directly.
