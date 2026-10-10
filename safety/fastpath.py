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
    r"\bi\s+have\s+fall\b",
    r"\b(i('ve| have)?\s+fallen|fall(en|ing)?\s+(down|over|off))\b",
    r"\bi('m| am)\s+falling(?!\s+asleep)\b",
    r"\bfell(?!\s+asleep)\b",
    r"\bcan(?:'?t|not)\s+get up\b",
    # Criterion 3 (#55): on/hit the floor tied to a distress co-token, either
    # order. Requires stuck / can't move / can't get up / hurt / help so benign
    # "on the floor watching telly" stays a near-miss.
    r"\b(on|hit)\s+the\s+floor\b.*\b(can(?:'?t|not)\s+(move|get up)|stuck|hurts?|help)\b",
    r"\b(stuck|can(?:'?t|not)\s+(move|get up))\b.*\b(on|hit)\s+the\s+floor\b",
    r"\b(someone\s+help\s+me|please\s+help\s+me|help\s+me\s+please)\b",
    r"\bhelp\s+me\s+(up|get\s+up|i\s+can'?t|i\s+fell|i('m| am)\s+(hurt|bleeding|stuck|trapped|in\s+pain))\b",
    r"^\s*(can\s+someone\s+)?help\s+me[!.?\s]*$",
    # Criterion 2 (#55, option A): a bare plea that is the WHOLE utterance.
    # Anchored ^...$ so "help" / "help!" fire, but "help me remember Leo"
    # (embedded) stays a near-miss -- does not reopen the #33 narrowing.
    r"^\s*help[!.?\s]*$",
    # "help me" + a fear word. The optional (me[...])? is what makes the most
    # natural phrasing reach us at all; the separator excludes '?' on purpose
    # so "Does that help? I'm scared of the dark" stays a near-miss, while '?' is
    # allowed *after* "me" so "help me? I'm scared" still fires. See #51.
    r"\bhelp\b[\s,!.:\-]*(me[\s,!.?:\-]*)?(i('m| am)\s+)?(so\s+|really\s+|very\s+)?(scared|afraid|frightened|terrified)\b",
    r"\bi('m| am)?\s*(hurt|bleeding|dizzy|can(?:'?t|not)\s+breathe)\b",
    r"\bchest (pain|hurts?)\b",
    r"\bcall\s+(for\s+)?(911|an\s+ambulance|help)\b",
]

CRISIS_PATTERNS = [
    r"\b(don'?t\s+want\s+to\s+be\s+here\s+anymore|do\s+not\s+want\s+to\s+live|want\s+to\s+die|wanna\s+die|everyone\s+would\s+be\s+better\s+off\s+without\s+me|wish\s+i\s+(was|were)\s+dead|better\s+off\s+dead|kill\s+myself|end\s+(my\s+life|it\s+all)|take\s+my\s+own\s+life|i('m| am)\s+suicidal|life\s+isn'?t\s+worth\s+living|suicide)\b",
]

CONFUSION_PATTERNS = [
    r"\bwhere am i\b",
    r"\bi don'?t know (where|what day)\b",
]


def _normalize(text: str) -> str:
    """Normalize punctuation that varies by source before matching.

    Curly quotes come from phone keyboards and ASR output, so "I'm hurt" and
    the curly-quoted form must match identically. Dashes are folded to a space
    for the same reason: transcripts arrive as "-", en dash, em dash or hyphen,
    and a separator class in the rules would otherwise have to name every one --
    which is how "help—I'm frightened" slipped through as a false negative
    (#51). Folding to a space also keeps \\b intact, so "well-known" still
    yields word boundaries rather than becoming one long token.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text)
    for dash in ("—", "–", "―", "‐", "‑", "−"):
        text = text.replace(dash, " ")
    return text.lower()


_BENIGN_CRISIS_IDIOMS = (
    r"\bto\s+die\s+for\b",
    r"\b(?:so\s+)?tired\s+i\s+could\s+die\b",
    r"\blaughing\s+so\s+hard\b",
)


def _without_benign_crisis_idioms(clause: str) -> str:
    """Remove only known idiom spans; preserve nearby genuine crisis text."""
    for pattern in _BENIGN_CRISIS_IDIOMS:
        clause = re.sub(pattern, " ", clause)
    return clause


@dataclass
class FastPathResult:
    triggered: bool
    severity: str  # "none" | "confusion" | "distress" | "crisis"
    immediate_reply: str | None   # spoken right away, before THINK runs
    continuation_note: str | None  # fed into THINK so the turn doesn't dead-end
    caregiver_flag: str | None


def check(transcript: str) -> FastPathResult:
    text = _normalize(transcript)

    clauses = re.split(r'[.!?;\n]+', text)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        crisis_text = _without_benign_crisis_idioms(clause)
        for pattern in CRISIS_PATTERNS:
            if re.search(pattern, crisis_text):
                return FastPathResult(
                    triggered=True,
                    severity="crisis",
                    immediate_reply=(
                        "I am so sorry you are feeling this way. Please call or text 988 to speak with someone who can help right now. "
                        "I am also letting your family know you are in distress."
                    ),
                    continuation_note=(
                        f'The person just said something indicating severe crisis: "{transcript.strip()}". '
                        "You already told them to call 988 and notified their family. "
                        "Offer gentle, non-judgmental emotional support."
                    ),
                    caregiver_flag=f"URGENT CRISIS: Senior expressed suicidal ideation or severe distress - \"{transcript.strip()}\"",
                )

    for pattern in DISTRESS_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="distress",
                immediate_reply=(
                    "I hear you, and I'm taking this seriously. "
                    "I'm letting your family know right now so someone can check on you. "
                    "I'll only tell them if I'm worried about your safety."
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
