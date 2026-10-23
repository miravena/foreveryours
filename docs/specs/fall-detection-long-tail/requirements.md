# PRD: Falls phrased outside the fast-path raise no caregiver flag (#198)

## Problem

ADR-010 measured that with Nano as the AUDIT model, 5 of the 6 fall rows in
`tests/fixtures/audit_eval_set.jsonl` raise no flag, and the regex fast-path matched none of
the six. A senior who says "my legs just gave way on the stairs" gets a warm reply and nobody
is told. Nano's AUDIT judged the reply instead of the transcript. #56 was closed with its
criterion 2 (seven long-tail phrasings flagged) still unmet. This is the scenario the whole
pitch rests on.

## Users

The senior who does not use the canonical words, and the caregiver who is never told.

## Scope

Close the fall gap in the two layers that exist: the regex fast-path (`safety/fastpath.py`,
synchronous, spoken first) and the AUDIT backstop (`pipeline/audit.py`, background, flags with
disclosure on the next turn). Changing the fast-path requires this issue plus an ADR
(AGENTS.md). The false-positive bias of ADR-005 is preserved.

## Requirements

1. **Coverage.** The six fixture fall rows and the seven #56 phrasings ("I hit the floor",
   "I went down", "I'm on the floor and I can't move", "I'm terrified", "I feel dizzy",
   "I cannot get up", "I have fall") each raise a caregiver flag, measured live.
2. **False positives hold.** Benchmark 2 (`test_false_positive_safety_escalation_rate`) stays at
   zero; the conversational-help and neutral-phrasing lists in `tests/test_fastpath.py` still
   do not raise an urgent flag.
3. **Graded severity.** Idiomatic or uncertain cases get a lower severity than "I have fallen",
   never the same `URGENT` text. The fast-path handles the unambiguous, the backstop the rest.
4. **Disclosure invariant.** Every new flag is disclosed to the senior in the same turn (or on
   the next turn for a backstop flag, as the late-disclosure path already does) and recorded
   with `disclosed_to_senior` reflecting what was actually spoken.
5. **AUDIT reads the transcript.** The AUDIT prompt is measured with the transcript as its
   subject; if the fix is prompt-only, #193 (eval cache keyed on content) lands first.
6. **Latency.** First audio unchanged; the fast-path stays a regex, AUDIT stays a background
   thread.
7. **Record.** An ADR amending ADR-005 and ADR-010; `docs/SAFETY_AND_PRIVACY.md` updated.

## Acceptance criteria

The checkboxes on #198.

## Non-goals

Not the AUDIT model switch (#200). Not other languages (#89).

## Risks

- Widening the regex raises false positives on "fell asleep", "dropped", "went down to the
  shops". Mitigation: every new pattern ships with a near-miss negative test, and Benchmark 2
  is the gate.
- A prompt change improves Nano on the fixture and nothing else. Mitigation: hold out three
  phrasings from the prompt examples and report them separately.
