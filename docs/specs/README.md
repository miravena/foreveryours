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

## Relationship to `.kiro/specs/`

These are human-readable mirrors. The authoritative copies live in
`.kiro/specs/<name>/`, where Kiro's spec tooling reads them (validation,
task-run links). Kiro-internal files like `.config.kiro` are deliberately not
mirrored here. If you don't use Kiro, read these `docs/specs/` copies. If a doc
changes in `.kiro/specs/`, it is re-mirrored here in the same change so the two
do not drift.

The repo-wide review policy is `REVIEW.md` at the repo root -- it is not a
per-feature doc and does not live here.
