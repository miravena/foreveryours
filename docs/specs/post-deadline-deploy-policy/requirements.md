# PRD: Post-deadline deploy policy (#197)

## Problem

After 2026-10-30 17:00Z the Devpost submission cannot change, but the Project can, and the
Space is what the judges open. A deploy during judging that changes visible behaviour can only
create a contradiction between the frozen text and the live page; it cannot add points.
`deploy-space.yml` enforces the mechanics (after `FREEZE_UTC`, only a Release or a manual run
deploys) but no document says what is allowed to ship.

## Users

Both maintainers, and any assistant asked to "fix the Space" between 10-30 and 12-15.

## Scope

One ADR amending ADR-003, one paragraph in `HOW_TO_WORK_HERE.md`, and the release-line
convention in `CHANGELOG.md`. No workflow change.

## Requirements

1. **Patch-only.** During judging only `v1.0.x` releases deploy.
2. **The test for a patch.** A change is patch-eligible only if it keeps a claim the frozen
   Devpost text, video or README already makes: a regressed judge turn, a crash, a privacy fix,
   a dependency pin, wording that matches the submission (#204). Anything that adds a visible
   feature or changes wording a judge could compare against the text waits for `v1.1.0`.
3. **Safety exception.** A fix for a missed emergency flag or a false "family notified" claim
   ships as a patch even if it changes a reply, because the frozen text promises that behaviour.
4. **Process.** Every judging-window deploy is a published Release from a tag on `main`, runs
   the live judge check, and is posted on #196 with the scorecard before and after.
5. **Rollback.** Re-run `deploy-space.yml` on the previous tag. Rehearsed under #196.
6. **Reviewed.** Both maintainers comment on #197 before the freeze.

## Acceptance criteria

The checkboxes on #197.

## Non-goals

No change to `deploy-space.yml`; `FREEZE_UTC` and the Release trigger already do the right thing.

## Risks

- Over-caution leaves a real regression on the Space for six weeks. The safety exception and
  the weekly check (#196) are the counterweight.
- A patch widens into a feature. The "keeps a claim already made" test is the gate; the
  reviewer of the patch PR quotes the claim it keeps.
