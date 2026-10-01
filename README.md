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

### Nebius access

Get a free key at [Nebius AI Studio](https://studio.nebius.ai/) (Token Factory). The hackathon
offers $25 in sponsor credits via activation code `NEBIUS-DEVPOST-GLOBAL26`, plus another $25
through the free [Nebius Builders Program](https://dev.nebius.com/builders) (which also unlocks
Tavily credits).

## Docs

- [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) — the handful of non-negotiables (honest
  disclosure, no medical claims, fail loud never fake) that every other doc defers to.
- [`docs/PRD.md`](docs/PRD.md) — product requirements: personas, explicit non-goals, and the
  demo script as the acceptance bar.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — what we're working on, in what order, and why — the
  single place to check "what's next." Also tracks the hackathon's actual judging requirements
  against our current status.
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — build status per component,
  open design decisions, and the known-issues backlog. We code from the PRD + roadmap + this
  plan, not from memory of a conversation.
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — the exact beat-by-beat script.
- [`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md) — no silent surveillance, no
  medical claims, what's stored and why.

## Status / what's not here yet

This is a thin vertical slice, intentionally. Out of scope for this build: weather/news, a
weekly digest, physical hardware, medical certification — see `docs/PRD.md`'s non-goals. See
open GitHub Issues and `docs/IMPLEMENTATION_PLAN.md` for the current remaining-work list, and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for how we work on this together.
