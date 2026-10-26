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

# The fall triggers. They stay broad (a false positive is cheap), so a match
# alone does not establish that the senior himself fell: "my grandson fell off
# his bike" and "I fell in love with jazz" trigger too.
FALL_PATTERNS = [
    r"\b(i('ve| have)?\s+had\s+a\s+fall|had\s+a\s+fall|took\s+a\s+fall)\b",
    r"\bi\s+have\s+fall\b",
    r"\b(i('ve| have)?\s+fallen|fall(en|ing)?\s+(down|over|off))\b",
    r"\bi('m| am)\s+falling(?!\s+asleep)\b",
    r"\bfell(?!\s+asleep)\b",
]

# A first-person fall report. Only these get the fall-specific reply and flag
# (are you hurt, can you get up safely; "Dad reported a fall"); any other
# trigger, including a third-person fall and the ambiguous "I can't get up",
# keeps the generic distress reply and flag.
_NOT_A_FALL = (
    r"(?!\s+(?:asleep|in\s+love|for\b|behind\b|apart\b|silent\b|ill\b|sick\b|through\b|short\b"
    r"|out\s+(?:with|of\s+(?:love|touch|favou?r|fashion))\b|into\s+(?:a\s+)?(?:habit|conversation|line)\b))"
)
FALL_REPORT_PATTERNS = [
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?(?:had|took)\s+a\s+(?:bad\s+|little\s+|nasty\s+)?fall\b",
    r"\bi\s+have\s+fall\b",
    r"\bi(?:'ve|\s+have)\s+(?:just\s+)?fallen" + _NOT_A_FALL + r"\b",
    r"\bi\s+(?:just\s+|have\s+)?fell" + _NOT_A_FALL + r"\b",
    r"\bi(?:'m|\s+am)\s+falling" + _NOT_A_FALL + r"\b",
    r"\bi\s+(?:just\s+)?(?:fall|fell)\s+(?:down|over|off)\b",
]

DISTRESS_PATTERNS = FALL_PATTERNS + [
    r"\bcan(?:'?t|not)\s+get up\b",
    # Criterion 3 (#55): on/hit the floor tied to a distress co-token, either
    # order. Requires stuck / can't move / can't get up / hurt / help so benign
    # "on the floor watching telly" stays a near-miss.
    r"\b(on|hit)\s+the\s+floor\b.*\b(can(?:'?t|not)\s+(move|get up)|stuck|hurts?|help)\b",
    r"\b(stuck|can(?:'?t|not)\s+(move|get up))\b.*\b(on|hit)\s+the\s+floor\b",
    # #198: falls phrased outside the canonical words. First person only, so
    # "prices hit the floor" / "the ball hit the floor" / "hit the floor running"
    # stay near-misses; each has a negative in tests/test_fastpath.py.
    r"\bi\s+(?:just\s+)?hit\s+the\s+floor\b(?!\s+(?:running|laughing|mat|rug)\b)",
    r"\bmy\s+(?:legs?|knees?)\s+(?:just\s+)?gave\s+(?:way|out)\b(?!\s+to\b)(?!.*\b(?:years?\s+ago|decades?\s+ago|long\s+ago|when\s+i\s+was|as\s+a\s+(?:boy|girl|child|kid)|in\s+my\s+youth)\b)",
    # "went down" needs a place a fall happens, and no errand cue after it.
    r"\bi\s+(?:just\s+)?went\s+down\s+(?:in|on)\s+the\s+(?:stairs?|staircase|kitchen|bathroom|bedroom|garden|yard|hall(?:way)?|shower|toilet|street|driveway|path|living\s+room)\b(?!.*\b(?:to\s+(?:get|fetch|water|feed|see|pick|check|have|do|buy)|for\s+a\s+(?:walk|look|stroll))\b)",
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
    r"\bi('m| am)?\s*(hurt|dizzy)\b",
    r"\bcall\s+(for\s+)?help\b",
]

# A possible medical emergency: the senior must be told to call 911, because a
# caregiver flag is a notification, not a 911 call. 988 is the crisis line for
# suicidal ideation, not for chest pain or bleeding (SAMHSA's 988 FAQ: 911 is the
# contact for anything that needs immediate physical intervention). Severity
# stays "distress"; only the reply and flag wording differ. Dizziness, "hurt"
# and the fall words stay with the generic or fall reply.
PHYSICAL_EMERGENCY_PATTERNS = [
    r"\bi('m| am)?\s*(bleeding|can(?:'?t|not)\s+breathe)\b",
    r"\bchest (pain|hurts?)\b",
    r"\bcall\s+(for\s+)?(911|an\s+ambulance)\b",
]

