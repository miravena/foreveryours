# Feature Review: AI Restraint (Quiet Mode)

## Feature Overview
The "Quiet Mode" feature intercepts the senior's requests for alone time, rest, or sleep (e.g. "I'm going to take a nap"). It relies on the background extraction LLM to parse this intent into a `QUIET_MODE` command, which instructs the memory store to block all proactive check-ins for 4 hours.

## Evaluation & Test Results
- **Benchmark 13**: Passed (100% compliance).
- When the senior states they are going to rest, the LLM correctly extracts the command, `MemoryStore` accurately tracks the expiration TTL, and the `orchestrator` immediately aborts proactive turns while the TTL is active.
- The Gradio webapp properly flags this interception visually to the judge: "🔕 Proactive trigger suppressed: Senior requested Quiet Mode."

## Honest Gap Analysis (Loopholes & Downfalls)
While this feature technically fulfills the critique requirement for "Quiet Mode," there are several undeniable shortcomings in its current implementation:

1. **Hardcoded 4-Hour TTL**: We arbitrarily hardcoded the quiet mode duration to `hours=4.0`. If Robert says "Don't bother me for the rest of the day," the system will still resume proactive check-ins after exactly 4 hours. A robust version would require the LLM to extract the *requested duration* along with the command (e.g. `QUIET_MODE: 8 hours`).
2. **Cannot Overrule Caregiver Emergencies**: The orchestrator strictly aborts `run_turn` if `is_proactive=True` and quiet mode is active. This means if a caregiver creates a high-priority emergency schedule update (e.g. "Take your heart medication NOW"), the proactive engine will still blindly suppress it because the senior is napping. There is no concept of "Break-Through" alerts.
3. **No Granular Un-Mute**: If Robert wakes up early after 1 hour and says "I'm awake," the extraction model does not have a `CANCEL_QUIET_MODE` command. The system will continue to block proactive check-ins for the remaining 3 hours until the TTL expires naturally.
4. **Reactive Interactions Are Unaffected (Working as Designed)**: If Robert pushes the mic button and speaks, the system will still respond to him (since `is_proactive=False`). This is actually correct behavior, but it's worth noting that quiet mode only governs *AI-initiated* interactions.

**Conclusion**: This is a solid MVP for hackathon judging, successfully demonstrating AI restraint without surveillance. However, for a production V2, the TTL engine must be made dynamic and caregiver emergencies must be able to break through the silence.
