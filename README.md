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
   companion flags the caregiver immediately **and tells Dad so, honestly, in the conversation**
   ("I'm letting your family know right now") — never a silent report behind his back.

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
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in NEBIUS_API_KEY — see "Nebius access" below
.venv/bin/python main.py beat1                               # caregiver memo
.venv/bin/python main.py beat2 "Hi, how's it going today? By the way, my daughter is visiting tomorrow."   # senior turn, uses memory
.venv/bin/python main.py beat3 "I fell down earlier and I'm scared"  # safety fast-path
.venv/bin/python main.py beat4 "Who is visiting me tomorrow?"        # day-2 recall (persistence)
```

`beat1` and `beat3` run fully offline (no API key needed — the fast-path and local TTS don't call
Nebius). `beat2` needs `NEBIUS_API_KEY` set, since it calls a real open-weight model; without a
key it fails loudly with a clear message rather than returning a mocked reply.

### Nebius access

Get a free key at [Nebius AI Studio](https://studio.nebius.ai/) (Token Factory). The hackathon
offers $25 in sponsor credits via activation code `NEBIUS-DEVPOST-GLOBAL26`, plus another $25
through the free [Nebius Builders Program](https://dev.nebius.com/builders) (which also unlocks
Tavily credits).

## Status / what's not here yet

This is a thin vertical slice, intentionally. Out of scope for this build: weather/news, a
weekly digest, physical hardware, medical certification. See open GitHub Issues for the current
remaining-work list, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for how we work on this together.
