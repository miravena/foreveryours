# Plan: Privacy & Logging Audit (Issue #47)

## Goal
Audit all logging to ensure no PII (caregiver memos, senior transcripts) or secrets (`.env` variables) are exposed in stdout/stderr, which would leak into Hugging Face Spaces public logs.

## Findings
1. The `pipeline/` modules (`orchestrator.py`, `think.py`, `audit.py`, `hear.py`) contain zero `print` or `logging` statements. They are completely silent.
2. `pipeline/speak.py` contains minor prints for audio playback failures, but they only log file paths (`out/audio/chunk.wav`), not transcript text.
3. `webapp.py` currently has a `raise` statement inside `_run_demo_turn()`'s catch-all exception handler. 
    - **The Risk:** In Gradio, an unhandled `raise` dumps the full traceback to `stderr`. This traceback includes local variables and function arguments, meaning the `transcript` (PII) would be fully exposed in the Hugging Face server logs every time an error occurs. 

## Proposed Changes
### `webapp.py`
- Replace the unhandled `raise` in `_run_demo_turn` with a safe, sanitized log and a graceful UI fallback.
