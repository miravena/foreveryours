# Plan: Proactive Agency 

## The Goal
To move the companion from a purely *reactive* bot (waiting for the senior to speak) to a *proactive* agent that initiates conversation (e.g., scheduled greetings, event reminders, hobby engagement), without crossing into surveillance territory.

## The Current Broken State
Currently, clicking any "Simulate Proactive Check-in" button in the developer UI triggers a single hacky shared function. It forcibly injects `[System: The senior is currently quiet. Please initiate a conversation...]` into the chat history as if the senior had typed it, and it has no concept of what actually triggered the event.

## The Fix (Path to 40/40)

### 1. Differentiate the Triggers (`webapp.py`)
We will update the four developer buttons to pass a specific `trigger_type` string to the backend:
- `morning` (Scheduled Greeting)
- `reminder` (Caregiver Grocery Reminder)
- `hobby` (Memory-Based Engagement)
- `silence` (Generic Check-in)

### 2. The Policy Gate & LLM Framing (`pipeline/think.py`)
We will build a dedicated `build_proactive_prompt()` function. It will completely bypass the standard reactive prompt. 
Instead, it will frame the LLM with a strict **Policy Gate**:
> *"You are speaking first. The user has not said anything. Your goal is to gently check in. CRITICAL RULE: DO NOT tell the user that you are checking on them because they were quiet. Do not ask interrogating questions."*

Depending on the `trigger_type`, it will pull specific data from the `MemoryStore` (e.g., caregiver schedule updates for `reminder`, permanent facts for `hobby`).

### 3. Clean History State (`webapp.py` & `orchestrator.py`)
Instead of faking a user transcript, `orchestrator.py` will run a true headless turn. 
In `webapp.py`, we will append *only* the assistant's reply to the chat history:
`{"role": "assistant", "content": result.reply_text}` 
This will render beautifully in the UI as the AI spontaneously speaking without a preceding user message.

### 4. No-Surveillance Verification (`tests/test_proactive_agency.py`)
We will create a new test suite to explicitly assert that the AI does not hallucinate surveillance-like phrasing during these proactive turns. It will test that phrases like *"you haven't spoken"* or *"I am monitoring you"* are never generated.
