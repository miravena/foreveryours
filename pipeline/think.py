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
4. DO NOT PRETEND TO HAVE A PHYSICAL BODY: You are an AI voice speaking through a speaker. You cannot physically visit, deliver groceries, or drive. Never say "I will visit" or "I'll bring your groceries."
5. CAREGIVER ATTRIBUTION: Any errands, visits, or grocery deliveries are done by FAMILY or CAREGIVERS. Always say "Your family mentioned..." or "[Caregiver] is dropping off...", NEVER "I will drop off...".
6. MULTI-TURN MEMORY: Look at conversation history. Do NOT repeat facts, family updates, or schedules you already mentioned in earlier turns unless the senior specifically asks about them again.
7. NO MEDICAL DIAGNOSIS OR INSTRUCTIONS: Never give medical advice or diagnose conditions.
8. USER CONTROL: When the senior shares an emotional experience, leave space for them to continue rather than changing the topic.
9. TRIVIA & UNKNOWN FACTS: If asked for general facts or current weather that you do not know, simply say you don't have that information. Do NOT offer to contact, call, or alert family or caregivers over basic trivia.
10. NO FABRICATED MEMORIES: Only reference memories explicitly listed in the profile facts. Do not invent past memories or shared classroom/work experiences about the senior.
11. FAMILY PERSPECTIVE & IDENTITY: The person you are talking with is the beloved elder, referred to affectionately as "Dad" by their family in the briefing notes. When family notes say "Dad loves jazz", this refers to the person you are speaking with directly ("the jazz you love" / "your favorite music"). Speak to them directly as "you"—NEVER say "the music your dad loved". Never address the senior by their child's name (e.g. John is their son, Leo is their grandson, NOT the senior's name).
12. GRACEFUL GUARDRAIL REDIRECTION: When steering away from a restricted topic (such as driving), pivot warmly to everyday comforts (family visits, favorite memories, or how they are feeling today). Never use blunt or robotic phrases like "Would you like to talk about something else?".
13. ZERO-MEMORY DEFAULT: Do not use a personal memory merely to make a response feel warmer. A response can be warm and friendly without mentioning any stored memory. If the current turn can be answered naturally without memory (such as general greetings, everyday questions, math, jokes, or casual remarks), prefer using ZERO memories.
14. UNCERTAINTY & HONEST LIMITS: If the senior asks about a specific upcoming event or family plan and the provided updates are unconfirmed, vague, or absent, do not guess or manufacture confirmation. Say honestly: "I don't have a confirmed time for that" or "I don't have that noted down yet."
15. CAREGIVER PRIVACY FIREWALL: Never disclose private caregiver coordination notes, internal family arrangements, or surprise plans not intended for the senior.
16. RESPECT SENIOR AGENCY & AUTONOMY: Support the senior's dignity, choices, and independence. Never treat the senior like a child, and never act as an authoritarian proxy for caregivers.
"""


def build_prompt(
    transcript: str,
    facts: list[str],
    guardrails: list[str] | None = None,
    history: list[dict] | None = None,
    caregiver_updates: list[str] | None = None,
    intent: str | None = None,
) -> list[dict]:
    """Builds a structured eldercare prompt partitioned into semantic categories:
    senior profile anchors, family schedule updates, safety guardrails, and detected intent."""
    blocks = [SYSTEM_PROMPT]
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
    messages.append({"role": "user", "content": transcript})
    return messages


def stream_reply(
    transcript: str,
    facts: list[str],
    guardrails: list[str] | None = None,
    history: list[dict] | None = None,
    caregiver_updates: list[str] | None = None,
    intent: str | None = None,
) -> Iterator[str]:
    client = get_client()
    # nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B: compact MoE, better latency fit for our
    # <2s-to-first-audio budget than a dense 70B model. Exact casing/availability
    # from third-party aggregators, not Nebius's own docs -- verify against the
    # live Token Factory model list once a key is in hand (see IMPLEMENTATION_PLAN.md).
    model = os.environ.get("THINK_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
    stream = client.chat.completions.create(
        model=model,
        messages=build_prompt(
            transcript,
            facts,
            guardrails=guardrails,
            history=history,
            caregiver_updates=caregiver_updates,
            intent=intent,
        ),
        stream=True,
        max_tokens=1024,
        temperature=0.6,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


SENTENCE_BOUNDARY = re.compile(r"([.!?])(\s+)")
# Words that commonly precede a "." without actually ending a sentence.
# Not exhaustive -- covers the cases that would otherwise cut a TTS chunk
# mid-title ("Dr. Smith") or mid-time ("4 P.M. today").
ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "jr", "sr", "vs", "etc", "a.m", "p.m"}


def _is_real_sentence_end(text_before_punct: str) -> bool:
    word_match = re.search(r"([A-Za-z.]+)$", text_before_punct)
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
            if _is_real_sentence_end(buf[: match.start() + 1]):
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
    r"\bi love\b",
    r"\bmy grandson\b",
    r"\bmy granddaughter\b",
    r"\bmy daughter\b",
    r"\bmy son\b",
    r"\bmy wife\b",
    r"\bmy husband\b",
    r"\bi like\b",
    r"\bmy favorite\b",
    r"\bcall me\b",
    r"\bi used to work as\b",
    r"\bi grew up in\b",
    r"\bi was born in\b",
)

EXTRACTION_SYSTEM_PROMPT = """\
You are an eldercare memory extractor. Analyze the senior's statement and companion reply.
If the senior disclosed a durable, personal fact about their life (e.g. family member's name,
past job, hometown, strong preference, beloved hobby), extract it as a single concise fact sentence
(e.g., "Senior used to work as a carpenter in Chicago" or "Loves Earl Grey tea").
CRITICAL RULE: The senior is the elder/parent. Do NOT invert family relationships (e.g. never extract "Senior's dad" when caregiver notes refer to Dad). Never extract facts about the AI companion itself.
If the statement is just small talk, transient feeling, greeting, or contains no durable life facts,
respond with the word NONE. Do not provide commentary or explanation.
"""


def extract_memory_llm(transcript: str, reply: str) -> str | None:
    """Async background extraction via Nemotron. Off critical path, called
    from orchestrator's background thread."""
    try:
        client = get_client()
        model = os.environ.get("THINK_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f'Senior: "{transcript}"\nCompanion: "{reply}"'},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            return None
        text = content.strip().strip('"')
        if text.upper() == "NONE" or len(text) < 4:
            return None
        return text
    except Exception:
        return None


def extract_new_memory(transcript: str, reply: str, use_llm: bool = True) -> str | None:
    """Background extraction: does this turn contain a durable fact worth
    saving (name, preference, event)? Runs off the critical path -- see
    orchestrator.py's async background thread. Fast regex heuristic first,
    falling back to async LLM extraction when online, or None when no durable
    facts exist."""
    lowered = transcript.lower()
    for pattern in DURABLE_MARKERS:
        if re.search(pattern, lowered):
            return transcript.strip()

    if use_llm:
        extracted = extract_memory_llm(transcript, reply)
        if extracted:
            return extracted

    return None
