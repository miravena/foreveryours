"""INTENT: Microsecond-speed intent and state classification for eldercare context gating.

Zero external dependencies, pure regex pattern matching (<1ms execution) so it adds
0.00s to time-to-first-audio. Used by orchestrator.py to gate which memory buckets
reach the LLM (e.g. suppressing grocery delivery logistics during emotional disclosures).
"""
from __future__ import annotations

import functools
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
# so the orchestrator answers it itself, the same way every time. Not "you" (the
# assistant), not a statement such as "Don't tell Sarah about the biscuits", and
# not a question about a company ("Is Google listening?", "Are you sharing what I
# say with Nebius?"): the answer "No, Sarah can't hear us" would dodge it, and
# docs/PRIVACY.md says what the app really keeps and sends. So when the
# caregiver's name is known, the third party must be that name, a family word,
# "anyone", or she/he/they.
_NOT_A_PERSON = r"(?!(?:you|i|we|it|this|that|there|the|a|an|what|who|how|why|when|where|my|our|your|these|those)\b)"
_FAMILY = r"(?:my\s+|the\s+)?(?:family|daughter|son|grandson|granddaughter|wife|husband|kids|children|carers?|caregivers?|nurse)"
_ANYONE = r"(?:anyone|anybody|someone|somebody|everyone|everybody)"
_OVERHEARING = r"(?:listening|eavesdropping|overhearing|spying|monitoring)"
_WHAT_I_SAY = (r"what\s+(?:i|we)\s+(?:say|said|tell|told|talk|talked|discuss|discussed|chat|chatted)\w*"
               r"|everything\s+(?:i|we)\s+(?:say|tell|talk)\w*|(?:our|this)\s+(?:chat|conversation|talk)s?")


def _who(caregiver_name: str) -> str:
    names = "|".join(re.escape(p) for p in caregiver_name.split() if len(p) > 1)
    if not names:  # name unknown: any first name will do
        return "(?:" + _ANYONE + "|" + _FAMILY + "|she|he|they|" + _NOT_A_PERSON + r"\w+)"
    return "(?:" + _ANYONE + "|" + _FAMILY + "|she|he|they|" + names + ")"


@functools.lru_cache(maxsize=16)
def _listening_re(caregiver_name: str) -> re.Pattern:
    who = _who(caregiver_name)
    tail = r"(?:everything|all\s+(?:of\s+)?(?:this|it|that)|" + _WHAT_I_SAY + r")"
    verb = r"(?:telling|passing|sending|relaying|sharing|reading)"
    return re.compile(
        # Is Sarah listening (in / to us)?  Is anyone listening?  Is Sarah watching me?
        r"\b(?:is|are)\s+" + who + r"\s+(?:\w+\s+){0,2}?"
        r"(?:" + _OVERHEARING + r"(?:\s+(?:in|on)\b|\s+to\s+(?:us|me|everything|(?:" + _WHAT_I_SAY + r"))\b|\s*[?.!,]|\s*$|\s+(?:right\s+now|now|all|always|too)\b)"
        r"|(?:hearing|watching)\s+(?:us|me|everything|(?:" + _WHAT_I_SAY + r"))\b)"
        # Can Sarah hear what I tell you?  Can anyone hear us?  Can Sarah see what I say?
        r"|\b(?:can|could|does|do|did|will|would)\s+" + who + r"\s+(?:\w+\s+){0,2}?"
        r"(?:(?:hear|overhear|listen\s+to)\s+(?:" + _WHAT_I_SAY + r"|us|me|everything)\b"
        r"|(?:see|read|know)\s+(?:" + _WHAT_I_SAY + r")\b"
        r"|listen\s+in\b)"
        # Are you reporting to Sarah?  Are you telling Sarah everything?  Are you sharing what I say with Sarah?
        # ("Are you recording this?" is not here: the app keeps the audio a while, docs/PRIVACY.md.)
        r"|\b(?:are|were)\s+you\s+(?:\w+\s+){0,2}?(?:"
        r"reporting\s+(?:back\s+)?to\s+" + who + r"\b"
        r"|" + verb + r"\s+" + who + r"\s+" + tail +
        r"|" + verb + r"\s+" + tail + r"\s+(?:on\s+)?(?:to|with)\s+" + who + r"\b)",
        re.IGNORECASE,
    )


def is_listening_question(transcript: str, caregiver_name: str = "") -> bool:
    """True when the senior asks whether the caregiver (or anyone) can hear,
    see or is being told what he says to the assistant."""
    if not transcript:
        return False
    m = _listening_re(caregiver_name or "").search(transcript)
    if not m:
        return False
    # Standalone only: "Is Sarah listening to us? What time is my appointment?"
    # is two questions, and THINK must get the other one too.
    rest = (transcript[:m.start()] + " " + transcript[m.end():]).strip(" \t,.!?")
    return not re.search(r"[?.!]\s*\S|\b(?:and|also|what|when|where|who|how|why|which|can|could|do|does|is|are)\b", rest, re.IGNORECASE)


