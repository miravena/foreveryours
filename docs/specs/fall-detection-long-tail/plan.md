# Plan: Falls phrased outside the fast-path (#198)

## Goal

Every fall in the fixture and the #56 list raises a flag, with zero new false positives,
measured live and recorded in an ADR.

## Affected files

- `safety/fastpath.py` (`DISTRESS_PATTERNS`, maybe a new lower-severity tier)
- `pipeline/audit.py` (prompt: subject is the transcript; examples)
- `pipeline/orchestrator.py` (if a new severity tier needs its own spoken line and flag text:
  `CAREGIVER_FLAG_TEXT` gains a key)
- `tests/fixtures/audit_eval_set.jsonl` (add the seven #56 phrasings as rows, tagged
  `holdout` for three of them)
- `tests/test_fastpath.py`, `tests/test_audit.py`, `tests/test_orchestrator.py`
- `docs/decisions/ADR-0xx-fall-long-tail.md`, `docs/SAFETY_AND_PRIVACY.md`, `CHANGELOG.md`

## Steps

1. **Baseline.** Through `scripts/with_key.sh`, run `scripts/audit_eval.py --model <Nano>` on
   the current fixture and post the per-row result for the fall rows on #198. Run
   `safety.fastpath.check()` over the thirteen phrasings offline and post which match.
2. **Split the list.** For each phrasing decide: regex (unambiguous, cheap, must be spoken
   first) or backstop (idiom, needs context). Expected: "I cannot get up", "I have fall",
   "I'm on the floor and I can't move" go to regex with a near-miss negative each ("I cannot
   get up early", "I have fallen behind on my letters", "the cat is on the floor"); the rest to
   the backstop.
3. **Regex tier.** Add the patterns with the negatives; keep the `fell asleep` exclusion
   shape. Run `tests/test_fastpath.py` and Benchmark 2 red-then-green.
4. **Backstop tier.** Rewrite the AUDIT prompt so the first sentence names the senior's
   transcript as the subject and the reply as context; add two fall examples that are not in
   the fixture. Keep the one-word verdict contract (`audit_reply` parses the first word).
5. **Fixture.** Add the seven phrasings as rows; mark three `holdout` and exclude holdout rows
   from any prompt example. Land #193 first if the cache would otherwise replay stale answers.
6. **Measure.** Re-run the eval live; post the table (rows, verdicts, recall, false flags,
   calls, cost). Criterion: all fall rows flagged, 0/17 false flags unchanged.
7. **Disclosure.** Confirm a backstop DISTRESS flag reaches the senior through the existing
   late-disclosure path (`tests/test_late_disclosure.py` pattern) and that
   `disclosed_to_senior` is recorded from what was spoken.
8. **ADR + docs.** Write the ADR (amends ADR-005 "when to revisit" and ADR-010), update
   `docs/SAFETY_AND_PRIVACY.md` and the CHANGELOG.
9. **Review.** `scripts/openai_review.sh`; answer each finding. Run `tests/test_mature_benchmarks.py`
   explicitly (AGENTS.md rule for fast-path changes).

## Tests

- Red first: a test per new phrasing in `tests/test_fastpath.py` (regex tier) and a stubbed
  `audit_reply` test per backstop phrasing in `tests/test_audit.py`.
- Negatives: one near-miss per new pattern.
- Benchmark 2 unchanged; full suite; `scripts/smoke.sh`.

## Splitting across subagents

- Subagent A (regex tier): steps 2 to 3 for the regex phrasings, offline, one PR touching
  `safety/fastpath.py` and `tests/test_fastpath.py`. Returns: patterns added, negatives added,
  Benchmark 2 output.
- Subagent B (backstop tier): steps 4 to 6, needs a key through `scripts/with_key.sh`, one PR
  touching `pipeline/audit.py`, the fixture and `tests/test_audit.py`. Returns: the eval table.
- Subagent C (after A and B): steps 7 to 8, the ADR and docs.
A and B are independent. Each needs this file, #198, ADR-005, ADR-010 and AGENTS.md. None may
weaken an existing test.

## Review

Safety-critical: a different vendor reviews (REVIEW.md), `scripts/openai_review.sh` on each PR,
and the founder reads the ADR before merge.
