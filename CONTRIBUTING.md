# Contributing

Two of us are building this for the Nebius x NVIDIA Global AI Hackathon
(deadline: 2026-10-30, 10:00am PDT / 17:00 UTC). This repo is public from day
one, so treat it like a normal open-source project, not a scratch space.

## Workflow

The repo is still young and moving fast under a hard deadline, so **PRs are
an invitation for feedback, not a merge gate.** Changes land on `main`
directly and iterate from there — reverting is cheap (`git revert`), so
don't let an open PR sit unreviewed and block progress.

- **Direct commits to `main` are fine**, including for pipeline/safety/memory
  changes. Use a branch + PR when you want the other person's eyes on
  something *before* it's final, or when you want to leave something open
  for discussion — not because it's required.
- **Comment, don't gate.** If you spot something after it's merged, open an
  issue or comment on the commit — we'll fix it in the next pass, not revert
  by default. Revert only if `main` is actually broken.
- **Keep `main` demo-able.** Judges and teammates should be able to
  `git pull` and run the three-beat demo (`README.md`) at any point before
  the deadline. If a change breaks that, fix it forward quickly or revert —
  don't leave it broken.
- **Commit messages:** say what changed and why, not just what file moved.

## What never gets committed

- `.env` (real API keys) — only `.env.example` with variable names.
- `data/` (generated memory/flag state) and `out/` (generated audio) — both
  gitignored, regenerate locally.
- Anything identifying either of our non-GitHub accounts, internal tooling,
  or infrastructure unrelated to this project. This repo is judged on its own
  merits; keep it self-contained.

## One source of truth

This is one small repo with two workers, so work state lives in exactly one place:
**GitHub**. [Milestones](../../milestones) = order and due dates; Issues = scope, owner and
acceptance criteria; *blocked by* relationships = dependencies. Docs describe what, why and
how, never state. Don't copy status into a doc, and don't track work in chat or in a second
file; both drift. Details: `HOW_TO_WORK_HERE.md`.

## Documentation guidelines

- **`CHANGELOG.md`** — add a line under `[Unreleased]` in the same PR as the change. Releases are tagged `vX.Y.Z` on `main` with GitHub Release notes.
- **`docs/WORK_LOG.md`** and **`docs/decisions/`** — dated session log and decision records (ADRs). See `HOW_TO_WORK_HERE.md` for which record gets what.
- **README.md** is the pitch + setup — keep it current with whatever actually
  runs. If a setup step changes, update it in the same PR, not a follow-up.
- **`docs/DEMO_SCRIPT.md`** is the contract for what "working" means. If your
  change breaks a beat in it, fix the beat or update the script in the same
  PR — don't let them drift apart.
