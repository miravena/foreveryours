# ADR-008: Build vs reuse — what we keep custom and what we adopt from open source

**Status:** Proposed
**Date:** 2026-10-09
**Decided by:** Team (maintainers) — awaiting review
**Affects:** `pipeline/speak.py`, `memory/store.py`, `VENDOR_DECISIONS.md`, ADR-001
**Related issue:** [#52](../../issues/52) (better offline TTS), [#14](../../issues/14) (what makes this different), [#88](../../issues/88), [#104](../../issues/104) (disclosure gaps)

## Question

Are we rebuilding things that open-source projects or existing products already solve, and for
each component: reuse, or keep ours, and why?

## Context

`VENDOR_DECISIONS.md` records which vendors we picked, not what we chose not to build. On
2026-10-09 we checked each component against current OSS and products, then had the draft
reviewed independently twice (OpenAI Codex with live web search, and Claude Opus with web
search). Both reviews were told to re-verify every claim and look for omissions. This version
folds in what they found, including three errors in the first draft. Claims are checked
against primary pages (repo, LICENSE, model card, vendor page) unless marked *unverified*.

## Components

| Component | What we have | Existing option | Verdict |
|---|---|---|---|
| **TTS** | `espeak-ng` CLI. Robotic; accepted Design-score risk (ADR-001) | **Kokoro-82M** (Apache-2.0, 82M params, 54 voices / 8 languages, v1.0). Runtimes/alternatives: **kokoro-onnx** (MIT runtime), **KittenTTS Nano 0.8** (Apache-2.0, 15M), **Pocket TTS** (MIT code, CC-BY-4.0 weights), **sherpa-onnx** (Apache-2.0 engine; model licences vary), **MeloTTS** (MIT; stale since 2024-12). **Piper** now **GPL-3.0** | **Reuse — trial Kokoro, with a measured shortlist** (#52). See licence note |
| **Memory retrieval** | 416-line JSON store; keyword overlap with stopword pruning and synonym expansion | **Mem0** (Apache-2.0, ~67k stars; local HF embeddings and metadata filters are documented). **Graphiti** (Apache-2.0, ~32k; needs a graph DB; validity windows). **Letta** (Apache-2.0, ~25k; agent runtime, development moved to `letta-code`). Lighter: sentence-transformers + MiniLM (Apache-2.0), LangMem (MIT) | **Conditional trial.** Keep current retrieval until a local embedding model measurably beats it on representative recall without breaking privacy, expiry or supersession. Try hybrid (lexical + embedding) rather than a replacement |
| **Memory privacy** | `MemoryScope`, `PrivacyLevel`, filtering | Mem0's metadata filters exist but Mem0 documents backend-dependent limits (custom metadata silently dropped on Weaviate) | **Keep ours**, and say plainly what it guarantees today (see below) |
| **Voice loop** | Hand-built `sentence_chunks`, pipelined playback; no barge-in | **FastRTC** (MIT, Gradio's own real-time voice library; `ReplyOnPause` with barge-in, Kokoro TTS, HF Spaces deployment guide; may need TURN). **Pipecat** (BSD-2; local audio, WebSocket and WebRTC transports). **LiveKit Agents** (Apache-2.0; console mode works without a server, browser deployment uses one) | **Keep for submission; trial FastRTC time-boxed** if the <2s budget allows. Earlier draft said adopting Pipecat "means WebRTC": that was wrong |
| **Safety fast-path** | 149 lines of rules (ADR-005) | **NeMo Guardrails** (Apache-2.0; programmable rails with custom Python actions). **Llama Guard** (Llama licence) and **Nemotron Safety Guard** (NVIDIA Open Model licence). **Granite Guardian 3.3** (Apache-2.0). RoBERTa GoEmotions (MIT) | **Keep the fast-path.** Evaluate Granite Guardian or an emotion classifier as a *supplement* to the background audit only, never as a narrowing of the rules |
| **ASR** | `faster-whisper` (MIT) | already OSS | Reused |
| **Orchestration, UI, daemon** | plain Python, Gradio, 28-line `daemon.py` | LangGraph; APScheduler | **Keep.** No demonstrated need |

## Products

| Product | Status (checked 2026-10-09) | Relation |
|---|---|---|
| **ElliQ** (Intuition Robotics) | Active. Caregivers can send messages and suggest reminders and wellness goals (accepted by the senior). Washington Medicaid coverage announced 2026-03-18 for eligible in-home recipients; NY State programme | Closest product. A **device**. Caregivers contribute reminders and goals; whether they can give it a confidential narrative brief is *unverified* |
| **inTouch** (intouch.family) | Active. Asks family for interests, hobbies, family information, health considerations and conversation preferences, then uses them to initialise its AI conversations | **A direct precedent for caregiver briefing.** The earlier claim that no product offers it was wrong |
| **Meela**, **Joy Calls**, **Sentai** | Active, commercial. Family-provided background and family-facing insights or alerts | Same space; details are from vendor pages and secondary coverage |
| **Alexa Together** | **Discontinued**; Amazon's note is dated 2025-05-21 and points to Alexa Emergency Assist (feature parity not established) | Not a competitor |
| **ChatGPT / Gemini voice** | Active | See #14 |

## What is actually different

Caregiver briefing alone is **not** distinctive. inTouch and ElliQ both take caregiver input.
What we can defend is narrower: a **private-scoped caregiver brief** (items marked
`caregiver_only`) plus **disclosure-first alerts**. No product we found documents disclosing
to the senior before alerting family, but public pages do not show enforcement, so that is
*unverified* for competitors.

**What our code does today, which is less than the README sentence says:**
- It enforces truthful *recording*: `disclosed_to_senior` has no default, so every flag states
  whether the senior was told. It does not enforce *ordering*.
- The fast-path records a flag as disclosed before the disclosure is synthesised
  (`pipeline/orchestrator.py:192`). The audit path raises the family flag even if disclosure
  failed, recording `False` (`orchestrator.py:392`). Memory-conflict escalation records
  `False` (`memory/store.py:222`). Even when disclosure succeeds, "disclosed" means audio was
  synthesised, not that the senior heard it (#11; #88; #104).
- `caregiver_guardrails()` loads `caregiver_only` avoid/never items into the senior-facing
  prompt (`memory/store.py:321`, `think.py`), so "never spoken" is partly a prompt rule that
  the model must follow, not only a code filter.

The accurate pitch is "built so the senior is told first, with the gaps tracked", not "enforced
in code". The README and Devpost sentence should be checked against this before submission
(#14, #20).

## Decision

**We propose:** trial Kokoro for TTS (#52) against a shortlist, measured on beat2; trial
embeddings or hybrid retrieval behind the existing store interface and privacy filter; keep
the voice loop for submission and time-box a FastRTC trial; keep the safety fast-path, privacy
layer and orchestration; narrow the differentiation claim as above.

## Rationale

Voice quality is the largest visible gap and a contained change in `speak.py`, but nothing
has been measured on our hardware. The privacy layer and fast-path are where our value and
risk sit, so they stay code we own and test, with their current limits stated. Retrieval is
commodity, but "stronger recall" is a prediction until measured.

## Consequences

- **Unlocked:** better voice without new infrastructure, if latency holds; a documented exit
  path for the voice loop.
- **Licence note (corrects the first draft):** this repo is MIT. The first draft said Kokoro
  fits and Piper needs a decision; that did not hold. Kokoro's English path installs
  `misaki[en]`, which pulls `phonemizer-fork` (GPL-3) and `espeakng-loader` (bundles
  eSpeak NG, GPL), and Piper embeds eSpeak NG too. We already call the eSpeak NG CLI as a
  separate process. Treat Kokoro and Piper alike: both need a recorded licence decision (engine
  version, integration boundary, whether a hosted Space is "distribution", voice-model terms).
  `kokoro-onnx` and `sherpa-onnx` have not had their dependency licences checked. This is a
  licensing question for the maintainers, not one we can settle here.
- **Not yet measured:** Kokoro/FastRTC CPU latency on HF Spaces free tier (2 vCPU, 16 GB per
  HF docs) or locally; embedding recall; the `WORK_LOG.md` baseline. #52's criteria require
  these before adoption.
- **Unverified:** that no memory framework offers an end-to-end "never speak this"
  guarantee; how ElliQ and inTouch handle disclosure; Meela's onboarding form; that no guard
  model is on Token Factory *for our account* (#56 recorded a full-list check).
- **Self-harm classifier evidence is narrow:** the NAACL 2025 paper shows one detector
  degrading on machine-generated text. It does not show how classifiers handle human senior
  speech, so it is not a reason against them.

## When to revisit

- Kokoro or FastRTC misses the <2s to first audio budget, or the Space cannot hold the model.
- A licence review rules out the GPL-dependent TTS options.
- ElliQ, inTouch or another product documents disclosure-first alerts.
- Post-submission, if barge-in becomes scope (FastRTC, Pipecat or LiveKit).

## Provenance and cost (2026-10-09)

Who and what produced this ADR, so the cost of the research is tracked next to the decision.
Dollar figures are **list-price equivalents** of the tokens used, not necessarily what was
billed (the Claude usage ran on a flat-rate plan). Claude token counts and costs come from
Claude Code's own OpenTelemetry usage metrics; Codex counts come from its session log.
Totals include web search/fetch helper calls but not per-search tool fees.

| Role | Harness : model | Effort | Input (uncached / cache read / cache write) | Output | List-price cost |
|---|---|---|---|---|---|
| Scan, drafting, revisions | claude-code : claude-sonnet-5-5 | medium | 70 / 3,498,334 / 329,779 | 28,310 | $2.30 |
| Web search and fetch helper | claude-code : claude-haiku-5-5 | n/a | 367,429 / 0 / 0 | 28,554 | $0.19 (telemetry figure) |
| Independent review 1 | claude-code : claude-opus-5-5 (subagent) | unknown (harness default) | 34 / 1,168,851 / 88,824 | 12,215 | $0.92 |
| Independent review 2 | codex : gpt-6.1-sol, live web search, read-only | high | 146,617 / 2,502,400 cached / n/a | 11,900 (1,881 reasoning) | $0.66 |
| **Total** | | | | | **about $4.08** |

Rates used ($ per million tokens). Claude Opus 5.5: $4 input, $20 output, $0.20 cache read, $5
cache write (5-minute). Claude Sonnet 5.5: $2 input, $10 output, $0.20 cache read, $4 cache
write (1-hour). Both reproduce the telemetry cost to the cent. Claude Haiku 5.5 is $0.10 / $0.50
for prompts up to 100K tokens and more beyond, so its figure is the telemetry number rather
than a rate-card calculation. gpt-6.1-sol: $2 input, $0.10 cached input, $10 output; **these
come from a third-party pricing aggregator and one news article, not an OpenAI page**, so treat
the Codex cost as an estimate. Claude rates are from Anthropic's published model table as
cached on 2026-10-06. The Sonnet row covers the whole working session, including the first
scan and the two drafts, not only the review rounds. The Opus review and the Codex review
each ran once.

## Sources (checked 2026-10-09)

- Kokoro-82M: <https://huggingface.co/hexgrad/Kokoro-82M> · misaki deps: <https://github.com/hexgrad/misaki/blob/main/pyproject.toml> · kokoro-onnx: <https://github.com/thewh1teagle/kokoro-onnx>
- Piper (active, GPL-3.0): <https://github.com/OHF-Voice/piper1-gpl> · original (MIT, archived 2025-10-06): <https://github.com/rhasspy/piper>
- KittenTTS: <https://github.com/KittenML/KittenTTS> · Pocket TTS: <https://github.com/kyutai-labs/pocket-tts> · sherpa-onnx: <https://github.com/k2-fsa/sherpa-onnx>
- Mem0: <https://github.com/mem0ai/mem0> (metadata filtering: <https://docs.mem0.ai/open-source/features/metadata-filtering>) · Graphiti: <https://github.com/getzep/graphiti> · Letta: <https://github.com/letta-ai/letta>
- FastRTC: <https://github.com/gradio-app/fastrtc> · deployment: <https://fastrtc.org/deployment/> · Pipecat: <https://github.com/pipecat-ai/pipecat> · LiveKit startup modes: <https://docs.livekit.io/agents/server/startup-modes/>
- NeMo Guardrails: <https://github.com/NVIDIA-NeMo/Guardrails> · Granite Guardian: <https://huggingface.co/ibm-granite/granite-guardian-3.3-8b> · Nemotron Safety Guard: <https://huggingface.co/nvidia/Llama-3.1-Nemotron-Safety-Guard-8B-v3>
- Self-harm classifiers on machine text: <https://aclanthology.org/2025.naacl-industry.15>
- ElliQ FAQ: <https://elliq.com/pages/faqs> · ElliQ 2.0 (2022-12-07): <https://blog.elliq.com/announcing-the-launch-of-elliq-2.0> · Washington Medicaid: <https://www.prnewswire.com/news-releases/elliq-the-ai-smart-care-device-to-help-washington-medicaid-recipients-stay-independent-engaged-and-healthy-302717658.html>
- inTouch FAQ: <https://intouch.family/en/intouch-faq> · Joy Calls: <https://joycalls.ai/> · Meela: <https://www.businesswire.com/news/home/20250911525548/en/>
- Alexa Together retired: <https://www.aboutamazon.com/news/devices/alexa-together-is-helping-bridge-the-miles-between-families>
- HF Spaces hardware: <https://huggingface.co/docs/hub/spaces-overview#hardware-resources>
