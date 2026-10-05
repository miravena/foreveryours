# Plan: Memory Control & Correction (Priority 1)

## Goal
Give the senior true agency over their digital footprint. If they correct a fact ("His name is Liam, not Leo") or ask the system to forget something ("Forget I used to be a teacher"), the background extraction pipeline must formally supersede or delete the old memory, rather than just blindly adding contradictory facts.

## Findings
- `memory/store.py` already has a `supersede()` function (tested by Benchmark 5), but the `orchestrator.py` pipeline currently never uses it because the LLM extractor only outputs raw strings to `add()`.
- `memory/store.py` does not currently have a `delete()` function for when the senior says "Forget this".

## Proposed Changes

### 1. `memory/store.py`
Add a `delete(text: str)` method that finds the active memory and marks its status as "deleted", immediately removing it from all future prompts.

### 2. `pipeline/think.py`
Update `EXTRACTION_SYSTEM_PROMPT` to support three explicit commands instead of just returning raw strings:
- `ADD: <fact>`
- `SUPERSEDE: <exact_old_fact> | <new_fact>`
- `DELETE: <exact_old_fact>`

Update `extract_new_memory` and `extract_memory_llm` to accept the `active_facts` list as an argument, so the LLM knows the exact strings it is allowed to supersede or delete.

### 3. `pipeline/orchestrator.py`
Update the background extraction thread to parse the `ADD:`, `SUPERSEDE:`, and `DELETE:` commands and call the appropriate methods on the `MemoryStore`. 

### 4. `tests/test_mature_benchmarks.py`
Update Benchmark 5 to run an end-to-end `run_turn` test simulating a correction, proving that the orchestrator successfully intercepts the correction and supersedes the memory in the data store.

## User Review Required
Please review the plan above. If approved, I will apply these changes, run the test suite (which includes the memory correction benchmark you asked about), and review it.
