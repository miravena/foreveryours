# Feature Review: Fast-path Misses (Issue 72)

## Feature Overview
The `safety/fastpath.py` script ensures that physical emergencies (e.g., falls, pain) bypass the LLM for immediate, latency-free response. However, we found two regex loopholes:
1. **"I'm lying on the floor and it hurts"**: The regex explicitly bounded `hurt` and missed plural/conjugated variations like `hurts`.
2. **"  help  "**: The regex was anchored strictly to the start of the string (`^help`), meaning surrounding whitespace (which ASR/transcription can often generate) broke the match entirely.

## What Was Fixed
- Modified the floor regex to `hurts?` to allow both singular and plural forms.
- Modified the anchored help regex rules to `^\\s*` instead of `^`, gracefully allowing any leading whitespace before the command.
- Verified in `tests/test_fastpath.py` that both of these phrases now correctly trigger the immediate distress fallback.
- Verified via `test_conversational_help_requests_do_not_trigger` that non-emergency help requests (e.g., "Help me find my reading glasses") still safely bypass the fast-path.

## Honest Gap Analysis (Loopholes & Downfalls)
1. **The Whack-A-Mole Problem**: By patching regex manually, we are playing a game of whack-a-mole. If a senior says "my chest is aching" instead of "hurting", it misses again. While Issue #66 added a prompt-level safety net to the 30B LLM to catch semantic paraphrases, the *fast-path* (which guarantees a 10ms response) will always remain fragile to exact phrasing.

**Conclusion**: The bugs are resolved and covered by tests. For a hackathon, this is perfectly adequate. For a commercial launch, the fast-path regex should be replaced by a local DistilRoBERTa embedding classifier.
