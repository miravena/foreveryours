# Plan: Freeze carry-over triage (#203)

## Goal

Leave the issue tracker honest on freeze day: every red turn owned, every verdict label current.

## Affected files

`docs/ROADMAP.md` (stretch list) and `CHANGELOG.md` (Docs line) only. Everything else is GitHub
state: labels and comments.

## Steps

1. Wait for the `v1.0.0` Release deploy to post its scorecard on #37.
2. List open issues with `must-before-freeze` and with `should-if-time` (GitHub issue list,
   label filter).
3. For each failing turn in the scorecard: find the owning issue; if none, open one with the
   turn number, the reply text and the scorecard run link. Post the full table on #203.
4. For each open verdict issue: decide close / `judging-window` / `after-submission` using the
   #197 test ("keeps a claim already made"). Relabel. One line per issue on #203 with the
   reason. Do not change #48, #126, #130; list them with a proposal and tag the teammate once.
5. Edit `docs/ROADMAP.md` stretch list: remove items now tracked by #196 to #206 and link the
   post-submission section. Commit with a Docs changelog line.
6. Comment on #37 with the link to #203.

## Tests

`python -m unittest discover tests -v` for the docs change.

## Splitting across subagents

Steps 3 and 4 are independent and can run in parallel: one subagent builds the failing-turn
table from the scorecard, another builds the relabel table from the two label lists. Each
returns a markdown table for the human to post, or posts with the attribution trailers. The
relabel subagent must not relabel the three protected issues. Step 5 is a third, small PR.

## Review

Not code. The founder reads #203 before the Devpost form is submitted.
