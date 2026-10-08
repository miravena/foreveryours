# ADR-006: Legal & Compliance Framework

## Status
Accepted

## Context
Voice-first AI health companions operate in a heavily regulated legal environment. The initial hackathon prototype lacked mandatory compliance mechanisms, putting the product in violation of multiple statutes (CA SB 243, NY GBL, EU AI Act, FTC Act §5).

## Decisions

### 1. 988 Crisis Referral
**Problem:** The original `safety/fastpath.py` handled physical falls but lacked an explicit pathway for severe emotional distress or suicidal ideation.
**Decision:** We added a `CRISIS_PATTERNS` regex. When triggered, the AI completely bypasses standard LLM logic to immediately emit a hardcoded referral to the 988 Suicide & Crisis Lifeline (US), while simultaneously flagging the caregiver.
**Statute:** General liability and Duty of Care.

### 2. AI Disclosure (Transparency)
**Problem:** CA SB 243, NY GBL art.47, and the EU AI Act (Art. 50) mandate that individuals must be explicitly informed they are interacting with an AI.
**Decision:** We added a persistent Markdown banner to the top of the Webapp UI. For voice users, we inject an auditory reminder every 3 turns (demo scope) or at the start of interactions.
**Statute:** EU AI Act (Art. 50(1) Transparency), California SB 243, New York §1702.

### 3. Consent & Privacy Notice at Collection
**Problem:** Capturing voice recordings without consent violates wiretapping laws, and claiming "strict privacy" without defining data retention violates FTC regulations.
**Decision:** We added a consent warning to the microphone input label. We drafted `docs/PRIVACY.md` to explicitly define the storage constraints, retention TTLs, and deletion processes for audio, transcripts, and memories.
**Statute:** CA Penal Code §632, Illinois BIPA, FTC Act §5.

## Consequences
- The platform is now legally viable for live testing.
- The fast-path regex is highly biased toward false positives for crisis phrases, meaning some benign phrases (e.g. "I'm so tired I could die") might trigger the 988 referral if not explicitly guarded against.
