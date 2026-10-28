# Feedback: Nebius Token Factory & NVIDIA Tools

This feedback is provided for the Nebius x NVIDIA Global AI Hackathon (Requirement 9) and the Most Valuable Feedback prize. We used Nebius Token Factory only; we have no feedback on Nebius AI Cloud because the project does not use it.

## Nebius Token Factory

**What worked well:**
- **Latency & Speed:** Once optimized, latency was exceptional. We achieved ~0.91s to first audio output on the command line (the hosted demo is slower; no hosted figure is claimed), which was critical for maintaining a natural pace in a voice-first interface.
- **Credit Allocation:** The provided sponsor credits and Builder Program allowance ($25 + $25) were generous and frictionless to activate, and more than sufficient for full prototyping.

**Areas for improvement:**
- **Missing Audio/Transcription Endpoints:** Token Factory lacked a direct audio-transcription API. We had to pivot to using a local `faster-whisper` deployment (ADR-004), which complicated our initial cloud-native architecture. Adding native STT endpoints would greatly simplify voice-first development on the platform.
- **Reasoning Tokens Impacting Latency:** By default, hidden reasoning tokens significantly degraded time-to-first-byte (initial tests showed 4.22s to first audio). We had to explicitly discover and pass `enable_thinking: false` to reach our <1s target. `enable_thinking: false` is the single most important setting for voice and is easy to miss; documentation that says plainly what hidden reasoning tokens cost a real-time app would help.
- **Model-ID Casing:** We encountered friction with exact model-ID string casing and undocumented variations. Clearer documentation or case-insensitive matching on the API side would smooth out the initial developer experience.

## NVIDIA Models (Nemotron 3 Nano and Super)

The streamed reply runs on `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`; the background safety backstop runs on `nvidia/nemotron-3-super-120b-a12b` (ADR-016).

**What worked well:**
- **Contextual Recall (reply):** Nano used the caregiver's briefing (from our JSON-backed MemoryStore) in a warm, conversational way, fast enough for a spoken reply. It recalled specific details (e.g., "Grandson Leo") without sounding robotic.
- **No false flags:** As a safety backstop, neither Nano nor Super raised a false flag in our labelled evaluation (ADR-010, ADR-016).

**Areas for improvement:**
- **Backstop recall on the small model:** As the backstop, Nano caught only 12 of 19 true events on our first 36-row set (missing five of six falls) and reached 0.88 recall on a later 43-row set, below the 0.90 floor we set. Super caught all of them, so the small model is not enough on its own for safety, and we pay about five times as much per check for Super (ADR-010, ADR-016).
- **Conversational Brevity:** Nano is verbose by default. For a zero-screen, voice-first application aimed at older adults, we had to prompt hard for short, patient turns.
- **Invented detail:** Nano sometimes adds plausible detail that was never in the briefing (a school, a granddaughter). Our prompt now forbids it explicitly, and it still happens occasionally.
