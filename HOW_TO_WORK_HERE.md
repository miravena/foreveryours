# How to work in ForeverYours

Anyone picking up work (any AI assistant, or by hand) follows the same loop. **The repo is the
source of truth; GitHub Issues are how we talk.** Read [`TEAM_STATUS.md`](TEAM_STATUS.md)
first, then [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Pick up, work, land

1. **Pick up:** check `TEAM_STATUS.md` and the roadmap, open the Issue, read its acceptance
   criteria and comments (what was already tried), then comment `Starting work on this` and put
   your handle in the Owner column.
2. **Work:** comment progress on the Issue (tried / result / next). Don't report findings only
   in chat; the Issue is the record.
3. **Land:** commit with `Fixes #N: <what and why>` and one logical change per commit. Per
   [`CONTRIBUTING.md`](CONTRIBUTING.md), direct commits to `main` are fine; use a branch + PR
   when you want the other person's eyes first. Never force-push. Keep `main` demo-able.
4. **Prove and close:** comment with evidence (test output, commit sha, date) and close the Issue.

## Which log gets what

| Record | Where | When |
|--------|-------|------|
| Scope, acceptance criteria, per-issue progress | GitHub Issue (+ comments) | during work |
| What you tried, measurements, gotchas, session notes | [`docs/WORK_LOG.md`](docs/WORK_LOG.md) | after every session |
| A choice with alternatives and consequences | New ADR in [`docs/decisions/`](docs/decisions/README.md) (copy `ADR-000-template.md`), plus a one-liner in the WORK_LOG decisions table | when decided |
| What users/judges would notice changed | [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]` | in the same PR |
| Current status and ownership | [`TEAM_STATUS.md`](TEAM_STATUS.md) | weekly, or when a blocker changes |

## Releases

When `[Unreleased]` has something worth tagging: rename it to the version and date, commit,
tag `vX.Y.Z` on `main`, and publish a GitHub Release (notes auto-generate from labels via
`.github/release.yml`).

## Issues

- Title starts with the milestone: `[M5] Fix ...`. Use the *Work item* issue template.
- Acceptance criteria must be testable. Link related Issues and the relevant ADR.
- Labels: `bug`, `enhancement`, `documentation`, `question` (needs a team decision), `help wanted`.
- Found a bug while on something else? Open a new Issue. Want to change the architecture? Open
  an Issue first, then write the ADR.

## Done means

- [ ] acceptance criteria checked
- [ ] tested, with evidence pasted on the Issue
- [ ] commit references `Fixes #N`
- [ ] `WORK_LOG.md` entry added; ADR added if a decision was made
- [ ] `CHANGELOG.md` updated if user-visible

## Gotchas

- Both of us push to `main`: `git pull` before you start and before you push.
- Don't both edit the same file without saying so on the Issue.
- Never commit `.env`, keys, `data/` or `out/` (see `CONTRIBUTING.md`).
- Don't close an Issue without proof.
