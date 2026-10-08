# Plan: Disclosed Lifestyle Tracking System

## The Goal
Track specific physical and functional wellbeing metrics (Sleep, Appetite, Mobility, Hygiene) and report them to the caregiver, **without violating the "No Silent Surveillance" invariant.**

## Architectural Strategy
To prevent the LLM from hallucinating medical diagnoses, we will strictly constrain the background memory extraction agent to a predefined list of lifestyle categories. To prevent silent wiretapping, the orchestrator will intercept these logs and force a hardcoded audio disclosure before saving them.

### Phase 1: Constrained Memory Extraction (`pipeline/think.py`)
We will add a new explicit command to the background extraction LLM's system prompt:
`8. To record a significant update about the senior's daily physical habits, use: LIFESTYLE: <CATEGORY> | <FACT>`
**Rule:** `<CATEGORY>` must be exactly one of: `SLEEP`, `APPETITE`, `MOBILITY`, or `HYGIENE`.
*Example:* 
Transcript: *"I haven't had the energy to cook, I've just been eating crackers for two days."*
Output: `LIFESTYLE: APPETITE | Has only eaten crackers for two days due to low energy.`

### Phase 2: The Orchestrator Disclosure Pipeline (`pipeline/orchestrator.py`)
When `run_turn` processes the background extraction and sees a `LIFESTYLE:` command, it will:
1. Parse the category and the fact.
2. Synthesize a **hardcoded disclosure string** based on the category: 
   *"I'm making a quick note for your family about your [sleep / appetite / mobility] so they know how you're feeling lately."*
3. Push that string to the immediate audio queue via `_speak_turn()` so the senior hears it *before* the LLM's conversational reply.
4. Add the note to the `MemoryStore` flagged as `disclosed_to_senior=True`.

### Phase 3: Storage & TTL (`memory/store.py`)
Lifestyle logs shouldn't bloat the AI's system prompt permanently. We will add a new memory scope (`MemoryScope.LIFESTYLE`) with a **7-day Time-To-Live (TTL)**. After 7 days, they expire, ensuring the Caregiver dashboard only shows *current* functional wellbeing, not stale data from last month.

### Phase 4: Caregiver Dashboard (`webapp.py`)
We will update the right-hand Gradio panel to include a new block: **"Weekly Lifestyle Logs"**. This will pull directly from the `MemoryStore`'s unexpired lifestyle facts, complete with the `✅ Disclosed to Senior` audit badge.

---
**Why this is the best implementation:**
- **No Hallucinations:** By forcing the LLM to categorize into exactly 4 buckets, it can't invent random clinical diagnoses (like `LIFESTYLE: DEPRESSION`).
- **No Privacy Violations:** The hardcoded audio pipeline mathematically guarantees the senior is informed every single time a habit is logged.
