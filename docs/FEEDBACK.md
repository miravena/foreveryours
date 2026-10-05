# Nebius and NVIDIA Feedback

This feedback is provided as part of the Nebius x NVIDIA Global AI Hackathon submission requirements.

## 1. Nebius Token Factory & AI Cloud

**What worked well:**
*   **API Compatibility:** Integrating with Token Factory was extremely smooth as a drop-in replacement for standard OpenAI-compatible endpoints. It allowed us to quickly connect our orchestrator pipeline.
*   **Performance:** Once optimized, the inference speed on Nebius Token Factory was exceptional, giving us the sub-second perceived latency (~0.91s to first audio) required for a natural conversational voice AI.

**Areas for improvement (Friction points):**
*   **Missing Audio Transcription Endpoint:** We originally planned to use an NVIDIA-hosted ASR model via Nebius, but calls to `/audio/transcriptions` returned a 404 (as verified in our live testing on 2026-10-02). We had to pivot to using local `faster-whisper` for our speech-to-text layer. Adding a standard audio transcription endpoint to Token Factory would greatly simplify voice-first application architectures.
*   **Reasoning Token Latency Surprises:** Initially, we experienced significant latency spikes (over 4.22s to first audio). We eventually diagnosed that hidden reasoning tokens were dominating the generation time. Setting `enable_thinking: false` fixed this immediately. Surfacing reasoning token behavior more transparently in the API documentation or usage dashboards would help developers diagnose latency faster.
*   **Model ID Casing:** We experienced minor friction with exact model ID casing requirements when interacting with the API compared to some documentation references. 

## 2. NVIDIA Models (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`)

**What worked well:**
*   **Dual-Purpose Capability:** We used the Nemotron Nano 30B model for two very different tasks in our pipeline: the primary conversational generative layer (THINK) and a secondary, analytical safety checker (AUDIT). The model excelled at both. It maintained the warm, empathetic tone required for an eldercare companion, while also being capable of strict, rule-based auditing of its own outputs.
*   **Efficiency:** The 30B size was the perfect sweet spot for our use case—large enough to maintain conversational context and follow strict system prompts (such as time-of-day circadian rules), but light enough to hit our stringent latency targets for real-time voice interaction.

**Areas for improvement:**
*   We found that the model would occasionally struggle with very short word inflections in our early retrieval pipelines, requiring us to build more robust substring matching logic on our end. However, as an LLM, its core generative performance was highly reliable.
