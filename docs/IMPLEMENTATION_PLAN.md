# Implementation plan

Architecture, current build status per component, and the open backlog. `PRD.md` says what
we're building and why, `PRINCIPLES.md` says the non-negotiables, `ROADMAP.md` says what order
we're working in and why — this doc says how, and what's actually done versus still open. Keep
this page current rather than writing a new doc when something changes — see
`CONTRIBUTING.md`.

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

- **ASR backend — DECIDED.** NVIDIA-hosted ASR via Nebius Token Factory, not local
  `faster-whisper`. Rationale and the offline-capability tradeoff are in `ROADMAP.md`'s
  "Decided: ASR backend" section. This unblocks [Issue #9](../../issues/9) (real voice I/O).
  `faster-whisper` stays in `hear.py` as a fallback/dev convenience, not the primary path.
- **Judge-accessible hosting — newly required, not yet decided.** The hackathon's rules page
  requires a live/testable demo link OR a test build — these aren't equivalent effort. A test
  build (our README's existing setup steps) is near-free but assumes the judge gets their own
  free `NEBIUS_API_KEY`; a hosted demo on Nebius AI Cloud compute costs some of our $50 credit
  + deploy effort but removes that friction *and* doubles as the required proof of deployment
  on sponsor infrastructure. Leaning test-build-first (cheapest), hosted demo as a stretch if
  credit/time allow. See `ROADMAP.md`'s "Judging requirements" table and
  [Issue #11](../../issues/11).
- **THINK model ID — tentatively decided, unverified.** Default is
  `nvidia/Llama-3_1-Nemotron-70B-Instruct-HF` (`pipeline/think.py`), chosen before Nebius's
  2025-11 Token Factory relaunch exposed a newer Nemotron 3 lineup (Nano 30B, Nano Omni,
  Super 120B, Ultra 550B — see nebius.com/services/token-factory/nemotron). **Nemotron 3 Nano**
  is the better fit for this project specifically: a compact MoE model optimized for efficient
  chat/reasoning matches the <2s-to-first-audio latency budget better than a dense 70B model,
  without giving up the "open-weight NVIDIA model" sponsor-tech requirement. Not switched in
  code yet — the exact Token Factory model-ID string for Nemotron 3 Nano needs confirming
  against a live key, same as the `NEBIUS_BASE_URL` question below. Bundle both checks into
  [Issue #1](../../issues/1) rather than opening a separate issue.
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

- [Issue #9](../../issues/9) — real voice I/O, the single biggest remaining
  hackathon-readiness risk: the demo today takes typed text and prints to a terminal, so
  nothing in the recorded video can show the product's own premise (a *voice* companion). Now
  unblocked (ASR backend decided above).
- **Judge-accessible hosting** — new, see "Open design decisions" above. Tracking issue to be
  filed.
- [Issue #1](../../issues/1) — wire a real `NEBIUS_API_KEY` and verify beat2/beat3's
  continuation path end to end (currently only verified in the no-key degraded path).
  Also confirms the `NEBIUS_BASE_URL` domain decision above.
- [Issue #3](../../issues/3) — Day-2 recall demo (a memory saved in one process run surfacing
  correctly in a later run, proving persistence isn't just in-memory-per-run).
- [Issue #5](../../issues/5) — record the submission video (needs voice I/O + hosting done
  first — see `ROADMAP.md`).
- [Issue #6](../../issues/6) — decide the Devpost submission representative.

Closed: [Issue #2](../../issues/2) (ASR backend) — decided, see above.

Not filed as an issue (lower priority, explicitly deferred per `README.md`'s Status section):
a caregiver-facing dashboard beyond the terminal panel. The old Issue #4 covered this; see its
closing comment for why it was replaced with a narrower, higher-priority voice-I/O issue
instead of being built as scoped.
