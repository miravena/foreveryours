# Vendor decisions

One place to check "what did we pick and why" for every external dependency — so a decision
doesn't have to be re-litigated or re-discovered from code. Update this when a decision
changes; link the GitHub Issue/commit that changed it.

| Component | Decision | Status | Why / alternatives considered |
|---|---|---|---|
| **LLM (THINK)** | Nebius Token Factory, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | **Verified live** (PR #25: model inventory + beat2 end to end, 4.22s to first audio). Emits hidden reasoning tokens first, so test `enable_thinking: false` for latency (#17) | Required by hackathon rules (must use ≥1 NVIDIA open-weight model via Nebius). Nano chosen over Super/Ultra for latency fit under our <2s-to-first-audio budget. Fallback if unprovisioned: point `NEBIUS_BASE_URL` and `NEBIUS_API_KEY` at another OpenAI-compatible provider and set **both** `THINK_MODEL` and `AUDIT_MODEL` to models it serves — leave `AUDIT_MODEL` alone and every safety recheck asks a provider that has no Nemotron, then fails. Not sponsor-stack: it keeps the demo working but costs the judging line it satisfies. |
| **LLM (AUDIT)** | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` via Nebius Token Factory (replaced Llama 3.1 8B, which returned 404, in PR #25) | Verified live (PR #25) | Background safety-recheck pass, off the critical path. **NVIDIA NemoGuard was considered** as a purpose-built content-safety replacement, which would also add a second NVIDIA model for the tech score. **Resolved 2026-10-07 (#81 row 1, #56): checked the full Token Factory model list — no NemoGuard or other guard model is served.** The model-level distress backstop (#56) instead points `AUDIT_MODEL` at a different, larger Nemotron model (e.g. `nemotron-3-super-120b-a12b`) so THINK and AUDIT are distinct models. |
| **ASR (speech-to-text)** | Default: local `faster-whisper` (CPU, no key). Candidate: Nebius-hosted `nvidia/parakeet-tdt-1.1b` | **Decided: local `faster-whisper`.** Token Factory returns 404 on `/audio/transcriptions` (verified live, PR #25) | Local default chosen deliberately so the safety fast-path works with zero API dependency. **Resolved 2026-10-07 (#81 row 1, #56): the Token Factory model list serves no NVIDIA ASR or TTS model at all**, confirming no Nebius-hosted speech path exists to strengthen the sponsor-stack story. |
| **TTS (speak)** | Local `pyttsx3` / `espeak-ng` | Working, but robotic — flagged as a Design-criterion risk. The Linux silence bug after ~19 sentences is resolved ([#28](../../issues/28): verified over a 200-sentence run, regression test hardened to 60 cases) | No Nebius TTS offering confirmed yet. If one exists, it's a straight upgrade for voice quality; until then, local is the only thing proven to produce real audio. |
| **Memory storage** | Flat JSON file per profile, on local disk (`memory/store.py`) | Working, proven to persist across process runs (Day-2 recall) | No database needed for a single-profile MVP; file-backed is simplest thing that's actually durable. Revisit only if multi-profile support becomes real scope. |
| **Judge-facing web demo (UI)** | Gradio (`webapp.py`) | Built, browser-tested (per-visitor isolated sessions, PR #26); not yet deployed | Fastest path to a real browser UI wrapping existing pipeline functions with no new logic. Alternatives considered: hand-rolled Flask/FastAPI + HTML (more control, much more build time for no judging benefit); Streamlit (similar tradeoffs to Gradio, less common for audio-first demos). |
| **Hosting for the web demo** | **Primary: Hugging Face Spaces** (free, zero-infra, Gradio-native). **Stretch: Nebius AI Cloud VM** (more setup, but double-counts for the "runs on Nebius" sponsor-tech requirement) | Not yet deployed to either | Spaces gets a judge-accessible link fastest, which is the actual deadline risk. The sponsor-tech requirement is satisfied either way since we call the Token Factory API at runtime regardless of where the UI is hosted — moving to a Nebius VM later is additive, not required. **Risk:** free-tier Spaces sleep when idle, so a judge's first click can hang waiting for a cold start — plan to keep the Space awake through the actual judging window (upgraded/always-on hardware for that window, or fall back to the Nebius VM stretch) rather than discovering this live. |
| **Static landing page** | Cloudflare Pages (`docs/index.html`) | Built, live | Free, zero setup, good for a stable project-overview link (screenshots, status, links to video/demo/repo) — but **cannot** run the actual pipeline (static-files-only), so it's a front door, not the demo itself. |
| **Credit protection on a public demo URL** | Per-day request counter (`MAX_DAILY_REQUESTS`, default 50), counted in `data/rate_limit.json` so it survives a restart | Built | Simplest thing that stops a shared public link from draining the whole Nebius credit balance; the count is keyed by date, so it resets daily rather than on restart — deleting `data/rate_limit.json` resets it by hand. |

## Build vs reuse

What we keep custom, what we may adopt from open source, and the sourced reasoning: [ADR-009](docs/decisions/ADR-009-build-vs-reuse.md) (Proposed; review thread [#114](../../issues/114)).

## If we must leave it

Half this table needs no exit plan — `faster-whisper`, `espeak-ng`, the JSON store and the rate
limiter have no vendor behind them, so nothing can take them away. These are the rows that do, and
what each one costs to move:

| Depends on | Stranded when… | The exit | Cost |
|---|---|---|---|
| **Nebius Token Factory** (THINK, AUDIT) | key revoked, credits run out, endpoint changes | Set **all three**: `NEBIUS_BASE_URL`, `NEBIUS_API_KEY`, and `THINK_MODEL` / `AUDIT_MODEL`. The key matters most — `get_client()` sends whichever key it finds, so changing only the URL and models hands a Nebius credential to another provider and fails auth | Three env values; the demo keeps working and we lose only the "runs on Nebius" line |
| **Hugging Face Spaces** (hosted demo) | the Space is removed, or the free tier changes under us | `python webapp.py` runs the same app anywhere; the Nebius AI Cloud VM stretch in [ADR-003](docs/decisions/ADR-003-hosting.md) *is* this contingency | An afternoon — `scripts/deploy_hf_space.py` becomes a plain deploy |
| **Gradio** (judge-facing web UI) | a breaking major lands — `requirements.txt` pins `gradio>=4.44.0` with no upper bound, so it can arrive unannounced | Re-write `webapp.py` only; it wraps `pipeline/` functions, so no pipeline logic moves with it | Days — the largest single exit on this list |
| **Cloudflare Pages** (landing page) | the account or plan changes | Static files, no build step: any static host is a DNS change | Minutes |

## Open vendor questions (need a live key to resolve)

Resolved by PR #25: the Nemotron 3 Nano model ID exists; Token Factory has no
audio-transcription endpoint; the activation-code credits work.

Resolved 2026-10-07 (#81 row 1, #56, full `GET /v1/models` list, 25 models):
Token Factory serves four NVIDIA Nemotron chat models
(`NVIDIA-Nemotron-3-Nano-30B-A3B`, `nemotron-3-super-120b-a12b`,
`Nemotron-3-Ultra-550b-a55b`, `Nemotron-3_5-Lightning`) and no NemoGuard or
other guard model, and no NVIDIA speech (ASR or TTS) model of any kind.

- Does Token Factory honour `chat_template_kwargs: {"enable_thinking": false}` on Nemotron 3 Nano, and how much latency does it save? ([#17](../../issues/17))
