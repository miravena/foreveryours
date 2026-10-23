# Plan: the hosted page says which model does what, and which layer raised each flag (#214)

## Goal

A judge on the live Space sees, without opening anything, which model writes the reply and runs
the safety backstop, and on every caregiver flag whether the rules or the model raised it. Both
are true today and both are what the Technological Implementation criterion scores; today the
only line naming Nemotron is inside a `DEV_MODE`-only accordion (`webapp.py`, "Model & Pipeline
Info").

## Affected files

- `caregiver.py`: `CaregiverFlag` gains `source: str | None = None` (`"fastpath"`, `"audit"`,
  `"perseveration"`); `CaregiverFlags.add` accepts and persists it; old JSON without the key
  loads as `None` (no migration, no crash).
- `pipeline/orchestrator.py`: the flag sites pass `source`: the fast-path site (~:653), the
  perseveration site (~:733), the three AUDIT sites (~:1021-1032).
- `webapp.py`: flag line (~:1150) appends "raised by: safety rules, before the model" /
  "raised by: Nemotron backstop, after the reply" / "raised by: repeated-question check" and
  nothing when `source` is `None`; a `gr.Markdown` footer at the end of the `gr.Blocks`, always
  visible (not under `DEV_MODE`), text only:
  "Reply and safety backstop: NVIDIA Nemotron 3 Nano 30B on Nebius Token Factory · Hearing:
  faster-whisper, on this app's server · Voice: Piper, on this app's server". The model id
  comes from the same constant `pipeline/think.py` uses, so the footer cannot drift from the
  call.
- `tests/test_caregiver.py`: round-trip of `source`, and loading a record without it.
- `tests/test_webapp.py`: the footer text is in the rendered page; a fast-path flag renders
  "raised by: safety rules"; an AUDIT flag renders "raised by: Nemotron backstop"; a flag with
  no source renders neither phrase.
- `CHANGELOG.md` under `[Unreleased]`; `README.md` "Web demo" one sentence.

## Steps

1. Failing tests first (caregiver round-trip, webapp render, footer presence).
2. `caregiver.py` field + persistence.
3. Orchestrator: pass `source` at the five `flags.add(` calls; nothing else changes.
4. `webapp.py` flag line and footer. Keep the footer one line at 1920 px; no logos, no links to
   vendor pages (the rules' trademark item).
5. Full suite (`.venv/bin/python -m unittest discover tests`), then `scripts/openai_review.sh`.

## Tests

The ones above, plus the existing privacy benchmark (`tests/test_mature_benchmarks.py`) and
`tests/test_late_disclosure.py` still green: `source` must not change disclosure logic.

## Splitting across subagents

One subagent (fleet worker profile, medium effort) does all five steps in its own worktree and
branch; the change is one feature across three files and splitting it would cost more in
handoff than it saves. It gets: this file, issue #214, `AGENTS.md`, `caregiver.py`,
`pipeline/orchestrator.py` flag sites, `webapp.py` ~:1140-1160 and ~:2087-2240,
`tests/test_webapp.py`, and ADR-005 (fast path) and ADR-010 (AUDIT model). It returns: branch
name, the five test names, the suite count, the Codex review result and the PR link. It must
land before `space-action-first` (#215) starts, since both edit the header region of `webapp.py`.

## Review

`scripts/openai_review.sh` on the branch (REVIEW.md). Flag rendering is caregiver-facing, so
the review prompt names the disclosure invariant explicitly.