# Said once, in the fast-path reply; THINK is told not to repeat it. The 911
# instruction is unconditional: the senior has just reported the emergency or
# asked for 911 / an ambulance, so "call 911 if you have chest pain" would make
# him re-check a symptom list he may not match ("I think I'm having a stroke").
PHYSICAL_EMERGENCY_REPLY = (
    "I hear you. Please call 911 now, or ask someone near you to call. "
    "I'm letting your family know right now so someone can check on you."
)
# Appended to the crisis reply when the same utterance also reports one.
CRISIS_PHYSICAL_EMERGENCY_SENTENCE = (
    "Please also call 911 now, or ask someone near you to call."
)

# Down and unable to summon help (#242): the senior is on the floor or has
# fallen AND cannot reach the phone, cannot call anyone, cannot get up, or has
# been down for hours. That is a physical emergency (911 or the medical alert
# button), never the 988 crisis line. Before this rule, "I'm on the floor and
# can't reach the phone" matched nothing here and the model answered with 988.
# A place word alone ("on the floor watching telly") and an unreachable phone
# alone ("can't reach the phone charger from the sofa") stay near-misses; the
# two together fire even in a benign-sounding sentence, because a needless flag
# is cheap and a missed one is not.
_DOWN_PLACE = (
    r"\b(?:on\s+the\s+(?:floor|ground)|hit\s+the\s+floor|down\s+here"
    r"|(?:had|took)\s+a\s+(?:bad\s+|little\s+|nasty\s+)?fall"
    r"|fell" + _NOT_A_FALL + r"|fallen" + _NOT_A_FALL + r")\b"
)
_CANNOT_SUMMON_HELP = (
    r"\bcan(?:'?t|not)\s+(?:"
    # can't reach / get to / find the phone (not its charger, case, bill ...)
    r"(?:reach|get\s+to|get\s+at|get\s+hold\s+of|find)\s+(?:the|my|a)\s+"
    r"(?:tele|cell\s*|mobile\s*)?phone\b(?!\s+(?:charger|case|cover|bill|book|number)\b)"
    # can't call anyone / for help / 911
    r"|(?:call|ring|phone|reach)\s+(?:anyone|anybody|someone|somebody|for\s+help|911|an\s+ambulance)\b"
    r"|get\s+up\b|move\b)"
)
_DOWN_FOR_LONG = (
    r"\b(?:been|lying|lain|lay|stuck)\s+(?:\w+\s+){0,2}?(?:on\s+the\s+(?:floor|ground)|down\s+here)\b"
    r".*\b(?:for\s+(?:hours|ages|a\s+long\s+time|(?:an?|one|two|three|four|five|six|several|a\s+few|many|\d+)\s+hours?)"
    r"|all\s+(?:night|day|morning|afternoon)|since\s+(?:last\s+night|this\s+morning|yesterday|breakfast|lunch))\b"
)
DOWN_UNABLE_PATTERNS = [
    _DOWN_PLACE + r".*" + _CANNOT_SUMMON_HELP,
    _CANNOT_SUMMON_HELP + r".*" + _DOWN_PLACE,
    _DOWN_FOR_LONG,
]

# The senior may be unable to reach a phone, so the reply offers the medical
# alert button first, gives 911, and says the family is being told now: the
# one thing that does not depend on him.
DOWN_UNABLE_REPLY = (
    "I hear you, and I'm getting help. If you can, press your medical alert button or call 911. "
    "I'm letting your family know right now so someone can check on you."
)

CRISIS_PATTERNS = [
    r"\b(don'?t\s+want\s+to\s+be\s+here\s+anymore|do\s+not\s+want\s+to\s+live|want\s+to\s+die|wanna\s+die|everyone\s+would\s+be\s+better\s+off\s+without\s+me|wish\s+i\s+(was|were)\s+dead|better\s+off\s+dead|kill\s+myself|end\s+(my\s+life|it\s+all)|take\s+my\s+own\s+life|i('m| am)\s+suicidal|life\s+isn'?t\s+worth\s+living|suicide)\b",
    # Paraphrases of the same intent (#199, ADR-013). Each is an explicit
    # first-person statement; euphemism and context-dependent talk ("I'm ready
    # to go", a plan with no stock phrase) stays with the AUDIT backstop.
    r"\b(don'?t|do\s+not)\s+want\s+to\s+(live|be\s+alive|exist)\b",
    r"\b(don'?t|do\s+not)\s+(want\s+to|wanna)\s+be\s+(around|here)\s+any\s?more\b",
    r"\b(kill(ing)?\s+myself|end(ing)?\s+my\s+own\s+life|take\s+my\s+life|taking\s+my\s+(own\s+)?life)\b",
    r"\bwish\s+i\s+(was|were)(n'?t|\s+not)\s+(here|alive)\b",
    r"\bwish\s+i('d|\s+had)\s+never\s+been\s+born\b",
    r"\b(no\s+(reason|point)\s+(to|in)\s+(live|living)|nothing\s+to\s+live\s+for|not\s+worth\s+living|(tired|sick)\s+of\s+living|had\s+enough\s+of\s+living)\b",
    r"\bsleep\s+and\s+(never|not)\s+wake\s+up\b",
    r"\bsuicidal\b",
]

