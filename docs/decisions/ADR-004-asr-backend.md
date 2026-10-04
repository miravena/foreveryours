# ADR-004: ASR is local `faster-whisper`

**Status:** Accepted (supersedes the earlier NVIDIA-hosted ASR plan)
**Date:** 2026-10-02
**Decided by:** Team
**Affects:** `pipeline/hear.py`
**Related issue:** [#9](../../issues/9)

## Question

How do we transcribe speech?

## Context

Token Factory returns 404 on `/audio/transcriptions` (verified live, PR #25), so hosted NVIDIA
ASR is not available there.

## Decision

**Local `faster-whisper`** (`ASR_BACKEND=whisper_local`).

## Rationale

It is the only working option. Nebius + NVIDIA still power THINK and AUDIT (ADR-002), so the
sponsor-tech requirement is met.

## Consequences

Local compute and model download on the host; works offline. The `ASR_BACKEND=nebius` path in
`pipeline/hear.py` is retained but unused until Token Factory offers transcription.

## When to revisit

Token Factory adds an audio-transcription endpoint.
