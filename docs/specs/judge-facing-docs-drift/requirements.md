# PRD: Judge-facing docs match the frozen submission (#204)

## Problem

Judges read the frozen Devpost text, then the README. The text pasted on 10-29 is fixed for six
weeks; the repo is not. Any sentence where the two disagree costs Technological Implementation,
the tie-break criterion. The repo also still carries the proof-of-concept video pipeline under
`video/` and a README "Demo video" line that predates the YouTube cut.

## Users

The judges, reading for two minutes each.

## Scope

One consistency pass after the Devpost text is final, shipped as a `v1.0.x` wording patch
under #197, and a second pass only if a judging-window patch changes behaviour.

## Requirements

1. **The submission is in the repo.** `docs/DEVPOST_SUBMISSION.md` holds the pasted text
   verbatim with the submission date.
2. **A claims table.** In that file, every factual claim (models, services, local vs hosted,
   test count, voice, notification, languages, licence) has the README line and the code line
   that back it, verified on the tagged commit.
3. **Five documents agree.** `README.md`, `docs/Project_Description.md`, `docs/FEEDBACK.md`,
   `docs/SAFETY_AND_PRIVACY.md`, `docs/PRIVACY.md` say what the submission says on every row.
   #108, #135, #138, #173, #174 are closed or folded in.
4. **Video.** `README.md` "Demo video" points at the public YouTube link from #5; `video/` is
   removed or moved under `docs/archive/` with one line saying it was the pre-hosting proof of
   concept.
5. **Checks.** `tests/test_no_internal_refs.py`, the full suite and `scripts/smoke.sh` pass.
6. **Shipped.** As a patch Release before 12-01, recorded on #196.

## Acceptance criteria

The checkboxes on #204.

## Non-goals

No wording that goes beyond the submission. Match it; do not improve it.

## Risks

- The pass "fixes" a sentence in the README that the submission also carries, creating the
  drift it was meant to remove. Rule: the submission text wins; the repo changes, never the
  claim.
