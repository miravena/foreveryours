# Plan: Post-deadline deploy policy (#197)

## Goal

Write down, before the freeze, what may deploy to the Space during judging, so nobody has to
decide it under pressure on a weekend in November.

## Affected files

- `docs/decisions/ADR-011-judging-window-deploys.md` (new; take the next free number if 011 is
  used by then; follow `ADR-000-template.md`)
- `docs/decisions/README.md` (index row)
- `HOW_TO_WORK_HERE.md` "Releases": a "During judging" paragraph
- `docs/ROADMAP.md`: already names the judging window; link the ADR
- `CHANGELOG.md`: a Docs line under `[Unreleased]`

## Steps

1. Read ADR-003 (hosting, keep-awake, concurrency) and `HOW_TO_WORK_HERE.md` "Releases" and
   "After every Space deploy".
2. Draft the ADR with the template's sections: Question, Context, Decision, Rationale,
   Consequences, When to revisit. The Decision section holds requirements 1 to 5 of the PRD as
   numbered rules; the Rationale quotes rules section 5 of `docs/HACKATHON_RULES.md`.
3. Add the "During judging" paragraph to `HOW_TO_WORK_HERE.md` pointing at the ADR, and the
   `v1.0.x` / `v1.1.0` line convention to the Releases section.
4. Open a PR; both maintainers comment on #197 (agree or edit). Merge before the freeze.

## Tests

`python -m unittest discover tests -v` (the no-internal-refs test covers docs) and
`scripts/smoke.sh`. No behaviour change.

## Splitting across subagents

One subagent, one PR. It needs this file, #197, ADR-003, ADR-000-template, and
`HOW_TO_WORK_HERE.md`. It returns the PR link. It must not touch `.github/workflows/`.

## Review

Docs only; run `scripts/openai_review.sh` anyway because the ADR is a rule other people follow,
and answer each finding on the PR.
