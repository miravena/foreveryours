# Proactive Companion Agency: Implementation Plan

**Status: not built.** This plan describes a policy gate, a no-surveillance output test, and four
distinct trigger types; the shipped code has one shared function, no output test, and stores a
fabricated `[System: ...]` turn into history as if the senior had said it. The four-button
developer panel described in Step 3 is out of the public demo UI. See #65 for the audit and
decision not to build this before submission.

## 1. Analysis of the Gap
The critique provided is profoundly accurate for the eldercare domain. The gap between a "chatbot" and a "Companion" is agency. However, the gap between "Companion" and "Surveillance State" is entirely defined by the *Policy Gate and LLM Framing*.

If an AI says: *"You haven't spoken in 6 hours, are you okay?"*, it breaks the core product philosophy ("Peace of mind without surveillance"). The senior immediately feels tracked and infantalized. 
Instead, the AI must translate internal metric triggers (Time elapsed = 6h) into natural, spontaneous human behavior (*"Good afternoon Robert, I was just thinking of you. How's the day going?"*). 

This requires transforming the current purely reactive architecture (`User speaks -> AI replies`) into a **Proactive Agent Architecture** with three core layers: Triggers, Policy Gates, and LLM Framing.

## 2. Implementation Plan

For the Hackathon, we cannot wait 6 hours for a cron job to fire during a 3-minute judge demo. Therefore, the implementation must involve the actual backend logic, coupled with a **Gradio Developer UI Panel** to simulate the passage of time or trigger specific events.

### Step 1: The Policy Gate & LLM Framing (Backend)
We will create a new function in `pipeline/think.py` (e.g., `stream_proactive_initiation`).
When triggered, it will inject a specific block into the `SYSTEM_PROMPT`:
```text
[PROACTIVE INITIATION MODE]: 
You are speaking first. The user has not said anything. 
Your goal is to gently check in, remind them of an event, or offer companionship based on their memories.
CRITICAL RULE: DO NOT tell the user that you are checking on them because they were quiet. 
CRITICAL RULE: Do not ask interrogating questions ("Did you take your pills?"). 
Be warm, spontaneous, and brief. Example: "Hi Robert, just thought I'd say hello. How's the afternoon treating you?"
```

### Step 2: The Four Trigger Types (Memory Integration)
We will implement logic to pull specific context based on the trigger type:
1. **Scheduled Greeting:** Uses current time (e.g., Morning -> "How did you sleep?"). Ties directly into our existing Circadian/Night Mode logic.
2. **Important Reminder:** Scans the `MemoryStore` for `[Temporary]` events happening today (e.g., "Sarah's groceries").
3. **Memory-Based Engagement:** Scans the `MemoryStore` for `[Permanent]` hobbies (e.g., "Jazz", "Gardening") to spark natural conversation.
4. **Gentle Check-in:** Generic, warm greeting triggered by a lack of interaction.

### Step 3: The Demo Integration (Gradio UI)
In `webapp.py`, we will add a new accordion panel visible only to judges/developers: **"🛠️ Simulate Proactive Triggers"**.
It will have 4 buttons:
* `[Trigger: Morning Greeting]`
* `[Trigger: Caregiver Reminder (Grocery)]`
* `[Trigger: Hobby Engagement]`
* `[Trigger: Silence Check-in]`

When a button is clicked, it will bypass the microphone, hit `stream_proactive_initiation()`, and the AI will speak its proactive message out loud, appearing in the chat history as:
**ForeverYours initiated:** *"Hi Robert, Sarah should be dropping by soon..."*

## 3. Verification & Safety
We will add a new test file (`tests/test_proactive_agency.py`) to assert that the AI does NOT hallucinate surveillance behavior. We will write regex assertions ensuring phrases like *"you haven't spoken"* or *"I am monitoring"* never appear in the proactive generation outputs.
