# Plan: Guided interview mode (#206)

## Goal

A caregiver with nothing written can brief the companion in five answers, each saved exactly
as a typed memo would be.

## Affected files

- `caregiver.py`: `INTERVIEW_QUESTIONS` (list of dicts: `key`, `prompt`, `scope`,
  `skippable`, `example`), derived from the `SAMPLE_FAMILY` keys
- `webapp.py`: an "Interview" accordion in the caregiver column; a small state object in the
  session (`interview_index`, `answers`); handlers `interview_next`, `interview_skip`,
  `interview_confirm` that call the same helper as the memo box (the function
  `save_caregiver_memo` delegates to; factor it out if it is inline)
- `tests/test_caregiver.py`, `tests/test_webapp.py`
- `docs/PRD.md`, `CHANGELOG.md`

## Steps

1. Read `caregiver.SAMPLE_FAMILY`, `validate_sample_profile`, `split_memo_facts`, and the
   memo-box handler in `webapp.py`; identify the one helper every answer must go through.
   If the memo box writes inline, extract `_save_memo_text(session, text) -> panel` first,
   with a test that the memo box behaviour is unchanged.
2. `INTERVIEW_QUESTIONS` with five entries; a unit test that every key exists in
   `SAMPLE_FAMILY` and every scope is a known scope.
3. Session state and the three handlers; a confirm saves through the helper and advances;
   skip advances; resume reads `interview_index`.
4. Accordion UI; progress line "3 of 5 answered, 1 skipped".
5. Tests: scope per question; refusal shown and nothing saved; resume does not re-ask;
   session-end sweep clears the state and the memos (reuse the sample-family sweep test).
6. PRD paragraph, CHANGELOG, `scripts/openai_review.sh`, `scripts/smoke.sh`.

## Tests

`tests/test_caregiver.py` (question data), `tests/test_webapp.py` (handlers through the Gradio
functions, not the UI), Benchmark 4 (caregiver privacy firewall) still green.

## Splitting across subagents

- Subagent A: steps 1 and 2 (helper extraction with its regression test, question data).
- Subagent B (after A): steps 3 to 5.
- Subagent C: step 6.
Each needs this file, #206, `caregiver.py`, `webapp.py`'s caregiver column, and
`tests/test_sample_family.py` as the pattern. No key needed.

## Review

`scripts/openai_review.sh` on the PR.
