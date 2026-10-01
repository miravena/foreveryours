# Implementation plan

Architecture, current build status per component, and the open backlog. `PRD.md` says what
we're building and why; this says how, and what's actually done versus still open. Keep this
page current rather than writing a new doc when something changes — see `CONTRIBUTING.md`.

## Architecture

See `README.md`'s "Pipeline" section for the HEAR → fast-path → RECALL → THINK → SPEAK →
AUDIT/extraction diagram and the latency rationale — not repeated here, per
`CONTRIBUTING.md`'s "no separate architecture doc" rule; this doc is status and backlog, not a
second copy of the pipeline description.

**Disclosure is a hard invariant, not a default.** Every caregiver flag states explicitly
whether the senior was actually told, in the conversation — see `SAFETY_AND_PRIVACY.md` for
the design rationale and `caregiver.py`/`pipeline/orchestrator.py` for where it's enforced.

## Component status

| Component | File | Status |
|---|---|---|
| Fast-path safety check | `safety/fastpath.py` | Done — regex-based, synchronous, continues into THINK after an immediate reassurance (not a dead end) |
| Memory store | `memory/store.py` | Done — caregiver facts always recalled, conversation memories overlap-searched, dedupe on save, atomic writes |
| Caregiver flags | `caregiver.py` | Done — `disclosed_to_senior` is a required, honest argument everywhere |
| THINK (model call) | `pipeline/think.py` | Done — streamed, sentence-chunked (abbreviation-aware), facts/guardrails split in the prompt |
| SPEAK (TTS) | `pipeline/speak.py` | Done — `pyttsx3`, local/offline, per-turn-unique filenames |
| HEAR (ASR) | `pipeline/hear.py` | **Not wired into the demo path** — `faster-whisper` integration exists but `main.py`'s beats take text input, not real audio. See "Real voice I/O" below. |
| AUDIT (async safety pass) | `pipeline/audit.py` | Done — runs off the critical path, considers both the senior's words and the reply, discloses via a spoken follow-up |
| Orchestrator | `pipeline/orchestrator.py` | Done — ties the above together, graceful degradation without a live API key |
| CLI demo runner | `main.py` | Done for the three-beat script; terminal-only (no caregiver-facing UI) |

## Open design decisions

- **ASR backend** (tracked as [Issue #2](../../issues/2)): NVIDIA-hosted ASR via Nebius Token
  Factory vs. local `faster-whisper`. Tradeoff is latency/cost (hosted, consistent with THINK's
  provider) vs. offline-capability (local, consistent with the fast-path's "works with no key"
  property). Not yet decided — block on this before wiring real voice I/O, since it changes
  `hear.py`'s shape.
- **`NEBIUS_BASE_URL` domain**: changed to `https://api.studio.nebius.com/v1` based on a
  secondary source during a code review; **unverified against a live key** (see
  `pipeline/nebius_client.py`'s comment). Confirm once someone has a real `NEBIUS_API_KEY` —
  tracked in [Issue #1](../../issues/1).
- **Conversation history across turns**: each beat today is a single, independent turn (no
  memory of what was said earlier *in the same conversation*, only durable facts saved across
  sessions). Explicitly deferred — not needed for the three-beat demo script, but a real
  caregiver/senior conversation would span many turns. No issue filed yet; file one if this
  becomes a priority before the deadline.

## Known-issues backlog (seeded from the first adversarial review, 2026-10-01)

Fixed in [PR #7](../../pull/7) (merge once a live key confirms the continuation path): fast-path
dead-ending, caregiver-recall reliability, disclosure-honesty gaps, inverted audit check,
audio-overwrite bug, sentence-chunking on abbreviations, durable-memory substring false
positives, non-atomic writes, and doc/code drift in `SAFETY_AND_PRIVACY.md`/`DEMO_SCRIPT.md`.

Still open, tracked as GitHub Issues:

- **Real voice I/O** — the single biggest remaining hackathon-readiness risk: the demo today
  takes typed text and prints to a terminal, so nothing in the recorded video can show the
  product's own premise (a *voice* companion). See the issue for exact scope.
- [Issue #1](../../issues/1) — wire a real `NEBIUS_API_KEY` and verify beat2/beat3's
  continuation path end to end (currently only verified in the no-key degraded path).
  Also confirms the `NEBIUS_BASE_URL` domain decision above.
- [Issue #2](../../issues/2) — decide the ASR backend (blocks real voice I/O).
- [Issue #3](../../issues/3) — Day-2 recall demo (a memory saved in one process run surfacing
  correctly in a later run, proving persistence isn't just in-memory-per-run).
- [Issue #5](../../issues/5) — record the submission video.
- [Issue #6](../../issues/6) — decide the Devpost submission representative.

Not filed as an issue (lower priority, explicitly deferred per `README.md`'s Status section):
a caregiver-facing dashboard beyond the terminal panel. The old Issue #4 covered this; see its
closing comment for why it was replaced with a narrower, higher-priority voice-I/O issue
instead of being built as scoped.
