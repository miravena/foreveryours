"""INTENT: Microsecond-speed intent and state classification for eldercare context gating.

Zero external dependencies, pure regex pattern matching (<1ms execution) so it adds
0.00s to time-to-first-audio. Used by orchestrator.py to gate which memory buckets
reach the LLM (e.g. suppressing grocery delivery logistics during emotional disclosures).
"""
from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    EMOTIONAL_SUPPORT = "EMOTIONAL_SUPPORT"
    LOGISTICAL = "LOGISTICAL"
    MEMORY_REQUEST = "MEMORY_REQUEST"
    MIXED = "MIXED"
    CASUAL = "CASUAL"


EMOTIONAL_PATTERNS = [
    re.compile(r"\b(sad|sadness|unhappy|crying|depressed|heartbroken|miserable|downhearted)\b", re.IGNORECASE),
    re.compile(r"\b(feel(ing)?\s+(down|blue|sad|terrible|bad|alone)|feeling\s+a\s+bit\s+blue)\b", re.IGNORECASE),
    re.compile(r"\b(lonely|alone|isolated|nobody|miss\s+(my|her|him|them))\b", re.IGNORECASE),
    re.compile(r"\b(scared|frightened|afraid|anxious|worried|nervous|dread)\b", re.IGNORECASE),
    re.compile(r"\b(tired\s+of\s+life|hopeless|hurting|grief|grieving|lost)\b", re.IGNORECASE),
]

LOGISTICAL_PATTERNS = [
    re.compile(r"\b(what('s|\s+is|\s+do\s+i\s+have)\s+.*(today|tomorrow|planned|scheduled|coming|happening))\b", re.IGNORECASE),
    re.compile(r"\b(what\s+(things\s+)?do\s+i\s+have\s+to\s+do|what\s+am\s+i\s+doing|my\s+schedule|plans?\s+today|planned\s+today|my\s+day)\b", re.IGNORECASE),
    re.compile(r"\b(plan|plans|planned|planning|agenda|itinerary|schedule|scheduled)\b", re.IGNORECASE),
    re.compile(r"\b(what\s+time|when\s+is|when\s+are|is\s+.*coming|coming\s+today|coming\s+at|arriving|dropping\s+off)\b", re.IGNORECASE),
    # Plurals count (#189): "Do I have any appointments this week?" is the
    # general schedule question, and a CASUAL turn reaches THINK with no
    # caregiver updates at all.
    re.compile(r"\b(groceries|appointments?|doctors?|visits?|visiting|calendar)\b", re.IGNORECASE),
]

MEMORY_REQUEST_PATTERNS = [
    re.compile(r"\b(what\s+do\s+you\s+remember|tell\s+me\s+about\s+my|do\s+you\s+know\s+my)\b", re.IGNORECASE),
    re.compile(r"\b(who\s+is\s+my|what\s+is\s+my)\s+(grandson|granddaughter|son|daughter|wife|husband|family|relative|friend|name)\b", re.IGNORECASE),
    re.compile(r"\b(who\s+am\s+i|where\s+was\s+i\s+born|what\s+did\s+i\s+do|my\s+grandson's\s+name|my\s+son's\s+name|my\s+daughter's\s+name)\b", re.IGNORECASE),
]


# The senior hands the choice of subject to ForeverYours ("What should we talk
# about?", "I've got nothing to talk about"). The orchestrator answers these
# with one briefed anchor and today's updates so SYSTEM_PROMPT rule 21 has
# something to offer; without it a CASUAL turn reaches THINK with no facts.
TOPIC_INVITATION_PATTERNS = [
    re.compile(r"\bwhat\s+(should|shall|can|could|do|would)\s+(we|i|you)\s+(want\s+to\s+)?(talk|chat)\s+about\b", re.IGNORECASE),
    re.compile(r"\b(nothing|anything)\s+(much\s+)?to\s+(talk|chat)\s+about\b", re.IGNORECASE),
    re.compile(r"\b(don't|do\s+not|dont)\s+know\s+what\s+to\s+(talk|chat)\s+about\b", re.IGNORECASE),
]


def is_topic_invitation(transcript: str) -> bool:
    """True when the senior invites a topic without naming one of his own."""
    return bool(transcript) and any(p.search(transcript) for p in TOPIC_INVITATION_PATTERNS)


# "Is anyone coming by today?" and its phrasings (#229). The answer is a fact
# the caregiver wrote down, so the orchestrator answers it from the caregiver
# updates instead of letting THINK improvise a visitor.
VISITOR_QUESTION_RE = re.compile(
    r"\b(anyone|anybody|someone|somebody|who|visitors?)\b[^?.!]*"
    r"\b(coming|comes?\s+(by|over|round|around|to\s+see)|visiting|visits?|stopping\s+(by|in)|stop\s+(by|in)|"
    r"dropping\s+(by|in)|drop\s+(by|in)|popping\s+(by|in|round|over)|pop\s+(by|in|round|over)|arriving|expected)\b"
    r"|\bany\s+(visitors?|company|guests?)\b",
    re.IGNORECASE,
)


