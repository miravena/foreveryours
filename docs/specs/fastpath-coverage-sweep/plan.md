# plan.md -- #55: fastpath coverage sweep (cheap distress misses)

> Written per `.agents/skills/plan-feature`. NO source changed in this phase.
> Implement per `.agents/skills/implement-feature` after approval.
> SAFETY-CRITICAL FILE (`safety/fastpath.py`): per AGENTS.md + ADR-005 this change
> may ONLY ADD triggers (widen coverage), never narrow. Every pattern change needs
> a trigger test AND a near-miss test. Benchmark 2 must stay 0.0% (0/15).

## Intent (GitHub #55)

The fastpath is the only component that detects senior distress (think.py has no
distress rule; audit.py only reads the reply). Phrases the regex misses mean nobody
is told. #55 is scoped to THREE cheap, bounded wins only -- the long tail
(synonyms/idioms/reversed order) is #56, not this.

## Ground-truth measurements (run on current main via check())

CRIT1 contraction gap:
  "I cannot get up"   -> False (BUG)   | "I can't get up"   -> True
  "I cannot breathe"  -> False (BUG)   | "I can't breathe"  -> True
CRIT2 bare plea:
  "help"  -> False | "help!" -> False | "help me" -> True
  "Help me remember Leo's birthday" -> False (correct; must stay False)
CRIT3 on the floor:
  "I'm on the floor and I can't move" -> False (BUG)
  "I'm stuck on the floor"            -> False (BUG)
  "I'm on the floor watching telly"   -> False (correct; must stay False)
Near-misses (must stay False): all currently False. Good.

## The three changes

### Criterion 1 -- contraction gap (lowest risk, pure widen)

Two patterns accept only `can't`; widen to also accept `cannot`, per the issue's
fix shape `can(?:'?t|not)`:
- `r"\bcan'?t get up\b"`            -> `r"\bcan(?:'?t|not)\s+get up\b"`
- in `r"...(hurt|bleeding|dizzy|can'?t breathe)..."` -> `can(?:'?t|not)\s+breathe`
  (note: add `\s+` so "cannot breathe" / "can't breathe" both match; today it is a
  literal space after `can'?t`).
This is strictly additive: everything that fired before still fires.

### Criterion 3 -- on the floor + distress (new rule, additive)

Add ONE new DISTRESS_PATTERNS entry that fires on "floor" tied to being stuck /
unable to move, but NOT benign floor use. Proposed:
  `r"\b(on|hit)\s+the\s+floor\b.*\b(can(?:'?t|not)\s+(move|get up)|stuck|hurt|help)\b"`
  plus the reverse order `r"\b(stuck|can(?:'?t|not)\s+(move|get up))\b.*\bon\s+the\s+floor\b"`
  -- OR a single rule allowing either order. Decide exact form in implement; the
  REQUIREMENT is: fires on "I'm on the floor and I can't move" and "I'm stuck on the
  floor"; does NOT fire on "I'm on the floor watching telly" / "sitting on the floor
  doing a puzzle". Because it requires a distress co-token (stuck / can't move /
  hurt / help), benign floor use stays clear.
  Note "I hit the floor" ALONE is an idiom -> that's #56's long tail, NOT required
  here; only floor + explicit distress co-token is in scope.

### Criterion 2 -- bare plea (HIGHEST RISK; needs your decision)

The issue asks that "help" / "help!" fire on their own. Measured: both are False
today, and that is BY DESIGN -- #15/#33 deliberately narrowed bare "help" because
"help me remember Leo's birthday" was a false positive. Options:

  (A) Fire only on a bare plea that is the WHOLE utterance: extend the existing
      anchored rule `^(can\s+someone\s+)?help\s+me[!.?\s]*$` with a sibling
      `^help[!.?\s]*$` so "help" / "help!" / "Help!!" as the entire message fire,
      while "help me remember..." (embedded) still does NOT. LOW false-positive
      risk because it is anchored to ^...$. RECOMMENDED.
  (B) Fire on "help!" anywhere (exclamation = plea) but never bare "help". Medium
      risk (e.g. "that is a big help!").
  (C) Do nothing for Crit 2 -- treat it as already-covered by "help me" and defer
      bare-plea to the founder policy call the issue itself flags.

Recommendation: (A). It satisfies the criterion's literal cases ("help", "help!")
without reopening the #33 false positive, because the match is the whole string.
FLAGGED for maintainer sign-off since it touches the exact area #33 narrowed.

## Explicitly OUT of scope (per the issue)

- Bare fear statements ("I'm terrified" with no help) -- founder policy + ADR (#56-ish).
- `help?` after nothing -- intentionally stays a near-miss.
- Synonyms / idioms / reversed order / non-native grammar -- that is #56.
- No change to think.py / audit.py / orchestrator.py.

## Affected files

- `safety/fastpath.py` -- widen 2 patterns (Crit 1), add 1 rule (Crit 3), and
  (pending your call) add 1 anchored bare-plea rule (Crit 2 option A).
- `tests/test_fastpath.py` -- for EACH change, a trigger case in
  `test_distress_triggers` AND a near-miss in `test_conversational_help_requests_do_not_trigger`
  or `test_neutral_phrasings_do_not_trigger` (ADR-005 / Criterion 5).
- Plan: `.kiro/specs/fastpath-coverage-sweep/plan.md` + `docs/specs/.../plan.md`.

## Risks

- **Re-introducing the #33 false positive** via Crit 2. Mitigation: anchored ^...$
  form (option A); explicit near-miss test for "help me remember Leo's birthday"
  and "that was a big help".
- **Crit 3 over-matching** benign floor use. Mitigation: require a distress
  co-token; near-miss tests for "watching telly" / "doing a puzzle".
- **Accidental narrowing.** Mitigation: run the FULL existing fastpath test list
  (both near-miss tests) + Benchmark 2; all must stay green/0.0%.

## Verification (per testing.md, ADR-005, and #55 ACs)

- `tests.test_fastpath` all green, including the unchanged near-miss lists (Crit 4).
- `tests.test_mature_benchmarks` Benchmark 2 = 0.0% (0/15) (Crit 4).
- New trigger + near-miss per rule (Crit 5).
- `scripts/smoke.sh` (beat3 is the fastpath beat) and, if available,
  `scripts/openai_review.sh` on the change (Crit 6). Note: smoke.sh is bash; on
  Windows I can run the unittest subset directly and note smoke.sh for CI/coworker.
- Windows: PYTHONUTF8=1.

## Open decisions for implement phase

1. **Criterion 2 approach: (A) anchored whole-string bare plea [recommended], (B)
   help! anywhere, or (C) skip and defer to founder.** Needs your pick -- it is the
   one place that edges toward the #33-narrowed zone.
2. Crit 3 rule as one combined regex vs two (either-order) -- cosmetic; implement
   picks the clearer one.
