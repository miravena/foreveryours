# Feature Review: AI Restraint (Quiet Mode)

## Feature Overview
The "Quiet Mode" feature intercepts the senior's requests for alone time, rest, or sleep (e.g. "I'm going to take a nap"). It relies on the background extraction LLM to parse this intent into a `QUIET_MODE: <hours>` command, which instructs the memory store to block all proactive check-ins for the requested duration.

## What Works
- The memory extraction accurately identifies intent for solitude vs generic statements.
- The Gradio webapp properly flags this interception visually to the judge: "⏸ Proactive trigger suppressed: Senior requested Quiet Mode."

## Resolved Shortcomings
1. **Dynamic TTL**: The Quiet Mode duration is no longer hardcoded to 4 hours. The LLM now extracts the *requested duration* along with the command (e.g. `QUIET_MODE: 8`), and the memory store honors that precise TTL.
2. **Caregiver Emergency Overrides**: The orchestrator now scans the raw caregiver schedule updates. If an update contains "NOW", "URGENT", "EMERGENCY", "CRITICAL", or "IMPORTANT", the proactive engine will immediately break through the Quiet Mode silence and deliver the alert.

## Current State
- **Reactive Interactions Are Unaffected (Working as Designed)**: If Robert pushes the mic button and speaks, the system will still respond to him (since `is_proactive=False`). This is actually correct behavior, but it's worth noting that quiet mode only governs *AI-initiated* interactions.
