# PRD: Self-judging retro (#205)

## Problem

`docs/SELF_JUDGING.md` has one unscored row from 2026-10-01 and nothing since. The real
judging happens once, 12-01 to 12-15; without a prediction there is nothing to learn from the
result.

## Users

Both maintainers; the next entry.

## Scope

Two scoring passes (frozen submission on 10-29, real result when published), a comparison, a
retro section, a winner study.

## Requirements

1. **Prediction.** On 10-29, before submitting, both maintainers score the frozen `v1.0.0`
   Space, the final video and the pasted text on the four criteria, independently, and append
   rows with the biggest single gap and the next action; the founder adds the "founder call"
   row.
2. **Disagreement.** Every gap of 2 or more points between the two gets one explaining line
   on #205.
3. **Result.** When Devpost publishes, the placement and any judge feedback are appended next
   to the prediction.
4. **Retro.** A dated section at the bottom of `docs/SELF_JUDGING.md`: three things to keep,
   three to change, each traced to a criterion. No status.
5. **Winner study.** One paragraph per Personal AI track winner (public entries only) on what
   they showed that we did not, in `docs/WORK_LOG.md`.
6. **Outputs become issues** or ROADMAP stretch items, not prose.

## Acceptance criteria

The checkboxes on #205.

## Non-goals

No rubric change before the result arrives.

## Risks

- Scores drift toward the average once the two compare. Rule: write before reading the
  other's row; post both at once.
