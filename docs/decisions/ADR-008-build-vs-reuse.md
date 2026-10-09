# ADR-008: Build vs reuse — what we keep custom and what we adopt from open source

**Status:** Proposed
**Date:** 2026-10-09
**Decided by:** Team (maintainers) — awaiting review
**Affects:** `pipeline/speak.py`, `memory/store.py`, `VENDOR_DECISIONS.md`, ADR-001
**Related issue:** [#52](../../issues/52) (better offline TTS), [#14](../../issues/14) (what makes this different)

## Question

Are we rebuilding things that open-source projects or existing products already solve, and for
each component: reuse, or keep ours, and why?

## Context

`VENDOR_DECISIONS.md` records which vendors we picked, not what we chose not to build. A
scan on 2026-10-09 (sources at the end) checked each component against current OSS and
products. Checked against primary pages (repo or model card) unless marked *unverified*.

## Components

| Component | What we have | Existing option | Verdict |
|---|---|---|---|
| **TTS** | `espeak-ng` CLI. Robotic; accepted Design-score risk (ADR-001) | **Kokoro-82M**: Apache-2.0, 82M params, 54 voices / 8 languages (v1.0). **Piper**: now **GPL-3.0** (see below) | **Reuse — trial Kokoro first** (#52) |
| **Memory retrieval** | 416-line JSON store; keyword overlap | **Mem0** (Apache-2.0, ~67k stars; `user_id` scoping, self-host via Docker). **Graphiti** (Apache-2.0, ~32k stars; needs a graph DB; facts get validity windows). **Letta** (Apache-2.0, ~25k stars; an agent runtime, not a library) | **Split.** Replace the *retrieval* with embeddings. Keep the *privacy layer* ours |
| **Memory privacy** (`caregiver_only` never spoken, scopes, supersession) | `MemoryScope`, `PrivacyLevel` | None offers "never speak this to the senior" as a guarantee | **Keep.** A leak here is the product's worst failure; it must be code we can test |
| **Voice loop** (turn-taking, barge-in, streamed sentence-to-TTS) | Hand-built `sentence_chunks`, pipelined playback | **Pipecat** (BSD-2, ~16k stars; lists Kokoro, Piper, Whisper, SmallWebRTC). **LiveKit Agents** (Apache-2.0; tied to a WebRTC server) | **Keep for now.** Adopting means WebRTC; Gradio-on-HF-Spaces support was *not* documented on the Pipecat page. Revisit after submission |
| **Safety fast-path** | 143 lines of rules (ADR-005) | **Llama Guard**, **NeMo Guardrails** (Apache-2.0), Nemotron Safety Guard | **Keep.** Generic moderation, not elder distress/confusion. No guard model on Token Factory (#56). Self-harm classifiers also degrade on machine-generated text (NAACL 2025 industry paper) |
| **ASR** | `faster-whisper` | already OSS | Reused |
| **Orchestration, UI, daemon** | plain Python, Gradio, 28-line `tick()` | LangGraph etc.; APScheduler | **Keep.** No gain at this size |

## Products

| Product | Status (2026-10-09) | Relation |
|---|---|---|
| **ElliQ** (Intuition Robotics) | Active. Companion app for families/caregivers since ElliQ 2.0; Washington Medicaid reimbursement code (Apr 2026); NY State programme | Closest product. A **device** with proactive companionship and a caregiver app; the caregiver views the senior, rather than briefing the companion. *Whether its caregiver app lets a caregiver brief the companion is unverified* |
| **Alexa Together** | **Discontinued** — Amazon note dated 2025-05-21; replaced by Alexa Emergency Assist | No longer a competitor. *Correction to an earlier informal claim* |
| **ChatGPT / Gemini voice** | Active | See #14: the answer stays "briefed by the person who isn't there, and never tells the senior anything it hasn't already told him" |

## What is actually different

No OSS project or product found provides (1) a caregiver who *briefs* the companion, or (2)
disclosure to the senior before any report to the family, enforced in code. The custom code
that carries that is small: the memory privacy layer, `safety/fastpath.py`, and the
disclosure flow in the orchestrator. Everything else is glue, where mature OSS is likely
better.

## Decision

**We propose:** trial Kokoro for TTS (#52); move memory *retrieval* to embeddings behind the
existing store interface and privacy filter; keep the voice loop, safety fast-path, privacy
layer and orchestration; record Pipecat/LiveKit as the post-submission exit.

## Rationale

Voice quality is the largest visible gap and the cheapest to close: a contained change in
`speak.py`. The privacy layer and fast-path are where our value and our risk both sit, so
they stay code we own and test. The voice-loop swap costs days and a transport change, with
no judging payoff before the deadline.

## Consequences

- **Unlocked:** better voice without new infrastructure; stronger recall than keyword overlap.
- **Locked in to:** Kokoro's `espeak-ng` dependency (already ours) and a model download.
- **Licence gotcha:** this repo is MIT. Kokoro (Apache-2.0) fits. **Piper's active repo
  (OHF-Voice/piper1-gpl) is GPL-3.0**; the original MIT repo was archived Oct 2025 (secondary
  source). Using Piper means a licence decision, so it is not the default candidate. #52
  currently lists Piper first; this ADR would re-order it.
- **Not yet measured:** no CPU latency figure for Kokoro on our hardware or on HF Spaces free
  tier. #52's acceptance criteria require it before adoption: beat2 time-to-first-sound
  against the current number in `WORK_LOG.md`.
- **Unconfirmed:** whether Mem0 runs with local embeddings (default embedder is OpenAI's);
  whether Mem0 filters on metadata beyond `user_id`. Embeddings alone may be enough, in which
  case Mem0 is unnecessary.

## When to revisit

- Kokoro misses the <2s to first audio budget, or HF Spaces cannot hold the model.
- Post-submission, if barge-in or real-time interruption becomes scope (Pipecat/LiveKit).
- ElliQ or another product ships caregiver-briefs-the-companion.

## Sources (checked 2026-10-09)

- Kokoro-82M model card: <https://huggingface.co/hexgrad/Kokoro-82M>
- Piper (active, GPL-3.0): <https://github.com/OHF-Voice/piper1-gpl>
- Mem0: <https://github.com/mem0ai/mem0> · Graphiti: <https://github.com/getzep/graphiti> · Letta: <https://github.com/letta-ai/letta>
- Pipecat: <https://github.com/pipecat-ai/pipecat> · LiveKit comparison (vendor-authored): <https://livekit.io/field-guides/guide/livekit-vs-pipecat>
- Alexa Together retired: <https://www.aboutamazon.com/news/devices/alexa-together-is-helping-bridge-the-miles-between-families>
- ElliQ 2.0 caregiver app: <https://www.robotics247.com/article/intuition_robotics_launches_elliq_2.0_hardware_software_app_families_caregivers>
- Self-harm classifiers on machine-generated text: <https://preview.aclanthology.org/setup/2025.naacl-industry.15>
