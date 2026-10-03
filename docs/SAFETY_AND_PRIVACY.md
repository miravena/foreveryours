# Safety & privacy design

Short, because the design choices matter more than the length of this doc.

## No silent surveillance

Every caregiver flag records whether the senior was actually told, in the
conversation — `CaregiverFlags.add()` takes `disclosed_to_senior` as a
required argument, not a default, specifically so this can't quietly drift
from true to false:

- **Fast-path flags** (`safety/fastpath.py`) are always disclosed — the
  immediate reply the senior hears ("I'm letting your family know right now
  so someone can check on you.") *is* the disclosure, spoken before anything
  else happens.
- **Audit flags** (`pipeline/audit.py`, see below) try to disclose via a
  spoken follow-up line after the fact. If that follow-up fails for some
  reason, the flag is recorded as `disclosed_to_senior=False` — honestly,
  not papered over — rather than assumed to have succeeded.

The senior is never meant to be monitored silently behind their back; the
code's job is to make that true in both cases above, not just the easy one.

**Refinement (implemented 2026-10-03):** the fast-path reply today discloses this *one* instance ("I'm letting your family know right now so someone can check on you.") but also states the standing rule — i.e. when disclosure happens and when it doesn't. Spelling that rule out loud, e.g. *"I'll only tell them if I'm worried about your safety,"* answers the "elder surveillance" objection more directly than a single-instance disclosure can: it tells the senior the boundary up front, not just that this one thing got reported.

## No medical claims

The companion is a companion, not a diagnostic tool. `pipeline/audit.py`'s
secondary model pass exists to catch medical advice or diagnosis language
in a reply **after it has already been spoken** (it runs async, off the
latency-critical path — see below, and note this means it can flag and
disclose, but it cannot retract something already said). If `AUDIT_MODEL`
flags a reply `UNSAFE`, that's logged as a caregiver flag and spoken to the
senior as a follow-up, not silently dropped.

## Two safety layers, different jobs

1. **Fast-path** (`safety/fastpath.py`) — synchronous, regex-based, runs
   before the LLM call. Catches the clearest distress/confusion signals
   instantly, speaking an immediate reassurance before the model is even
   called, so the highest-stakes replies are also the fastest. The
   conversation then continues into THINK with a short context note, rather
   than ending the turn — a distress signal shouldn't make the companion go
   silent right after. Deliberately conservative patterns — a false positive
   here (an unnecessary caregiver note) is far cheaper than a false negative.
2. **Audit** (`pipeline/audit.py`) — asynchronous, a second small-model pass
   over every *other* reply (given both the senior's words and the
   companion's reply, since some advice is only unsafe in context), checking
   for medical-hallucination or unsafe-advice risk. Runs after the reply is
   already on its way to audio, so it never adds latency — it can only flag
   and disclose after the fact, not block in time.

Neither layer is a substitute for the other. The fast-path is a narrow net
for the highest-urgency, most time-critical cases; the audit pass is a wider
net for everything else, accepted at the cost of running after the words are
already said.

## What's stored

Caregiver memos and caregiver daily notes, stored verbatim. When the senior's
turn contains a durable-fact marker (name, preference, family — see
`pipeline/think.py`'s `DURABLE_MARKERS`), **the whole turn's transcript is
stored verbatim, not just the extracted fact** — real extraction (pulling
just "I love Miles Davis" out of a longer sentence) needs an LLM call we
haven't budgeted into the latency path yet. Known imprecision, not a design
goal: a future pass should extract the fact, not the sentence it arrived in.
Nothing else is kept on purpose, but audio does touch disk, so here is
exactly where and for how long (issue #18):

- **Hosted web demo (`webapp.py`).** Each browser tab is its own throwaway
  household under `FY_SESSIONS_DIR`. The reply WAVs from one turn are deleted
  at the start of the next; the whole household (memory, flags, reply audio)
  is deleted when the tab closes, or after `SESSION_TTL_S` (default 1 hour)
  if the close event never arrives. Uploaded or recorded input clips and
  served reply audio also pass through Gradio's own file cache, which the app
  expires on the same 1-hour clock (`delete_cache`). No other visitor can see
  another tab's household.
- **Local CLI (`main.py`).** Reply audio stays in `out/audio/` and memory in
  `data/` until you delete them. That's your own machine, and keeping them is
  what lets `day2` prove persistence.
- **Third parties.** Transcripts (text, not audio) of each turn go to Nebius
  Token Factory for THINK/AUDIT. With the default `ASR_BACKEND=whisper_local`
  (what the hosted demo runs; Token Factory has no transcription endpoint,
  PR #25), speech recognition is local, so raw audio is never sent to a
  model provider.

## What this is not

No medical certification, no clinical claims, no emergency-dispatch
integration (a caregiver flag is a notification, not a 911 call). These are
explicitly out of scope for the hackathon build — see the main README.
