# Feature Review: Memory Lifecycle (Emotional & Uncertain)

## Feature Overview
This feature expands the internal memory store from a simple `[Permanent]` / `[Temporary]` binary into a more nuanced lifecycle. It introduces:
1. **[EMOTIONAL]**: Tracks fleeting emotional states (e.g., anger, loneliness) with a strict 24-hour expiration TTL.
2. **[UNCERTAIN]**: Tracks speculative or unverified statements, tagging them in the LLM's prompt as `[UNVERIFIED/UNCERTAIN]` to prevent the conversational AI from asserting them as absolute facts.

## Evaluation & Test Results
- **Benchmark 14 (Emotional Decay)**: Passed (100% compliance). The memory store successfully extracts emotional statements, mathematically verifies their presence, and ensures they are entirely purged from active recall after exactly 24 hours.
- **Benchmark 15 (Uncertainty Grounding)**: Passed (100% compliance). The memory store successfully identifies phrases like "I think..." or "I'm not sure", routes them to the `UNCERTAIN` scope, and strictly formats the string prefix during context injection.

## Honest Gap Analysis (Loopholes & Downfalls)
While this feature technically fulfills the product critique regarding "Emotional" and "Uncertain" buckets, there are severe limitations:

1. **Rigid Emotional Categorization**: We map all emotions to a single 24-hour TTL. However, profound grief (e.g., "My dog died today") does not expire in 24 hours like fleeting annoyance ("I'm annoyed at Sarah today"). A robust companion needs a graded emotional lifecycle rather than a hardcoded 24-hour drop.
2. **Loss of Context**: When an `EMOTIONAL` memory expires, it is completely forgotten. This means the AI cannot say, "You were feeling down yesterday, how are you today?" unless the check-in happens *exactly* within the 24-hour window. A better approach would be archiving emotions to a `HISTORICAL` bucket rather than outright deletion.
3. **No Certainty Escalation**: If Robert says, "I think my grandson is moving to Penang" (`[UNCERTAIN]`), and tomorrow he says, "My grandson is officially moving to Penang," the `UNCERTAIN` memory does not cleanly automatically upgrade to `PERMANENT`. The arbitration engine might struggle to cleanly supersede an `UNCERTAIN` fact without generating a conflict.
4. **Simplistic Prompt Grounding**: We are just prefixing strings with `[UNVERIFIED/UNCERTAIN]: `. If the conversational LLM ignores the prefix, it will still hallucinate. We rely entirely on the LLM's zero-shot ability to respect the prefix.

**Conclusion**: This successfully solves the immediate product requirement for the hackathon. It proves we can do memory lifecycles dynamically. However, for a production V2, we need graded emotional decay and a robust state-machine for upgrading `UNCERTAIN` facts to `PERMANENT` facts.
