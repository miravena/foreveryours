# REVIEW.md -- how we review changes to ForeverYours

Read by a human reviewer and by Claude/Kiro when reviewing a PR. The actual
policy lives in [`AGENTS.md`](AGENTS.md) and [`docs/decisions/`](docs/decisions/);
this file only says which passes to run and how to rank what they find. It does
not restate policy, so it cannot drift from it.

## Passes

Run each pass and tag every finding with the pass it came from.

- **Bugs** -- logic errors, broken edge cases, regressions. The clearest signal:
  does the change keep `main` demo-able? The three-beat demo in
  [`README.md`](README.md) must still work after every change.
- **Safety** -- the heart of this project. Flag as **Important** any change that:
  - narrows or weakens a pattern in `safety/fastpath.py`. This path is
    *deliberately* biased to false positives; narrowing it needs a linked Issue
    and an ADR (see `AGENTS.md` -> "Things people get wrong" and
    `docs/decisions/ADR-005-safety-fastpath.md`). A narrowing PR with no ADR is a
    blocking finding.
  - reduces or removes a caregiver disclosure, or lets a flag be raised without
    stating whether the senior was told. No silent surveillance -- every flag
    discloses, in the conversation, that it was raised.
  - makes a medical, physical-action, or parasocial claim the prompt forbids
    (guarded by `tests/test_mature_benchmarks.py` Benchmark 6).
- **Privacy** -- no new PII in logs or error messages; `.env`, `data/`, `out/`
  are never committed (the pre-commit hook enforces this; flag anything that
  tries to defeat it). Caregiver-only memories must not leak into senior turns
  (Benchmark 4).
- **Compliance-with-plan** -- the diff matches the committed
  `docs/specs/<feature>/plan.md` (or the Issue's acceptance criteria) for the
  change. Call out undocumented scope.

## What "Important" means here

Reserve **Important** for findings that break a README demo beat, weaken a
safety or disclosure invariant, or leak data. Everything else -- style, naming,
micro-refactors -- is a **nit**.

## Cap the nits

At most five nits per review; summarize the rest as a count.

## Do not report

Generated / cache dirs (`__pycache__/`, `.venv/`, `out/`), and anything the
pre-commit hook or CI (`.github/workflows/`) already enforces.
