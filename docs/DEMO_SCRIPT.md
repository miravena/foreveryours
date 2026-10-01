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

Caregiver submits a 60-second voice memo (text input for now — the mic/dashboard
widget is UI polish, not pipeline work):

> "Dad loves jazz. His grandson is named Leo. Avoid talking about driving.
> I'm dropping off groceries at 4 PM today."

**Expect:** memory panel shows 4 facts saved under `caregiver_memo`.

## Beat 2 — Senior conversation uses that context

```bash
python main.py beat2 "Hi, how's it going today?"
```

**Expect:**
- Reply naturally references at least one caregiver fact (Leo, avoiding
  driving, or the 4 PM groceries) without announcing "according to my notes."
- Time-to-first-audio printed and under 2 seconds.
- Memory panel shows what was *recalled* for this turn.
- If the turn contained anything durable and new, the panel shows a newly
  *saved* memory too.

This beat is the one that needs `NEBIUS_API_KEY` set — it's the only beat that
calls the real model.

## Beat 3 — Worrying remark → honest caregiver flag

```bash
python main.py beat3 "I fell down earlier and I'm scared"
```

**Expect:**
- The companion's reply is honest and in-conversation, e.g. *"I hear you, and
  I'm taking this seriously. I'm letting your family know right now so
  someone can check on you."* — never a silent report.
- A caregiver flag appears in the panel, severity `distress`.
- This path never calls the LLM (see `safety/fastpath.py`) — it's fast on
  purpose, since this is the highest-stakes moment to be slow in.

## Beat 4 — Day-2 recall (Persistence)

Shows a memory saved in one session surfacing correctly in a *later* session
(different process run, same `data/` directory). Needed to prove persistence
isn't just in-memory-per-run.

```bash
python main.py beat4 "I forgot, what is my grandson's name?"
```

**Expect:**
- The companion naturally recalls the durable fact from the caregiver memo (that the grandson is Leo).

## What the video should NOT open on

Architecture diagrams, pipeline boxes, or "here's our tech stack" slides.
Open on beat 2 — the senior actually talking and the companion actually using
what the caregiver told it. Explain the pipeline after the demo lands, not
before.
