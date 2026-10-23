# Plan: AUDIT model switch rule (#200)

## Goal

A written rule, fresh numbers, and either a one-line model change or a reasoned "no".

## Affected files

- `docs/decisions/ADR-0xx-audit-model-switch.md` (amends ADR-010), `docs/decisions/README.md`
- If Super: `pipeline/audit.py` default, `.env.example`, `README.md` Pipeline, ADR-002,
  `VENDOR_DECISIONS.md`, `CHANGELOG.md`
- `docs/WORK_LOG.md` (measurements)

## Steps

1. Land #193 (cache keyed on fixture content and model/prompt) or confirm it landed.
2. Through `scripts/with_key.sh`, run `scripts/audit_eval.py --model` for Nano and Super on the
   current fixture (after #198's rows if merged). Post the two tables on #200 with calls and
   cost.
3. Measure AUDIT wall time per call for both models on the Space (the `LAST_USAGE` hook plus a
   timer around `audit_reply`, or the live judge check's timing output) and post it.
4. Write the ADR: the rule, the numbers, the ceiling, the decision.
5. If Super: change the default, update the five documents, CHANGELOG. If not: ADR only.
6. Open a PR; `scripts/openai_review.sh`; both maintainers comment on #200.

## Tests

`tests/test_audit.py` and `tests/test_audit_eval.py` pass unchanged; the full suite;
`scripts/smoke.sh`. A default-model test asserts `.env.example` and the code default agree.

## Splitting across subagents

- Subagent A: steps 2 and 3, needs a key, returns the tables and timings; no file edits.
- Subagent B: steps 4 and 5 from A's tables; one PR.
Each needs this file, #200, ADR-002, ADR-010, `scripts/audit_eval.py`.

## Review

`scripts/openai_review.sh` on the PR; the founder decides the ceiling.
