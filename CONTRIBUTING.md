# Contributing

Two of us are building this for the Nebius x NVIDIA Global AI Hackathon
(deadline: 2026-10-30, 10:00am PDT / 17:00 UTC). This repo is public from day
one, so treat it like a normal open-source project, not a scratch space.

## Workflow

- **Branch per feature/fix.** No direct commits to `main` for anything beyond
  a one-line typo fix.
  ```bash
  git checkout -b <name>/<short-description>
  ```
- **Open a PR, get the other person's eyes on it before merging.** With two
  people, that can be quick — a skim is enough for most changes — but don't
  self-merge silently on anything touching the pipeline (`pipeline/`,
  `safety/`, `memory/`).
- **Keep `main` demo-able at all times.** Judges and teammates should be able
  to `git pull` and run the three-beat demo (`README.md`) at any point before
  the deadline. If a branch leaves things broken, don't merge it until it's
  fixed.
- **Commit messages:** say what changed and why, not just what file moved.

## What never gets committed

- `.env` (real API keys) — only `.env.example` with variable names.
- `data/` (generated memory/flag state) and `out/` (generated audio) — both
  gitignored, regenerate locally.
- Anything identifying either of our non-GitHub accounts, internal tooling,
  or infrastructure unrelated to this project. This repo is judged on its own
  merits; keep it self-contained.

## Documentation guidelines

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
- **`docs/ROADMAP.md`** is the single place for "what are we working on, in
  what order, and why" — including the hackathon's actual judging
  requirements mapped against our status. Update its status column in the
  same PR that changes it; don't let it and the GitHub Issues disagree.
- **`docs/IMPLEMENTATION_PLAN.md`** is the single place for build status per
  component, open design decisions, and the known-issues backlog. We code
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

## Secrets

Nebius Token Factory key setup is in `README.md` → Setup. If you get your own
key, it's config, not a merge conflict — `.env` is gitignored per-machine.

## Submission logistics

Devpost requires one designated team "Representative" to hit submit. Decide
who that is before the deadline and note it here once settled:

- **Representative:** _TBD_
