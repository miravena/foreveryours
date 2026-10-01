# Vendor decisions

One place to check "what did we pick and why" for every external dependency — so a decision
doesn't have to be re-litigated or re-discovered from code. Update this when a decision
changes; link the GitHub Issue/commit that changed it.

| Component | Decision | Status | Why / alternatives considered |
|---|---|---|---|
| **LLM (THINK)** | Nebius Token Factory, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Endpoint confirmed from first-party docs; **model ID not yet verified against a live key** | Required by hackathon rules (must use ≥1 NVIDIA open-weight model via Nebius). Nano chosen over Super/Ultra for latency fit under our <2s-to-first-audio budget. Fallback if unprovisioned: a Llama model (not sponsor-stack, but keeps the demo working) — see `.env.example`. |
| **LLM (AUDIT)** | Meta Llama 3.1 8B via Nebius Token Factory | Not yet live-tested | Cheap/fast model for a background safety-recheck pass; doesn't need to be the NVIDIA model since THINK already satisfies that requirement. |
| **ASR (speech-to-text)** | Default: local `faster-whisper` (CPU, no key). Candidate: Nebius-hosted `nvidia/parakeet-tdt-1.1b` | Local path works today; Nebius path is an **unverified hypothesis** — nobody has confirmed Token Factory exposes an audio-transcription endpoint at all | Local default chosen deliberately so the safety fast-path works with zero API dependency. Nebius ASR would strengthen the sponsor-stack story if it exists; test on key-day (`GET /v1/models`), don't assume. |
| **TTS (speak)** | Local `pyttsx3` / `espeak-ng` | Working, but robotic — flagged as a Design-criterion risk | No Nebius TTS offering confirmed yet. If one exists, it's a straight upgrade for voice quality; until then, local is the only thing proven to produce real audio. |
| **Memory storage** | Flat JSON file per profile, on local disk (`memory/store.py`) | Working, proven to persist across process runs (Day-2 recall) | No database needed for a single-profile MVP; file-backed is simplest thing that's actually durable. Revisit only if multi-profile support becomes real scope. |
| **Judge-facing web demo (UI)** | Gradio (`webapp.py`) | Built, backend-tested; not yet deployed | Fastest path to a real browser UI wrapping existing pipeline functions with no new logic. Alternatives considered: hand-rolled Flask/FastAPI + HTML (more control, much more build time for no judging benefit); Streamlit (similar tradeoffs to Gradio, less common for audio-first demos). |
| **Hosting for the web demo** | **Primary: Hugging Face Spaces** (free, zero-infra, Gradio-native). **Stretch: Nebius AI Cloud VM** (more setup, but double-counts for the "runs on Nebius" sponsor-tech requirement) | Not yet deployed to either | Spaces gets a judge-accessible link fastest, which is the actual deadline risk. The sponsor-tech requirement is satisfied either way since we call the Token Factory API at runtime regardless of where the UI is hosted — moving to a Nebius VM later is additive, not required. |
| **Static landing page** | GitHub Pages (`docs/index.html`) | Built | Free, zero setup, good for a stable project-overview link (screenshots, status, links to video/demo/repo) — but **cannot** run the actual pipeline (static-files-only), so it's a front door, not the demo itself. |
| **Credit protection on a public demo URL** | In-memory per-day request counter (`MAX_DAILY_REQUESTS`, default 50) | Built | Simplest thing that stops a shared public link from draining the whole Nebius credit balance; resets on process restart, which is fine for a hackathon-duration deployment. |

## Open vendor questions (need a live key to resolve)

- Does the Nemotron 3 Nano model ID actually exist on our account? (`GET /v1/models`)
- Does Token Factory expose an audio-transcription endpoint at all, and does Parakeet exist on it?
- Does Nebius offer any TTS model, and is it better than local espeak?
- Do the two $25 credit codes in `README.md` actually work? (report back once tried)
