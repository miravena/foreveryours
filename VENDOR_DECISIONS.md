# Vendor decisions

One place to check "what did we pick and why" for every external dependency — so a decision
doesn't have to be re-litigated or re-discovered from code. Update this when a decision
changes; link the GitHub Issue/commit that changed it.

| Component | Decision | Status | Why / alternatives considered |
|---|---|---|---|
| **LLM (THINK)** | Nebius Token Factory, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | **Verified live** (PR #25: model inventory + beat2 end to end, 4.22s to first audio). Emits hidden reasoning tokens first, so test `enable_thinking: false` for latency (#17) | Required by hackathon rules (must use ≥1 NVIDIA open-weight model via Nebius). Nano chosen over Super/Ultra for latency fit under our <2s-to-first-audio budget. Fallback if unprovisioned: a Llama model (not sponsor-stack, but keeps the demo working) — see `.env.example`. |
| **LLM (AUDIT)** | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` via Nebius Token Factory (replaced Llama 3.1 8B, which returned 404, in PR #25) | Verified live (PR #25) | Background safety-recheck pass, off the critical path. **Candidate to replace it:** NVIDIA NemoGuard (Llama-Nemotron safety guard) — purpose-built for exactly this job (content-safety classification), and would add a second NVIDIA model for the tech score. **Availability on Token Factory unverified; check on key-day (`GET /v1/models`).** |
| **ASR (speech-to-text)** | Default: local `faster-whisper` (CPU, no key). Candidate: Nebius-hosted `nvidia/parakeet-tdt-1.1b` | **Decided: local `faster-whisper`.** Token Factory returns 404 on `/audio/transcriptions` (verified live, PR #25) | Local default chosen deliberately so the safety fast-path works with zero API dependency. Nebius ASR would strengthen the sponsor-stack story if it exists; test on key-day (`GET /v1/models`), don't assume. |
| **TTS (speak)** | Local `pyttsx3` / `espeak-ng` | Working, but robotic — flagged as a Design-criterion risk. **Linux bug: goes silent after ~19 sentences in one process ([#28](../../issues/28)), blocks hosting** | No Nebius TTS offering confirmed yet. If one exists, it's a straight upgrade for voice quality; until then, local is the only thing proven to produce real audio. |
| **Memory storage** | Flat JSON file per profile, on local disk (`memory/store.py`) | Working, proven to persist across process runs (Day-2 recall) | No database needed for a single-profile MVP; file-backed is simplest thing that's actually durable. Revisit only if multi-profile support becomes real scope. |
| **Judge-facing web demo (UI)** | Gradio (`webapp.py`) | Built, browser-tested (per-visitor isolated sessions, PR #26); not yet deployed | Fastest path to a real browser UI wrapping existing pipeline functions with no new logic. Alternatives considered: hand-rolled Flask/FastAPI + HTML (more control, much more build time for no judging benefit); Streamlit (similar tradeoffs to Gradio, less common for audio-first demos). |
| **Hosting for the web demo** | **Primary: Hugging Face Spaces** (free, zero-infra, Gradio-native). **Stretch: Nebius AI Cloud VM** (more setup, but double-counts for the "runs on Nebius" sponsor-tech requirement) | Not yet deployed to either | Spaces gets a judge-accessible link fastest, which is the actual deadline risk. The sponsor-tech requirement is satisfied either way since we call the Token Factory API at runtime regardless of where the UI is hosted — moving to a Nebius VM later is additive, not required. **Risk:** free-tier Spaces sleep when idle, so a judge's first click can hang waiting for a cold start — plan to keep the Space awake through the actual judging window (upgraded/always-on hardware for that window, or fall back to the Nebius VM stretch) rather than discovering this live. |
| **Static landing page** | Cloudflare Pages (`docs/index.html`) | Built, live | Free, zero setup, good for a stable project-overview link (screenshots, status, links to video/demo/repo) — but **cannot** run the actual pipeline (static-files-only), so it's a front door, not the demo itself. |
| **Credit protection on a public demo URL** | In-memory per-day request counter (`MAX_DAILY_REQUESTS`, default 50) | Built | Simplest thing that stops a shared public link from draining the whole Nebius credit balance; resets on process restart, which is fine for a hackathon-duration deployment. |

## Open vendor questions (need a live key to resolve)

Resolved by PR #25: the Nemotron 3 Nano model ID exists; Token Factory has no
audio-transcription endpoint; the activation-code credits work.

- Does Token Factory honour `chat_template_kwargs: {"enable_thinking": false}` on Nemotron 3 Nano, and how much latency does it save? ([#17](../../issues/17))
- Does Nebius offer any TTS model, and is it better than local espeak?
- Is NVIDIA NemoGuard available on Token Factory, as a safety-purpose-built replacement for the AUDIT model? (`GET /v1/models`)
