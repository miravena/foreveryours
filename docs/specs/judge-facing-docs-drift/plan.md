# Plan: Judge-facing docs match the frozen submission (#204)

## Goal

Zero contradictions between the pasted Devpost text and what a judge finds in the repo, shipped
as `v1.0.1` (or the next patch) before 12-01.

## Affected files

- `docs/DEVPOST_SUBMISSION.md` (new)
- `README.md`, `docs/Project_Description.md`, `docs/FEEDBACK.md`,
  `docs/SAFETY_AND_PRIVACY.md`, `docs/PRIVACY.md`
- `video/` (remove or move to `docs/archive/video-poc/`), `README.md` "Demo video"
- `CHANGELOG.md`: a `[1.0.1]` section when tagged

## Steps

1. After the teammate pastes the text (10-29), copy it verbatim from the Devpost page into
   `docs/DEVPOST_SUBMISSION.md` with the date and the form fields as headings.
2. Build the claims table: read the text sentence by sentence; for each factual claim add a row
   with the claim, the README line (`README.md:N`), and the code or config line that proves it
   on the `v1.0.0` tag. Mark a row "mismatch" when the repo says something else.
3. For each mismatch, change the repo document, never the claim. Close #108, #135, #138, #173,
   #174 where the change covers them, citing the row.
4. `git rm -r video/` (or `git mv` to `docs/archive/video-poc/`), update the README "Demo video"
   section to the YouTube link, remove `video/README.md` references from other docs.
5. Run the full suite and `scripts/smoke.sh`. Open a PR; `scripts/openai_review.sh`.
6. Tag `v1.0.1` on `main` after merge, publish the Release, confirm the live judge check in the
   Release deploy, post on #196.

## Tests

`python -m unittest discover tests -v`, `scripts/smoke.sh`. No code change expected; if the
README code samples change, run the commands they show.

## Splitting across subagents

- Subagent A: step 2, the claims table, from `docs/DEVPOST_SUBMISSION.md` and the tagged tree.
  Returns the table only; it must not edit documents.
- Subagent B (after A): step 3, one PR with the five documents edited to match, citing rows.
- Subagent C (independent): step 4, the `video/` retirement, its own small PR.
Each needs this file, #204, and the tag name. None needs a key.

## Review

`scripts/openai_review.sh` on the PR; answer each finding. The teammate reads the claims table
once, since they pasted the text.
