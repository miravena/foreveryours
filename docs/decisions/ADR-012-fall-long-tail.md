# ADR-012: Falls phrased outside the canonical words: three more fast-path patterns, and an AUDIT prompt that reads the transcript

**Status:** Accepted (founder 2026-10-23; teammate review open on the issue)
**Date:** 2026-10-23
**Decided by:** Team; the founder reads this before merge (safety-critical)
**Affects:** `safety/fastpath.py` (`DISTRESS_PATTERNS` only), `pipeline/audit.py` (prompt), `tests/fixtures/audit_eval_set.jsonl`, `tests/test_fastpath.py`, `tests/test_audit.py`, `tests/test_late_disclosure.py`
**Related issue:** [#198](../../issues/198). Amends [ADR-005](ADR-005-safety-fastpath.md) ("when to revisit") and [ADR-010](ADR-010-audit-model-eval.md). Related: #56, #55, #193, #200, #199.

## Question

How do falls the senior words in their own way ("my legs just gave way", "I went down in the
garden") reach the caregiver, without giving up ADR-005's bias against false positives?

## Context

ADR-010 measured Nano as AUDIT missing 5 of the 6 fixture fall rows, and the regex fast-path
matched none of the six. Offline, over the six fixture transcripts plus the seven phrasings left
open on #56, `safety.fastpath.check()` before this change:

| Phrasing | Fast-path before |
|---|---|
| fall-01 "I hit the floor in the bathroom and I can't get back up." | none |
| fall-02 "My legs just gave way on the stairs and my hip really hurts." | none |
| fall-03 "I slipped on the kitchen floor about an hour ago..." | none |
| fall-04 "I tripped over the rug and banged my head..." | none |
| fall-05 "I went down in the garden and I can't put any weight..." | none |
| fall-06 "I'm on the floor next to the bed, ... I just went over." | none |
| "I hit the floor" / "I went down" / "I'm terrified" / "I feel dizzy" | none |
| "I'm on the floor and I can't move" / "I cannot get up" / "I have fall" | distress (already, from #55) |

So 3 of the 13 were already covered; 10 were not.

## Decision

1. **Three first-person regex patterns** in `DISTRESS_PATTERNS`, each with a near-miss negative
   in `tests/test_fastpath.py`: `I (just) hit the floor` (not `... running`), `my legs/knees
   (just) gave way/out`, and `I (just) went down in/on the <place of a fall>`. Guards: not
   `hit the floor running/laughing/mat/rug`; not `gave way to ...` or with a past-time cue
   (years ago, when I was ...); `went down` only before a fall place (stairs, kitchen, bathroom,
   garden, hall ...) and not before an errand cue (`to get/water/see ...`). After the change the fast-path
   catches fall-01, fall-02, fall-05 and the #56 phrasings "I hit the floor", "I cannot get up",
   "I have fall" and "I'm on the floor and I can't move". No existing pattern was narrowed and
   `CRISIS_PATTERNS` is untouched.
2. **Everything idiomatic or thin stays with the backstop:** fall-03, fall-04, fall-06, "I went
   down" alone, "I'm terrified", "I feel dizzy". A bare "went down" or "dizzy" is too
   ambiguous for an urgent, spoken-first line.
3. **AUDIT prompt rewritten** so the first sentence names the senior's transcript as the subject
   and the reply as context, with two worked fall examples that are not fixture rows. The
   one-word verdict contract is unchanged (`audit_reply` still parses the first word).
4. **Fixture:** seven rows (fall-07 to fall-13) for the #56 phrasings; three are tagged
   `"holdout": true` (fall-08, fall-10, fall-11, the backstop-tier ones). A test fails if a
   holdout transcript, or any longer fixture fall transcript, appears in the prompt.
5. **Disclosure** is unchanged and now tested for a backstop fall: the AUDIT DISTRESS flag is
   spoken on the late-disclosure path and `disclosed_to_senior` follows what was actually spoken
   (`tests/test_late_disclosure.py`).

Deliberately left to the backstop: "I went down in the basement/lift/world", "I went down on
the bus", "years ago my knees gave out" (past cue before the verb), and any other "went down"
with a place not in the list.

## Not decided here

- **Graded severity (a lower-severity flag for uncertain cases)** needs a new tier and its own
  caregiver text in `CAREGIVER_FLAG_TEXT`; that is a change to the orchestrator and flag
  wording, not done here. Today a backstop flag uses the existing `audit_distress` text, which is
  already distinct from the fast-path `distress` text.
- **Nano's floor.** Live, Nano still misses two holdout rows; whether to switch AUDIT to Super
  was #200's decision; ADR-016 switched AUDIT to Super.

## Measured (live, 2026-10-23, fresh `--out-dir`, 43-row fixture)

| Model | Recall | False flags | Missed | Cost |
|---|---|---|---|---|
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (current) | 0.88 (was 0.63 on the 36-row set) | 0/17 | fall-10 "I'm terrified" (holdout), fall-11 "I feel dizzy" (holdout), confusion-01 | $0.0016 |
| `nvidia/nemotron-3-super-120b-a12b` | 1.00 | 0/17 | none | ~$0.008 |

Nano is below the eval's 0.90 recall floor, so `audit_eval.py` exits FAIL for it; Super clears
it with no added false flags. Command:
`scripts/with_key.sh python3 scripts/audit_eval.py --model <id> --out-dir <fresh dir>`.

## Consequences

- More urgent flags on first-person fall wording; the false-positive risk is the idioms "I went
  down in/on the ..." and "hit the floor" that mean something else, which the negatives pin.
- Known pre-existing over-matches, left as they are (ADR-005 bias, and narrowing is out of
  scope): "I can't get up early" and "I have fallen behind" already fire the fast-path.
- Fixture is 43 rows (was 36); `tests/test_audit_eval.py` counts follow.

## When to revisit

After the live run: if any non-holdout fall row is still missed, or a false flag appears, or
holdout recall is far below the rest (prompt overfit). Also if graded severity is added.
