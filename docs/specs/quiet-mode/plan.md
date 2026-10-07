# AI Restraint (Quiet Mode) Plan

## Objective
Implement Point 1 from the critique: "The AI doesn't really know when NOT to speak". If the senior says "I'm going to take a nap" or "I want some quiet time", the system should extract a `QUIET_MODE` command and temporarily suppress any proactive triggers (check-ins, schedule reminders) for a set duration (e.g., 4 hours).

## Changes Required

### 1. `pipeline/think.py` (Extractor Prompt)
- Add a new command to `EXTRACTION_SYSTEM_PROMPT`:
  `5. To activate a temporary quiet mode because the senior requested rest, sleep, or alone time: QUIET_MODE`
- Add a Few-Shot example:
  ```
  [SCENARIO E]
  Senior: "I'm feeling tired, I'm going to take a nap for a while."
  Output: QUIET_MODE
  ```

### 2. `memory/store.py` (State Management)
- Add a `quiet_mode_until: float | None` field to the main `MemoryStore` state (or simply store a special `MemoryItem` with `text="[QUIET_MODE]"` and an `expires_at` timestamp).
- For simplicity and durability, we will use a specific `MemoryItem`: `add("[QUIET_MODE]", source="system", scope="temporary", expires_at=time.time() + 4*3600)`.
- Add a helper method: `is_quiet_mode_active() -> bool` which checks if `[QUIET_MODE]` is in active facts.

### 3. `pipeline/orchestrator.py` (Logic & Routing)
- **Background Extraction**: If `saved_cmd == "QUIET_MODE"`, add the special `[QUIET_MODE]` fact to `MemoryStore` with a 4-hour expiration.
- **Proactive Interception**: At the start of `run_turn`, if `is_proactive=True` and `memory_store.is_quiet_mode_active()` is True, immediately abort the turn and return a special `TurnResult` indicating silence: `result.audio_paths = []`, `result.audit_verdict = "Blocked by Quiet Mode"`.

### 4. `webapp.py` (UI Feedback)
- Modify `run_demo_turn` so that if `result.audit_verdict == "Blocked by Quiet Mode"`, the UI explicitly shows the judge: *"🔕 Proactive trigger suppressed: Senior is in Quiet Mode."*

## Verification
Create Benchmark 13 in `test_mature_benchmarks.py`:
1. Send transcript: "I'm going to sleep now."
2. Extract `QUIET_MODE`.
3. Set quiet mode in store.
4. Call `run_turn(is_proactive=True)`.
5. Assert it returns without generating any audio.

## Review
After verification, write an honest analysis of the feature's strengths and loopholes to `docs/specs/quiet-mode/review.md`.
