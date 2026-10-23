# Plan: One-week trial (#202)

## Goal

Seven days of real use, measured the way we said we would, written up honestly.

## Affected files

- `docs/trial/CONSENT.md`, `docs/trial/SETUP.md`, `docs/trial/MEASUREMENTS.md`,
  `docs/trial/EXIT_INTERVIEW.md` (all new)
- `docs/WORK_LOG.md` (after the week), `docs/PRD.md` (only if a decision changes)

## Steps

1. Write the four documents. Keep each to one page.
2. Have someone who did not write `SETUP.md` follow it on a clean machine with a fresh key;
   fix the guide until they succeed without help.
3. Recruit the household; walk through the consent sheet in person; both sign.
4. Install; run `scripts/smoke.sh` on their machine; show the caregiver the panel and the
   daily log sheet.
5. Day 1 to 7: the caregiver keeps the log; a maintainer calls once mid-week.
6. Exit interviews; collect the counts; delete local data if asked.
7. Write up in `docs/WORK_LOG.md`; open issues for every miss; change the PRD if a persona
   assumption broke.

## Tests

None in code. The setup-guide test (step 2) is the verification.

## Splitting across subagents

- Subagent A: step 1, the four documents, from this file, #202, `docs/PRD.md`,
  `docs/SAFETY_AND_PRIVACY.md`, `docs/PRIVACY.md` and `README.md` setup. Returns a PR.
Steps 2 to 7 are human work and cannot be delegated.

## Review

The founder reads the consent sheet before anyone signs it.
