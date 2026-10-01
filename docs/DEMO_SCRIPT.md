# Demo script

This is the exact sequence the live demo (and the submission video) follows.
Both of us should be able to run this from a clean `data/` directory and get
the same result — if a change breaks this, it's a blocker for `main`, not a
follow-up.

## Setup

```bash
rm -rf data out   # start from a clean slate
python main.py beat1
```

## Beat 1 — Caregiver memo

Caregiver submits a 60-second voice memo (supports real speech via `--audio` or default text):

```bash
python main.py beat1 --audio samples/caregiver_memo.wav   # real voice memo
# or: python main.py beat1                               # default text
```

> "Dad loves jazz. His grandson is named Leo. Avoid talking about driving.
> I'm dropping off groceries at 4 PM today."

**Expect:** memory panel shows 4 facts saved under `caregiver_memo`.

## Beat 2 — Senior conversation uses that context

```bash
python main.py beat2 --audio samples/senior_jazz.wav     # real voice input
# or: python main.py beat2                               # default text
```

**Expect:**
- Reply references the caregiver facts (Leo, the 4 PM groceries) and never
  raises the guardrail ("avoid driving") on its own — caregiver memos/notes
  are always injected into the prompt now, not dependent on word-overlap
  with what the senior said (`memory/store.py`'s `caregiver_context()`).
- Time-to-first-audio printed and under 2 seconds.
- Memory panel shows what was *recalled* for this turn (always includes the
  caregiver facts; conversation-derived memories are still overlap-searched).
- Because the audio mentions a durable fact (listening to Miles
  Davis), the panel should show a newly *saved* memory too.

This beat needs `NEBIUS_API_KEY` set — it's the only beat with no fast-path
underneath it, so without a key it fails loudly rather than falling back to
anything mocked.

## Beat 3 — Worrying remark → honest caregiver flag, conversation continues

```bash
python main.py beat3 --audio samples/senior_distress.wav # real voice distress
# or: python main.py beat3 "I fell down earlier"         # text input
```

**Expect:**
- The companion speaks an immediate, honest reassurance first — *"I hear
  you, and I'm taking this seriously. I'm letting your family know right now
  so someone can check on you."* — never a silent report. That line itself
  IS the disclosure (see `docs/SAFETY_AND_PRIVACY.md`).
- A caregiver flag appears in the panel, severity `distress`, marked
  "disclosed to senior."
- The fast-path's regex check (`safety/fastpath.py`) never calls the LLM for
  that immediate line, so it's fast on purpose. The conversation then tries
  to continue into THINK with context about what just happened, rather than
  ending the turn there — **with `NEBIUS_API_KEY` set**, expect a real
  follow-up reply after the reassurance. **Without a key**, the turn still
  completes (degrades gracefully — see the audit verdict line printed), it
  just doesn't continue past the immediate reassurance.

## Day-2 recall (`python main.py day2`, built and verified)

Shows a memory saved in one session surfacing correctly in a *later* session
(different process run, same `data/` directory) — run after beat1, as a
genuinely separate process invocation. Proves persistence isn't just
in-memory-per-run; good footage for the video since it's a visible "fresh
process, PID printed, still remembers" moment. Runs completely offline without an API key.
```bash
python main.py day2
```

**Expect:**
- Terminal prints its own new process PID and verifies facts loaded directly from disk.
- Output confirms: `"4 fact(s) recalled from a prior run. Persistence confirmed."`

## Beat 4 — Conversational Day-2 recall (needs `NEBIUS_API_KEY`)

The conversational version of Day-2 recall: senior asks for a durable fact established in Beat 1 ("Leo"), proving the companion retrieves it across session boundaries.

```bash
python main.py beat4 --audio samples/senior_grandson.wav   # real voice recall
# or: python main.py beat4 "I forgot, what is my grandson's name?"
```

**Expect:**
- The companion naturally recalls the durable fact from the caregiver memo (that the grandson is Leo).
- When run without `NEBIUS_API_KEY`, it prints a clean, friendly message directing to `python main.py day2` instead of crashing.

## What the video should NOT open on

Architecture diagrams, pipeline boxes, or "here's our tech stack" slides.
Open on beat 2 — the senior actually talking and the companion actually using
what the caregiver told it. Explain the pipeline after the demo lands, not
before.
