# PRD: Judging-window operations (#196)

## Problem

The hackathon rules require the Project to stay available, free and unrestricted to the
judges until the Judging Period ends on 2026-12-15, and judges open the live Space between
12-01 and 12-15, about five weeks after the last commit. #11 covers standing the Space up and
closes at submission. Nothing owns keeping it reachable, funded and correct for six weeks.
ADR-003 records the keep-awake and the credit dependency, but no issue checks that they hold.

## Users

- The judges: open the Space cold, from a clean browser, possibly all on the same day.
- The maintainers: need to know, every week, that nothing has gone dark, and to be able to
  roll back in minutes if a patch goes wrong.

## Scope

A weekly, dated checklist run from the freeze (2026-10-29) to 2026-12-15, with every result
posted as a comment on #196. No product change.

## Requirements

1. **Ownership.** One named owner and one backup on #196, both reachable 12-01 to 12-15.
2. **Keep-awake.** The oracle job in ADR-003 runs twice a day until 12-16. Confirm at the
   freeze and on 11-30 that it is running and that a cold open of the Space answers inside the
   Hugging Face wake-up time.
3. **Credit runway.** The Nebius balance is checked weekly in the console. Post the date and a
   rounded figure, never the key. Set a floor; below it, use the backup key or top up.
4. **Hugging Face token.** `HF_TOKEN_FY_SPACE` must be valid past 12-15. Check its expiry at
   the freeze; rotate before the freeze if needed.
5. **Weekly live check.** Run `scripts/live_judge_check.py` against the frozen Release once a
   week through `scripts/with_key.sh`; post the scorecard. A newly failing turn is triaged under
   the deploy policy (#197), never silently redeployed.
6. **Daily cap.** Review `MAX_DAILY_REQUESTS` on the Space against expected judge traffic and
   record the decision in ADR-003 (the #11 hosting record).
7. **Rollback rehearsal.** Before 12-01, re-run `deploy-space.yml` on the previous tag and
   confirm the `Build: <sha7>` line on the page changes back, then deploy the current tag again.
8. **Closing.** On 12-16, a closing comment: what happened, what was patched, what failed.

## Acceptance criteria

The checkboxes on #196 are the acceptance criteria. All must be ticked with a dated comment.

## Non-goals

No features, no prompt changes, no fast-path changes. Code goes to a new issue under #197.

## Risks

- The Space sleeps despite the keep-awake (Hugging Face changes its idle rule). Mitigation:
  the 11-30 cold-open check, and a manual deploy as the fallback wake.
- Credit runs out mid-judging. Mitigation: the floor, the backup key (#75), the weekly check.
- The weekly live check itself spends credit. It is capped by `LIVE_CHECK_MAX_CALLS` (25).
