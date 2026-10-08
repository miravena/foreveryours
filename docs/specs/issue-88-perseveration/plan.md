# Plan: Issue 88 (Perseveration Flag Privacy Violation)

## The Bug
Currently, in `pipeline/orchestrator.py`, if the senior asks the same type of question (Logistical or Memory Request) 3 times in a row, a "Perseveration loop" flag is raised for the caregiver. However, it explicitly sets `disclosed_to_senior=False`, keeping this tracking secret from the senior. This violates the core invariant: "ForeverYours never reports anything to the family that it hasn't first said to him out loud."

## The Fix
1. In `pipeline/orchestrator.py`, modify the flag creation to set `disclosed_to_senior=True`.
2. To ensure it is actually disclosed, we will inject a `continuation_note` into the LLM context for that specific turn when the perseveration flag triggers.
3. The note will instruct the LLM: `"The person has repeated this question multiple times. Answer gently, and clearly tell them out loud that you are noting this repetition for their family so they are aware you are observing it."`
4. Since `think_input` already appends `continuation_note` if it exists, the LLM will naturally incorporate this disclosure into its spoken reply.

## Verification
1. Update `tests/test_orchestrator.py` if there's a test for the perseveration flag to ensure `disclosed_to_senior` is True and the note is passed.
2. Run tests to confirm.

## Review
1. Draft `review.md`.
