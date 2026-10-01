"""Rule-based emergency/distress fast-path.

Runs synchronously on the transcript BEFORE the THINK call. This is the
latency-critical safety net: if it fires, we skip the LLM entirely for the
immediate reply and go straight to a canned, reassuring line + an urgent
caregiver flag. The slower, smarter AUDIT stage (a second LLM pass over the
model's own response) still runs after THINK on every turn, but it is async
and off the critical path to first audio -- see pipeline/orchestrator.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DISTRESS_PATTERNS = [
    r"\bfall(en|ing)?\b.*\b(down|hurt)\b",
    r"\bi('m| am)?\s*(hurt|bleeding|dizzy|can'?t breathe)\b",
    r"\bchest pain\b",
    r"\bcall (911|an ambulance|help)\b",
    r"\bi('m| am) (scared|confused and alone)\b",
]

CONFUSION_PATTERNS = [
    r"\bwhere am i\b",
    r"\bwho are you\b",
    r"\bi don'?t know (where|what day)\b",
]


@dataclass
class FastPathResult:
    triggered: bool
    severity: str  # "none" | "confusion" | "distress"
    reply_text: str | None
    caregiver_flag: str | None


def check(transcript: str) -> FastPathResult:
    text = transcript.lower()

    for pattern in DISTRESS_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="distress",
                reply_text=(
                    "I hear you, and I'm taking this seriously. "
                    "I'm letting your family know right now so someone can check on you."
                ),
                caregiver_flag=f"URGENT: possible distress in conversation — \"{transcript.strip()}\"",
            )

    for pattern in CONFUSION_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="confusion",
                reply_text=(
                    "That's okay, let's take it slow. You're safe. "
                    "I'll make a note so your family can check in with you."
                ),
                caregiver_flag=f"Possible confusion in conversation — \"{transcript.strip()}\"",
            )

    return FastPathResult(triggered=False, severity="none", reply_text=None, caregiver_flag=None)
