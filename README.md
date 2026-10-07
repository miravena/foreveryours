# ForeverYours

**The companion the family briefs — your voice in Dad's day when you can't be there.**

ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't
there, and never tells the senior anything it hasn't already told him.

A voice-first AI companion for older adults. A caregiver gives it context once (a voice memo:
names, preferences, daily updates), and the senior gets a warm, low-friction voice conversation
that actually uses that context — while the caregiver gets honest safety flags, never silent
surveillance.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/)
(Personal AI track, which permits either Nebius Token Factory or Nebius AI Cloud). This project
runs on Nebius Token Factory with open-weight NVIDIA Nemotron models; it does not use Nebius AI
Cloud.

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

THINK and AUDIT run on Nebius Token Factory with open-weight NVIDIA Nemotron models; speech-to-text
and text-to-speech are local (`faster-whisper` and `espeak-ng`) and run on neither Nebius service.

```
HEAR (speech-to-text via local faster-whisper, offline-resilient)
  -> fast-path safety check (rule-based, synchronous, microseconds)
  -> RECALL (memory search, scoped by caregiver-supplied context)
  -> THINK (NVIDIA Nemotron 3 Nano via Nebius Token Factory, streamed)
  -> SPEAK (streamed TTS, starts on the first sentence)
  -> [async, off the critical path] AUDIT (safety pass) + memory extraction (via Nebius Nemotron)
```

