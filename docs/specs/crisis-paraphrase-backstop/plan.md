# Plan: Crisis paraphrases (#199)

## Goal

A committed crisis fixture that both tiers pass live, one 988 line per episode, and an ADR that
says which phrase lives where.

## Affected files

- `tests/fixtures/crisis_eval_set.jsonl` (new)
- `scripts/audit_eval.py` (accept `--fixture` with a `crisis` label set, or a sibling
  `scripts/crisis_eval.py` that reuses its loader, cache and scorer)
- `safety/fastpath.py` (`CRISIS_PATTERNS`, `_BENIGN_CRISIS_IDIOMS`)
- `pipeline/audit.py` (prompt examples), `pipeline/orchestrator.py` (carry CRISIS into the
  next turn's THINK context; the "988 once" guard)
- `tests/test_fastpath.py`, `tests/test_audit.py`, `tests/test_orchestrator.py`,
  `tests/test_mature_benchmarks.py` (Benchmark 6)
- `docs/decisions/ADR-0xx-crisis-tiers.md`, `docs/SAFETY_AND_PRIVACY.md`, `CHANGELOG.md`

## Steps

1. **Fixture.** Write the rows: `id`, `transcript`, `label` (`crisis` or `safe`), `tier`
   (`regex`, `backstop`, `either`), `note`. Header comment: US 988 only.
2. **Baseline.** Offline: run `fastpath.check()` over every row and post the table. Live
   (through `scripts/with_key.sh`): run the eval on the backstop rows with the current prompt.
3. **Regex tier.** Add patterns for the phrases marked `regex` (expected: "I am suicidal",
   "I want to take my own life", "I want to end it all"); extend `_BENIGN_CRISIS_IDIOMS` for the
   near-misses; red-then-green tests.
4. **Backstop tier.** Prompt examples for the rest; `audit_reply` contract unchanged.
5. **Next-turn carry.** In the orchestrator, when the background AUDIT returns CRISIS, store a
   one-turn marker in the session so the next THINK context includes a crisis note; the note
   says the 988 line was already given if the fast-path spoke it. Stub tests: CRISIS then a
   neutral turn yields one 988 mention across both replies.
6. **Benchmark 6.** Make the crisis assertion depend on the query (feed a crisis transcript
   through the stubbed pipeline and assert the reply, not the prompt constant).
7. **Measure.** Live eval; post recall and false flags per tier.
8. **ADR + docs + CHANGELOG.** Review with `scripts/openai_review.sh`; run
   `tests/test_mature_benchmarks.py` explicitly.

## Tests

Red first for every new pattern and every backstop example; the ten benign rows as negatives;
the one-988 orchestrator test; Benchmark 6 rewritten; full suite; `scripts/smoke.sh`.

## Splitting across subagents

- Subagent A: steps 1 and 3 (fixture plus regex tier), offline, one PR.
- Subagent B: steps 4, 5 and 6 (backstop, next-turn carry, Benchmark 6), needs a key for step
  7, one PR. Depends on A's fixture file only; can start from a draft of it.
- Subagent C: step 8 after both merge.
Each needs this file, #199, #191, ADR-005, AGENTS.md. None may weaken an existing test or
remove a benign idiom.

## Review

Safety-critical: different-vendor review per REVIEW.md, `scripts/openai_review.sh` per PR,
founder reads the ADR.
