# ForeverYours

An older adult tells a general-purpose voice assistant "I fell earlier today and I'm scared." It
answers with sympathy, the turn ends, and nobody in the family is told. The assistants that are good
at conversation have no concept of the person who isn't in the room: the daughter who knows Dad
loves jazz, that his grandson is Leo, that driving is a sore subject, and that she is dropping off
groceries at 4 PM.

**ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't
there, and never reports anything to the family that it hasn't first said to him out loud.**

It is a voice-first companion built for people who cannot or will not use a screen: no app to learn,
no typing, no reading. The senior only talks. The caregiver briefs it once, sees what it knows and
what it flagged, and the family stays connected without anyone being watched.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/)
(Personal AI track, which permits either Nebius Token Factory or Nebius AI Cloud). This project
runs on Nebius Token Factory with open-weight NVIDIA Nemotron models; it does not use Nebius AI
Cloud.

**Live demo:** <https://huggingface.co/spaces/elevenbaselab/foreveryours>. No login: talk as the senior on the left (or click a
sample clip) and watch the caregiver side on the right. Each visitor gets a private demo household,
removed about an hour after the tab closes; recorded clips can stay in the web framework's cache
for up to about 70 minutes ([PRIVACY.md](docs/PRIVACY.md)).

## The three-beat demo

1. **Caregiver memo.** "Dad loves jazz, his grandson is Leo, avoid talking about driving. I'm
   dropping off groceries at 4 PM."
2. **Senior conversation.** Dad talks to the companion; it recalls Leo, avoids driving, mentions
   the 4 PM groceries — and the caregiver column shows what it was briefed and what it flagged,
   each item labelled permanent or temporary.
3. **A worrying remark.** If Dad says something that sounds like distress or confusion, the
   companion speaks an immediate, honest reassurance **and tells Dad so, in the conversation**
   ("I'm letting your family know right now") — never a silent report behind his back — then the
   conversation keeps going instead of dead-ending there.

## Known limitations

Written down on purpose: a judge or a family should know where this stops.

- A fall described in other words ("I'm on the floor and can't reach the phone") is not caught by
  the rules. It depends on the background backstop, which runs after the reply and, on Nemotron 3
  Super, caught every labelled event in our evaluation (Nano, the previous backstop, missed some,
  including falls; [ADR-016](docs/decisions/ADR-016-audit-model-super.md)). A small labelled set is
  not proof of coverage.
- Some crisis paraphrases come back SAFE from the backstop; the rules catch the direct phrases.
- Replies the rules do not cover are written by the model. It is told to use only what the family
  briefed or what Dad said. A sentence that names a relative nobody briefed, or says something about
  a family member that no memo and nothing Dad said contains, is dropped before it is spoken, and a
  "no news" line takes its place. Sentences about the caregiver herself are checked only when Dad
  asks about the family or the day, so her privacy and fall-alert answers are never cut. The check
  compares words, not meaning: it can drop a warm, true paraphrase, and an invented detail made only
  of words the memos happen to contain still passes.
- On the hosted demo the alert stays on the caregiver's half of the screen. Nothing reaches a phone.
- A flag is marked "Dad was told" once the spoken line is synthesised, not once it is heard; a
  browser that blocks autoplay still shows it as told.
- The hosted demo is slower than the command line (about 0.9 s to first audio there; a hosted turn
  took several seconds in our checks). No hosted latency figure is claimed.
- English only. Not a medical device, not a diagnosis, not an emergency dispatcher.

## Uptime monitor

`.github/workflows/uptime.yml` checks the hosted demo every 30 minutes (and on demand from the
Actions tab, with an optional dry run). A check passes when the Space runtime stage is `RUNNING`
and the app's `/config` answers 200; it counts as down only when two checks a few minutes apart
both fail. On down it opens an Issue labelled `outage`, assigned to both maintainers so GitHub
emails them; while that Issue stays open it adds at most one comment every 6 hours, and when
the checks pass again it comments how long the demo was down and closes it. An open Issue you
label `outage` by hand is adopted instead of a second one being opened. To silence it, disable
the workflow in the Actions tab, or close the Issue (the next failed check opens a fresh one).
Logic and tests: `scripts/uptime_check.py`, `tests/test_uptime_check.py`. It stops checking
after 2027-01-15.

## Pipeline

THINK and AUDIT run on Nebius Token Factory with open-weight NVIDIA Nemotron models; speech-to-text
and text-to-speech are local (`faster-whisper`, and Piper with `espeak-ng` as the fallback) and run
on neither Nebius service.

