# Feature Review: Perseveration Flag Privacy Violation (Issue 88)

## Feature Overview
The `orchestrator.py` script automatically tracks "Cognitive Drift" (perseveration). If a senior asks a logistical or memory question 3 times in a row, a flag is added to the caregiver panel with the `confusion` severity. 

Previously, this flag explicitly set `disclosed_to_senior=False`, which completely violated the app's core privacy invariant: "ForeverYours never reports anything to the family that it hasn't first said to him out loud."

## What Was Fixed
1. Set `disclosed_to_senior=True` when raising the perseveration flag.
2. Injected a `continuation_note` into the `think.stream_reply` prompt when the loop triggers, explicitly instructing the LLM: `"The person has repeated this question multiple times. Answer gently, and clearly tell them out loud that you are noting this repetition for their family so they are aware you are observing it."`
3. Updated `tests/test_orchestrator.py` to assert that `disclosed_to_senior` is True and the `continuation_note` is injected into the prompt.

## Honest Gap Analysis (Loopholes & Downfalls)
1. **Model Compliance:** We instruct the LLM via `continuation_note` to disclose this fact out loud, but we are relying on the LLM to follow this instruction in its generated output. While 30B models are usually compliant, a strict invariant like this shouldn't rely on probabilistic text generation. A better architecture would force a hardcoded prefix before handing generation off to the LLM.
2. **Intent Matching Rigidity:** The orchestrator only flags perseveration if the intent classifier specifically outputs `LOGISTICAL` or `MEMORY_REQUEST` 3 times in a row. A senior could repeat a fear (e.g. `DISTRESS` or `CONFUSION`) 3 times in a row, and it would completely fly under the radar of this particular flag.