- **`docs/SAFETY_AND_PRIVACY.md`** documents the safety design stance (no
  silent surveillance, no medical claims, what's stored). Update it when a
  safety-relevant decision changes (new flag type, new audit behavior,
  anything touching `safety/` or `pipeline/audit.py`) — don't let the code
  and the stated design diverge.
- **`docs/PRINCIPLES.md`** is the half-page of non-negotiables that every
  other doc defers to instead of restating. Change it only when we're
  actually changing what we stand for, not for a one-off feature call.
- **`docs/PRD.md`** is the product requirements doc — personas, explicit
  non-goals, and the demo script as the acceptance bar. Update it when the
  pitch or scope actually changes, not for implementation detail.
- **`docs/ROADMAP.md`** is the plan and the reasoning: milestones, why this
  order, and the hackathon's judging requirements. It holds **no status or
  dates**; those live only on GitHub (see "One source of truth" above).
- **`docs/IMPLEMENTATION_PLAN.md`** is the component map and design notes
  (not a task list). We code
  from `PRINCIPLES.md` + `PRD.md` + `ROADMAP.md` + this plan, not from memory
  of a conversation — if a design decision changes, update the doc in the
  same PR.
- **Still no separate architecture doc beyond that.** The pipeline diagram
  and latency rationale live in README's "Pipeline" section and in each
  module's module-level docstring (`pipeline/*.py`) — `IMPLEMENTATION_PLAN.md`
  links to README rather than repeating the diagram. One source of truth
  beats two docs that can disagree.
- **Comments in code:** only for the *why* (a non-obvious constraint, a
  workaround, a latency tradeoff) — see the existing modules for the style.
  Not for the *what*; names should already say that.
- **This repo is self-contained.** No references to non-GitHub tooling,
  internal ticket IDs, or infrastructure outside this project — if a doc
  needs that context to make sense, it belongs in our private notes, not here.

## AI coding tools / credits

We're using different AI coding assistants day to day — that's fine, it doesn't affect the
code itself, just flagging it so neither of us is surprised by the other's commit style or
pace. Neither of us can run models locally (no GPU hardware for it), so both rely on hosted
inference. Options if you need another one (e.g., your current tool's credits run low):

- **Nebius Token Factory** — same `NEBIUS_API_KEY` we're already using for the product itself
  (OpenAI-compatible, so most coding-assistant tools can point straight at it). First choice:
  no new signup, and it's the sponsor stack we're building on anyway.
- **Google AI Studio's free Gemini tier** — generous free quota, no student program required.
- **Groq's free API tier** — fast hosted inference on open-weight models.
- Check whether you already have the **GitHub Student Developer Pack** — it bundles credits
  across several providers, worth five minutes to check what's in it.
- For occasional heavier experiments (not a coding-assistant backend, but useful if you need
  to test something like `faster-whisper` without your own GPU): **Google Colab**'s free GPU
  tier, or **Kaggle Notebooks**' free ~30h/week GPU quota.

## Working with AI-assisted code

Some of this codebase is written with AI assistance. That's fine, but it changes what
"reviewing a PR" means and it's worth being explicit about, especially if this is new to you:

- **Read the comments that explain WHY, not just WHAT.** Good comments in this repo
  (`orchestrator.py`'s disclosure invariant, `fastpath.py`'s false-positive-is-cheaper
  tradeoff, `webapp.py`'s polling-vs-push note) exist because the reasoning isn't obvious
  from the code alone and would otherwise need to be re-derived or re-asked every time.
  If you can't tell *why* something was built a certain way, that's a real gap worth
  asking about — it usually means a decision was made that should've been written down
  better, not that you're missing something you should already know.
- **Match effort to what the demo/deadline actually needs, not to generic "best
  practice."** There's no fixed "right" amount of testing, error handling, or
  abstraction — the right amount depends on what could actually go wrong and what the
  cost of being wrong is. A regex safety check that might over-trigger is worth real
  care (issue #15); a polling interval for a UI panel almost never is. If you're ever
  unsure whether something needs more rigor, ask "what breaks, for whom, if this is
  wrong?" — that question is more useful than a checklist.
- **Safety-critical code gets more scrutiny than everything else.** `safety/fastpath.py`,
  the disclosure logic in `orchestrator.py`, and anything touching what gets stored about
  someone (`memory/store.py`, `caregiver.py`) should get read carefully, line by line,
  even under deadline pressure — these are the parts where a bug has a real person on
  the other end, not just a worse demo. Everything else can move faster.
- **It's fine, and expected, to push back or ask "why not do X instead?"** on anything
  in a PR, AI-written or not. Treating a diff as settled because it compiles and runs is
  how `.env.example` drifted from the actual code for a full day (see the PR that fixed
  it) — a question would've caught it faster than a careful read would have.
- **The docs are part of the deliverable, not an afterthought.** `docs/PRINCIPLES.md`,
  `docs/SAFETY_AND_PRIVACY.md`, and this file exist so a decision only has to be explained
  once. If you make a call that isn't obvious from the code, write it down somewhere
  (an issue, `docs/ROADMAP.md`, a comment) instead of leaving it in chat — chat doesn't
  outlive the hackathon, the repo does.

## Secrets

Nebius Token Factory key setup is in `README.md` → Setup. If you get your own
key, it's config, not a merge conflict — `.env` is gitignored per-machine.

## Submission logistics

Devpost requires one designated team "Representative" to hit submit. Decide
who that is before the deadline and note it here once settled:

- **Representative:** _TBD_
