# Plan: Issue 66 (Compliance Gaps)

## A. Crisis / 988 Referral
1. Modify `safety/fastpath.py`:
   - Add `CRISIS_PATTERNS` regex for "don't want to be here", "better off without me", "want to die", etc.
   - Guard against false positives ("tired I could die", "to die for").
   - When matched, return `(True, "I am so sorry you are feeling this way. Please call or text 988 to speak with someone who can help right now. I am also letting your family know you are in distress.")`
2. Modify `pipeline/think.py`:
   - Update `SAFETY_AUDIT_PROMPT` or the main orchestrator to refer to 988 if a crisis is detected.
3. Tests:
   - Add cases in `tests/test_fastpath.py` (if it exists) or `tests/test_mature_benchmarks.py` to ensure correct matching and rejection of false positives.

## B. AI Disclosure
1. Webapp UI (`webapp.py`):
   - Add a persistent markdown banner to the UI: "You are speaking with an AI assistant, not a human."
2. `pipeline/orchestrator.py` or `main.py`:
   - Add periodic disclosure logic based on turn count or time. For the demo, every 5 turns append: "(Just a reminder, I am an AI companion, not a human.)"
3. CLI Beats (`main.py`):
   - Print the disclosure at initialization.

## C. Recording Consent & Privacy Notice
1. Webapp UI (`webapp.py`):
   - Add text near the microphone button: "By speaking, you consent to your voice being recorded and transcribed."
2. Docs:
   - Create `docs/PRIVACY.md` detailing storage, retention (1 hour TTL for sessions, etc.).
   - Update `README.md` to link to it.
   - Create `docs/decisions/ADR-006-compliance.md` outlining CA SB 243, NY GBL, EU AI Act compliance.

## Review
- Write `review.md` and push to PR.
