# Feature Review: Proactive Agency

## Feature Overview
The AI companion can now autonomously initiate conversation based on specific triggers (Morning greeting, Caregiver reminders, Hobby engagement, or Silence check-ins). This completes the transformation from a reactive chatbot to a proactive companion.

## Resolved Gaps (Issue 65)

1. **Distinct Triggers:** 
   The developer UI previously routed all four proactive buttons to the same generic function. Now, `webapp.py` passes a distinct `trigger_type` (`morning`, `reminder`, `hobby`, `silence`) to the orchestrator.

2. **Policy Gate (No Surveillance):**
   Previously, the proactive engine faked a user prompt (`[System: The senior is currently quiet...]`), which risked the LLM telling the senior they were being monitored. Now, the system uses a dedicated `build_proactive_prompt()` function in `think.py`. It explicitly tells the LLM: *"CRITICAL RULE: DO NOT tell the user that you are checking on them because they were quiet."*

3. **Clean History Tracking:**
   The proactive engine no longer pollutes the chat history with a fake user prompt. It runs a headless turn and appends *only* the assistant's proactive reply to the chat history, making it look and behave like true autonomous initiation.

4. **Surveillance Tests:**
   A new test suite (`tests/test_proactive_agency.py`) verifies the prompt policy gate to mathematically guarantee the AI cannot hallucinate surveillance phrasing.
