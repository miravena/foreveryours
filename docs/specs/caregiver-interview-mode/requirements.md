# PRD: Guided get-to-know-you interview mode (#206)

## Problem

A real caregiver faced with a blank memo box does not know what to write. `docs/ROADMAP.md`
lists a guided interview as a stretch goal with no issue. The one-click sample household
(`caregiver.SAMPLE_FAMILY`) already defines the fields a good briefing contains.

## Users

The caregiver on first use; indirectly the senior, whose companion is better briefed.

## Scope

A caregiver-side mode that asks the `SAMPLE_FAMILY` fields one question at a time and saves
each confirmed answer as a caregiver memo through the existing memo path. Text first; voice
memo per answer only if it reuses `save_caregiver_voice_memo` unchanged.

## Requirements

1. **Question list** as data in `caregiver.py`, mirroring `SAMPLE_FAMILY` (people, likes,
   routine, topics to avoid, schedule), each with the scope it saves to and whether it may be
   skipped.
2. **Same path, plus validation.** Each answer goes through the memo helper the memo box
   uses, so fact splitting and fact supersede apply unchanged. That path does **not** refuse
   medical content today (`save_caregiver_text_memo` never calls `validate_sample_profile`;
   only the sample-household loader does), so each answer is first passed through
   `validate_sample_profile` (dosing, diagnosis, clinical claims) and a refused answer is not
   saved. Whether the plain memo box should validate too is a separate decision, not this one.
3. **Visible progress.** The caregiver panel shows answered, skipped and remaining; the mode
   can be left and resumed in the same session; nothing is saved before the caregiver confirms.
4. **Senior untouched.** The senior never hears the interview; no THINK call is made for it.
5. **Offline.** Works with no key.
6. **Tests.** Every question saves to the expected scope; a refused answer is not saved and
   the reason is shown; resuming does not re-ask answered questions; the session-end sweep
   removes everything.
7. **Docs.** `docs/PRD.md` caregiver onboarding; `CHANGELOG.md`.

## Acceptance criteria

The checkboxes on #206.

## Non-goals

Not a caregiver dashboard; not a model-driven conversation with the caregiver.

## Risks

- The interview tempts the caregiver to enter medical detail. Mitigation: the refusal path
  already exists; the question wording asks for routine and preferences, never conditions.
- UI sprawl in `webapp.py`. Mitigation: one accordion in the caregiver column, state in the
  session store, no new Gradio page.
