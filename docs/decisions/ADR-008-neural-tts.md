# ADR-008: Offline neural voice (Piper) preferred, espeak-ng/System.Speech/pyttsx3 as fallbacks

**Status:** Accepted
**Date:** 2026-10-09
**Decided by:** Team
**Affects:** `pipeline/speak.py`, voice quality (Design score), optional dependency footprint
**Related issue:** [#52](../../issues/52) (better offline TTS), supplements [ADR-001](ADR-001-tts-backend.md)

## Question

ADR-001 accepted a robotic voice "given budget and deadline" and listed a trigger to
revisit: *"a drop-in offline neural TTS with clearly better quality and small size appears."*
That trigger is now met and Design-score feedback named voice quality as a reason we lose
points. Can we adopt a better offline neural voice without losing the offline guarantee,
the latency budget, or the #28 silence fix — and without making `main` require an extra
install?

## Context

- **Design score:** the output voice is the single biggest Design-score weakness; it is the
  first thing a judge hears. ADR-001's own "When to revisit" lists both "better offline neural
  TTS appears" and "Design-score feedback names voice quality."
- **Offline + latency:** ADR-001's and ADR-003's offline rationale still holds — judges may
  have flaky WiFi, and hosted TTS adds a round trip and cost.
- **#28 non-regression:** the espeak silence bug was a long-lived in-process engine draining a
  C buffer; the fix is one clean subprocess per sentence. Any new backend must keep that shape.
- **Demo-ability:** a fresh clone (`pip install -r requirements.txt`, no voice download) must
  still run the demo.

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| **Piper CLI per sentence, auto-detected, preferred** | Offline neural VITS voice on CPU, small model, same clean-subprocess-per-sentence shape as espeak (#28-safe), optional | Needs a one-time model download; extra optional dep | Yes |
| Replace espeak outright with Piper | Simplest mental model | Breaks demo-ability with no model present; loses the resilient fallback | No |
| Piper in-process (Python API) | No subprocess spawn | Re-introduces the long-lived-engine risk ADR-001/#28 guard against; couples import success to demo-ability | No |
| Hosted neural TTS (ElevenLabs / cloud) | Best quality | Needs network + key + cost; violates offline guarantee | No |

## Decision

**We chose Piper as a new PREFERRED, auto-detected tier, additive to the existing fallbacks.**
Per-sentence synthesis order is: (0) Piper when both its CLI and a complete voice model
resolve → (1) Windows System.Speech → (2) espeak-ng/espeak CLI → (3) pyttsx3. `TTS_BACKEND`
(`auto`/`espeak`) and `TTS_PIPER_MODEL` are env-configured.

## Rationale

Piper slots into the exact "one clean subprocess per sentence writing a WAV" shape the espeak
branch already uses, so it inherits the #28 isolation for free and stays fully offline (it reads
a local `.onnx` voice). Making it optional and auto-detected means a clone with no voice download
still demos on the existing voice — so we get the better voice where present and lose nothing
where absent. *Content was rephrased for compliance with licensing restrictions.*

## Consequences

- **Unlocked:** a warm, natural offline neural voice (`en_US-lessac-medium`) when the model is
  present; the Design-score weakness ADR-001 accepted is addressed.
- **Locked in to:** an optional `piper-tts` dependency and a gitignored `models/piper/` voice
  directory fetched once via `scripts/get_piper_voice.sh`; the voice is configurable via env.
- **Gotchas:** model binaries are large — never commit them (`.gitignore` blocks `models/piper/`
  and `*.onnx`). If only the `.onnx` or only the `.onnx.json` is present, Piper is treated as
  unavailable (no half-start). `TTS_BACKEND=espeak` forces the legacy path for deterministic CI.

## When to revisit

- The hosted HF Space (ADR-003) cannot run Piper and the `auto` fallback voice is judged
  insufficient there.
- A smaller or clearly better offline voice/model appears.
- Measured time-to-first-sound with Piper exceeds the latency budget on the free CPU Space.