CONFUSION_PATTERNS = [
    r"\bwhere am i\b",
    r"\bi don'?t know (where|what day)\b",
]

# The caregiver-facing flag text. FIXED, content-minimized
# descriptions of the trigger category -- the caregiver panel must never
# carry the senior's own words, nor a model's free-text reason about the
# conversation: both can hold health details, names or a bank PIN, and the
# panel is a caregiver-visible surface, so quoting them turns a safety
# notification into a transcript leak. The OWASP Logging Cheat Sheet's
# "data to exclude" rule applies here -- record the category, not the
# sensitive content. The AUDIT background path (pipeline/orchestrator.py)
# imports these same constants instead of re-stating the wording, so there
# is exactly one wording per category in the repo.
# Keys: fast-path severities ("crisis", "distress", "confusion"), the
# "fall" and "medical" wordings of a distress flag, and the
# AUDIT classifications ("audit_crisis", "audit_distress", "audit_unsafe").
CAREGIVER_FLAG_TEXT = {
    "crisis": (
        "URGENT CRISIS: Senior expressed suicidal ideation or severe distress. "
        "Please check on the senior now."
    ),
    "distress": (
        "URGENT: possible distress detected (a fall, injury or physical distress). "
        "Please check on the senior now."
    ),
    # Severity stays "distress"; this is only the wording for an explicit fall
    # report. Fixed text like the others: no quote, and no claim about when
    # the fall happened, which the utterance may not say.
    # Severity stays "distress"; wording for chest pain, breathing trouble,
    # bleeding or a call for 911. Fixed text, no quote, like the others.
    "medical": (
        "URGENT: possible medical emergency (chest pain, trouble breathing or bleeding). "
        "Please check on the senior now."
    ),
    "fall": (
        "URGENT: Dad reported a fall (physical distress). Please check on him now."
    ),
    # Severity stays "distress"; wording for a senior who is down and cannot
    # get up or call for help (#242). Fixed text, no quote, like the others.
    "down_unable": (
        "URGENT: the senior may be on the floor and unable to get up or call for help "
        "(physical distress). Please check on the senior now, and call 911 if you cannot reach them."
    ),
    "confusion": (
        "Possible confusion in conversation: the senior asked where they are "
        "or what is happening. Please check on the senior now."
    ),
    "audit_crisis": (
        "URGENT CRISIS: the conversation audit flagged signs of severe distress "
        "in the senior's turn. Please check on the senior now."
    ),
    "audit_distress": (
        "URGENT: possible distress detected by the conversation audit. "
        "Please check on the senior now."
    ),
    "audit_unsafe": (
        "AUDIT flagged a reply as unsafe: the companion's reply may have contained "
        "medical or unsafe advice, and it was not acted on by the companion."
    ),
}


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
    # #199: hyperbole and housing talk that the paraphrase patterns would catch.
    r"\b(?:could|would)\s+(?:just\s+)?(?:have\s+)?kill(?:ed)?\s+myself\s+for\s+(?:forgetting|losing|misplacing|missing|breaking|dropping)\b",
    r"\b(?:could|would)\s+(?:just\s+)?die\s+(?:of|from)\s+(?:embarrassment|shame|boredom|laughter|laughing)\b",
    r"\b(?:i'?d|i\s+would)\s+die\s+for\b",
    r"\bdon'?t\s+want\s+to\s+live\s+in\s+(?:a|an|the|my\s+own)\s+(?:\w+\s+){0,2}?(?:flat|house|home|street|area|city|neighbourhood|neighborhood|town|village|apartment|bungalow)\b(?!\s+(?:without|any\s?more|in\s+pain|with\s+(?:out|this|that|it)))",
    r"\b(?:tired|sick)\s+of\s+living\s+(?:in\s+(?:this|my|a|the)\s+(?:\w+\s+){0,2}?(?:flat|house|home|street|area|city|neighbourhood|neighborhood|town|village|apartment|bungalow)\b(?!\s+(?:without|any\s?more|in\s+pain|with\s+(?:out|this|that|it)))|on\s+(?:takeaways?|toast|soup|sandwiches|ready\s+meals|my\s+own))",
    r"\bnot\s+(?:feeling\s+)?suicidal\b",
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
    # The canned reply sent the senior to 911 for a physical emergency; THINK's
    # continuation then gets no 988 budget (pipeline/orchestrator.py).
    calls_911: bool = False


