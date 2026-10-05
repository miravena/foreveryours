# docs/specs -- planning docs per feature and bug fix

One folder per change, named in kebab-case (e.g. `webapp-empty-transcript-crash`).
Each folder holds the markdown written before and during the work. Which files
appear depends on whether the change is a bug fix or a feature.

## Bug fix

```
docs/specs/<name>/
  bugfix.md     bug analysis: current vs expected behavior, root symptom
  design.md     root cause, the fix, and the test strategy
  tasks.md      implementation plan: failing test first -> fix -> verify
```

Example: `webapp-empty-transcript-crash/`.

## Feature

```
docs/specs/<name>/
  requirements.md   what the feature must do
  design.md         the technical design
  tasks.md          the implementation task list
  plan.md           optional: the .agents/skills/plan-feature artifact
```

## Small / quick changes

Scale the docs to the work -- a one-line change does not need the full set. A
small feature may have only a `plan.md`. Examples: `latency-pipelined-playback/`
and `review-policy-and-verify-hardening/` each carry just a `plan.md`.

## File meanings

- `bugfix.md` -- defect analysis (bug fixes only).
- `requirements.md` -- what the change must do (features only).
- `design.md` -- technical design: root cause / approach + test strategy.
- `tasks.md` -- the ordered implementation plan.
- `plan.md` -- the `.agents/skills/plan-feature` plan, written before any code.

Rule of thumb: a bug fix uses `bugfix.md`; a feature uses `requirements.md`.
Both share `design.md` + `tasks.md`. `plan.md` is used when the `.agents`
plan-before-code step produced one.

## Relationship to `.kiro/`

**`docs/specs/` is the authoritative copy.** One repo, any number of tools: Kiro,
Claude Code, OpenCode and a human with `cat` all read the same committed files,
so the copy in git is the one that counts. A tool's private directory is local
state, never a second source of truth.

`.kiro/` is Kiro's own working directory -- gitignored, present only on a machine
running Kiro, and holding what Kiro needs to keep for itself (`.config.kiro`,
task-run links), none of which is committed. If Kiro's spec tooling needs a
`plan.md` under `.kiro/specs/` to do validation or task links, derive it from
this folder; **on any conflict the `docs/specs/` copy wins**, so nobody has to
know which tool was the last writer. Never let a doc exist *only* under
`.kiro/` -- nobody else can see it, and it will drift.

That rule scales to whatever tool shows up next: it gets a gitignored directory
for its own state and reads `AGENTS.md` plus `docs/` for the shared rules. If a
tool insists on being the authoritative writer for a doc, it doesn't belong here.

The repo-wide review policy is `REVIEW.md` at the repo root -- it is not a
per-feature doc and does not live here.
