# Proactive Agency - Gap Closure Plan

## Goal
Implement three production safeguards for Proactive Agency: a Pre-flight context verifier, a Two-Strike history suppression rule, and a background Daemon.

## 1. Pre-Flight Context Verification
**File:** `pipeline/orchestrator.py (run_turn)`
Before checking the pipeline cache or hitting the LLM, verify:
- If `trigger_type == 'hobby'` and no permanent facts exist, return a fallback/skip result.
- If `trigger_type == 'reminder'` and no caregiver updates exist, return a fallback/skip result.

## 2. Two-Strike Suppression Rule
**File:** `pipeline/orchestrator.py (run_turn)`
If `is_proactive == True`, check `history`. If the last two turns are both from the assistant (or a specialized proactive flag), return a skip result to prevent spam.

## 3. The Daemon / Poller
**File:** `pipeline/daemon.py` or `webapp.py`
Implement a tick-based poller that can be called to simulate time passing. Since we are in a Gradio UI, true threading might clash with Gradio's state, but we can implement a `tick()` function that evaluates rules and fires triggers. We will add a 'Start Proactive Daemon' toggle in the Dev UI to run this loop.