def check(transcript: str) -> FastPathResult:
    text = _normalize(transcript)
    # Decided before the crisis loop so a mixed report ("I want to die and I
    # can't breathe") keeps the crisis handling AND gets the 911 sentence.
    down_unable = any(re.search(p, text) for p in DOWN_UNABLE_PATTERNS)
    physical = down_unable or any(re.search(p, text) for p in PHYSICAL_EMERGENCY_PATTERNS)

    clauses = re.split(r'[.!?;\n]+', text)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        crisis_text = _without_benign_crisis_idioms(clause)
        for pattern in CRISIS_PATTERNS:
            if re.search(pattern, crisis_text):
                reply = (
                    "I am so sorry you are feeling this way. Please call or text 988 to speak with someone who can help right now. "
                    "I am also letting your family know you are in distress."
                )
                given, numbers = "told them to call or text 988", "the 988 number"
                if physical:
                    reply += " " + CRISIS_PHYSICAL_EMERGENCY_SENTENCE
                    given = "told them to call or text 988 and to call 911 now"
                    numbers = "the 988 or 911 number"
                return FastPathResult(
                    triggered=True,
                    severity="crisis",
                    immediate_reply=reply,
                    continuation_note=(
                        f'The person just said something indicating severe crisis: "{transcript.strip()}". '
                        f"You already said you are sorry, {given}, and notified their family. "
                        f"Do NOT repeat {numbers} or any hotline, and do NOT apologize or say sorry again. "
                        "Continue with gentle, non-judgmental emotional support."
                    ),
                    caregiver_flag=CAREGIVER_FLAG_TEXT["crisis"],
                )

    # Down and unable to summon help (#242) comes first among the 911 replies:
    # "I fell, I'm bleeding and can't reach the phone" needs the medical alert
    # button as much as 911, and must not be asked whether he can get up.
    if down_unable:
        return FastPathResult(
            triggered=True,
            severity="distress",
            immediate_reply=DOWN_UNABLE_REPLY,
            continuation_note=(
                f'The person may be on the floor and unable to get up or call for help: "{transcript.strip()}". '
                "You already told them to press their medical alert button or call 911 if they can, and that "
                "you're notifying their family -- don't repeat either. This is a physical emergency: never "
                "mention 988 or a crisis line. Do not give medical instructions or a diagnosis (rule 7). "
                "Stay with them, keep them talking, and gently ask whether they are hurt."
            ),
            caregiver_flag=CAREGIVER_FLAG_TEXT["down_unable"],
            calls_911=True,
        )

    # Before the fall and generic replies: "I fell and I'm bleeding" needs the
    # 911 instruction more than the get-up-safely question.
    if physical:
        return FastPathResult(
            triggered=True,
            severity="distress",
            immediate_reply=PHYSICAL_EMERGENCY_REPLY,
            continuation_note=(
                f'The person just reported a possible medical emergency: "{transcript.strip()}". '
                "You already told them to call 911 (or have someone nearby call) and that you're "
                "notifying their family -- don't repeat either. Do not give medical instructions "
                "or a diagnosis (rule 7). Stay with them and gently ask whether they have been "
                "able to call."
            ),
            caregiver_flag=CAREGIVER_FLAG_TEXT["medical"],
            calls_911=True,
        )

    # Checked on its own: a first-person fall report triggers even
    # when no broader pattern does ("I had a nasty fall").
    for pattern in FALL_REPORT_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="distress",
                immediate_reply=(
                    "I hear you, and I'm taking this seriously. Are you hurt? Can you get up safely? "
                    "I'm letting your family know right now so someone can check on you."
                ),
                continuation_note=(
                    f'The person just reported a fall: "{transcript.strip()}". '
                    "You already asked whether they are hurt and whether they can get up safely, "
                    "and told them you're notifying their family -- don't repeat any of that. "
                    "Follow up on their answer: any pain or injury, and whether it is safe to get up "
                    "slowly or better to stay put and wait for help."
                ),
                caregiver_flag=CAREGIVER_FLAG_TEXT["fall"],
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
                caregiver_flag=CAREGIVER_FLAG_TEXT["distress"],
            )

    for pattern in CONFUSION_PATTERNS:
        if re.search(pattern, text):
            return FastPathResult(
                triggered=True,
                severity="confusion",
                immediate_reply=(
                    "That's okay, let's take it slow. You're safe. "
                    "I'm letting your family know so someone can check on you."
                ),
                continuation_note=(
                    f'The person just said something that sounded like confusion: "{transcript.strip()}". '
                    "You already told them you're letting their family know -- don't repeat that. "
                    "Answer their question plainly and reassure them -- don't ignore what they asked."
                ),
                caregiver_flag=CAREGIVER_FLAG_TEXT["confusion"],
            )

    return FastPathResult(
        triggered=False, severity="none", immediate_reply=None,
        continuation_note=None, caregiver_flag=None,
    )