def is_visitor_question(transcript: str) -> bool:
    """True when the senior asks who (if anyone) is visiting today."""
    return bool(transcript) and bool(VISITOR_QUESTION_RE.search(transcript))


# "Is Sarah listening to us?" and its phrasings (live judge T05/T06). Rule 19's
# answer needs a limit the model keeps dropping ("she only sees safety flags"),
# so the orchestrator answers it itself, the same way every time. The caregiver
# is any third party: a first name, "my daughter", "anyone". Not "you" (the
# assistant), and not a statement such as "Don't tell Sarah about the biscuits".
_NOT_A_PERSON = r"(?!(?:you|i|we|it|this|that|there|the|a|an|what|who|how|why|when|where|my|our|your|these|those)\b)"
_THIRD_PARTY = (
    r"(?:anyone|anybody|someone|somebody|everyone|everybody|"
    r"(?:my\s+|the\s+)?(?:family|daughter|son|grandson|granddaughter|wife|husband|kids|children|carers?|caregivers?|nurse)|"
    + _NOT_A_PERSON + r"\w+)"
)
_OVERHEARING = r"(?:listening|eavesdropping|overhearing|spying|monitoring)"
_WHAT_I_SAY = (r"what\s+(?:i|we)\s+(?:say|said|tell|told|talk|talked|discuss|discussed|chat|chatted)\w*"
               r"|everything\s+(?:i|we)\s+(?:say|tell|talk)\w*|(?:our|this)\s+(?:chat|conversation|talk)s?")
LISTENING_QUESTION_RE = re.compile(
    # Is Sarah listening (in / to us)?  Is anyone listening?  Is Sarah watching me?
    r"\b(?:is|are)\s+" + _THIRD_PARTY + r"\s+(?:\w+\s+){0,2}?"
    r"(?:" + _OVERHEARING + r"(?:\s+(?:in|on)\b|\s+to\s+(?:us|me|you|this|everything|our|what|my)\b|\s*[?.!,]|\s*$|\s+(?:right\s+now|now|all|always|too)\b)"
    r"|(?:hearing|watching)\s+(?:us|me|this|everything|over)\b)"
    # Can Sarah hear what I tell you?  Can anyone hear us?  Can Sarah see what I say?
    r"|\b(?:can|could|does|do|did|will|would)\s+" + _THIRD_PARTY + r"\s+(?:\w+\s+){0,2}?"
    r"(?:(?:hear|overhear|listen\s+to)\s+(?:" + _WHAT_I_SAY + r"|us|me|this|everything|anything)\b"
    r"|(?:see|read|know)\s+(?:" + _WHAT_I_SAY + r")\b"
    r"|listen\s+in\b)"
    # Are you recording this?  Are you reporting to Sarah?  Are you telling Sarah everything?
    r"|\b(?:are|were)\s+you\s+(?:\w+\s+){0,2}?"
    r"(?:(?:recording|taping)\s+(?:me|us|this|our|everything|what)\b"
    r"|reporting\s+(?:to|on|back)\b"
    r"|(?:telling|passing|sending|relaying|sharing|reading)\s+(?:\w+\s+){0,2}?(?:everything|all\s+(?:of\s+)?(?:this|it|that)|" + _WHAT_I_SAY + r"))",
    re.IGNORECASE,
)


def is_listening_question(transcript: str) -> bool:
    """True when the senior asks whether the caregiver (or anyone) can hear,
    see or is being told what he says to the assistant."""
    return bool(transcript) and bool(LISTENING_QUESTION_RE.search(transcript))


def detect_intent(transcript: str) -> Intent:
    """Classifies the senior's utterance to gate memory retrieval and prompt construction."""
    if not transcript:
        return Intent.CASUAL
    if is_visitor_question(transcript) and not any(p.search(transcript) for p in EMOTIONAL_PATTERNS):
        return Intent.LOGISTICAL

    # Pure clock inquiries ("What time is it?") are factual/casual, not schedule retrieval
    if re.search(r"\b(what\s+time\s+is\s+it|what('s|\s+is)\s+the\s+time|do\s+you\s+have\s+the\s+time)\b", transcript, re.IGNORECASE):
        if not re.search(r"\b(sarah|john|leo|appointment|doctor|groceries|visit|meeting|arrive|dropping)\b", transcript, re.IGNORECASE):
            return Intent.CASUAL

    is_emotional = any(p.search(transcript) for p in EMOTIONAL_PATTERNS)
    is_logistical = any(p.search(transcript) for p in LOGISTICAL_PATTERNS)
    is_memory_request = any(p.search(transcript) for p in MEMORY_REQUEST_PATTERNS)

    if is_emotional and is_logistical:
        return Intent.MIXED
    if is_memory_request:
        return Intent.MEMORY_REQUEST
    if is_emotional:
        return Intent.EMOTIONAL_SUPPORT
    if is_logistical:
        return Intent.LOGISTICAL

    return Intent.CASUAL
