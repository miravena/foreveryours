"""Rule-based emergency/distress fast-path.

Runs synchronously on the transcript BEFORE the THINK call. This is the
latency-critical safety net: a match speaks an immediate, canned reassurance
first (so the highest-stakes moment is also the fastest), then the turn
CONTINUES into THINK with a short context note so the model picks the
conversation back up instead of dead-ending it -- see orchestrator.py. The
slower, smarter AUDIT stage (a second LLM pass over the model's own
response) still runs after THINK on every turn, async and off the critical
path to first audio.

Deliberately conservative patterns: a false positive here (an unnecessary
caregiver note) is far cheaper than a false negative on a real fall.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

DISTRESS_PATTERNS = [
    r"\b(i('ve| have)?\s+had\s+a\s+fall|had\s+a\s+fall|took\s+a\s+fall)\b",
    r"\b(i('ve| have)?\s+fallen|fall(en|ing)?\s+(down|over|off))\b",
    r"\bi('m| am)\s+falling\b",
    r"\bfell(?!\s+asleep)\b",
    r"\bcan'?t get up\b",
    r"\bhelp me\b",
    r"\bi('m| am)?\s*(hurt|bleeding|dizzy|can'?t breathe)\b",
    r"\bchest (pain|hurts?)\b",
    r"\bcall (911|an ambulance|help)\b",
]

CONFUSION_PATTERNS = [
    r"\bwhere am i\b",
    r"\bi don'?t know (where|what day)\b",
]


def _normalize(text: str) -> str:
    """Normalize curly quotes (common from ASR/phone keyboards) to ASCII
    before matching, so "I’m hurt" matches the same as "I'm hurt"."""
    text = unicodedata.normalize("NFKD", text)
    return text.replace("’", "'").replace("‘", "'").lower()


@dataclass
class FastPathResult:
    triggered: bool
    severity: str  # "none" | "confusion" | "distress"
    immediate_reply: str | None   # spoken right away, before THINK runs
    continuation_note: str | None  # fed into THINK so the turn doesn't dead-end
    caregiver_flag: str | None


def check(transcript: str) -> FastPathResult:
    text = _normalize(transcript)

    for pattern in DISTRESS_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="distress",
                immediate_reply=(
                    "I hear you, and I'm taking this seriously. "
                    "I'm letting your family know right now so someone can check on you."
                ),
                continuation_note=(
                    f'The person just said something that sounded like distress: "{transcript.strip()}". '
                    "You already told them you're notifying their family -- don't repeat that. "
                    "Gently check in on how they're doing right now."
                ),
                caregiver_flag=f"URGENT: possible distress in conversation — \"{transcript.strip()}\"",
            )

    for pattern in CONFUSION_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="confusion",
                immediate_reply="That's okay, let's take it slow. You're safe.",
                continuation_note=(
                    f'The person just said something that sounded like confusion: "{transcript.strip()}". '
                    "Answer their question plainly and reassure them -- don't ignore what they asked."
                ),
                caregiver_flag=f"Possible confusion in conversation — \"{transcript.strip()}\"",
            )

    return FastPathResult(
        triggered=False, severity="none", immediate_reply=None,
        continuation_note=None, caregiver_flag=None,
    )
