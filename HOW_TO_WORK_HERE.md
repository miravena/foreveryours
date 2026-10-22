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

## Deploying the Space

The judge-facing demo is the Hugging Face Space `elevenbaselab/foreveryours` (#11). Nobody
deploys it by hand: `.github/workflows/deploy-space.yml` does, so a collaborator deploys by
**merging to `main`** or by **Actions -> deploy-space -> Run workflow**.

- **Before the freeze** (the `FREEZE_UTC` date in the workflow): every push to `main` runs the
  tests, deploys that commit, waits for the Space to come up, checks the deployed sha, smokes the
  Gradio API and runs the live judge check suite (`scripts/live_judge_check.py`) with a small
  call cap.
- **After the freeze:** a push to `main` only runs the tests. Deploy by publishing a GitHub
  Release (see *Releases*) or by *Run workflow* with `action=deploy`. Rollback = publish or re-run
  the workflow on the previous tag. Nothing deploys automatically.
- **`Run workflow` with `action=check`** only proves the token works and the Space is reachable;
  it uploads nothing.
- **Token:** the repo secret `HF_TOKEN_FY_SPACE` (a fine-grained Hugging Face token with write
  access to this one Space), exported to the scripts as `HF_TOKEN`. Without it the workflow skips
  the deploy with a notice. The workflow never runs on `pull_request`, so a fork never sees it.
- **Which commit is live:** every deploy stages a one-line `BUILD_INFO` (full git sha) and sets
  the Space variable `BUILD_SHA`; the app shows `Build: <sha7>` under *About this demo
  household*. `python scripts/verify_space_sha.py elevenbaselab/foreveryours` exits 0 only when
  the Space runs your local `HEAD` (`--sha <sha>` to compare against another commit,
  `--wait 900` to first wait for a build, `--smoke` to also call `view_api()`).
- **By hand, if Actions is unavailable:** from a clean, pushed `main`,
  `HF_TOKEN=... NEBIUS_API_KEY= python scripts/deploy_hf_space.py elevenbaselab/foreveryours --hardware zero-a10g`
  then `python scripts/verify_space_sha.py elevenbaselab/foreveryours --wait 900 --smoke`.
  The deploy script refuses a dirty tree, so the recorded sha is always a real commit.

## After every Space deploy: the live judge check

The unit tests stub the LLM, so they cannot see what the hosted model actually says (the
2026-10-22 judge simulation found the live companion telling Dad "Sarah is listening", and no
test could catch it). **After every deploy of the HF Space, run the live judge check** from a
worktree with its own `.venv`:

```bash
.venv/bin/python scripts/live_judge_check.py                 # --space elevenbaselab/foreveryours --max-calls 25
```

It plays a judge against the running Space through `gradio_client`: about twenty scripted turns
in fresh sessions per scenario (pre-brief recall, "Is Sarah listening?", a typed "Dr. Tan" memo,
driving, a fall, a crisis phrase, a private disclosure), with keyword assertions on the reply and
on the caregiver panel, then prints a scorecard. The privacy group ends with a linger line
that waits the full settle window again and re-reads the panel, because AUDIT and memory
extraction run in the background and can land after the panel looked settled. Exit 0 means every turn passed, 1 means a turn
failed or errored, 2 means the call cap stopped the run.

- **A deploy is not done until the check exits 0, or every failing turn is on a GitHub Issue.**
  Paste the scorecard and the live-call count on the deploy's Issue as evidence, not into a doc.
- **The cap (`--max-calls`, default 25) counts submitted reply turns**, one per invocation of the
  streaming reply endpoint, not raw Nebius requests. The app issues extra background requests per
  turn (THINK, AUDIT, memory extraction), so real Nebius requests are about 2-3x the number the
  scorecard reports. A full run is 19 turns; the run aborts before the turn that would exceed the
  cap, marks the rest SKIPPED and exits 2. The cap exists because the Nebius credit must last
  through judging on 2026-12-15 ([ADR-003](docs/decisions/ADR-003-hosting.md)): run it once per
  deploy, not on every push.
- It complements, never replaces, the stubbed unit tests (`python -m unittest discover tests`):
  those run offline on every change; this one runs after a deploy and costs credit.
- Offline: `--fake good` and `--fake bad` run the same turns against an in-process stub (zero
  network), which is what `tests/test_live_judge_check.py` uses and how a change to the script
  itself is verified.

## Done means

- [ ] acceptance criteria checked, with evidence pasted on the Issue
- [ ] commit references `Fixes #N`
- [ ] **no work state written outside GitHub** (no status/date/blocker copied into a doc)
- [ ] `WORK_LOG.md` entry added; ADR added if a decision was made
- [ ] `CHANGELOG.md` updated if user-visible
- [ ] after a Space deploy: `scripts/live_judge_check.py` exit 0, or each failing turn on an Issue

## Gotchas

- Both of us push to `main`: `git pull` before you start and before you push.
- Don't both edit the same file without saying so on the Issue.
- Never commit `.env`, keys, `data/` or `out/` (see `CONTRIBUTING.md`).
- Don't close an Issue without proof.
