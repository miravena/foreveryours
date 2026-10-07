# Memory Conflict Resolution Plan

## Objective
Implement conflict-aware memory updating as outlined in critique point 5 ("Liam vs Leo"). The AI should not blindly overwrite an existing active memory if it detects an ambiguous contradiction (e.g., a potential second entity, a misunderstanding, or a speech-recognition error). Instead, it should flag the conflict and ask the senior for clarification in a future conversational turn.

## Context
Currently, `extract_memory_llm` uses `SUPERSEDE` to blindly overwrite memories when it detects a change. Because this runs asynchronously *after* the conversational reply, we cannot immediately ask for clarification in the same reply stream. Instead, we must store the pending conflict and resolve it proactively or reactively on the next turn.

## Changes Required

### 1. Extractor Prompt Update (`pipeline/think.py`)
Update `EXTRACTION_SYSTEM_PROMPT` to add a new command:
`4. To flag an ambiguous conflict: CONFLICT: <exact_old_fact> | <new_fact> | <reason>`
Instruct the LLM: 
- Use `SUPERSEDE` ONLY for explicit, direct corrections (e.g., "Actually, his name is Liam, not Leo").
- Use `CONFLICT` when the new information contradicts the old information implicitly and it might be a second entity, a mistake, or a nuanced change (e.g., Old: "Grandson is Liam" vs New: "My grandson Leo is coming").

### 2. Orchestrator Handling (`pipeline/orchestrator.py`)
In the async background thread within `run_turn`, if `saved_cmd.startswith("CONFLICT:")`:
- Parse `old_fact`, `new_fact`, and `reason`.
- Pass this to a new `add_conflict()` method in `MemoryStore` or just store it as a special internal `[CONFLICT]` flag in the active session history / context.
- Given `orchestrator.py` already manages `history` and `continuation_note`, we can inject a `continuation_note` for the next turn, or better yet, we can add a method in `MemoryStore` to persist pending conflicts.

### 3. MemoryStore Update (`memory/store.py`)
Add a new list/dictionary in the JSON schema for `pending_conflicts`.
- `add_conflict(old_fact, new_fact, reason)`
- `get_pending_conflicts()`
- `resolve_conflict(conflict_id, resolution_action)` (or simply delete the conflict once handled).

### 4. Think Prompt Injection (`pipeline/think.py`)
In `build_prompt`, if there are `pending_conflicts` in the `MemoryStore`, inject them as an urgent `continuation_note` or `[PENDING MEMORY CONFLICT]` block.
Example:
```
[PENDING MEMORY CONFLICT]: You previously noted "{old_fact}", but the senior recently said "{new_fact}". 
Reason for ambiguity: {reason}.
INSTRUCTION: Before continuing the conversation normally, gently ask the senior to clarify this discrepancy. 
For example: "By the way, I remember you mentioning Liam, but you just said Leo. Do you have two grandsons?"
```

### 5. MemoryStore Sync
Since `orchestrator.py` calls `extract_new_memory` async, the `MemoryStore` needs to be thread-safe for reading/writing. (It already writes async via JSON dumps, but we should make sure we don't clobber). Wait, we just need to read `pending_conflicts` in `run_turn` and pass them to `stream_reply`.

## Risks & Mitigations
- **Risk:** Infinite loop of asking about conflicts.
  **Mitigation:** The `extract_memory_llm` should be instructed to output `RESOLVE_CONFLICT: <old_fact>` or we automatically clear conflicts after asking once. For simplicity, once a conflict is injected into the prompt, we can remove it from the store (fire-and-forget), assuming the LLM will handle it in the conversational turn and a new explicit fact will be extracted.
- **Simplest approach for Hackathon:** Just use a `continuation_note` for the next turn if the session is alive, OR save it as a `[Pending Conflict]` fact in the `MemoryStore` that gets deleted as soon as it's injected into `build_prompt`.

## Testing
Update `tests/test_mature_benchmarks.py` to add `test_memory_conflict_resolution` which verifies the LLM outputs a `CONFLICT` command for an ambiguous change, and verifies that `build_prompt` receives the instruction to clarify it.
