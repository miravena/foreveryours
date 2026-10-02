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
    re.compile(r"\b(groceries|appointment|doctor|visit|visiting|calendar)\b", re.IGNORECASE),
]

MEMORY_REQUEST_PATTERNS = [
    re.compile(r"\b(what\s+do\s+you\s+remember|tell\s+me\s+about\s+my|do\s+you\s+know\s+my)\b", re.IGNORECASE),
    re.compile(r"\b(who\s+is\s+my|what\s+is\s+my)\s+(grandson|granddaughter|son|daughter|wife|husband|family|relative|friend|name)\b", re.IGNORECASE),
    re.compile(r"\b(who\s+am\s+i|where\s+was\s+i\s+born|what\s+did\s+i\s+do|my\s+grandson's\s+name|my\s+son's\s+name|my\s+daughter's\s+name)\b", re.IGNORECASE),
]


def detect_intent(transcript: str) -> Intent:
    """Classifies the senior's utterance to gate memory retrieval and prompt construction."""
    if not transcript:
        return Intent.CASUAL

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