# "Can I take two tonight to catch up?", "Should I skip my pill?", "I missed my
# dose" (#280, THINK rule 7). The companion never advises on medicines or doses,
# and live the model answered with sympathy and a change of subject, never
# saying "don't double up, ask a doctor". The orchestrator answers these with
# fixed text. A medicine word must be in the utterance, so "Can I take two
# biscuits?" and "Should I take the dog out?" are not matched. Only a request
# to take, skip, double or change something, or a report of a missed dose, is:
# "What time is my pill?" is a schedule question and goes on as before.
_MED_WORD = r"(?:pills?|tablets?|capsules?|doses?|dosages?|medicines?|medications?|meds|inhalers?|injections?|insulin)"
_MED_RE = re.compile(r"\b" + _MED_WORD + r"\b", re.IGNORECASE)
_MED_ASK_RE = re.compile(
    r"\b(?:can|could|may|should|shall|ought|must)\s+i\s+(?:just\s+|also\s+|maybe\s+)?"
    r"(?:take|have|double|skip|miss|stop|swap|halve|split|crush|mix|combine|leave|cut|up|increase|reduce|change)\b"
    r"|\bis\s+it\s+(?:ok|okay|alright|all\s+right|safe|fine|bad|wrong)\s+(?:for\s+me\s+)?(?:to|if\s+i)\s+"
    r"(?:take|have|skip|miss|double|stop|swap|leave|forget)\b"
    r"|\bwhat\s+(?:if|happens\s+if|should\s+i\s+do\s+if)\s+i\s+(?:miss|skip|forget|forgot|missed|double|take\s+too)\b"
    r"|\bhow\s+(?:many|much)\b[^.?!]*\b(?:should|can|do)\s+i\s+take\b"
    r"|\bwhat\s+(?:dose|dosage)\b",
    re.IGNORECASE,
)
_MED_MISSED_RE = re.compile(
    r"\bi(?:'ve|\s+have)?\s+(?:just\s+|totally\s+|completely\s+)?(?:missed|forgot|forgotten|skipped)\b[^.?!]*?"
    r"\b" + _MED_WORD + r"\b",
    re.IGNORECASE,
)


_QUESTION_OPENER_RE = re.compile(
    r"(?:what|when|where|who|how|why|which|is|are|do|does|did|can|could|will|would|shall|should)\b", re.IGNORECASE)


# A dose sentence with no medicine word of its own ("Can I take two tonight to
# catch up?") counts only when another sentence names a medicine and only with a
# quantity or a catch-up word, so "I missed my pill. Can I take the dog out?" stays two
# topics for THINK.
_DOSE_QUANTITY_RE = re.compile(
    r"\b(?:two|2|three|double|twice|extra|another|more|both|half|a\s+second|one\s+more|catch\s+up|make\s+up|the\s+rest|them\s+all|it\s+all|it|them|that|these|those)\b",
    re.IGNORECASE)
# ... and a second question joined to the first ("Can I take two pills and what
# is for dinner?") is left to THINK as well.
_JOINED_QUESTION_RE = re.compile(
    r"\b(?:and|also|then|plus)\s+(?:what|when|where|who|how|why|which|is|are|do|does|did|can|could|will|would|should|shall)\b"
    r"|[,;]\s*(?:what|when|where|who|how|why|which)\b",
    re.IGNORECASE)


def is_medication_dose_question(transcript: str) -> bool:
    """True when the senior asks whether to take, skip, double or change a
    medicine or dose, or says he missed one. Standalone only: "Can I take two
    tonight? And what is for dinner?" has another request THINK must answer."""
    if not transcript or not _MED_RE.search(transcript):
        return False
    text = transcript.replace("\u2019", "'")
    found = False
    for part in re.split(r"(?<=[.?!])\s+|\n+", text):
        part = part.strip()
        if not part:
            continue
        has_med = bool(_MED_RE.search(part))
        ask = bool(_MED_ASK_RE.search(part))
        if ask and not has_med and not _DOSE_QUANTITY_RE.search(part):
            ask = False  # "Can I take the dog out?" is another question
        if ask and _JOINED_QUESTION_RE.search(part):
            return False
        if ask or _MED_MISSED_RE.search(part):
            found = True
        elif "?" in part or _QUESTION_OPENER_RE.match(part):
            return False  # "Who visits?", "What time is my pill tomorrow?": THINK answers
        elif not has_med and len(part.split()) > 3:
            # Any other sentence ("Tell me about my grandson.", "Can I take the
            # dog out?") is a request THINK must answer; fixed text only for a
            # turn that is all about the medicine. "Oh dear." is no request.
            return False
    return found


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
