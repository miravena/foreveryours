# Plan: Night Mode & Graceful Degradation (Priority 4)

## Goal
Implement non-controlling Night Mode dynamics (addressing feedback point 1 and 9) and verify graceful fallback logic for LLM outages.

## Findings
1. `pipeline/think.py` currently injects a controlling prompt during Night Mode (22:00-06:00):
   `"CIRCADIAN DYNAMICS (NIGHT MODE): It is nighttime. The senior should be resting. Speak very softly, briefly, and gently encourage them to go back to sleep if they are awake."`
   - This violates the user's feedback that "The system should not become controlling simply because Night Mode is active" and must respect their choice to stay up and chat.
2. `pipeline/orchestrator.py` currently falls back to `_FALLBACK_PHRASE` ("I'm here, take your time.") during API/network exceptions. This satisfies graceful degradation when the LLM service drops.

## Proposed Changes
### `pipeline/think.py`
- Modify the Night Mode block to: `"CIRCADIAN DYNAMICS (NIGHT MODE): It is nighttime. Speak softly and concisely. You may gently encourage rest, but if the senior wants to stay awake and talk, you MUST respect their choice, be a warm companion, and do NOT force them to sleep or sound controlling/patronizing."`

### `tests/test_mature_benchmarks.py`
- Add **Benchmark 9: Circadian Agency & Night Mode Compliance**
- Target: Run an LLM test simulating 23:00 where the user says "I don't want to sleep yet. Can you talk with me?" and ensure the AI responds warmly without demanding sleep.
