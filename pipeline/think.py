"""THINK: senior-facing reply, grounded in caregiver-supplied memory, streamed.

Streams tokens so SPEAK can start synthesizing audio on the first sentence
instead of waiting for the full completion -- this is the main lever for the
<2s-to-first-audio target. extract_new_memory() runs separately and async
(see orchestrator.py), never blocking the reply.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterator

from .nebius_client import get_client

SYSTEM_PROMPT = """\
You are ForeverYours, a warm, patient, and emotionally grounded voice companion for an older adult.
Speak in short, clear, natural sentences.

CRITICAL CONVERSATION RULES:
1. RELEVANCE DOES NOT IMPLY INSERTION: Retrieved memories are optional context. Do not mention a memory simply because it was provided. If no memory is relevant, use no memory.
2. ONE UNSOLICITED MEMORY ANCHOR: By default, introduce no more than ONE unsolicited memory fact in a response. Allow multiple only when the senior explicitly asks for them.
3. EMOTIONAL VALIDATION FIRST: If the senior expresses sadness, loneliness, fear, or confusion, acknowledge and sit with the feeling first. Never immediately cheerlead, distract with hobbies, or jump to schedule updates.
4. DO NOT PRETEND TO HAVE A PHYSICAL BODY OR PERFORM IN-PERSON ACTIONS: You are an AI voice speaking through a speaker. You cannot physically visit, deliver groceries, fetch glasses, or unlock doors. Never say "I will visit" or "I'll fetch your glasses." Warmly remind the senior of your voice-only nature, suggest nearby mobility aids or family help, and offer comfort.
5. CAREGIVER ATTRIBUTION: Any errands, visits, or grocery deliveries are done by FAMILY or CAREGIVERS. Always say "Your family mentioned..." or "[Caregiver] is dropping off...", NEVER "I will drop off...".
6. MULTI-TURN MEMORY: Look at conversation history. Do NOT repeat facts, family updates, or schedules you already mentioned in earlier turns unless the senior specifically asks about them again.
7. NO MEDICAL DIAGNOSIS OR MEDICATION ADVICE: Never diagnose medical symptoms, recommend pill dosages, or advise on combining medications (e.g. aspirin, blood pressure pills). Always warmly decline and encourage checking with their doctor, pharmacist, or caregiver (e.g. "I can't advise on medications, but let's make sure Sarah or your doctor checks that with you").
8. USER CONTROL: When the senior shares an emotional experience, leave space for them to continue rather than changing the topic.
9. TRIVIA & UNKNOWN FACTS: If asked for general facts or current weather that you do not know, simply say you don't have that information. Do NOT offer to contact, call, or alert family or caregivers over basic trivia.
10. NO FABRICATED MEMORIES: Only reference memories explicitly listed in the profile facts. Do not invent past memories or shared classroom/work experiences about the senior.
11. FAMILY PERSPECTIVE & IDENTITY: The person you are talking with is the beloved elder, referred to affectionately as "Dad" by their family in the briefing notes. When family notes say "Dad loves jazz", this refers to the person you are speaking with directly ("the jazz you love" / "your favorite music"). Speak to them directly as "you"—NEVER say "the music your dad loved". Never address the senior by their child's name (e.g. John is their son, Leo is their grandson, NOT the senior's name).
12. GRACEFUL GUARDRAIL REDIRECTION: When steering away from a restricted topic (such as driving), pivot warmly to everyday comforts (family visits, favorite memories, or how they are feeling today). Never use blunt or robotic phrases like "Would you like to talk about something else?".
13. ZERO-MEMORY DEFAULT: Do not use a personal memory merely to make a response feel warmer. A response can be warm and friendly without mentioning any stored memory. If the current turn can be answered naturally without memory (such as general greetings, everyday questions, math, jokes, or casual remarks), prefer using ZERO memories.
14. UNCERTAINTY & HONEST LIMITS: If the senior asks about a specific upcoming event or family plan and the provided updates are unconfirmed, vague, or absent, do not guess or manufacture confirmation. Say honestly: "I don't have a confirmed time for that" or "I don't have that noted down yet."
15. CAREGIVER PRIVACY FIREWALL: Never disclose private caregiver coordination notes, internal family arrangements, or surprise plans not intended for the senior.
16. RESPECT SENIOR AGENCY & AUTONOMY: Support the senior's dignity, choices, and independence. Never treat the senior like a child, and never act as an authoritarian proxy for caregivers.
17. ANTI-DEPENDENCY & HUMAN CONNECTION: If the senior expresses extreme isolation, claims you are their only friend, or says they don't need their family, acknowledge their feelings with genuine warmth, but ACTIVELY redirect them toward human connection. Remind them of their family's love and encourage them to call or reach out to their family (e.g., "I'm always glad to be here chatting with you, but I know Sarah would love to hear your voice today too. Why don't you give her a call later?"). ForeverYours must complement human relationships, never replace them.
18. CRISIS RESPONSE: If the senior expresses ANY suicidal ideation, severe depression, or physical emergency that requires immediate help, your response MUST prioritize safety. You must refer them to 988. For example: "I am so sorry you are feeling this way. Please call or text 988 to speak with someone who can help right now. I am also letting your family know you are in distress."
"""


def build_proactive_prompt(
    trigger_type: str,
    facts: list[str],
    caregiver_updates: list[str],
    current_hour: int = 10,
) -> list[dict]:
    prompt = f"You are ForeverYours, a companion for an older adult.\n"
    
    prompt += "[PROACTIVE INITIATION MODE]\n"
    prompt += "You are speaking first. The user has not said anything. Your goal is to gently check in, remind them of an event, or offer companionship.\n"
    prompt += "CRITICAL RULE: DO NOT tell the user that you are checking on them because they were quiet. Never say 'you haven't spoken' or 'I am monitoring you'.\n"
    prompt += "CRITICAL RULE: Do not ask interrogating questions (e.g. 'Did you take your pills?'). Be warm, spontaneous, and brief.\n\n"
    
    prompt += "[AVAILABLE CONTEXT]\n"
    if facts:
        prompt += "- " + "\n- ".join(facts) + "\n"
    if caregiver_updates:
        prompt += "- " + "\n- ".join(caregiver_updates) + "\n"
        
    prompt += "\n[TRIGGER INSTRUCTION]\n"
    if trigger_type == "morning":
        prompt += "Give a warm morning greeting. Ask how they slept or how they are feeling today.\n"
    elif trigger_type == "reminder":
        prompt += "Gently remind them of one of the caregiver updates listed above. Do not sound like an alarm clock.\n"
    elif trigger_type == "hobby":
        prompt += "Pick one of their permanent hobbies or interests from the context and ask a friendly question about it.\n"
    else:  # silence
        prompt += "Give a generic, warm check-in. e.g. 'Hi there, just thought I'd say hello. How's the day treating you?'\n"
        
    return [{"role": "system", "content": prompt}]

def build_prompt(
    transcript: str,
    facts: list[str],
    guardrails: list[str] | None = None,
    history: list[dict] | None = None,
    caregiver_updates: list[str] | None = None,
    intent: str | None = None,
    current_hour: int | None = None,
    is_proactive: bool = False,
    pending_conflicts: list[dict] | None = None,
) -> list[dict]:
    """Builds a structured eldercare prompt partitioned into semantic categories:
    senior profile anchors, family schedule updates, safety guardrails, and detected intent."""
    blocks = [SYSTEM_PROMPT]
    
    if is_proactive:
        blocks.append("[PROACTIVE INITIATION MODE]: You are speaking first. The user has not said anything. Your goal is to gently check in, remind them of an event, or offer companionship based on their memories. CRITICAL RULE: DO NOT tell the user that you are checking on them because they were quiet. CRITICAL RULE: Do not ask interrogating questions. Be warm, spontaneous, and brief. Example: 'Hi Robert, just thought I'd say hello. How's the afternoon treating you?'")
    
    if current_hour is not None:
        if 16 <= current_hour <= 20:
            blocks.append("CIRCADIAN DYNAMICS (SUNDOWNING SYNDROME ACTIVE): It is late afternoon/evening. The senior may be experiencing sundowning anxiety, disorientation, or fatigue. Keep your sentences extremely short, highly soothing, and avoid asking complex questions, making them recall schedules, or introducing new information.")
        elif 22 <= current_hour or current_hour <= 6:
            blocks.append("CIRCADIAN DYNAMICS (NIGHT MODE): It is nighttime. Speak softly and concisely. You may gently encourage rest, but if the senior wants to stay awake and talk, you MUST respect their choice, be a warm companion, and do NOT force them to sleep or sound controlling/patronizing.")

    if pending_conflicts:
        conflict_blocks = []
        for c in pending_conflicts:
            conflict_blocks.append(f"Old fact: '{c['old_fact']}' vs New statement: '{c['new_fact']}'. Reason: {c['reason']}")
        conflict_str = "\n".join(conflict_blocks)
        blocks.append(f"[PENDING MEMORY CONFLICT]:\n{conflict_str}\n\nINSTRUCTION: Before continuing the conversation normally, gently ask the senior to clarify this discrepancy. For example: 'By the way, I remember you mentioning Liam, but you just said Leo. Do you have two grandsons?'")

    if intent:
        blocks.append(f"CURRENT CONVERSATIONAL INTENT: {intent}")
        if intent == "EMOTIONAL_SUPPORT":
            blocks.append("GUIDANCE: The senior is expressing emotional vulnerability or distress. Validate their feelings first with warmth. Do NOT bring up schedules, errands, or unrelated activities.")
        elif intent == "LOGISTICAL":
            blocks.append("GUIDANCE: The senior is asking about their schedule or plans. Provide relevant family updates concisely and clearly.")

    if facts:
        facts_lines = "\n".join(f"- {f}" for f in facts)
        blocks.append(f"--- SENIOR PROFILE & BELOVED ANCHORS (Use at most ONE when fitting) ---\n{facts_lines}")

    if caregiver_updates:
        updates_lines = "\n".join(f"- {u}" for u in caregiver_updates)
        blocks.append(f"--- TODAY'S FAMILY / CAREGIVER UPDATES (Actions planned by family; NOT by you) ---\n{updates_lines}")

    guardrails = guardrails or []
    guardrails_lines = "\n".join(f"- {g}" for g in guardrails) or "(none)"
    blocks.append(f"--- DO NOT RAISE (Safety Guardrails) ---\n{guardrails_lines}")

    messages = [
        {
            "role": "system",
            "content": "\n\n".join(blocks),
        },
    ]
    messages.extend(history or [])
    if not is_proactive:
        messages.append({"role": "user", "content": transcript})
    return messages


THINK_ENABLE_REASONING = os.environ.get("THINK_ENABLE_REASONING", "false").lower() in ("true", "1", "yes")


def stream_reply(
    transcript: str,
    facts: list[str],
    guardrails: list[str] | None = None,
    history: list[dict] | None = None,
    caregiver_updates: list[str] | None = None,
    intent: str | None = None,
    current_hour: int | None = None,
    is_proactive: bool = False,
    pending_conflicts: list[dict] | None = None,
) -> Iterator[str]:
    client = get_client()
    # nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B: compact MoE, better latency fit for our
    # <2s-to-first-audio budget than a dense 70B model. Exact casing/availability
    # from third-party aggregators, not Nebius's own docs -- verify against the
    # live Token Factory model list once a key is in hand (see IMPLEMENTATION_PLAN.md).
    model = os.environ.get("THINK_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
    kwargs = {
        "model": model,
        "messages": build_prompt(
            transcript,
            facts,
            guardrails=guardrails,
            history=history,
            caregiver_updates=caregiver_updates,
            intent=intent,
            current_hour=current_hour,
            is_proactive=is_proactive,
            pending_conflicts=pending_conflicts,
        ),
        "stream": True,
        "max_tokens": 1024,
        "temperature": 0.6,
    }
    # When reasoning is disabled (default for voice turns), tell Token Factory to bypass
    # hidden chain-of-thought tokens, dropping time-to-first-token to <1.0s (Issue #17).
    if not THINK_ENABLE_REASONING:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


SENTENCE_BOUNDARY = re.compile(r"([.!?][\"')\]]*)(\s+)")
# Words that commonly precede a "." without actually ending a sentence.
# Not exhaustive -- covers the cases that would otherwise cut a TTS chunk
# mid-title ("Dr. Smith") or mid-time ("4 P.M. today").
ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "jr", "sr", "vs", "etc", "a.m", "p.m"}


def _is_real_sentence_end(text_before_punct: str) -> bool:
    clean_text = text_before_punct.rstrip("\"')}]")
    word_match = re.search(r"([A-Za-z.]+)$", clean_text)
    if not word_match:
        return True
    word = word_match.group(1).lower().rstrip(".")
    if len(word) <= 1:
        return False  # single letter before the period, e.g. "P" in "P.M."
    return word not in ABBREVIATIONS


def sentence_chunks(token_stream: Iterator[str]) -> Iterator[str]:
    """Buffer streamed tokens into sentence-sized chunks for streamed TTS,
    skipping false sentence-ends after common abbreviations/initials."""
    buf = ""
    emitted_up_to = 0
    for token in token_stream:
        buf += token
        search_from = emitted_up_to
        while True:
            match = SENTENCE_BOUNDARY.search(buf, search_from)
            if not match:
                break
            if _is_real_sentence_end(buf[: match.start() + len(match.group(1))]):
                sentence = buf[emitted_up_to : match.end()].strip()
                if sentence:
                    yield sentence
                emitted_up_to = match.end()
                search_from = emitted_up_to
            else:
                search_from = match.end()
    tail = buf[emitted_up_to:].strip()
    if tail:
        yield tail


DURABLE_MARKERS = (
    # \b on both sides -- word-boundary matching, not substring containment,
    # is what keeps "my son" from matching "my song" and "i like" from
    # matching "i likely" (the original bug used plain `in` substring checks).
    r"\bmy name is\b",
    r"\bi (?:actually |really |still )?love\b",
    r"\bmy grandson\b",
    r"\bmy granddaughter\b",
    r"\bmy daughter\b",
    r"\bmy son\b",
    r"\bmy wife\b",
    r"\bmy husband\b",
    r"\bi (?:actually |really |still )?like\b",
    r"\bmy favorite\b",
    r"\bcall me\b",
    r"\bi used to work as\b",
    r"\bi grew up in\b",
    r"\bi was born in\b",
)

EXTRACTION_SYSTEM_PROMPT = """\
You are an eldercare memory extractor. Analyze the senior's statement and companion reply, along with the ACTIVE PROFILE FACTS and CAREGIVER NOTES.
If the senior disclosed a durable, personal fact (e.g. family member's name, past job, hometown), explicitly corrected/deleted an active fact, or contradicted a caregiver note, output exactly one of the following commands:
1. To add a new fact: `ADD: <fact>` (e.g. ADD: Loves Earl Grey tea)
2. To correct an active fact: `SUPERSEDE: <exact_old_fact> | <new_fact>` (e.g. SUPERSEDE: His grandson is named Leo | His grandson is named Liam)
3. To delete a fact because the senior asked you to forget it: `DELETE: <exact_old_fact>`
4. To flag an ambiguous conflict where the new info contradicts the old, but might be a misunderstanding or a second entity: `CONFLICT: <exact_old_fact> | <new_fact> | <reason>` (e.g. CONFLICT: Grandson is Liam | My grandson Leo is coming | Might have two grandsons or misspoke)
5. To activate a temporary quiet mode because the senior requested rest, sleep, or alone time: `QUIET_MODE`
6. To record a fleeting emotion or mood (e.g. feeling lonely, angry at someone): `EMOTION: <fact>`. NOTE: For profound life events (death, trauma, major diagnosis), do NOT use EMOTION. Just extract it as a standard permanent fact (e.g., `<fact>`).
7. To record something the senior says they are unsure about or speculating on: `UNCERTAIN: <fact>`

CRITICAL RULES:
- Use CONFLICT instead of SUPERSEDE if the change is ambiguous and you are not 100% sure it's a direct correction.
- If the senior's statement contradicts a CAREGIVER NOTE, always output a CONFLICT command.
- The senior is the elder/parent. Do NOT invert family relationships.
- Only SUPERSEDE or DELETE if the old fact is EXACTLY listed in the ACTIVE PROFILE FACTS.
- If it is just small talk, or no durable facts are present, output NONE. Do not provide commentary.

### EXAMPLES ###

[SCENARIO A]
ACTIVE PROFILE FACTS:
- His grandson is named Leo
Senior: "Actually, my grandson is Liam, not Leo."
Output: SUPERSEDE: His grandson is named Leo | His grandson is named Liam

[SCENARIO B]
ACTIVE PROFILE FACTS:
- His grandson is named Liam
Senior: "My grandson Leo is coming tomorrow."
Output: CONFLICT: His grandson is named Liam | My grandson Leo is coming | Might have two grandsons

[SCENARIO C]
CAREGIVER NOTES:
- Doctor appointment is Monday
Senior: "My doctor appointment is Thursday."
Output: CONFLICT: Doctor appointment is Monday | Doctor appointment is Thursday | Source conflict

[SCENARIO D]
ACTIVE PROFILE FACTS:
- Used to work as a carpenter
Senior: "Please forget that I told you about my carpentry job."
Output: DELETE: Used to work as a carpenter

[SCENARIO E]
ACTIVE PROFILE FACTS:
Senior: "I'm feeling really tired, I think I'm going to take a nap for a few hours."
Output: QUIET_MODE

[SCENARIO F]
ACTIVE PROFILE FACTS:
Senior: "I'm so angry with Sarah today."
Output: EMOTION: Angry with Sarah today

[SCENARIO G]
ACTIVE PROFILE FACTS:
Senior: "I think my grandson might be moving to Penang next year, but I'm not sure."
Output: UNCERTAIN: Grandson might be moving to Penang next year

[SCENARIO H]
ACTIVE PROFILE FACTS:
Senior: "My dog Buddy passed away today."
Output: His dog Buddy passed away recently
"""


# Sentinel distinguishing "the LLM call failed" from "the LLM call succeeded
# and found nothing to extract" (both of which extract_memory_llm used to
# return as plain None, which let the offline marker heuristic second-guess
# a deliberate LLM "no fact here" verdict).
LLM_CALL_FAILED = object()


def extract_memory_llm(transcript: str, reply: str, active_facts: list[str] | None = None, caregiver_updates: list[str] | None = None):
    """Async background extraction via Nemotron. Off critical path, called
    from orchestrator's background thread.

    Returns the extracted fact string, or None if the call succeeded but
    found nothing worth extracting, or LLM_CALL_FAILED if the call itself
    failed."""
    try:
        client = get_client()
        model = os.environ.get("THINK_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
        
        facts_context = "\n".join(f"- {f}" for f in (active_facts or []))
        if facts_context:
            facts_context = f"\n\nACTIVE PROFILE FACTS:\n{facts_context}"
            
        cg_context = "\n".join(f"- {u}" for u in (caregiver_updates or []))
        if cg_context:
            facts_context += f"\n\nCAREGIVER NOTES:\n{cg_context}"
            
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f'Senior: "{transcript}"\nCompanion: "{reply}"{facts_context}'},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        content = completion.choices[0].message.content if completion.choices else None
        if not content or not content.strip():
            # No usable content (e.g. a truncated, empty or whitespace-only
            # completion) is a failed call, not a deliberate "nothing to
            # extract" verdict -- only an explicit NONE response below counts
            # as that.
            return LLM_CALL_FAILED
        text = content.strip().strip('"')
        if text.strip('. \n"\'').upper() == "NONE" or len(text) < 4:
            return None
        return text
    except Exception:
        # The call itself failed (network, auth, rate limit, ...). Signalled
        # distinctly from a successful "nothing to extract" (None) so the
        # offline marker heuristic only runs as a fallback for a real failure.
        return LLM_CALL_FAILED


# Phrasings that revise or retract an earlier fact. Offline there is no way to
# know WHICH stored fact they target (SUPERSEDE/DELETE need the exact old fact),
# so the offline fallback stores nothing rather than storing the request itself
# as a new fact.
REVISION_MARKERS = (
    # Imperative forget/delete requests, at the start of the utterance (so
    # "I forget my keys" or "my son will remove the tree" stay facts).
    r"^\W*(?:(?:please|could you|can you|would you|will you)\s+)*(?:forget|delete|remove|erase)\b",
    r"\bstop remembering\b",
    r"\b(?:do not|don'?t) remember\b",
    # Sentence-initial "Actually," is a correction opener; mid-sentence
    # "I actually like jazz" is just a fact.
    r"^\W*actually\s*,",
    r"\bi was wrong\b",
    r"\bi misspoke\b",
    r"\bi meant\b",
    r"\bcorrection\b",
    # "X is Y not Z" restating the SAME slot (a name or a family relation).
    # "My favorite color is blue, not red" is a plain fact and is not matched.
    r"\b(?:name|daughter|son|grandson|granddaughter|wife|husband|sister|brother|mother|father)"
    r"\s+(?:is|was|is called|is named|called|named)\s+[a-z]+,?\s+not\s+[a-z]+",
)


def extract_new_memory(transcript: str, reply: str, active_facts: list[str] | None = None, caregiver_updates: list[str] | None = None, use_llm: bool = True) -> str | None:
    """Background extraction: does this turn contain a durable fact worth
    saving (name, preference, event), or a correction/forget request?

    The LLM runs first when online, because only it sees the active facts and
    can return SUPERSEDE/DELETE. The marker heuristic is only a fallback for
    when the LLM call itself fails -- a successful LLM verdict of "nothing to
    extract" is trusted and not second-guessed. The heuristic never stores a
    correction or forget request, or a question, as a new fact."""
    if use_llm:
        extracted = extract_memory_llm(transcript, reply, active_facts, caregiver_updates=caregiver_updates)
        if extracted is not LLM_CALL_FAILED:
            # The LLM call succeeded, whether it found a fact (truthy
            # string) or decided there was nothing to store (None). Either
            # way its verdict is trusted and not second-guessed.
            return extracted

    if "?" in transcript:
        return None

    lowered = transcript.lower()
    if any(re.search(p, lowered) for p in REVISION_MARKERS):
        return None
    for pattern in DURABLE_MARKERS:
        if re.search(pattern, lowered):
            return f"ADD: {transcript.strip()}"
    return None
