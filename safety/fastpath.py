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
    # Softened first-person falls (live probe: "I took a tumble earlier" reached
    # only the backstop): a tumble, a bit of a fall, a small fall.
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?(?:had|took)\s+(?:a\s+)?(?:bit\s+of\s+a\s+|bad\s+|little\s+|nasty\s+|small\s+|wee\s+)?(?:fall|tumble)\b(?!\s+dryers?\b)",
    # "I slipped" and "I ended up on the floor" (live probe 2026-10-30: the Known-limitations
    # examples). Not "slipped my mind / out / away / into / up", nor slipping clothes on or off.
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?slipped\b(?!\s+(?:my\s+mind|out|away|off\s+to|into|in\s+(?:quietly|unnoticed|late)\b|up\b|it\b|them\b|"
    r"(?:(?:on|off)\s+)?(?:my|a|the|her|his)\s+(?:coat|jumper|shoes?|slippers?|socks?|ring|watch|cardigan|dress|top|glasses)))",
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?ended\s+up\s+on\s+(?:the|my)\s+(?:\w+\s+)?(?:floor|ground|rug|carpet|mat)\b",
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?lost\s+my\s+(?:footing|balance)\b",
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
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?(?:had|took)\s+a\s+(?:bit\s+of\s+a\s+|bad\s+|little\s+|nasty\s+|small\s+|wee\s+)?(?:fall|tumble)\b(?!\s+dryers?\b)",
    r"\bi\s+have\s+fall\b",
    r"\bi(?:'ve|\s+have)\s+(?:just\s+)?fallen" + _NOT_A_FALL + r"\b",
    r"\bi\s+(?:just\s+|have\s+)?fell" + _NOT_A_FALL + r"\b",
    r"\bi(?:'m|\s+am)\s+falling" + _NOT_A_FALL + r"\b",
    r"\bi\s+(?:just\s+)?(?:fall|fell)\s+(?:down|over|off)\b",
    # "I slipped" and "I ended up on the floor" (live probe 2026-10-30: the Known-limitations
    # examples). Not "slipped my mind / out / away / into / up", nor slipping clothes on or off.
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?slipped\b(?!\s+(?:my\s+mind|out|away|off\s+to|into|in\s+(?:quietly|unnoticed|late)\b|up\b|it\b|them\b|"
    r"(?:(?:on|off)\s+)?(?:my|a|the|her|his)\s+(?:coat|jumper|shoes?|slippers?|socks?|ring|watch|cardigan|dress|top|glasses)))",
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?ended\s+up\s+on\s+(?:the|my)\s+(?:\w+\s+)?(?:floor|ground|rug|carpet|mat)\b",
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+)?lost\s+my\s+(?:footing|balance)\b",
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
# A room or surface word may sit before "floor" (#280): "lying on the kitchen
# floor and can't get up" is the same emergency as "on the floor".
_ON_THE_FLOOR = (
    r"on\s+(?:the|my)\s+(?:(?:kitchen|bathroom|bedroom|living\s+room|sitting\s+room|dining\s+room|front\s+room|"
    r"utility\s+room|laundry\s+room|lounge|hall|hallway|landing|garage|cold|hard|wet|bare)\s+)?(?:floor|ground)"
)
_DOWN_PLACE = (
    r"\b(?:" + _ON_THE_FLOOR + r"|hit\s+the\s+floor|down\s+here"
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
    r"\b(?:been|lying|lain|lay|stuck)\s+(?:\w+\s+){0,2}?(?:" + _ON_THE_FLOOR + r"|down\s+here)\b"
    r".*\b(?:for\s+(?:hours|ages|a\s+long\s+time|(?:an?|one|two|three|four|five|six|several|a\s+few|many|\d+)\s+hours?)"
    r"|all\s+(?:night|day|morning|afternoon)|since\s+(?:last\s+night|this\s+morning|yesterday|breakfast|lunch))\b"
)
# Stuck on the floor (#244): being stuck on the floor is the same situation as
# being unable to get up, so it gets the same reply. First person (or a bare
# "stuck on the floor" as the whole opening of the utterance), so "the drawer
# is stuck on the floor" stays a near-miss; "the second floor", "the ground
# floor", "floor plan" and the like are not a person on the ground.
_STUCK_ON_FLOOR = (
    r"(?:\bi(?:'m|\s+am|\s+got|'ve\s+been|\s+have\s+been)\s+|^\s*(?:help[\s,!.]*)?)"
    r"(?:(?:just|really|still|so|completely)\s+)*(?:stuck|trapped|stranded)\s+(?:\w+\s+){0,2}?"
    r"on\s+the\s+(?:(?!(?:ground|first|second|third|top|dance|shop|factory)\b)\w+\s+)?(?:floor|ground)\b"
    r"(?!\s+(?:floor|plans?|puzzles?|mats?|rugs?|lamps?|tiles?|polish|wax|level|space|manager)\b)"
)
DOWN_UNABLE_PATTERNS = [
    _DOWN_PLACE + r".*" + _CANNOT_SUMMON_HELP,
    _CANNOT_SUMMON_HELP + r".*" + _DOWN_PLACE,
    _DOWN_FOR_LONG,
    _STUCK_ON_FLOOR,
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
    # Unambiguous indirect goodbyes (#199, ADR-013 amended). Each is a first-person
    # farewell or a settling of affairs. The live probe "I've said my goodbyes. I'm
    # ready to go now." was answered with "take all the time you need" and no 988
    # until the AUDIT pass flagged it, a turn late. The bare "I'm ready to go" stays
    # backstop-tier unless a goodbye or death context sits beside it (see
    # _READY_TO_GO_RE). A false positive is a warm check-in and a caregiver note.
    r"\b(?:said|made)\s+(?:all\s+)?my\s+(?:final\s+|last\s+)?(?:goodbyes?|farewells?)\b",
    r"\bthis\s+is\s+(?:my\s+)?(?:last\s+|final\s+)?(?:goodbye|good\s+bye|farewell)\b"
    r"(?!\s+(?:for\s+(?:now|today|tonight|the\s+(?:day|night|moment|time\s+being))|until|till|then))",
    r"\bi(?:\s+won'?t|(?:'ll|\s+will)\s+not|(?:'m|\s+am)\s+not\s+going\s+to)\s+be\s+(?:here|around)(?:\s+for)?\s+much\s+longer\b",
    r"\b(?:put|putting|got|getting|set|setting)\s+(?:all\s+)?my\s+affairs\s+in\s+order\b",
    r"\bgiving\s+(?:away\s+)?(?:all\s+(?:of\s+)?)?my\s+(?:things|stuff|belongings|possessions)(?:\s+away)?\b"
    r"(?!\s+(?:to|for)\s+(?:the\s+)?(?:charity|charities|church|library|hospice|jumble|car\s+boot|school|sale|shop|grandchildren|bin))",
    r"\bready\s+to\s+(?:leave|depart)\s+(?:this\s+)?(?:world|life|earth)\b",
    # Overdose intent: a stated wish or plan to take ALL of one's medicine. "Can I
    # take all my pills tonight?" stays a dose question (the fixed medicine answer,
    # with AUDIT behind it); "I want to take all my pills" is crisis-tier.
    r"\b(?:want(?:s|ed)?\s+to|going\s+to|gonna|thinking\s+(?:about|of)|plan(?:ning)?\s+(?:to|on)|might\s+just|could\s+just|"
    r"i'?ll\s+just|i\s+will\s+just)\s+(?:take|taking|swallow|swallowing)\s+all\s+(?:of\s+)?my\s+"
    r"(?:pills|tablets|meds|medication|medicine|sleeping\s+pills)\b",
]

# "I'm ready to go (now)" is crisis only beside a first-person goodbye or death
# context: "ready to go to the shops", "ready to go home" and a bare "ready to go"
# (the ADR-013 backstop example) stay silent. The phrase must be a whole clause.
_READY_TO_GO_RE = re.compile(
    r"\bi(?:'m|\s+am|'ve\s+been)\s+(?:(?:just|truly|really|finally|now|so)\s+)*ready\s+to\s+(?:go|leave|depart|pass|die)"
    r"(?:\s+(?:now|then|soon|tonight|today|whenever\s+(?:it'?s|it\s+is)\s+time|when\s+(?:it'?s|it\s+is)\s+time))?\s*$"
)
_GOODBYE_DEATH_CONTEXT_RE = re.compile(
    r"\bmy\s+(?:final\s+|last\s+)?(?:goodbyes?|farewells?)\b"
    r"|\b(?:said|say|saying)\s+(?:my\s+)?(?:final\s+|last\s+)?goodbyes?\s+to\s+(?:everyone|everybody|you|them|the\s+family|all)\b"
    r"|\bi(?:'ve|\s+have)\s+had\s+a\s+(?:good|long|full|great|wonderful|happy)\s+life\b"
    r"|\bmy\s+time\s+(?:is|has)\s+(?:come|up|near)\b"
    r"|\bi(?:'m|\s+am)\s+(?:dying|going\s+to\s+die)\b"
    r"|\bi(?:'m|\s+am)\s+(?:about\s+to\s+|going\s+to\s+)?pass(?:ing)?\s+(?:on|away)\b"
)

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
    # A low-severity NOTE, not an alert: the senior said he plans to drive
    # himself (see driving_plan below). Recorded with DRIVING_FLAG_SEVERITY,
    # which the caregiver panel lists but never raises as a safety alert.
    # Fixed text like the others: no quote of where he said he was going.
    "driving": "Note: Dad mentioned driving today.",
}

# Severity of the driving note. Not in webapp.HIGH_PRIORITY_SEVERITIES, so the
# panel keeps its calm state and lists the note without the red alert card.
DRIVING_FLAG_SEVERITY = "note"


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
    # #199: a goodbye said to someone at a door, station or gate is a visit ending.
    r"\bsaid\s+my\s+goodbyes\s+to\s+(?:\w+\s+){1,2}?(?:at|on|by)\s+the\s+(?:door|doorstep|front\s+door|gate|station|airport|bus\s+stop)\b",
)


def _without_benign_crisis_idioms(clause: str) -> str:
    """Remove only known idiom spans; preserve nearby genuine crisis text."""
    for pattern in _BENIGN_CRISIS_IDIOMS:
        clause = re.sub(pattern, " ", clause)
    return clause


# A first-person plan to drive himself somewhere. Not an emergency, so it is
# not part of check() and never speaks a canned line: the orchestrator uses it
# to give THINK a lift-first note, to guard the reply before it is spoken, and
# to record the disclosed DRIVING_FLAG_SEVERITY note.
# A plan, not a memory: the subject is "I" and the verb is future or
# intended ("I'll drive", "I'm going to drive", "I plan to drive", "I'm
# planning to drive", "I'm driving to the shop this afternoon"). A past
# reference elsewhere in the turn ("like I did years ago") does not cancel it. "I loved driving a bus", "I remember
# driving with my dad" and "I watched Sarah drive" name no plan of his own.
_DRIVE_ADVERBS = r"(?:\s+(?:just|probably|maybe|perhaps|still|myself|go\s+and|get\s+up\s+and|[a-z]+ly))*"
_DRIVING_INTENT_RE = re.compile(
    r"\bi(?:'ll|\s+will|\s+shall)" + _DRIVE_ADVERBS + r"\s+drive\b"
    r"|\bi(?:'m|\s+am)\s+(?:going\s+to|gonna)" + _DRIVE_ADVERBS + r"\s+drive\b"
    r"|\bi(?:'m|\s+am)" + _DRIVE_ADVERBS + r"\s+driving\b(?!\s+(?:myself|me|you|him|her)\s+(?:crazy|mad|nuts|round\s+the\s+bend|up\s+the\s+wall))"
    r"|\bi(?:'d|\s+would)\s+like\s+to" + _DRIVE_ADVERBS + r"\s+drive\b"
    r"|\bi(?:'m|\s+am)" + _DRIVE_ADVERBS + r"\s+(?:planning|hoping|meaning|wanting|intending|about|fixing|set)\s+to"
    + _DRIVE_ADVERBS + r"\s+drive\b"
    r"|\bi(?:'m|\s+am)" + _DRIVE_ADVERBS + r"\s+thinking\s+(?:of|about)" + _DRIVE_ADVERBS + r"\s+driving\b"
    r"|\bi\s+(?:plan|want|intend|mean|need|have|hope|think\s+i(?:'ll|\s+will)\s+have)\s+to" + _DRIVE_ADVERBS + r"\s+drive\b"
    r"|\bi\s+(?:might|may|could)" + _DRIVE_ADVERBS + r"\s+drive\b"
    r"|\b(?:let\s+me|gonna)" + _DRIVE_ADVERBS + r"\s+drive\b"
)
# High recall, like the rest of this module: any "I" within 40 characters of
# drive/driving counts ("I decided to drive", "I fancy driving") unless that
# span is a memory or someone else's driving ("I loved driving a bus", "I
# watched Sarah drive", "when I was young"). The strict pattern above wins
# first, so "I'm going to drive, like I did years ago" stays a plan.
_DRIVING_LOOSE_RE = re.compile(r"\b(?:i|let me|gonna)\b[^.!?]{0,40}?\bdriv(?:e|ing)\b")
_DRIVING_MEMORY_RE = re.compile(
    r"\b(?:loved|liked|enjoyed|remember(?:ed)?|recall(?:ed)?|miss(?:ed)?|watched|saw|seen|taught|"
    r"was|were|did|drove|driven|had)\b"
    r"|\bwhen\s+i\s+was\b|\byears\s+ago\b|\bback\s+then\b|\bin\s+my\s+day\b|\bas\s+a\s+(?:young|boy|lad|girl)\b"
)
_DRIVING_IDIOM_RE = re.compile(
    r"\bdriv(?:e|ing)\s+(?:myself|me|you|him|her|them)\s+(?:crazy|mad|nuts|round\s+the\s+bend|up\s+the\s+wall)\b"
)
# Past or negated driving ("I used to drive", "I don't drive anymore", "I don't
# think I'll drive") is not a plan to drive. The negation must sit within two
# words of the verb, so "I'm not tired and I'll drive" is still a plan.
_DRIVING_NOT_INTENT_RE = re.compile(
    r"\b(?:used to|can't|cannot|can not|don't|do not|won't|will not|never|stopped|gave up|no longer|not)\s+"
    r"(?:[a-z']+\s+){0,2}driv[a-z]*"
)
# Checked on the matched "I ... drive" span only, so "I'm going to drive and
# Sarah can drive me home" stays a plan (the strict pattern matched first).
_DRIVING_OTHER_DRIVER_RE = re.compile(
    r"\b(?:want|wants|ask|asks|asked|get|got|need|needs|like|have|had|let|wait\s+for)\s+(?!to\b|myself\b|me\b)[a-z']+\s+(?:to\s+)?driv"
    r"|\bdriv(?:e|ing)\s+me\b"
)


def driving_plan(text: str) -> bool:
    """True when `text` states a first-person plan to drive himself
    somewhere -- "I'll drive", "I will drive", "I'm going to drive", "I plan
    to drive down to ...", "I am driving this afternoon"; False for a
    past-tense, negated or remembered mention ("I used to drive a bus", "I
    don't drive anymore", "I loved driving a bus when I was younger"),
    someone else driving ("I watched Sarah drive", "Can Sarah drive to the
    shop for me?"), and "Alright, I'll wait for Sarah then." Curly apostrophes from
    ASR or a phone keyboard are folded by _normalize, so the curly "I'll
    drive" matches exactly like the straight one."""
    # Clause by clause, so "Sarah offered to drive me, but I'll drive myself"
    # is still a plan while "I don't drive anymore, I gave it up" is not.
    # Not split on "and": "I'm going to go and drive" is one plan.
    for clause in re.split(r"[,;.!?]|\b(?:but|so|then)\b", _normalize(text or "")):
        # Only the negated span is removed: "I don't drive at night and
        # I'll drive to the shop" keeps its plan.
        clause = _DRIVING_NOT_INTENT_RE.sub(" ", clause)
        if _DRIVING_INTENT_RE.search(clause):
            return True
        clause = _DRIVING_IDIOM_RE.sub(" ", clause)
        if any(not _DRIVING_MEMORY_RE.search(m.group(0)) and not _DRIVING_OTHER_DRIVER_RE.search(m.group(0))
               for m in _DRIVING_LOOSE_RE.finditer(clause)):
            return True
    return False


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
    goodbye_context = bool(_GOODBYE_DEATH_CONTEXT_RE.search(_without_benign_crisis_idioms(text)))
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        crisis_text = _without_benign_crisis_idioms(clause)
        ready_to_go = goodbye_context and _READY_TO_GO_RE.search(crisis_text.strip(" ,"))
        for pattern in CRISIS_PATTERNS + ([_READY_TO_GO_RE.pattern] if ready_to_go else []):
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
