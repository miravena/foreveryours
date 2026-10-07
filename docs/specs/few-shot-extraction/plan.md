# Loophole 3: Few-Shot Extraction Plan

## Objective
Fix the "Zero-Shot Dependency" Loophole. Currently, the `extract_memory_llm` relies entirely on zero-shot reasoning to determine if an update is a direct correction (`SUPERSEDE`) or an ambiguous contradiction (`CONFLICT`). By injecting a `FEW-SHOT EXAMPLES` block into the `EXTRACTION_SYSTEM_PROMPT`, we can drastically reduce hallucination and ensure the routing logic is mathematically reliable.

## Changes Required

### 1. `pipeline/think.py`
Update `EXTRACTION_SYSTEM_PROMPT` to include concrete examples:

**Example 1: Direct Correction (SUPERSEDE)**
- Active Facts: His grandson is named Leo
- Transcript: "Actually, my grandson is Liam, not Leo."
- Command: `SUPERSEDE: His grandson is named Leo | His grandson is named Liam`

**Example 2: Ambiguous Change (CONFLICT)**
- Active Facts: His grandson is named Liam
- Transcript: "My grandson Leo is coming tomorrow."
- Command: `CONFLICT: His grandson is named Liam | My grandson Leo is coming tomorrow | Might have two grandsons`

**Example 3: Caregiver Contradiction (CONFLICT)**
- Caregiver Notes: Doctor appointment is Monday
- Transcript: "My doctor appointment is Thursday."
- Command: `CONFLICT: Doctor appointment is Monday | Doctor appointment is Thursday | Source conflict`

**Example 4: Explicit Deletion (DELETE)**
- Active Facts: Used to work as a carpenter
- Transcript: "Please forget that I told you about my carpentry job."
- Command: `DELETE: Used to work as a carpenter`

### 2. Testing
Run the existing memory benchmarks (`test_mature_benchmarks.py`). We do not need to add a *new* test because Benchmarks 8, 10, and 11 already explicitly test `SUPERSEDE`, `DELETE`, and `CONFLICT`. If all 3 pass after the prompt update, the few-shot implementation is successful and regressions are prevented.