Latency is treated as a first-class judging risk: the fast-path skips the LLM entirely for
emergency/distress phrases, THINK streams tokens straight into sentence-sized TTS chunks, and the
slower safety audit + memory-save step run in a background thread *after* the first sentence of
audio is already on its way out. Target: under 2 seconds to first audio on the common path.
**Measured:** 0.11s on the fast-path (no LLM); about 0.9s to first audio on the command-line beat
on a live Nemotron turn with reasoning off (was 4.22s before, PR #25 -> PR #29). **The browser
demo was slower than this** because AUDIT and memory extraction were joined onto the critical
path before anything returned to the browser (#81 red-team finding B1) -- fixed: that join now
only happens on a turn where the crisis tier fired (so the spoken disclosure still reaches the
browser), the Nebius client has a bounded 20s timeout instead of the SDK's 600s default, and the
page shows "Companion is thinking..." the instant a turn starts. Six consecutive turns on the
local page after the fix measured 0.6-1.1s each (was 3-41s before), run live against Token Factory.
Dated measurements are in
[`docs/WORK_LOG.md`](docs/WORK_LOG.md). The CLI (`main.py`/`chat`) now plays each reply sentence
as soon as it is synthesized (pipelined playback, [#17](../../issues/17)), so it reports both
**time to first WAV written** (synthesis) and **time to first sound heard** (the number a judge
actually perceives). The browser demo still plays one combined clip; sentence-level browser
streaming is tracked separately.

## Demo script

The exact beat-by-beat script (and what each beat is supposed to prove) is in
[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

## Safety & privacy design

[`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md) — no silent
surveillance, no medical claims, what's stored and why.

## Setup

```bash
# pyttsx3 (local TTS) needs the espeak-ng system package:
sudo apt-get install -y espeak-ng   # Linux (Debian/Ubuntu)
# brew install espeak-ng            # macOS
# Windows: espeak-ng isn't packaged for pip; install from
#   https://github.com/espeak-ng/espeak-ng/releases, then add it to PATH.
#   Also run with PYTHONUTF8=1 (PowerShell: $env:PYTHONUTF8=1; cmd: set PYTHONUTF8=1) --
#   the suite's emoji assertions need UTF-8, which Windows consoles don't default to.

python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in NEBIUS_API_KEY — see "Nebius access" below
.venv/bin/python main.py beat1 --audio samples/caregiver_memo.wav  # caregiver voice memo
.venv/bin/python main.py beat2 --audio samples/senior_jazz.wav     # senior turn with real voice
.venv/bin/python main.py beat3 --audio samples/senior_distress.wav # safety fast-path with voice
.venv/bin/python main.py beat4 --audio samples/senior_grandson.wav # day-2 recall with voice
.venv/bin/python main.py chat                                      # interactive multi-turn CLI session
# (Pass typed text arguments instead of --audio if running without sound, or add --no-play)
```

### Running Automated Tests

```bash
# Zero extra dependencies required (standard library unittest):
python -m unittest discover tests -v

# Or with pytest if installed:
pytest tests/
```

Before pushing, `scripts/smoke.sh` (~10s, no key needed) runs the tests plus `beat1`, `beat3`
and `day2` in a throwaway copy of the repo and checks each beat's output.

`beat1` runs fully offline. `beat2` needs `NEBIUS_API_KEY` set — it calls a real open-weight
model with no fallback, so without a key it fails loudly with a clear message rather than
returning a mocked reply. `beat3`'s immediate safety reassurance is offline (fast-path, no LLM),
but the turn then tries to continue into a real model call like beat2 does; without a key it
degrades gracefully to just the immediate reassurance instead of crashing.

## Demo video

The hackathon submission video is screen-recorded from the hosted browser demo (see
[`docs/VIDEO_SCRIPT.md`](docs/VIDEO_SCRIPT.md)); it replaces the earlier terminal
proof-of-concept clip, [`video/output/foreveryours_poc_demo.mp4`](video/output/foreveryours_poc_demo.mp4)
(1920x1080, 2:57, auto-generated CLI recordings with zero API key -- see
[`video/README.md`](video/README.md)), which is kept for development reference only and does not
appear in the submission.

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

### Cloudflare & Cloud Hosting

- **Cloudflare Pages**: Deploys the landing page and presentation directly from `docs/index.html` with zero build commands.
- **Hugging Face Spaces** (the judge-facing link, issue #11): `scripts/deploy_hf_space.py`
  stages `app.py` + pipeline + `requirements.txt`/`packages.txt` with the Spaces config header
  and uploads them. `HF_TOKEN=... NEBIUS_API_KEY=... python scripts/deploy_hf_space.py <user>/<space>`;
  `--dry-run` builds the staging folder without uploading. The key goes in as a Space *secret*,
  never a file. Each visitor gets an isolated, auto-deleted session (see `SAFETY_AND_PRIVACY.md`).
- **Cloudflare Tunnel (`cloudflared`)**: Exposes a running `webapp.py` to a secure public HTTPS URL via `cloudflared tunnel --url http://localhost:7860`.

Works the same with or without a key: without one, a distress/confusion phrase still gets the
immediate fast-path reassurance (no LLM needed for that), it just can't continue the
conversation past it — same graceful-degradation behavior as `main.py beat3`. Record or upload
a short clip and hit Send; the memory panel updates live underneath.

`MAX_DAILY_REQUESTS` (default **50**, keyed per browser session so one judge filling theirs up
never blocks another judge's link) caps how many turns actually reach Nebius Token Factory per
day once the app is public — an empty send, a turn that fails for lack of a key, and the offline
safety fast-path never count against it. The deploy script and `docs/decisions/ADR-003-hosting.md`
use this same number. Bump it locally with `MAX_DAILY_REQUESTS=1000 .venv/bin/python webapp.py`
if you're iterating and hitting it.

### Nebius access

Get a free key at [Nebius AI Studio](https://studio.nebius.ai/) (Token Factory). The hackathon
offers $25 in sponsor credits via activation code `NEBIUS-DEVPOST-GLOBAL26`, plus another $25
through the free [Nebius Builders Program](https://dev.nebius.com/builders) (which also unlocks
Tavily credits).

## Self-judging

We score our own mock submissions against the real Devpost rubric before a real judge ever
sees it — see [`docs/SELF_JUDGING.md`](docs/SELF_JUDGING.md).

## Status / what's not here yet

This is a thin vertical slice, intentionally. Out of scope for this build: weather/news, a
weekly digest, physical hardware, medical certification. Current work, order, due dates and blockers live only on GitHub: [milestones](../../milestones)
and [Issues](../../issues). Plan and reasoning: [`docs/ROADMAP.md`](docs/ROADMAP.md). How we work
together: [`HOW_TO_WORK_HERE.md`](HOW_TO_WORK_HERE.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).
