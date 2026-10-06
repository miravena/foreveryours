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
| How do we write it? | [`docs/STANDARDS.md`](docs/STANDARDS.md) |
| Why did we choose X? | [`docs/decisions/`](docs/decisions/README.md) (ADRs) |
| What did we try, what did we measure, what bit us? | [`docs/WORK_LOG.md`](docs/WORK_LOG.md) (dated journal) |
| What changed for users or judges? | [`CHANGELOG.md`](CHANGELOG.md) |

If you're about to write "status", "blocked", "due" or "next" in a doc, put it on the GitHub
Issue or milestone instead. Not in chat, not in a second tracking file.

## Pick up, work, land

1. **Pick up:** open the [milestones page](../../milestones) (sorted by due date), take an Issue
   in the earliest open milestone that isn't blocked, read its acceptance criteria and
   comments, comment `Starting work on this`, and assign yourself.
2. **Plan, then work:** for anything non-trivial, write the plan into the Issue's
   acceptance criteria (or commit a `plan.md` alongside the change) *before* coding —
   a plan another person or an assistant can read beats a plan in someone's head, and
   the PR review checks the diff against it. Then comment progress on the Issue
   (tried / result / next). Journal measurements and gotchas in `WORK_LOG.md` after the
   session.
3. **Land:** commit with `Fixes #N: <what and why>`, one logical change per commit. Work happens
   on a short-lived branch in its own worktree (see *Branches and worktrees* below); land it by
   merging into `main` and pushing. Per [`CONTRIBUTING.md`](CONTRIBUTING.md) a direct commit to
   `main` is still fine when there is nothing to review, and a PR is how you ask for the other
   person's eyes first. Never force-push. Keep `main` demo-able.
   `git pull` before you start and before you push.
4. **Prove and close:** comment with evidence (test output, commit sha, date) and close the Issue.

## Branches and worktrees

**The `main` worktree stays clean** — a clean `git status`, committed and pushed — so `git pull`
is never a negotiation. All work happens in its own worktree on its own short-lived branch, which
is what lets two people in different timezones, plus assistants running in parallel, work at once
without blocking each other.

- **One Issue, one branch, one worktree.** From the `main` worktree:
  `git worktree add ../<slug> -b <type>/<short-slug> main`, where `<type>` is `feat`, `fix`,
  `docs` or `chore`. Do the work in that directory, never in `main`'s.
- **Land it:** from `main`, `git merge --no-ff <type>/<short-slug>`, run the suite, `git push`,
  then tidy up — `git worktree remove ../<slug>` and `git branch -d <type>/<short-slug>`.
  A merged branch left lying around is how the next person rebases onto a stale name.
- **Short-lived means short-lived.** The branch exists for as long as its Issue does. If it has
  outlived the Issue, split it; if it needs a second Issue, it was two branches.
- **Each worktree needs its own `.venv`** — they don't share one, and the pre-push hook runs
  `<worktree>/.venv/bin/python`, so a missing venv there makes the hook fall back to the system
  Python and fail loudly. Build it once per worktree:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- A direct commit to `main` is still allowed for a one-line change you're already looking at
  ([`CONTRIBUTING.md`](CONTRIBUTING.md)); the part that isn't negotiable is committing to a clean
  tree, not which branch it lands on.

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
