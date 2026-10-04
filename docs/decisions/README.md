# Architecture Decision Records (ADRs)

This folder is the **decision log**: *why* we made each major choice. Use it when:
- you wonder "why espeak and not gTTS?"
- your teammate asks "did we consider X?"
- you pick up work and need the design constraints
- a condition changed and you need to know whether a decision should too

## How to use

1. **New decision?** Copy [`ADR-000-template.md`](ADR-000-template.md) to `ADR-NNN-topic.md` (next number), fill it in, add a row below, and add a one-liner to the Decisions table in [`../WORK_LOG.md`](../WORK_LOG.md).
2. **Read one?** Find the topic below.
3. **Reference it?** Link from `WORK_LOG.md`, `ROADMAP.md` or the GitHub Issue it relates to.
4. **Revisit one?** Check its "When to revisit" section. If the condition changed, open an Issue labeled `question`. Don't edit an accepted ADR in place to reverse it: add a new ADR and mark the old one `Superseded by ADR-NNN`.

## Decisions

| # | Decision | Status | Date |
|---|----------|--------|------|
| [ADR-001](ADR-001-tts-backend.md) | Local TTS: pyttsx3, with the `espeak-ng` CLI on Linux/macOS | Accepted (amended 10-03) | 2026-10-01 |
| [ADR-002](ADR-002-think-audit-model.md) | THINK and AUDIT run NVIDIA Nemotron Nano 30B on Nebius | Accepted | 2026-10-01 |
| [ADR-003](ADR-003-hosting.md) | Host the judge demo on Hugging Face Spaces | Accepted | 2026-10-01 |
| [ADR-004](ADR-004-asr-backend.md) | ASR: local `faster-whisper` | Accepted | 2026-10-02 |
| [ADR-005](ADR-005-safety-fastpath.md) | Safety fast-path is deterministic rules, not a model | Accepted | 2026-10-01 |
| [ADR-006](ADR-006-working-agreement.md) | Direct commits to `main`; three writers; guardrails stay on | Accepted | 2026-10-04 |

## Superseded / reconsidered

None yet.
