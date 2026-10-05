# AGENTS.md — working in ForeverYours

Context for AI coding assistants (Claude Code, OpenCode, Kiro) and for a new human.
Process rules live in [`HOW_TO_WORK_HERE.md`](HOW_TO_WORK_HERE.md); style and
attribution in [`CONTRIBUTING.md`](CONTRIBUTING.md). This file stays under a page —
it is read in full at the start of every session.

## Commands

```bash
sudo apt-get install -y espeak-ng                      # local TTS dependency (once)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                                   # .env is gitignored; never commit it

python -m unittest discover tests -v                   # tests — standard library only
scripts/smoke.sh                                       # tests + beats 1/3/day2, ~10s, no key

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

## Conventions

- One logical change per commit, `Fixes #N: <what and why>`. Never force-push `main`.
  `git pull` before you start and before you push.
- **Plan before code** for non-trivial work: put the plan in the Issue's acceptance
  criteria (or commit a `plan.md` with the change) — a plan an assistant can read beats
  a plan in someone's head.
- **Attribution:** author = the human with a GitHub-linked email; AI help appears only
  as `Co-Authored-By` trailers, one per provider/model. See CONTRIBUTING.md →
  "Commit attribution".
- **State never goes in a doc** — status, dates, blockers and "next" live only on
  GitHub Issues/milestones. Docs describe what, why and how.
- Never commit `.env`, `data/`, `out/`, or anything secret. The repo is public.
  A pre-commit hook blocks staged secrets; a commit-msg hook warns when the author
  email isn't GitHub-linked (both in `.githooks/`), and CI re-checks on every push.

## Where to change what

| Change | File(s) |
|---|---|
| Behaviour | `pipeline/{hear,think,speak,audit,orchestrator}.py`, `memory/store.py`, `safety/fastpath.py`, `webapp.py` |
| Component map / design notes | `docs/IMPLEMENTATION_PLAN.md` |
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
- When an assistant makes the same mistake twice, put the correction here.
