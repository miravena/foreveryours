# Safety & privacy design

Short, because the design choices matter more than the length of this doc.

## No silent surveillance

If the companion flags something to the caregiver, the senior is told so, in
the conversation, honestly — e.g. *"I'll only tell Sarah if I'm worried about
your safety."* The senior is never monitored behind their back. This is a
hard design constraint, not a nice-to-have: see `safety/fastpath.py`, where
every triggered flag carries a `reply_text` that discloses it.

## No medical claims

The companion is a companion, not a diagnostic tool. `pipeline/audit.py`'s
secondary model pass exists specifically to catch medical advice or diagnosis
language before it reaches the senior. If `AUDIT_MODEL` flags a reply
`UNSAFE`, that's logged as a caregiver flag, not silently dropped or retried
into something riskier.

## Two safety layers, different jobs

1. **Fast-path** (`safety/fastpath.py`) — synchronous, regex-based, runs
   before the LLM call. Catches the clearest distress/confusion signals
   instantly, skipping the model entirely so the highest-stakes replies are
   also the fastest. Deliberately conservative patterns — a false positive
   here (an unnecessary caregiver note) is far cheaper than a false negative.
2. **Audit** (`pipeline/audit.py`) — asynchronous, a second small-model pass
   over every *other* reply, checking for medical-hallucination or unsafe-
   advice risk. Runs after the reply is already on its way to audio, so it
   never adds latency — it can only flag after the fact, not block in time.

Neither layer is a substitute for the other. The fast-path is a narrow net
for the highest-urgency, most time-critical cases; the audit pass is a wider
net for everything else, accepted at the cost of running after the words are
already said.

## What's stored

Caregiver memos, caregiver daily notes, and durable facts the senior mentions
in conversation (name, preferences, family) — see `memory/store.py`. Nothing
else: no audio recordings are retained past the synthesis step for this
thin-slice build, no transcripts beyond what's needed for the current turn.

## What this is not

No medical certification, no clinical claims, no emergency-dispatch
integration (a caregiver flag is a notification, not a 911 call). These are
explicitly out of scope for the hackathon build — see the main README.
