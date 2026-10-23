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
| [ADR-002](ADR-002-think-audit-model.md) | THINK and AUDIT run NVIDIA Nemotron Nano 30B on Nebius (AUDIT moved to Super by ADR-016) | Accepted (amended 10-23) | 2026-10-01 |
| [ADR-003](ADR-003-hosting.md) | Host the judge demo on Hugging Face Spaces | Accepted | 2026-10-01 |
| [ADR-004](ADR-004-asr-backend.md) | ASR: local `faster-whisper` | Accepted | 2026-10-02 |
| [ADR-005](ADR-005-safety-fastpath.md) | Safety fast-path is deterministic rules, not a model | Accepted | 2026-10-01 |
| [ADR-006](ADR-006-working-agreement.md) | Direct commits to `main`; three writers; guardrails stay on | Accepted | 2026-10-04 |
| [ADR-007](ADR-007-attribution.md) | The human is the author; AI help is an `Assisted-by` trailer (amended 2026-10-09; was `Co-Authored-By`); guardrails warn, never block | Accepted | 2026-10-05 |
| [ADR-008](ADR-008-neural-tts.md) | Offline neural voice (Piper) preferred, with espeak-ng/System.Speech/pyttsx3 as fallbacks (supplements ADR-001) | Accepted | 2026-10-09 |
| [ADR-009](ADR-009-build-vs-reuse.md) | Build vs reuse: keep privacy layer, fast-path and voice loop; licence check on `piper-tts` (GPL-3.0-or-later); trial embedding retrieval | Proposed | 2026-10-09 |
| [ADR-010](ADR-010-audit-model-eval.md) | AUDIT model chosen by a labelled 36-row eval across served NVIDIA models; Nano kept (Super: recall 1.00 vs 0.63, same 0/17 false flags); amended by ADR-016 | Accepted (amended 10-23) | 2026-10-22 |
| [ADR-011](ADR-011-voice-licence-and-warm-piper.md) | Public-domain Piper voice (`en_US-ljspeech`), kept warm in its own process; GPL engines stay separate programs (amends ADR-008) | Accepted | 2026-10-23 |
| [ADR-012](ADR-012-fall-long-tail.md) | Falls outside the canonical words: three more first-person fast-path patterns, AUDIT prompt reads the transcript; amends ADR-005 and ADR-010 | Accepted (founder 2026-10-23; teammate review open) | 2026-10-23 |
| [ADR-013](ADR-013-crisis-tiers.md) | Crisis phrases: explicit first-person statements in the regex tier, euphemism and context in the AUDIT backstop; next-turn carry and a 988-once guard (amends ADR-005) | Accepted (founder 2026-10-23; teammate review open) | 2026-10-23 |
| [ADR-014](ADR-014-outbound-notification.md) | One outbound caregiver notification: SMTP e-mail by default, webhook second, off when unset and always off on the hosted Space; fixed-text body, per-household hourly cap | Accepted (founder 2026-10-23; teammate review open) | 2026-10-23 |
| [ADR-015](ADR-015-judging-window-deploys.md) | During judging only `v1.0.x` patches deploy (safety exception), each a published Release; rollback by re-running the previous tag (amends ADR-003) | Accepted (founder 2026-10-23; teammate review open) | 2026-10-23 |
| [ADR-016](ADR-016-audit-model-super.md) | AUDIT default moves to Nemotron 3 Super 120B; THINK stays on Nano (amends ADR-010 and ADR-002) | Accepted | 2026-10-23 |

## Superseded / reconsidered

None yet.
