# AGENTS.md — working in ForeverYours

Context for AI coding assistants (Claude Code, OpenCode, Kiro) and for a new human.
Process rules live in [`HOW_TO_WORK_HERE.md`](HOW_TO_WORK_HERE.md); style and
attribution in [`CONTRIBUTING.md`](CONTRIBUTING.md), which also has a table for which
model and effort to use for what kind of work. This file stays under a page —
it is read in full at the start of every session.

## Commands

```bash
sudo apt-get install -y espeak-ng                      # local TTS dependency (once)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                                   # .env is gitignored; never commit it

python -m unittest discover tests -v                   # tests — standard library only
# Windows only: prefix with PYTHONUTF8=1 (set PYTHONUTF8=1) — emoji test asserts need UTF-8
scripts/smoke.sh                                       # tests + beats 1/3/day2, ~10s, no key
scripts/openai_review.sh [base]                        # OpenAI review of commits not yet on origin/main (needs `codex login`)

.venv/bin/python main.py beat1 --audio samples/caregiver_memo.wav   # offline
.venv/bin/python main.py beat2 --audio samples/senior_jazz.wav      # needs NEBIUS_API_KEY
.venv/bin/python main.py beat3 --audio samples/senior_distress.wav  # safety fast-path
.venv/bin/python main.py beat4 --audio samples/senior_grandson.wav  # day-2 recall
.venv/bin/python webapp.py                             # browser demo → http://localhost:7860
```

## Verify before reporting anything done

Run the test suite and paste the output in your summary. If a test fails, fix the
code, never the test. Keep `main` demo-able: the three-beat demo in `README.md` must
work after every change.

When changing `safety/fastpath.py`, this file, or `.agents/skills/`, also run
`tests/test_mature_benchmarks.py` before merging — it guards the fastpath
false-positive bias (Benchmark 2) and the caregiver privacy firewall (Benchmark 4).
It is part of the normal suite, so a full `discover` run covers it.

For non-trivial work, also commit, run `scripts/openai_review.sh`, and address or
answer each finding before reporting done. Assistants only run the script: never
read, print or ask for any OpenAI key or `~/.codex` contents; if it says codex is
missing or logged out, stop and tell the founder.

## Conventions

- One logical change per commit, `Fixes #N: <what and why>`. Never force-push `main`.
  `git pull` before you start and before you push.
- **Plan before code** for non-trivial work: put the plan in the Issue's acceptance
  criteria (or commit a `plan.md` with the change) — a plan an assistant can read beats
  a plan in someone's head.
- **Attribution:** author = the human with a GitHub-linked email; AI help appears only
  as `Assisted-by: <harness>:<model id> effort=<level>` trailers, one per model, no email
  and no `Co-Authored-By` for AI. See CONTRIBUTING.md → "Commit attribution".
- **State never goes in a doc** — status, dates, blockers and "next" live only on
  GitHub Issues/milestones. Docs describe what, why and how.
- **Never read, print, quote or ask for `.env` contents or any key** — assistant configs (`.claude/settings.json`, `opencode.jsonc`) deny it. Verify a key with `scripts/key_status.sh` (prints an HTTP code only); if a key ever reaches a chat, Issue or commit, it is leaked: rotate it (#67).
  To make a **live** call (beat2, key-gated benchmarks, a probe), run it as
  `scripts/with_key.sh <command>`: it puts the key in that command's environment only, redacts
  it from the output and prints `LIVE Nebius key in use`. A reviewer who ran something live says
  so in the review header; one who did not says that instead. `load_dotenv()` also finds a
  parent `.env` by itself, so run non-live checks from a directory with no `.env` above it.
- Never commit `.env`, `data/`, `out/`, or anything secret. The repo is public.
  A pre-commit hook blocks staged secrets; a commit-msg hook warns when the author
  email isn't GitHub-linked (both in `.githooks/`), and CI re-checks on every push.

## Where to change what

| Change | File(s) |
|---|---|
| Behaviour | `pipeline/{hear,think,speak,audit,orchestrator}.py`, `memory/store.py`, `safety/fastpath.py`, `webapp.py` |
| Component map / design notes | `docs/IMPLEMENTATION_PLAN.md` |
| Naming, error handling, API shapes, UI, tests | `docs/STANDARDS.md` |
| Pipeline diagram & latency rationale | `README.md` → "Pipeline" (don't restate it elsewhere) |
| Why we chose X over Y | `docs/decisions/` (open an Issue first, then the ADR) |
| Plan and ordering, judges' requirements | `docs/ROADMAP.md` (no status, no dates) |
| Scope, personas, acceptance bar | `docs/PRD.md` |
| What changed for users/judges | `CHANGELOG.md` under `[Unreleased]` |
| Session journal, measurements, gotchas | `docs/WORK_LOG.md` |

## Things people get wrong

- `beat2` fails loudly with no API key — intentional ("fail loud, never fake").
  Everything else runs offline.
- `safety/fastpath.py` is deliberately biased to false positives. Do not "optimise"
  it toward fewer alerts without an Issue and an ADR.
- `.env.example` must match the real config — it drifted once for a full day.
- On Windows the test suite fails on emoji assertions under the default
  cp1252 console. Run with `PYTHONUTF8=1` (PowerShell: `$env:PYTHONUTF8=1`;
  cmd: `set PYTHONUTF8=1`) or `chcp 65001`. Linux and CI are UTF-8 already.
- **`git commit -m` silently drops the attribution.** The commit template carries the
  `Assisted-by` example; passing `-m` bypasses it, and no hook warns, so a
  run of six commits went out with a correct author and no trailer at all. Append
  the `Assisted-by` line yourself whenever you use `-m` — see CONTRIBUTING.md →
  "Commit attribution" and ADR-007.
- When an assistant makes the same mistake twice, put the correction here.
