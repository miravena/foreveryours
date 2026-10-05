# docs/specs -- planning docs per feature and bug fix

One folder per change, named in kebab-case. Each holds the markdown that was
written before and during the work:

- `plan.md` -- the implementation plan (see `.agents/skills/plan-feature`).
- `requirements.md` / `bugfix.md` -- what the change must do, or the bug analysis.
- `design.md` -- the technical design.
- `tasks.md` -- the implementation task list.

Not every folder has every file; a small bug fix may only have `bugfix.md` +
`design.md` + `tasks.md`, a feature only a `plan.md`.

## Relationship to `.kiro/specs/`

These are human-readable mirrors. The authoritative copies live in
`.kiro/specs/<feature>/`, where Kiro's spec tooling reads them (validation,
task-run links). Kiro-internal files like `.config.kiro` are deliberately not
mirrored here. If you don't use Kiro, read these `docs/specs/` copies.

The repo-wide review policy is `REVIEW.md` at the repo root -- it is not a
per-feature doc and does not live here.
