# ADR-001: Local TTS (pyttsx3, with the `espeak-ng` CLI on Linux/macOS)

**Status:** Accepted (amended 2026-10-03)
**Date:** 2026-10-01
**Decided by:** Team
**Affects:** `pipeline/speak.py`, latency, hosting requirements
**Related issue:** [#9](../../issues/9) (real voice I/O), [#28](../../issues/28) (silent TTS on Linux)

## Question

Local TTS (pyttsx3 + espeak) or a hosted service (gTTS, NVIDIA-hosted, ElevenLabs)?

## Context

- **Latency:** target is under 2s to first audio; hosted services add 50-500ms of round trip.
- **Offline resilience:** judges may have flaky WiFi; hosted TTS fails without internet.
- **Cost:** the Nebius budget is tight; hosted TTS adds per-request charges.
- **Deadline:** rewriting TTS mid-sprint is expensive.

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| **Local pyttsx3 + espeak** | Offline, no network latency, free, portable | Robotic voice; pyttsx3's espeak driver went silent after ~19 sentences in one process | Yes |
| gTTS | Natural voice, free | Needs internet, adds latency | Yes (rejected) |
| NVIDIA-hosted (Token Factory) | Natural voice, sponsor tech | No audio endpoint available there, adds cost | Yes (unavailable) |
| ElevenLabs | Best quality | Expensive, adds latency | No |

## Decision

**We chose local TTS.** It meets the latency and offline constraints; the robotic voice is an
accepted Design-score tradeoff given budget and deadline.

## Rationale

Zero network overhead, works for judges offline, costs nothing, and was already built and tested.
Better voices are a nice-to-have after launch.

## Consequences

- **Unlocked:** fully offline demo; Nebius credits stay for THINK and AUDIT.
- **Locked in to:** espeak voice quality; the `espeak-ng` system package on Linux.
- **Amendment (2026-10-03, PR #29):** the #28 silence bug was fixed by invoking the
  `espeak-ng` CLI directly (one clean process per sentence) on Linux/macOS, bypassing
  pyttsx3's C buffer. Windows uses PowerShell `System.Speech`.
- **Gotcha:** `--no-play` suppresses playback (use it in tests and beat recording).

## When to revisit

- A drop-in offline neural TTS with clearly better quality and small size appears.
- The silence bug ([#28](../../issues/28)) recurs on the hosted instance.
- Design-score feedback names voice quality as the reason we lost points.
