# Implementation plan

How it's built: architecture and the component map. `PRD.md` says what we're building and why,
`PRINCIPLES.md` says the non-negotiables, `ROADMAP.md` says the plan and why in this order,
`decisions/` says why each choice was made. **This page describes the system; it does not track
work.** What's open, blocked or due lives only on GitHub ([milestones](../../milestones),
[Issues](../../issues)). Keep this page current when the design changes — see `CONTRIBUTING.md`.

## Architecture

See `README.md`'s "Pipeline" section for the HEAR → fast-path → RECALL → THINK → SPEAK →
AUDIT/extraction diagram and the latency rationale — not repeated here, per
`CONTRIBUTING.md`'s "no separate architecture doc" rule; this doc is the component map, not a
second copy of the pipeline description.

**Disclosure is a hard invariant, not a default.** Every caregiver flag states explicitly
whether the senior was actually told, in the conversation — see `SAFETY_AND_PRIVACY.md` for
the design rationale and `caregiver.py`/`pipeline/orchestrator.py` for where it's enforced.

## Components

| Component | File | What it does |
|---|---|---|
| Fast-path safety check | `safety/fastpath.py` | regex-based, synchronous, continues into THINK after an immediate reassurance. "Falling asleep" false positives are excluded; bare "help me" is narrowed to anchored/qualified forms (see [ADR-005](decisions/ADR-005-safety-fastpath.md)) |
| Memory store | `memory/store.py` | caregiver facts always recalled, stopword pruning & semantic domain synonym expansion, dedupe on save, atomic writes |
| Caregiver flags | `caregiver.py` | `disclosed_to_senior` is a required, honest argument everywhere |
| THINK (model call) | `pipeline/think.py` | streamed, sentence-chunked (abbreviation-aware), facts/guardrails split in prompt, off-critical-path async memory extraction |
| SPEAK (TTS) | `pipeline/speak.py` | native subprocess `espeak-ng` CLI on Linux/macOS eliminates in-process C-buffer leak and 19-sentence silence bug ([ADR-001](decisions/ADR-001-tts-backend.md)); PowerShell `System.Speech` on Windows. Built for long sessions |
| HEAR (ASR) | `pipeline/hear.py` | wired with `--audio` into all CLI beats & `webapp.py`, backed by local `faster-whisper` (Token Factory has no ASR endpoint, PR #25), bundled with `samples/` audio |
| AUDIT (async safety pass) | `pipeline/audit.py` | runs off the critical path, considers both the senior's words and the reply, discloses via a spoken follow-up |
| Orchestrator | `pipeline/orchestrator.py` | ties the above together, graceful degradation without a live API key |
| CLI demo runner | `main.py` | The 4-beat demo script + interactive multi-turn session (`python main.py chat`), cross-platform audio playback (Windows/macOS/Linux) |
| Automated test suite | `tests/` | Unit tests for every pipeline stage plus benchmarks. Run in one process: `python -m unittest discover tests -v` |
| Cloud hosting | Cloudflare Pages (landing page), `app.py`, `packages.txt`, `scripts/deploy_hf_space.py` | Landing page on Pages; the judge-facing demo on HF Spaces with per-visitor sessions. Plan: [`ROADMAP.md`](ROADMAP.md) M5 |

## Design decisions

Each decision, with alternatives and reasoning, is an ADR in [`decisions/`](decisions/README.md):
TTS ([ADR-001](decisions/ADR-001-tts-backend.md)), THINK/AUDIT model
([ADR-002](decisions/ADR-002-think-audit-model.md)), hosting
([ADR-003](decisions/ADR-003-hosting.md)), ASR ([ADR-004](decisions/ADR-004-asr-backend.md)),
safety fast-path ([ADR-005](decisions/ADR-005-safety-fastpath.md)).

Facts that don't fit an ADR:

- **`NEBIUS_BASE_URL`** is `https://api.tokenfactory.nebius.com/v1` (Nebius first-party docs,
  docs.tokenfactory.nebius.com/api-reference/introduction; verified live in PR #25).
- **Judge-accessible hosting:** a test build assumes a judge signs up for their own
  `NEBIUS_API_KEY` mid-review, which is unrealistic at judging volume, so we host it ourselves
  with our key configured. README setup steps remain for collaborators and local runs.
- **Conversation history:** `webapp.py` and `main.py chat` keep per-session history
  (`MAX_HISTORY_TURNS = 4`), isolated from the durable cross-session `MemoryStore`.

## Out of scope

A caregiver-facing dashboard (explicitly deferred per `README.md`'s Status section) beyond the terminal panel.
