# PRD: Freeze carry-over triage (#203)

## Problem

`HOW_TO_WORK_HERE.md` says a deploy is done when every live judge turn passes or every failing
turn is on an issue. The final scorecard on the frozen `v1.0.0` Space will leave some turns
red, and the `must-before-freeze` and `should-if-time` labels stop meaning anything once the
freeze has passed. Without a triage pass, open issues keep a verdict that no longer applies.

## Users

Both maintainers; any assistant reading the labels to pick work in November.

## Scope

One routing pass on freeze day, after the final scorecard is posted on #37. Nothing is fixed
under #203; it only routes.

## Requirements

1. Every failing turn in the final scorecard is listed on #203 by number with the reply text
   and the issue that owns it (#189, #190, #191, #192 or a new one).
2. Every still-open `must-before-freeze` issue is closed with its fixing commit, or relabelled
   `judging-window` (patch-eligible under #197) or `after-submission`, with one line why.
3. Every still-open `should-if-time` issue is relabelled the same way. The teammate's protected
   issues (#48, #126, #130) are proposed on #203, not changed.
4. Afterwards both labels have zero open issues.
5. `docs/ROADMAP.md` stretch list is checked; anything now owned by an issue is removed from
   the list in the same commit.
6. A comment on #37 links #203 as part of the freeze record.

## Acceptance criteria

The checkboxes on #203.

## Non-goals

No code.

## Risks

- A red turn that is really a flake is relabelled as a bug. Mitigation: the scorecard run is
  repeated once before triage if a turn's failure text differs between runs.