```
HEAR (speech-to-text via local faster-whisper, offline-resilient)
  -> fast-path safety check (rule-based, synchronous, microseconds)
  -> RECALL (memory search, scoped by caregiver-supplied context)
  -> THINK (NVIDIA Nemotron 3 Nano via Nebius Token Factory, streamed)
  -> SPEAK (streamed TTS, starts on the first sentence)
  -> [async, off the critical path] AUDIT (NVIDIA Nemotron 3 Super: reply safety + transcript
     distress/crisis backstop) + memory extraction (Nemotron 3 Nano)
```

Latency is treated as a first-class judging risk: the fast-path skips the LLM entirely for
emergency/distress phrases, THINK streams tokens straight into sentence-sized TTS chunks, and the
slower safety audit + memory-save step run in a background thread *after* the first sentence of
audio is already on its way out. Target: under 2 seconds to first audio on the common path.
AUDIT reads the senior transcript as well as the reply and grades `CRISIS`, `DISTRESS`, and
`UNSAFE` separately; malformed or failed audit output is recorded as unknown rather than safe.
**Measured:** 0.11s on the fast-path (no LLM); about 0.9s to first audio on the command-line beat
on a live Nemotron turn with reasoning off (was 4.22s before, PR #25 -> PR #29). **The browser
demo was slower than this** because AUDIT and memory extraction were joined onto the critical
path before anything returned to the browser (#81 red-team finding B1) -- fixed: that join is
gone (the next turn for the same session still joins the *previous* turn's background thread,
bounded, before starting, so memory writes stay ordered — see `webapp._join_previous_turn`), the
Nebius client has a bounded 20s timeout instead of the SDK's 600s default, and the page shows
"Companion is thinking..." the instant a turn starts. Six consecutive turns on the local page
after the fix measured 0.6-3.9s each (was 3-41s before), run live against Token Factory — a turn
can still wait on the *previous* turn's background thread (bounded, up to 10s) rather than on its
own. **Disclosure boundary:** if AUDIT flags a reply after the turn's response has already been handed
to the non-streaming browser path, the flag remains explicitly **NOT yet disclosed** and no
lifestyle note is saved. The streaming browser path and CLI pass an audio callback, so a
follow-up disclosure is delivered as a later audio chunk before the flag is marked as told.
Dated measurements are in
[`docs/WORK_LOG.md`](docs/WORK_LOG.md). The CLI (`main.py`/`chat`) now plays each reply sentence
as soon as it is synthesized (pipelined playback, [#17](../../issues/17)), so it reports both
**time to first WAV written** (synthesis) and **time to first sound heard** (the number a judge
actually perceives). Time to first sound heard is measured from player construction to the start
of the first *successful* playback, and excludes speech-to-text (ASR happens before the player is
constructed). On a box with no working audio player, the CLI reports **"No audio was played (no
working audio player)"** and prints no number -- it never reports a fake near-zero reading for
sound nobody heard ([#71](../../issues/71)). The browser demo streams the reply too: each
sentence's audio is sent to the page as soon as it is synthesized (`webapp.py`, `gr.Audio(streaming=True)`).

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
The page footer states which model does what, and each caregiver flag says whether the safety rules or the Nemotron backstop raised it.
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
- **Hugging Face Spaces** (the judge-facing link, issue #11): deploys run from GitHub Actions
  (`.github/workflows/deploy-space.yml`, see `HOW_TO_WORK_HERE.md` -> *Deploying the Space*);
  the Space shows the commit it runs as `Build: <sha7>`. Underneath, `scripts/deploy_hf_space.py`
  stages `app.py` + pipeline + `requirements.txt`/`packages.txt` with the Spaces config header
  and uploads them. `HF_TOKEN=... NEBIUS_API_KEY=... python scripts/deploy_hf_space.py <user>/<space>`;
  `--dry-run` builds the staging folder without uploading. The key goes in as a Space *secret*,
  never a file. Hugging Face needs a PRO account for a Gradio Space on the default
  `cpu-basic` hardware (ADR-017; the hardware is the `SPACE_HARDWARE` setting); on a free account
  (verified email, older than 30 days) add `--hardware zero-a10g` (ADR-003). The ZeroGPU outage of
  2026-10-27 and the hosting options are in
  [`docs/incidents/2026-10-27-space-outage.md`](docs/incidents/2026-10-27-space-outage.md). Each visitor gets an isolated, auto-deleted session (see `SAFETY_AND_PRIVACY.md`).
- **Cloudflare Tunnel (`cloudflared`)**: Exposes a running `webapp.py` to a secure public HTTPS URL via `cloudflared tunnel --url http://localhost:7860`.

Works the same with or without a key: without one, a distress/confusion phrase still gets the
immediate fast-path reassurance (no LLM needed for that), it just can't continue the
conversation past it — same graceful-degradation behavior as `main.py beat3`. Record or upload
a short clip and hit Send; the memory panel updates live underneath.

`MAX_DAILY_REQUESTS` (default **50**, keyed per browser session so one judge filling theirs up
never blocks another judge's link) caps how many turns actually reach Nebius Token Factory per
day once the app is public — an empty send, a turn that fails for lack of a key, and the offline
safety fast-path never count against it. The fast-path still answers at the cap: "I fell down" or
"I can't breathe" still gets its spoken reassurance and the caregiver flag, and only the paid
continuation after it is withheld (with a one-line cap notice); any other utterance at the cap
gets the daily-cap message. The deploy script and `docs/decisions/ADR-003-hosting.md`
use this same number. Bump it locally with `MAX_DAILY_REQUESTS=1000 .venv/bin/python webapp.py`
if you're iterating and hitting it. Audio is bounded before any speech recognition runs:
an upload over `MAX_AUDIO_UPLOAD_BYTES` (default 25 MB, also passed to Gradio as
`max_file_size`) or a recording longer than `MAX_AUDIO_SECONDS` (default 120) is refused, and a
recording that can't be decoded or transcribed gets a short "record again, or type instead"
reply that keeps the session; none of these count against the daily cap.

### Nebius access

Get a free key at [Nebius AI Studio](https://studio.nebius.ai/) (Token Factory). The hackathon
offers $25 in sponsor credits via activation code `NEBIUS-DEVPOST-GLOBAL26`, plus another $25
through the free [Nebius Builders Program](https://dev.nebius.com/builders) (which also unlocks
Tavily credits).

**Which NVIDIA models run where.** THINK (the reply) uses
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Token Factory; AUDIT (the background safety backstop)
uses `nvidia/nemotron-3-super-120b-a12b`. Each is overridable with `THINK_MODEL`
or `AUDIT_MODEL`. We chose AUDIT's model with a 36-row labelled eval across the NVIDIA models
Token Factory serves ([ADR-010](docs/decisions/ADR-010-audit-model-eval.md),
`scripts/audit_eval.py`):

| AUDIT model | Recall on true events | False flags | Cost per AUDIT call |
|---|---|---|---|
| Nemotron 3 Nano 30B | 0.63 | 0/17 | 0.000023 USD |
| Nemotron 3 Super 120B | 1.00 | 0/17 | 0.00011 USD |
| Nemotron 3 Ultra 550B | 0.95 | 0/17 | 0.00037 USD |

AUDIT defaults to Super ([ADR-016](docs/decisions/ADR-016-audit-model-super.md)). On the later
43-row set Nano's recall was 0.88, under our 0.90 floor, and Super's was 1.00; both had 0/17
false flags. Super costs about $0.0002 per AUDIT call (Nano about $0.00004) and measured a median
1.09 s (max 3.00 s) against Nano's 0.65 s (max 1.47 s); AUDIT runs after the reply, so that
time is off the critical path.

## Licences of the voice components

This repo is MIT. Two programs it starts are not:

- **espeak-ng** (GPL-3.0, <https://github.com/espeak-ng/espeak-ng>): the fallback voice, installed
  from `packages.txt`.
- **piper-tts** (GPL-3.0-or-later, <https://github.com/OHF-Voice/piper1-gpl>, bundles espeak-ng):
  the preferred voice, run as a separate program (the `piper` CLI, or `python -m piper.http_server`
  on the loopback interface). No Piper code is imported into this app.

Both are used at arm's length: this app sends a sentence and reads back a WAV. A Hugging Face Space
image built from this repo contains both programs; their source is at the links above. The Piper
voice `en_US-ljspeech-medium` is trained on the public-domain LJ Speech dataset
(<https://keithito.com/LJ-Speech-Dataset/>); the earlier `en_US-lessac-medium` voice is trained on
research-only data and is not used. Details and the reasoning:
[ADR-011](docs/decisions/ADR-011-voice-licence-and-warm-piper.md). Not legal advice.

## Self-judging

We score our own mock submissions against the real Devpost rubric before a real judge ever
sees it — see [`docs/SELF_JUDGING.md`](docs/SELF_JUDGING.md).

## Status / what's not here yet

This is a thin vertical slice, intentionally. Out of scope for this build: weather/news, a
weekly digest, physical hardware, medical certification. Current work, order, due dates and blockers live only on GitHub: [milestones](../../milestones)
and [Issues](../../issues). Plan and reasoning: [`docs/ROADMAP.md`](docs/ROADMAP.md). How we work
together: [`HOW_TO_WORK_HERE.md`](HOW_TO_WORK_HERE.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).
