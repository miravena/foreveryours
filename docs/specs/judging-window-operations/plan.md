# Plan: Judging-window operations (#196)

## Goal

Keep the frozen `v1.0.0` Space reachable, funded and passing its own judge check from the
freeze to 2026-12-15, with a written record on #196.

## Affected files

None in the product. Writes go to #196 (comments), ADR-003 (the daily-cap decision), and
`docs/WORK_LOG.md` (measurements only, no status).

## Steps

1. **Freeze day (10-29).** Post the ownership comment on #196. Check the HF token expiry in the
   Hugging Face settings page; rotate if it ends before 12-16. Confirm the keep-awake job is
   scheduled (ADR-003 names the host and the times). Record the `MAX_DAILY_REQUESTS` decision in
   ADR-003 under the existing "Concurrency" section as a new dated subsection.
2. **Weekly, Mondays, from 11-03 to 12-15.** Run:
   ```bash
   scripts/with_key.sh .venv/bin/python scripts/live_judge_check.py
   ```
   Post the scorecard as a comment. If a turn that passed on the Release deploy now fails,
   open an issue and decide under #197 whether it is patch-eligible.
   Check the Nebius console balance; post the date and a rounded figure.
3. **Rollback rehearsal, once, before 12-01.** On GitHub Actions, run `deploy-space.yml` with
   `action=deploy` on the previous tag, run `scripts/verify_space_sha.py`, confirm the page's
   `Build:` line, then deploy the current tag the same way and verify again. Post both runs.
4. **11-30.** Cold-open check from a clean browser; post the wake time observed.
5. **12-16.** Closing comment and close #196.

## Tests

None. Verification is the posted scorecards and the two rollback runs.

## Splitting across subagents

Each step is independent and can be a separate run; none needs the conversation that wrote
this plan. A subagent needs: this file, #196, ADR-003, `HOW_TO_WORK_HERE.md` "Releases", and a
key through `scripts/with_key.sh`. It must never print the key, and must return the scorecard
text and the console figure for the human to post, or post them itself with the three
attribution trailers. A subagent cannot do step 1's token rotation or the console check; those
need the founder's accounts.

## Review

Not a code change; `scripts/openai_review.sh` is not required. The founder reviews the closing
comment.
