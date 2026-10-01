# ForeverYours

**The companion the family briefs — your voice in Dad's day when you can't be there.**

A voice-first AI companion for older adults. A caregiver gives it context once (a voice memo:
names, preferences, daily updates), and the senior gets a warm, low-friction voice conversation
that actually uses that context — while the caregiver gets honest safety flags, never silent
surveillance.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/)
(Personal AI track), on Nebius AI Cloud / Token Factory with open-weight NVIDIA models.

## The three-beat demo

1. **Caregiver memo.** "Dad loves jazz, his grandson is Leo, avoid talking about driving. I'm
   dropping off groceries at 4 PM."
2. **Senior conversation.** Dad talks to the companion; it recalls Leo, avoids driving, mentions
   the 4 PM groceries — with a live memory panel showing exactly what was retrieved and what's new.
3. **A worrying remark.** If Dad says something that sounds like distress or confusion, the
   companion speaks an immediate, honest reassurance **and tells Dad so, in the conversation**
   ("I'm letting your family know right now") — never a silent report behind his back — then the
   conversation keeps going instead of dead-ending there.

## Pipeline

```
HEAR (speech-to-text)
  -> fast-path safety check (rule-based, synchronous, microseconds)
  -> RECALL (memory search, scoped by caregiver-supplied context)
  -> THINK (open-weight model via Nebius Token Factory, streamed)
  -> SPEAK (streamed TTS, starts on the first sentence)
  -> [async, off the critical path] AUDIT (safety pass) + memory extraction
```

Latency is treated as a first-class judging risk: the fast-path skips the LLM entirely for
emergency/distress phrases, THINK streams tokens straight into sentence-sized TTS chunks, and the
slower safety audit + memory-save step run in a background thread *after* the first sentence of
audio is already on its way out. Target: under 2 seconds to first audio on the common path.

## Demo script

The exact beat-by-beat script (and what each beat is supposed to prove) is in
[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

## Safety & privacy design

[`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md) — no silent
surveillance, no medical claims, what's stored and why.

## Setup

```bash
# pyttsx3 (local TTS) needs the espeak-ng system package on Linux:
sudo apt-get install -y espeak-ng

python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in NEBIUS_API_KEY — see "Nebius access" below
.venv/bin/python main.py beat1   # caregiver memo
.venv/bin/python main.py beat2   # senior turn, uses memory + a real model call
.venv/bin/python main.py beat3   # safety fast-path, then the conversation continues
```

`beat1` runs fully offline. `beat2` needs `NEBIUS_API_KEY` set — it calls a real open-weight
model with no fallback, so without a key it fails loudly with a clear message rather than
returning a mocked reply. `beat3`'s immediate safety reassurance is offline (fast-path, no LLM),
but the turn then tries to continue into a real model call like beat2 does; without a key it
degrades gracefully to just the immediate reassurance instead of crashing.

## Web demo (judge-facing, same pipeline)

[`webapp.py`](webapp.py) wraps the exact same pipeline in a one-page browser UI (mic in, reply
audio out, live memory/flags panel) — no new pipeline logic, just a UI on top of `run_turn`.
This is what we'll host as the "working demo" link the hackathon requires; see
[`docs/ROADMAP.md`](docs/ROADMAP.md) and [`VENDOR_DECISIONS.md`](VENDOR_DECISIONS.md) for why.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in NEBIUS_API_KEY for the full pipeline; works without one too
.venv/bin/python webapp.py
# open http://localhost:7860
```

Works the same with or without a key: without one, a distress/confusion phrase still gets the
immediate fast-path reassurance (no LLM needed for that), it just can't continue the
conversation past it — same graceful-degradation behavior as `main.py beat3`. Record or upload
a short clip and hit Send; the memory panel updates live underneath.

`MAX_DAILY_REQUESTS` (default 50) caps how many turns the app will run per day once it's
public, so a shared link can't burn through the whole Nebius credit balance — bump it locally
with `MAX_DAILY_REQUESTS=1000 .venv/bin/python webapp.py` if you're iterating and hitting it.

### Nebius access

Get a free key at [Nebius AI Studio](https://studio.nebius.ai/) (Token Factory). The hackathon
offers $25 in sponsor credits via activation code `NEBIUS-DEVPOST-GLOBAL26`, plus another $25
through the free [Nebius Builders Program](https://dev.nebius.com/builders) (which also unlocks
Tavily credits).

## Status / what's not here yet

This is a thin vertical slice, intentionally. Out of scope for this build: weather/news, a
weekly digest, physical hardware, medical certification. See open GitHub Issues for the current
remaining-work list, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for how we work on this together.
