# Feedback: Nebius Token Factory & NVIDIA Tools

This feedback is provided for the Nebius x NVIDIA Global AI Hackathon (Requirement 9) and the Most Valuable Feedback prize. We used Nebius Token Factory only; we have no feedback on Nebius AI Cloud because the project does not use it.

## Nebius Token Factory

**What worked well:**
- **Latency & Speed:** Once optimized, latency was exceptional. We achieved ~0.91s to first audio output, which was critical for maintaining a natural pace in a voice-first interface.
- **Credit Allocation:** The provided sponsor credits and Builder Program allowance ($25 + $25) were generous and frictionless to activate, and more than sufficient for full prototyping.

**Areas for improvement:**
- **Missing Audio/Transcription Endpoints:** Token Factory lacked a direct audio-transcription API. We had to pivot to using a local `faster-whisper` deployment (ADR-004), which complicated our initial cloud-native architecture. Adding native STT endpoints would greatly simplify voice-first development on the platform.
- **Reasoning Tokens Impacting Latency:** By default, hidden reasoning tokens significantly degraded time-to-first-byte (initial tests showed 4.22s to first audio). We had to explicitly discover and pass `enable_thinking: false` to reach our <1s target. It would be helpful if documentation highlighted the latency tradeoff of reasoning tokens for real-time applications.
- **Model-ID Casing:** We encountered friction with exact model-ID string casing and undocumented variations. Clearer documentation or case-insensitive matching on the API side would smooth out the initial developer experience.

## NVIDIA Models (Nemotron Nano 30B)

**What worked well:**
- **Contextual Recall (THINK pass):** Nemotron Nano 30B excelled at seamlessly integrating retrieved personal context (from our JSON-backed MemoryStore) without sounding robotic. It successfully recalled specific biographical details (e.g., "Grandson Leo") in a warm, conversational tone.
- **Safety Auditing (AUDIT pass):** The model proved capable of running secondary safety checks in the background asynchronously, ensuring responses adhered to our strict privacy and no-medical-claims policies without hallucinating false positives.

**Areas for improvement:**
- **Conversational Brevity:** The model tends to produce longer, more detailed responses by default. For a zero-screen, voice-first application aimed at older adults, we had to aggressively prompt it to maintain short, patient conversational pacing.
