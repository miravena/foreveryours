# How to work in ForeverYours

One small repo, two workers, **one source of truth**.

## The rule

**GitHub is the only place that records work state:** what's open or closed, who owns it, the
order and due dates ([milestones](../../milestones)), and what blocks what (**Relationships ->
blocked by** on the Issue). The repo's docs describe *what, why and how*, never *state*.

| Question | Answer lives in |
|----------|-----------------|
| What's next, what's blocked, what's due, who has it? | GitHub: [milestones](../../milestones) and [Issues](../../issues) |
| Scope and acceptance criteria for a task | The Issue |
| Why this order, what do the judges require? | [`docs/ROADMAP.md`](docs/ROADMAP.md) (plan, no status or dates) |
| How is it built? | [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md), `README.md` |
| Why did we choose X? | [`docs/decisions/`](docs/decisions/README.md) (ADRs) |
| What did we try, what did we measure, what bit us? | [`docs/WORK_LOG.md`](docs/WORK_LOG.md) (dated journal) |
| What changed for users or judges? | [`CHANGELOG.md`](CHANGELOG.md) |

If you're about to write "status", "blocked", "due" or "next" in a doc, put it on the GitHub
Issue or milestone instead. Not in chat, not in a second tracking file.

## Pick up, work, land

1. **Pick up:** open the [milestones page](../../milestones) (sorted by due date), take an Issue
   in the earliest open milestone that isn't blocked, read its acceptance criteria and
   comments, comment `Starting work on this`, and assign yourself.
2. **Work:** comment progress on the Issue (tried / result / next). Journal measurements and
   gotchas in `WORK_LOG.md` after the session.
3. **Land:** commit with `Fixes #N: <what and why>`, one logical change per commit. Per
   [`CONTRIBUTING.md`](CONTRIBUTING.md), direct commits to `main` are fine; use a branch + PR
   when you want the other person's eyes first. Never force-push. Keep `main` demo-able.
   `git pull` before you start and before you push.
4. **Prove and close:** comment with evidence (test output, commit sha, date) and close the Issue.

## Issues and milestones

- Title starts with the milestone: `[M5] Fix ...`, and **every Issue has the matching
  milestone**. Use the *Work item* template.
- Acceptance criteria must be testable. Link related Issues and the relevant ADR.
- If it can't start until something else lands, set **blocked by** on the Issue (not only a
  comment) and say why in a comment.
- Adding or reordering a milestone: change it on GitHub first, then update the table in
  `docs/ROADMAP.md` in the same commit.
- Labels: `bug`, `enhancement`, `documentation`, `question` (needs a team decision), `help wanted`.
- Found a bug while on something else? Open a new Issue. Want to change the architecture? Open
  an Issue first, then write the ADR.

## Releases

When `[Unreleased]` in the changelog has something worth tagging: rename it to the version and
date, commit, tag `vX.Y.Z` on `main`, publish a GitHub Release (notes auto-generate from labels
via `.github/release.yml`).

## Done means

- [ ] acceptance criteria checked, with evidence pasted on the Issue
- [ ] commit references `Fixes #N`
- [ ] **no work state written outside GitHub** (no status/date/blocker copied into a doc)
- [ ] `WORK_LOG.md` entry added; ADR added if a decision was made
- [ ] `CHANGELOG.md` updated if user-visible

## Gotchas

- Both of us push to `main`: `git pull` before you start and before you push.
- Don't both edit the same file without saying so on the Issue.
- Never commit `.env`, keys, `data/` or `out/` (see `CONTRIBUTING.md`).
- Don't close an Issue without proof.
