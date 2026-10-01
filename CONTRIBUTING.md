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
- **No separate architecture doc.** The pipeline is documented inline in
  README's "Pipeline" section and in each module's module-level docstring
  (`pipeline/*.py`). Keep it that way unless the project outgrows it — one
  source of truth beats two docs that can disagree.
- **Comments in code:** only for the *why* (a non-obvious constraint, a
  workaround, a latency tradeoff) — see the existing modules for the style.
  Not for the *what*; names should already say that.
- **This repo is self-contained.** No references to non-GitHub tooling,
  internal ticket IDs, or infrastructure outside this project — if a doc
  needs that context to make sense, it belongs in our private notes, not here.

## Secrets

Nebius Token Factory key setup is in `README.md` → Setup. If you get your own
key, it's config, not a merge conflict — `.env` is gitignored per-machine.

## Submission logistics

Devpost requires one designated team "Representative" to hit submit. Decide
who that is before the deadline and note it here once settled:

- **Representative:** _TBD_
