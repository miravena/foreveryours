# PRD: One-week trial with a real caregiver and older adult (#202)

## Problem

Nothing in the repo has been used by its intended users. Every number is a benchmark or a
scripted judge. The Devpost text ends "What's next" with a week of real use as the only
measurement that matters.

## Users

One caregiver and one older adult who agree to a week of use on a machine in their home.

## Scope

Plan, consent, setup guide, measurement sheet, exit interview, write-up. One household, local
install, never the public Space.

## Requirements

1. **Consent sheet** (`docs/trial/CONSENT.md`): what is recorded, where it lives, who reads it,
   how to withdraw, not a medical device, not an emergency service, deletion at the end on
   request.
2. **Data plan.** The household runs on its own machine with its own Nebius key; transcripts
   stay there; only the daily counts leave, by hand, with the family's agreement.
3. **Measurements fixed before day 1.** Turns per day; fast-path flags split into true,
   false and missed as reported by the family; memory corrections used; one open question a
   day to each participant; a two-line daily log kept by the caregiver.
4. **Setup guide** (`docs/trial/SETUP.md`) a non-engineer can follow, tested by someone who
   did not write it, including the `.env` step without ever showing a key in the doc.
5. **Exit interview** questions for both participants written in advance.
6. **Write-up** in `docs/WORK_LOG.md` as measurements; a PRD or ADR change if a decision
   changes; no participant data in the repo.
7. **Safety misses** observed become their own issue the same day.

## Acceptance criteria

The checkboxes on #202.

## Non-goals

Not a study for publication; not more than one household; not on the hosted Space.

## Risks

- A real emergency during the trial. The consent sheet says the companion is not an emergency
  service and names what to do instead; the caregiver keeps their normal arrangements.
- The family cannot run Python. Mitigation: the setup guide is tested by a non-engineer first;
  if it fails that test, the trial waits.
