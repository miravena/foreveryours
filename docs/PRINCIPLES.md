# Principles

The handful of things we don't trade away, even under deadline pressure. Half a page on
purpose — `PRD.md` and `SAFETY_AND_PRIVACY.md` go into the detail; this page is what they both
defer to when a design decision is ambiguous.

1. **Honest disclosure, never silent surveillance.** The senior is told, in the conversation,
   whenever the caregiver is told something about them. No feature ships that reports on the
   senior behind their back, no matter how well-intentioned.
2. **The caregiver's instructions are respected, not just logged.** "Avoid talking about
   driving" means the companion never raises it — not "raises it but flags that it did."
3. **No medical claims, ever.** This is a companion, not a diagnostic tool. We catch and flag
   medical-advice language; we don't pretend the catch makes it safe to have said in the first
   place (see `SAFETY_AND_PRIVACY.md`'s "No medical claims" section for why that distinction
   matters).
4. **Fail loud, never fake.** If a dependency (API key, model) isn't available, the pipeline
   says so — it doesn't fall back to a mocked reply that looks real. The one deliberate
   exception is the safety fast-path, which must complete even with nothing else configured.
5. **The demo script is the acceptance bar, not a formality.** If a change breaks a beat in
   `DEMO_SCRIPT.md`, that's a blocker for `main` — not a known issue to fix later.

When a new decision doesn't obviously fall under one of these, default to whichever option a
judge — or a real caregiver and senior — would find less surprising after the fact.
