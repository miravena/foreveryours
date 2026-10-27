"""One voice turn, end to end: HEAR -> fast-path check -> RECALL -> THINK
(streamed) -> SPEAK (streamed, sentence-by-sentence) -> async AUDIT +
async memory-extraction.

Latency design: SPEAK starts on the first sentence of THINK's stream, not
the full completion. AUDIT and memory-extraction run in a background
thread after the first sentence is already on its way to audio -- neither
blocks time-to-first-audio. The rule-based fast-path in safety/fastpath.py
runs synchronously but is regex-only (microseconds), so it doesn't cost
anything on the common path, and skips the LLM call for only the immediate
reassurance -- the turn still continues into THINK afterward (see below),
so a distress/confusion trigger doesn't dead-end the conversation.

Disclosure is a hard invariant, not a default: every CaregiverFlags.add()
call here states explicitly whether the senior was actually told, in the
conversation, that the flag was raised. The fast-path's immediate reply IS
that disclosure. The async AUDIT path discloses via a spoken follow-up
line -- if that fails, the flag is recorded as undisclosed, not silently
marked as if it succeeded.
"""
from __future__ import annotations

import dataclasses
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notify  # noqa: E402
from caregiver import CaregiverFlags  # noqa: E402
from memory.store import STOPWORDS, MemoryStore  # noqa: E402
from safety import fastpath  # noqa: E402

from . import audit, speak, think  # noqa: E402
from .intent import Intent, detect_intent, is_topic_invitation, is_visitor_question  # noqa: E402
from .nebius_client import NebiusNotConfigured  # noqa: E402

DISCLOSURE_LINE = "I want to let {caregiver} know about something I just said."
CRISIS_DISCLOSURE_LINE = (
    "I am also letting {caregiver} know that you may need support. "
    "If you might hurt yourself, please call or text 988 now. "
    "If you are in physical danger, call 911."
)

# Same line without the hotline, for a reply that already gave 988 (#191).
CRISIS_DISCLOSURE_LINE_NO_988 = "I am also letting {caregiver} know that you may need support."

# One-turn carry of a backstop CRISIS verdict (#199, ADR-013). The AUDIT pass
# runs after the reply, so the turn it flags has already been answered; the
# next turn's THINK context learns about it here. Process-local and keyed by
# the session's flags file, so it dies with the process and is consumed by the
# first turn that reads it. The value says whether the 988 line was actually
# heard (attested) or already in the reply, so it is given once, never twice.
_CRISIS_CARRY: dict[str, bool] = {}
_CRISIS_CARRY_LOCK = threading.Lock()

CRISIS_CARRY_NOTE_GIVEN = (
    "The conversation audit flagged signs of crisis in the person's last turn. "
    "The 988 line and the news that their family is being told were already given: "
    "do NOT mention 988 or any hotline again. Keep this reply short, warm and steady, "
    "and gently ask how they are feeling right now."
)
# The fast-path crisis note says 988 was already given; when the canned line's
# audio failed that is not true out loud, so THINK is told to say it once.
CRISIS_FASTPATH_AUDIO_FAILED_NOTE = (
    "Correction: your spoken safety line did not play aloud. In this reply say once, plainly, "
    "that they can call or text 988 right now. Still do not apologize again."
)
CRISIS_CARRY_NOTE_NOT_GIVEN = (
    "The conversation audit flagged signs of crisis in the person's last turn. "
    "Their family is being told. In this reply offer the 988 call-or-text line exactly once "
    "and say plainly that you are letting their family know. Keep it short and warm."
)

# The 988 hotline: ANY 988 token (also "9-8-8", "9 8 8", "nine eight eight")
# counts unless the surrounding text rules it out: a currency or percent sign,
# a longer number, a year, a count of things, or a room/page/number label.
# Under-detecting costs a second 988 line; over-dropping could cost the only one,
# so doubtful text counts as the hotline.
_HOTLINE_TOKEN_RE = re.compile(
    r"(?<![\w$\u00a3\u20ac#.,/-])(?:988|9[\s-]+8[\s-]+8|nine[\s-]+eight[\s-]+eight)\b(?![.,/-]?\d)",
    re.IGNORECASE,
)
_NOT_HOTLINE_AFTER_RE = re.compile(
    r"\s*(?:%|dollars?|pounds?|bucks|euros?|years?|ad\b|bc\b|ce\b|people|steps|miles|times|items|words|pages|calories|books|days|hours|minutes|dollar|kg|km)",
    re.IGNORECASE,
)
_NOT_HOTLINE_BEFORE_RE = re.compile(
    r"\b(room|suite|apartment|apt|flat|unit|page|number\s+of|box|floor|in\s+the\s+year|year|since|circa)\s+$",
    re.IGNORECASE,
)
# The crisis line named in words, not digits ("the crisis line", "the
# Suicide & Crisis Lifeline"): dropped on a physical-emergency turn (#242).
_CRISIS_LINE_WORDS_RE = re.compile(r"\b(crisis\s+(?:line|lifeline|hotline|text\s+line)|lifeline|suicide\s+(?:hotline|line|prevention))\b", re.IGNORECASE)
_OTHER_EMERGENCY_RE = re.compile(r"\b(911|999|112|emergency|ambulance)\b", re.IGNORECASE)
# Driving-plan guarantee (#192): when the senior states a plan to drive
# himself, every spoken reply on that turn -- THINK's full or partial stream,
# and the FALLBACK_REPLY_1/2 path after a stream error or empty stream --
# must offer an alternative and never endorse the drive. The prompt alone is
# not reliable (THINK sometimes only declines, or praises "getting out"), so
# this is enforced deterministically, output-side, before the text is spoken.
_DRIVING_INTENT_RE = re.compile(
    r"\b(?:i|let me|gonna)\b[^.!?]{0,40}\bdriv(?:e|ing)\b",
    re.IGNORECASE,
)
# Past or negated driving ("I used to drive", "I don't drive anymore") is not a plan to drive.
_DRIVING_NOT_INTENT_RE = re.compile(
    r"\b(?:used to|can't|cannot|can not|don't|do not|won't|will not|never|stopped|gave up|no longer)\b"
    r"[^.!?]{0,20}\bdriv",
    re.IGNORECASE,
)


def driving_plan(transcript: str) -> bool:
    """True when `transcript` states a first-person plan to drive himself
    somewhere -- "I'll drive", "I will drive", "I'm going to drive", "I plan
    to drive down to ...", "I am driving this afternoon" -- any mention of
    "i" within 40 characters of "drive"/"driving"; False for a past-tense or
    negated mention ("I used to drive", "I don't drive anymore"), a question
    about someone else driving ("Can Sarah drive to the shop for me?"), and
    T13 ("Alright, I'll wait for Sarah then."). Curly apostrophes are
    normalised the way safety.fastpath._normalize does, so ASR/phone-keyboard
    output matches the same as a plain apostrophe."""
    text = fastpath._normalize(transcript)
    if _DRIVING_NOT_INTENT_RE.search(text):
        return False
    return bool(_DRIVING_INTENT_RE.search(text))


# The two regexes below are copied from -- not imported from -- scripts/
# live_judge_check.py's OFFERS_ALTERNATIVE and ENCOURAGES_DRIVING (the script
# must not import the pipeline, nor the pipeline the script). Keeping them
# byte-for-byte identical is what makes enforce_driving_alternative()
# deterministically satisfy the judge's own checks.
_ENCOURAGES_DRIVE_ITSELF_SRC = (
    r"(glad|great|wonderful|lovely|enjoy|good idea|fun)[^.]{0,40}(getting out|driv|outing|trip|shop)|"
    r"have a (good|nice|safe|fun) (drive|trip)|drive safe"
)
# Note: the judge's own OFFERS_ALTERNATIVE accepts a bare refusal ("best not
# to drive", "avoid driving") and isn't word-bounded on "ride" (so "pride"
# matches) -- kept exactly as lenient as the deployed judge, on purpose, so
# this module can still assert its final output against the literal regex
# (AC3's negative control checks that literal match). But that leniency is
# never used to DECIDE whether to add a real alternative: _REAL_ALTERNATIVE_RE
# below is the stricter, word-bounded check enforce_driving_alternative()
# actually gates on, so "It's best not to drive" and "I know you take pride
# in your independence" (neither names an actual way there) still get the
# lift sentence prepended, even though both already satisfy OFFERS_ALTERNATIVE.
_OFFERS_ALTERNATIVE_RE = re.compile(
    r"(lift|ride|drive you|take you|pick you up|instead of driving|rather than driving|"
    r"not (to )?drive|avoid(ing)? driving|best not to drive|without driving|"
    r"someone (can|could|to) (take|drive|bring)|call (sarah|your family)|ask (sarah|your family))",
    re.IGNORECASE,
)
_REAL_ALTERNATIVE_RE = re.compile(
    r"\b(?:lifts?|rides?)\b|\bdrive you\b|\btake you\b|\bpick you up\b|"
    r"\bsomeone (?:can|could|to) (?:take|drive|bring)\b|"
    r"\bcall (?:sarah|your family)\b|\bask (?:sarah|your family)\b",
    re.IGNORECASE,
)
_ENCOURAGES_DRIVING_RE = re.compile(
    _ENCOURAGES_DRIVE_ITSELF_SRC
    + r"|(?:^|[.!?;]\s*)\W*(?:(?:oh|well|ok|okay|i see|yes|yeah|sure|alright|all right)\W+)*"
    r"(?:(?:that|it|this)(?:'s| is)? )?(?:sounds (?:like )?(?:a )?(?:good|nice|lovely|great|fun|plan)"
    r"|go for it)(?![^.!?;]*\bbut\b)",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def enforce_driving_alternative(reply: str, caregiver_name: str) -> str:
    """Rewrite `reply` so the ASSEMBLED result matches the judge's
    OFFERS_ALTERNATIVE and not ENCOURAGES_DRIVING: drop whichever sentences
    endorse the drive itself, then -- if nothing in what's left names a real
    way there (_REAL_ALTERNATIVE_RE, stricter than the judge's own regex) --
    prepend one warm lift-first sentence naming `caregiver_name`. Checked on
    the assembled text, not sentence-by-sentence, because
    _ENCOURAGES_DRIVING_RE's own gap (`[^.]{0,40}`) can span a `!` or `?`
    sentence break ("I'm glad you asked! Sarah can drive you." matches as a
    whole even though neither half matches alone). Idempotent: applying it
    to its own output changes nothing, because the endorsing sentences are
    already gone and the prepended sentence itself names a lift."""
    if not reply or not reply.strip():
        return reply
    kept = [s for s in _SENTENCE_SPLIT_RE.split(reply.strip()) if s.strip()]
    while kept and _ENCOURAGES_DRIVING_RE.search(" ".join(kept)):
        # Prefer dropping a sentence that matches on its own; if the match
        # only appears once the sentences are joined (the `!`/`?` gap above),
        # drop the first sentence to break the span, then recheck.
        for i, s in enumerate(kept):
            if _ENCOURAGES_DRIVING_RE.search(s):
                del kept[i]
                break
        else:
            kept.pop(0)
    out = " ".join(kept).strip()
    if not _REAL_ALTERNATIVE_RE.search(out):
        lift_sentence = f"Would you like me to ask {caregiver_name} for a lift instead?"
        out = f"{lift_sentence} {out}".strip() if out else lift_sentence
    return out


_CRISIS_EMPTY_REPLY = "I'm here with you. How are you feeling right now?"

# Invented relatives (#245). THINK rule 25 tells the model to state household
# facts only from the briefed memory or this conversation, but the live model
# still introduced people who do not exist ("your granddaughter Maya will bring
# lunch"). An invented relative is the most harmful kind of invented fact for
# someone with memory loss, and the one a deterministic check can see: a
# relation word after "your" (or a name bound to one) that nothing the family
# briefed and nothing the senior said contains. Narrow on purpose -- invented
# school, sport or visit detail about a KNOWN person is left to rule 25,
# because no keyword check can tell it from a briefed fact without also
# cutting ordinary small talk.
_GRANDCHILD = ("grandson", "granddaughter", "grandchild", "grandkid")
_CHILD = ("son", "daughter", "child", "kid")
# Canonical relation -> the canonical relations that vouch for it.
_KIN_ACCEPTS = {
    "son": ("son",), "daughter": ("daughter",),
    "grandson": ("grandson",), "granddaughter": ("granddaughter",),
    "grandchild": _GRANDCHILD, "grandkid": _GRANDCHILD, "child": _CHILD, "kid": _CHILD,
    "wife": ("wife",), "husband": ("husband",), "brother": ("brother",), "sister": ("sister",),
    "nephew": ("nephew",), "niece": ("niece",), "cousin": ("cousin",), "aunt": ("aunt",),
    "uncle": ("uncle",), "mother": ("mother",), "father": ("father",),
    "son-in-law": ("son-in-law",), "daughter-in-law": ("daughter-in-law",),
}
# Every spoken form -> its canonical relation.
_KIN_FORMS = {
    **{k: k for k in _KIN_ACCEPTS},
    "sons": "son", "daughters": "daughter", "grandsons": "grandson", "granddaughters": "granddaughter",
    "grandchildren": "grandchild", "grandkids": "grandkid", "children": "child", "kids": "kid",
    "wives": "wife", "husbands": "husband", "brothers": "brother", "sisters": "sister",
    "nephews": "nephew", "nieces": "niece", "cousins": "cousin", "aunts": "aunt", "uncles": "uncle",
    "mum": "mother", "mom": "mother", "sons-in-law": "son-in-law", "daughters-in-law": "daughter-in-law",
}
_KIN_ALT = "(?:" + "|".join(sorted((re.escape(f) for f in _KIN_FORMS), key=len, reverse=True)) + ")"
_KIN_ADJ = r"(?:(?:late|dear|little|eldest|oldest|youngest|younger|older|lovely|sweet)\s+)?"
_YOUR_KIN_RE = re.compile(r"\byour\s+" + _KIN_ADJ + r"(" + _KIN_ALT + r")\b(?!-)", re.IGNORECASE)
# A name: capitalised, case-sensitive, whole ("Jean-Luc", "O'Brien").
_NAME = r"[A-Z][a-z]+(?:[-'\u2019][A-Z]?[a-z]+)*"
_NAME_RE = re.compile(r"\b" + _NAME + r"\b")
_KIN_THEN_NAME_RE = re.compile(
    r"\b(?i:your)\s+(?i:" + _KIN_ADJ + _KIN_ALT + r"),?\s+(" + _NAME + r")\b"
)
# An apposition closes with a comma or ends the sentence: "Maya, your
# granddaughter, is coming". "Sorry, your grandson is Leo" is no apposition.
_NAME_THEN_KIN_RE = re.compile(
    r"\b(" + _NAME + r"),\s+(?i:your)\s+(?i:" + _KIN_ADJ + _KIN_ALT + r")\b(?=\s*(?:,|[.!?]|$))"
)
_WORD_RE = re.compile(r"[a-z]+(?:-[a-z]+)*")


_NAME_AFTER_RE = re.compile(r",?\s+(" + _NAME + r")\b")
_NAME_BEFORE_RE = re.compile(r"\b(" + _NAME + r"),\s+$")
# "I don't have any news about your wife" is honest, not an invention: a
# negation plus a no-news word earlier in the same clause clears a bare
# relation word. "I can't wait for your granddaughter to ..." does not.
_KIN_CLAUSE_BREAK_RE = re.compile(r"[,;:\u2014]|\bbut\b", re.IGNORECASE)
_KIN_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|nothing|without|don't|do not|doesn't|does not|haven't|have not|hasn't|didn't|"
    r"isn't|aren't|wasn't)\b|n['\u2019]t\b", re.IGNORECASE)


# A real question opens like one; "Your granddaughter will call, won't she?"
# is a statement with a tag.
_QUESTION_START_RE = re.compile(
    r"^\W*(?:(?:oh|and|so|well|dad|now)\W+)*(?:do|does|did|is|are|was|were|have|has|had|can|could|will|"
    r"would|shall|should|may|might|how|what|who|whom|where|when|why|which|any)\b",
    re.IGNORECASE,
)


def _name_key(name: str) -> str:
    """Lowercased, curly apostrophe straightened, possessive dropped
    ("Leo's" -> "leo"; "O'Brien" is kept whole)."""
    return re.sub(r"'s\b", "", name.lower().replace("\u2019", "'"))


# Lowercase words that never vouch for a name ("Sarah will bring groceries"
# is no proof of a grandson "Will").
_NOT_NAME_WORDS = STOPWORDS | {
    "will", "would", "can", "could", "may", "might", "must", "shall", "should", "be", "been", "being",
    "am", "not", "no", "this", "that", "these", "those", "his", "her", "him", "its", "our", "their",
    "them", "us", "there", "here", "so", "but", "if", "then", "than", "as", "by", "from", "up",
    "down", "out", "over", "just", "also", "very", "all", "any", "some", "one", "two", "new", "old",
}
# How the companion addresses the senior: "Your grandson, Dad, sounds lovely."
_ADDRESS_WORDS = {"dad", "daddy", "dear", "darling", "love", "honey", "sweetheart", "grandpa", "grandad", "granddad"}
# Capitalised words that open a sentence, never a name: "Well, your grandson is Leo."
_OPENER_WORDS = {
    "well", "yes", "yeah", "oh", "ah", "aw", "wow", "hmm", "actually", "now", "okay", "ok", "alright",
    "sure", "right", "also", "plus", "honestly", "look", "listen", "remember", "sadly", "luckily",
    "today", "tonight", "tomorrow", "indeed", "anyway", "besides", "still", "though", "meanwhile",
    "again", "first", "finally", "otherwise", "however", "course", "true", "sometimes", "perhaps",
    "maybe", "please", "thanks", "absolutely", "certainly", "definitely", "lovely", "great", "good",
    "wonderful", "sweet", "nice", "yesterday", "later", "soon",
}
# A relation the speaker denies having, right before the word: "I do not have
# a granddaughter", "no son". "Dad does not drive and his son Tom ..." is not.
_KIN_DENIED_RE = re.compile(
    r"\b(?:no|not|never|without|don't|doesn't|didn't|haven't|hasn't)\s+(?:(?:have|has|had|got|a|an|any|one)\s+){0,3}$"
    r"|n't\s+(?:(?:have|has|had|got|a|an|any|one)\s+){0,3}$",
)
_DENIED_NAME_RE = re.compile(r"\s+(?:(?:named|called)\s+)?([a-z]+(?:[-'][a-z]+)*)")
_ASKS_WHO_I_HAVE_RE = re.compile(
    r"[^.!?]*\b(?:(?:do|did)\s+i\s+(?:have|has)|have\s+i\s+(?:got|ever\s+had))\b[^.!?]*\?",
    re.IGNORECASE,
)
_LOWER_WORD_RE = re.compile(r"[a-z]+(?:[-'\u2019][a-z]+)*")


_NO_NEWS_RE = re.compile(
    r"\b(news|noted|notes?|know|knew|heard|hear|updates?|information|details?|record\w*|sure|told|"
    r"mention\w*|said|says|anything|nothing)\b", re.IGNORECASE)


def household_corpus(memory_texts: list[str], transcript: str, history: list[dict] | None,
                     caregiver_name: str) -> tuple[set[str], set[str], str]:
    """(known names, known canonical relations, caregiver's name) for
    unbriefed_relative(), all lowercased, from every active memory line, the
    senior's own words this session (his turns in `history` plus this
    transcript; the companion's turns never vouch for themselves) and the
    caregiver's name. A name is compared whole ("Jean-Luc", "O'Brien"). Any
    capitalised word there vouches for one ("named Will"), and so does any
    lowercase word -- a caregiver or the senior may type "leo" -- except
    function words such as "will" (see _NOT_NAME_WORDS). Words the companion
    calls the senior ("Dad", "dear") are never taken for a relative's name.
    A relation word counts unless denied just before it ("I have no
    granddaughter"); whose relation it is is not parsed, so "my sister has a
    son" still vouches for "your son" -- the guard is a backstop for rule 25,
    not a parser."""
    senior = [transcript or ""] + [m.get("content", "") for m in (history or []) if m.get("role") == "user"]
    # "Do I have a granddaughter named Maya?" asks; it vouches for nobody.
    senior = [_ASKS_WHO_I_HAVE_RE.sub(" ", str(t)) for t in senior]
    texts = list(memory_texts) + senior
    caregiver = _name_key((caregiver_name or "").strip())
    names: set[str] = set(_ADDRESS_WORDS) | ({caregiver} if caregiver else set())
    kin: set[str] = set()
    denied: set[str] = set()
    for t in texts:
        names.update(_name_key(n) for n in _NAME_RE.findall(str(t)))  # "named Will" stays a name
        text = _name_key(str(t))
        names.update(w for w in _LOWER_WORD_RE.findall(text) if w not in _NOT_NAME_WORDS)
        # "I do not have a granddaughter (named Maya)" vouches for neither.
        for clause in re.split(r"[.!?;,:\u2014]|\bbut\b", text):
            for m in _WORD_RE.finditer(clause):
                if m.group(0) not in _KIN_FORMS:
                    continue
                if _KIN_DENIED_RE.search(clause[:m.start()]):
                    named = _DENIED_NAME_RE.match(clause, m.end())  # only that relative's own name
                    if named:
                        denied.add(named.group(1))
                else:
                    kin.add(_KIN_FORMS[m.group(0)])
    return names - (denied - _NOT_NAME_WORDS - {caregiver}), kin, caregiver


def _bound_to(sentence: str, m: re.Match, names: set[str]) -> bool:
    """The relation word at `m` is bound to one of `names`: "your daughter
    Sarah", "Sarah, your daughter"."""
    after = _NAME_AFTER_RE.match(sentence, m.end())
    before = _NAME_BEFORE_RE.search(sentence[:m.start()])
    return any(x is not None and _name_key(x.group(1)) in names for x in (after, before))


def unbriefed_relative(sentence: str, corpus: tuple[set[str], set[str], str]) -> bool:
    """True when `sentence` introduces a relative nobody briefed: "your
    granddaughter Maya" (a name bound to a relation word, and the name is in
    nothing known), or "your granddaughter will bring lunch" (a relation the
    briefing and the senior never mention). Allowed: asking about an unknown
    relation ("Do you have a granddaughter?"), saying there is no news of one
    ("I don't have any news about your wife", see _NO_NEWS_RE), and a
    relation bound to a person the family or the senior named ("your
    daughter Sarah", "your wife Mary"). Never allowed: naming a stranger as a
    relative, even in a question. Not parsed: whose relation a memo states,
    so "your granddaughter Leo" for a briefed grandson Leo passes."""
    names, kin, _caregiver = corpus
    for m in _KIN_THEN_NAME_RE.finditer(sentence):
        if _name_key(m.group(1)) not in names:
            return True
    for m in _NAME_THEN_KIN_RE.finditer(sentence):  # "Well, your grandson ..." is no name
        key = _name_key(m.group(1))
        if key not in names and key not in _OPENER_WORDS and key not in _NOT_NAME_WORDS:
            return True
    if sentence.rstrip().rstrip("\"')\u201d\u2019").endswith("?") and _QUESTION_START_RE.match(sentence):
        return False
    for m in _YOUR_KIN_RE.finditer(sentence):
        relation = _KIN_FORMS[m.group(1).lower()]
        if any(k in kin for k in _KIN_ACCEPTS[relation]):
            continue
        # Bound to someone the family named ("your wife Mary" when a memo says
        # "Dad is married to Mary"): the person is real, and which relation
        # the memo used is not parsed.
        if _bound_to(sentence, m, names - _ADDRESS_WORDS):
            continue
        lead = _KIN_CLAUSE_BREAK_RE.split(sentence[:m.start()])[-1]
        if _KIN_NEGATION_RE.search(lead) and _NO_NEWS_RE.search(lead):
            continue
        return True
    return False


_PRONOUN_START_RE = re.compile(r"^\W*(?:she|he|they|her|his|their|them|him)\b", re.IGNORECASE)
_UNBRIEFED_EMPTY_REPLY = "I don't have any family news noted down. Have you heard from anyone lately?"

# An apology in THINK's continuation of a fast-path crisis turn: the canned
# fast-path line already apologised, so a second "sorry" is removed before it
# is spoken (output-side check; the prompt rule alone was ignored). It fails
# toward safety: a clause is removed only when it is recognisably apology-only
# ("I am so sorry you are feeling this way", "Sorry", "You don't need to
# apologize"); if any apology clause says more than that, the whole sentence is
# kept, because a second apology costs far less than a lost "don't jump".
_APOLOGY_RE = re.compile(r"\b(sorry|apologi[sz]e[sd]?|apologies)\b", re.IGNORECASE)
_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:[,;:]|\s-\s|[—–―])\s*|\s+(?=(?:but|yet)\s)", re.IGNORECASE
)
_LEADING_CONJ_RE = re.compile(r"^(?:but|and|yet)\s+", re.IGNORECASE)
_YOU_ARE = r"(?:that\s+)?you(?:'re|\s+are)\s+"
_APOLOGY_ONLY_RE = re.compile(
    r"^(?:(?:oh|dad|dear|well|and|but)\s+)*(?:"
    r"(?:i'm|im|i\s+am)\s+(?:(?:so|very|really|truly|deeply|just)\s+)*sorry"
    r"(?:\s+(?:"
    r"to\s+hear\s+(?:that|this|about\s+that)"
    r"|" + _YOU_ARE + r"(?:(?:feeling|going\s+through|dealing\s+with)\s+(?:this|that|all\s+this)(?:\s+way)?"
    r"|(?:so\s+)?(?:hurting|sad|lonely|upset|struggling|scared|in\s+pain))"
    r"|for\s+(?:what\s+you(?:'re|\s+are)\s+going\s+through|your\s+pain)"
    r"))?(?:\s+right\s+now|\s+today)?"
    r"|sorry"
    r"|(?:my\s+)?(?:sincere\s+)?apologies"
    r"|(?:you\s+)?(?:don't|do\s+not)\s+(?:need|have)\s+to\s+apologi[sz]e"
    r"|no\s+need\s+to\s+apologi[sz]e"
    r")(?:\s+(?:dad|dear))?$",
    re.IGNORECASE,
)
_FILLER_WORDS = {
    "dad", "dear", "darling", "love", "honey", "sweetheart", "friend",
    "okay", "ok", "oh", "well", "truly", "really", "now", "there",
}


def _is_filler(clause: str) -> bool:
    words = re.findall(r"[a-z']+", clause.lower())
    return len(words) <= 1 and (not words or words[0] in _FILLER_WORDS)


def _strip_apology(sentence: str) -> str:
    """`sentence` without its apology-only clauses; "" when nothing but an
    apology (and a vocative such as "Dad") was there. A sentence whose apology
    clause carries anything else comes back unchanged."""
    if not _APOLOGY_RE.search(sentence):
        return sentence
    end = sentence.rstrip()[-1:] if sentence.rstrip()[-1:] in ".!?" else "."
    body = sentence.rstrip().rstrip(".!?")
    kept = []
    for clause in _CLAUSE_SPLIT_RE.split(body):
        clause = (clause or "").strip()
        if not clause:
            continue
        if _APOLOGY_RE.search(clause):
            if not _APOLOGY_ONLY_RE.match(clause.replace("’", "'")):
                return sentence
            continue
        clause = _LEADING_CONJ_RE.sub("", clause, count=1).strip()
        if clause and not _is_filler(clause):
            kept.append(clause)
    if not kept:
        return ""
    out = ", ".join(kept) + end
    return out[0].upper() + out[1:]


def _hotline_matches(sentence: str) -> list:
    out = []
    for m in _HOTLINE_TOKEN_RE.finditer(sentence):
        if _NOT_HOTLINE_BEFORE_RE.search(sentence[: m.start()]):
            continue
        if _NOT_HOTLINE_AFTER_RE.match(sentence[m.end():]):
            continue
        out.append(m)
    return out


def _hotline_match(sentence: str):
    """The first 988-hotline mention in `sentence`, or None."""
    found = _hotline_matches(sentence)
    return found[0] if found else None


def _sub_hotline(text: str, replacement: str) -> str:
    """Replace every hotline mention (not room/price/year numbers)."""
    for m in reversed(_hotline_matches(text)):
        text = text[: m.start()] + replacement + text[m.end():]
    return text


def _strip_hotline(sentence: str) -> str:
    """Remove the hotline from a sentence that must keep its other safety
    content (for example "call 911 or 988")."""
    out = re.sub(
        r"\s*(?:,\s*)?(?:or|and)\s+(?:(?:call|text|dial)\s+(?:or\s+(?:call|text)\s+)?)?(?:" + _HOTLINE_TOKEN_RE.pattern + r")",
        "", sentence, flags=re.IGNORECASE,
    )
    return _sub_hotline(out, "the crisis line")

FALLBACK_REPLY_1 = "I'm right here with you, dear. My thoughts drifted for a second—could you say that one more time?"
FALLBACK_REPLY_2 = "I'm having a little trouble with my connection right now, dear, but I'm still right here beside you. Take your time."

# Fixes #139: a confusion/perseveration flag needs a repeated QUESTION, not
# just a repeated intent -- three distinct LOGISTICAL questions ("When is my
# appointment?" / "Are groceries coming?" / "What's planned tomorrow?") share
# one intent label but are not the same question, and must not flag.
PERSEVERATION_WINDOW_S = 1800  # 30 minutes

_CONTENT_WORD_RE = re.compile(r"[a-z0-9]+")

# Fixes #159/#153/#155/#157: generic logistics vocabulary ("appointment",
# "schedule", "dr", ...) is content, but it is not DISTINGUISHING -- three
# different appointments ("dentist" / "cardiologist" / "optometrist") or
# three different doctors ("Dr Li" / "Dr Wu" / "Dr Ng") all say "appointment"
# or "dr", so that overlap alone must never look like a repeated question.
GENERIC_LOGISTICS_WORDS = {"appointment", "appointments", "schedule", "scheduled", "coming", "dr"}


def _content_words(text: str) -> set[str]:
    """Lowercase alnum tokens of length >= 2, minus memory.store.STOPWORDS (the
    same stop-word source RECALL's own keyword matching uses, so "is this a
    repeated question" and "is this a relevant memory" agree on what counts as
    content) and minus this module's own MATCH_IGNORE_WORDS (the stop-word
    source used elsewhere in this file for fact/reminder matching)."""
    return {
        w for w in _CONTENT_WORD_RE.findall(text.lower())
        if len(w) >= 2 and w not in STOPWORDS and w not in MATCH_IGNORE_WORDS
    }


def _is_repeat_question(a: str, b: str) -> bool:
    """Two messages are the same repeated question when their CONTENT words
    overlap (Jaccard >= 0.5) AND they share a DISTINGUISHING word -- a content
    word that isn't generic logistics vocabulary (GENERIC_LOGISTICS_WORDS).
    "What time is my dentist appointment?" vs "...cardiologist appointment?"
    share {appointment} but no distinguishing word, so they do not flag; "Dr
    Li" vs "Dr Wu" share {dr} but not {li}/{wu}, so they do not flag either.
    When both distinguishing-word sets are empty (e.g. every PARAPHRASE
    reduces to the bare content word {appointment}), the content-word overlap
    alone decides it -- there's nothing more specific to disagree on.

    If both messages have NO content words at all (pure stop-word sentences
    like "What time is it?"), fall back to Jaccard over every lowercase
    alnum token at a stricter 0.8 threshold, so asking that three times still
    flags. If only one message has content words, they are never a repeat --
    an empty overlap must not look like a match."""
    words_a, words_b = _content_words(a), _content_words(b)
    if words_a and words_b:
        union = words_a | words_b
        if len(words_a & words_b) / len(union) < 0.5:
            return False
        dist_a = words_a - GENERIC_LOGISTICS_WORDS
        dist_b = words_b - GENERIC_LOGISTICS_WORDS
        if not dist_a and not dist_b:
            return True
        return bool(dist_a & dist_b)
    if not words_a and not words_b:
        all_a = set(_CONTENT_WORD_RE.findall(a.lower()))
        all_b = set(_CONTENT_WORD_RE.findall(b.lower()))
        if not all_a or not all_b:
            return False
        union = all_a | all_b
        return len(all_a & all_b) / len(union) >= 0.8
    return False


def _sanitize_caregiver_update(text: str, caregiver_name: str) -> str:
    """Rewrites first-person caregiver memos to third-person family updates so
    the AI never hallucinates that it is the one physically visiting or delivering."""
    cleaned = re.sub(r"^(i'm|i am)\s+", f"{caregiver_name} is ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(i will|i'll)\s+", f"{caregiver_name} will ", cleaned, flags=re.IGNORECASE)
    return cleaned


_VISIT_UPDATE_RE = re.compile(
    r"\b(groceries|grocery|dropping\s+off|drop(ping)?\s+by|stopping\s+by|stop\s+by|coming|come|visit(ing|s)?|"
    r"arriv\w*|bring(ing|s)?|pick(ing)?\s+you\s+up|taking\s+you)\b",
    re.IGNORECASE,
)


# The read-out speaks caregiver text without THINK, so it must never carry
# care instructions: a visit note that mentions medicine, dosing or health
# advice sends the whole question back to THINK and its guardrails.
_READOUT_UNSAFE_RE = re.compile(
    r"\b(medicat\w*|medicine|meds|pills?|tablets?|doses?|dosage|mg|aspirin|insulin|inhaler|"
    r"prescri\w*|take\s+(?:a|an|one|two|three|four|\d+|your|his|her|their)\b|don'?t\s+eat|"
    r"blood\s+pressure|sugar|symptoms?|hospital|emergency)\b",
    re.IGNORECASE,
)
# A visitor question about another day; the read-out only answers for today.
_OTHER_DAY_RE = re.compile(
    r"\b(tomorrow|yesterday|next\s+week|this\s+week(?:end)?|weekend|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def _visitor_answer(transcript: str, updates: list[str], caregiver_name: str) -> str | None:
    """Deterministic answer to "Is anyone coming by today?" (#229): the visit
    notes in today's caregiver updates, verbatim, naming who and when. None
    (THINK answers as before) when the question is not a plain visitor question
    about today, no note is a visit, or a visit note carries anything medical. The model never gets the chance to invent a visitor or drop the time."""
    if not is_visitor_question(transcript) or _OTHER_DAY_RE.search(transcript):
        return None
    parts = []
    for u in updates:
        u = u.strip()
        if not u or not _VISIT_UPDATE_RE.search(u):
            continue
        # The whole note is read (a time can sit in the next sentence), so the
        # whole note must be free of care instructions.
        if _READOUT_UNSAFE_RE.search(u):
            return None
        if caregiver_name.lower() not in u.lower():
            keep_case = u[:2].isupper() or re.match(r"I\b", u)
            u = f"{caregiver_name} mentioned: {u if keep_case else u[0].lower() + u[1:]}"
        parts.append(u if u[-1] in ".!?" else u + ".")
    return " ".join(parts) or None


MATCH_IGNORE_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "my", "your", "i", "you",
    "he", "she", "it", "we", "they", "in", "on", "at", "to", "for", "with",
    "of", "and", "or", "what", "where", "who", "when", "why", "how", "tell",
    "about", "me", "do", "did", "does", "have", "had", "has", "can", "could",
    "would", "should", "will", "today", "yesterday", "tomorrow", "day", "time",
    "morning", "afternoon", "evening", "night", "good", "hello", "hi", "hey",
    "please", "thanks", "thank", "you", "well", "yes", "no", "just", "so",
    "like", "likes", "liked", "love", "loves", "loved", "enjoy", "enjoys",
    "know", "knows", "knew", "think", "thinks", "thought", "remember", "remembers",
    "named", "called", "senior", "dad", "mom", "person", "joke", "weather",
    "capital", "plus", "minus", "divided", "times", "rain", "sun", "outside",
    "really", "much", "always", "never", "used", "also", "something", "anything",
    "thing", "things", "talk", "talking", "feel", "feeling", "felt", "say", "said",
    "there", "their",
}


def _words_match(w1: str, w2: str) -> bool:
    if w1 == w2:
        return True
    if len(w1) >= 5 and len(w2) >= 5:
        shorter, longer = (w1, w2) if len(w1) < len(w2) else (w2, w1)
        if longer.startswith(shorter) and len(longer) - len(shorter) <= 4:
            return True
    # Fixes #32: Safe inflection matching for short words (3-4 chars).
    # Allows common English suffixes (s, d, es, ed, ing) so that e.g.
    # "dog" matches "dogs" and "walk" matches "walked"/"walking".
    if len(w1) >= 3 and len(w2) >= 3:
        shorter, longer = (w1, w2) if len(w1) < len(w2) else (w2, w1)
        if longer.startswith(shorter):
            suffix = longer[len(shorter):]
            if suffix in ("s", "d", "es", "ed", "ing"):
                return True
    return False


def _find_matching_facts(transcript: str, candidates: list[str]) -> list[str]:
    """Finds candidate facts that have meaningful semantic/keyword overlap with the transcript.
    Used for Zero-Memory default in CASUAL intent so unrelated queries (math, jokes, greetings, trivia)
    receive ZERO memory anchors (avoiding forced personalization)."""
    transcript_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", transcript.lower()))
    meaningful = {w for w in transcript_words if w not in MATCH_IGNORE_WORDS}
    if not meaningful:
        return []

    scored = []
    for cand in candidates:
        cand_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", cand.lower()))
        cand_meaningful = {w for w in cand_words if w not in MATCH_IGNORE_WORDS}
        overlap = sum(1 for tw in meaningful for cw in cand_meaningful if _words_match(tw, cw))
        if overlap > 0:
            scored.append((overlap, cand))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


@dataclass
class TurnResult:
    transcript: str
    reply_text: str
    audio_paths: list[Path] = field(default_factory=list)
    memories_used: list[str] = field(default_factory=list)
    memory_saved: str | None = None
    caregiver_flag: str | None = None
    time_to_first_audio_s: float | None = None  # time to first WAV WRITTEN (synthesis)
    time_to_first_sound_s: float | None = None  # time to first SOUND played (issue #17)
    audit_verdict: str | None = None  # filled in async, may arrive after return
    background_thread: threading.Thread | None = None  # join() this before reading audit_verdict/memory_saved
    # Outbound-notification senders (#201): never joined by the app (a slow mail
    # server must not stall the next turn); tests join them.
    notify_threads: list = field(default_factory=list)
    is_fallback: bool = False
    consecutive_errors: int = 0


def _speak_turn(sentences, audio_out_dir: Path, on_chunk=None) -> tuple[str, list[Path], float | None]:
    """Runs one full SPEAK pass over a sentence stream, returns the joined
    reply text, every audio chunk's path, and the wall-clock time at which
    the FIRST chunk was ready (None if the stream was empty).

    If ``on_chunk`` is given, it is called as ``on_chunk(sentence, audio_path)``
    for each chunk the moment it is synthesized -- this lets a caller play a
    sentence while the next one is still being synthesized (issue #17). When
    ``on_chunk`` is None (the default), behavior is exactly as before, so
    callers like webapp.py that only read ``audio_paths`` are unaffected.
    The callback's return value is the consumer's acknowledgement; see
    ``_speak_disclosure`` for how it gates attestation."""
    t0 = time.monotonic()
    parts: list[str] = []
    paths: list[Path] = []
    first_audio_time: float | None = None
    for sentence, audio_path in speak.speak_sentences(sentences, audio_out_dir):
        parts.append(sentence)
        paths.append(audio_path)
        if first_audio_time is None:
            first_audio_time = time.monotonic() - t0
        if on_chunk is not None:
            on_chunk(sentence, audio_path)
    return " ".join(parts), paths, first_audio_time


def _speak_disclosure(
    text: str,
    audio_out_dir: Path,
    on_chunk=None,
) -> tuple[list[Path], bool]:
    """Synthesize and deliver a disclosure before it can be recorded as told.

    Returns ``(paths, disclosed)``. ``disclosed`` is True only when audio was
    synthesized AND an ``on_chunk`` consumer exists AND it ACCEPTED every
    chunk. Acceptance is the callback's return value, in the
    ``queue.task_done()`` sense -- an item counts as delivered only when the
    consumer says it took it, never because it was handed over: an explicit
    ``False`` (e.g. webapp's ``_ChunkConsumer.offer`` after the browser
    stopped listening, or a chunk that was enqueued but never dequeued and
    yielded) refuses attestation. Any other return value, including
    ``None`` from a plain callback that returns nothing, counts as accepted.
    A callback may instead return a pending acknowledgement -- any object
    with a ``wait_accepted()`` method, as webapp's streaming ``_on_chunk``
    does so the main reply never blocks on the browser -- and it is resolved
    here, blocking until the consumer settles it (bounded by the consumer).
    Without ``on_chunk`` (the non-streaming browser path, which has already
    handed its response to Gradio) a disclosure is never attested."""
    refused = False

    def _tracking(sentence, audio_path):
        nonlocal refused
        ack = on_chunk(sentence, audio_path)
        wait_accepted = getattr(ack, "wait_accepted", None)
        if callable(wait_accepted):
            ack = wait_accepted()
        if ack is False:
            refused = True

    _, paths, _ = _speak_turn(
        iter([text]), audio_out_dir, on_chunk=_tracking if on_chunk is not None else None
    )
    return paths, bool(paths) and on_chunk is not None and not refused


# Overall deadline for one outbound send (#201). The notifiers carry their own
# socket timeouts; this bounds everything else (DNS, a stuck relay) so a flag
# never reads "pending" forever. Patched down in tests.
NOTIFY_DEADLINE_S = 30.0


class _AckTracker:
    """Wraps a streaming `on_chunk` so the notification thread can later learn
    whether the senior's disclosure was DELIVERED, not merely synthesized
    (same acceptance rule as `_speak_disclosure`). It never blocks the turn:
    acknowledgements are collected as returned and resolved off-thread, each
    bounded by the consumer. Without an `on_chunk` nothing is attestable."""

    def __init__(self, on_chunk):
        self._on_chunk = on_chunk
        self._acks: list = []
        self._chunks: list = []

    def __call__(self, sentence, audio_path):
        ack = self._on_chunk(sentence, audio_path)
        self._acks.append(ack)
        self._chunks.append((sentence, ack))
        return ack

    def accepted_any(self, predicate) -> bool:
        """True when at least one chunk whose text matches `predicate` was
        accepted by the consumer (same acceptance rule as `attested`)."""
        if self._on_chunk is None:
            return False
        for sentence, ack in list(self._chunks):
            if not predicate(sentence):
                continue
            wait_accepted = getattr(ack, "wait_accepted", None)
            if callable(wait_accepted):
                ack = wait_accepted()
            if ack is not False:
                return True
        return False

    def attested(self, paths) -> bool:
        if self._on_chunk is None or not paths or not self._acks:
            return False
        for ack in list(self._acks):
            wait_accepted = getattr(ack, "wait_accepted", None)
            if callable(wait_accepted):
                ack = wait_accepted()
            if ack is False:
                return False
        return True


def _notify_flag(flags: CaregiverFlags, flag, notifier=None, told=None) -> None:
    """Send the one outbound notification for a flag that is already
    persisted (#201, ADR-014) and record the result on it. NEVER raises into
    the turn path: any failure, including `NOTIFY_DEADLINE_S` elapsing, becomes
    `notified=False` with the exception type name. With the channel off
    (NullNotifier) it returns at once and the flag record is untouched.

    `told` (optional callable -> bool) supplies the ATTESTED "senior was told"
    value for the message; without it the flag's stored value is used. The
    stored flag and the panel are not changed by it."""
    try:
        notifier = notifier if notifier is not None else notify.get_notifier()
        if isinstance(notifier, notify.NullNotifier):
            return
        outcome: list = []

        def _send() -> None:
            try:
                sent = flag
                if told is not None:
                    try:
                        attested = bool(told())
                    except Exception:
                        attested = False
                    sent = dataclasses.replace(flag, disclosed_to_senior=attested and flag.disclosed_to_senior)
                notifier.send(sent, str(getattr(flags, "path", "household")))
                outcome.append(None)
            except Exception as exc:
                outcome.append(type(exc).__name__)

        worker = threading.Thread(target=_send, name="fy-notify-send", daemon=True)
        worker.start()
        worker.join(timeout=NOTIFY_DEADLINE_S)
        error = outcome[0] if outcome else "TimeoutError"
        if error is None and outcome:
            flags.mark_notified(flag, True)
        else:
            flags.mark_notified(flag, False, error)
    except Exception as exc:  # the flag store itself failed; nothing left to record on
        print(f"[orchestrator] notification bookkeeping failed: {type(exc).__name__}", file=sys.stderr)


def _notify_in_background(flags: CaregiverFlags, flag, threads: list, told=None) -> None:
    """Send from a daemon thread so no turn, stream or audit step ever waits
    on a mail server. The thread is listed in `threads` (TurnResult.
    notify_threads) for tests and shutdown only; it is deliberately NOT part
    of `background_thread`, which the next turn joins."""
    try:
        notifier = notify.get_notifier()
        if isinstance(notifier, notify.NullNotifier):
            return
        t = threading.Thread(target=_notify_flag, args=(flags, flag, notifier, told),
                             name="fy-notify", daemon=True)
        t.start()
        threads.append(t)
    except Exception as exc:  # pragma: no cover - never into the turn path
        print(f"[orchestrator] notification not scheduled: {type(exc).__name__}", file=sys.stderr)


# "What did I just tell you?" -- a question about the conversation itself, not
# about stored memory (#230). The answer is in the session history, which
# reaches THINK as chat turns; the note below points at it so the reply does not
# fall back to "I missed that". It goes to THINK only, never to the caregiver
# panel, flags or memory, so a private disclosure stays private.
_SESSION_RECALL_RE = re.compile(
    r"\b(what\s+(did|was|were)\s+(i|we)\s+(just\s+)?(say|said|tell|told|mention|mentioned|talk(ed)?\s+about)"
    r"|what\s+(have\s+)?(i|we)\s+(just\s+)?(said|told|mentioned)"
    r"|do\s+you\s+remember\s+what\s+i\s+(just\s+)?(said|told|mentioned)"
    r"|what\s+i\s+just\s+(said|told|mentioned))\b",
    re.IGNORECASE,
)


def _session_recall_note(transcript: str, history: list[dict] | None) -> str | None:
    if not history or not _SESSION_RECALL_RE.search(transcript):
        return None
    last_user = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user" and m.get("content")),
        "",
    )
    if not last_user:
        return None
    last_user = " ".join(last_user.split())[:300]
    return (
        "The senior is asking what they said earlier in this conversation. "
        f'Their previous message was: "{last_user}". Tell it back to them plainly; '
        "do not say you missed it."
    )


def run_turn(
    transcript: str,
    memory_store: MemoryStore,
    flags: CaregiverFlags,
    audio_out_dir: Path,
    caregiver_name: str = "your family",
    history: list[dict] | None = None,
    consecutive_errors: int = 0,
    simulated_hour: int | None = None,
    on_chunk=None,
    is_proactive: bool = False,
    trigger_type: str = "silence",
    enable_perseveration_flag: bool = True,
    allow_hosted_call: bool = True,
) -> TurnResult:
    """`history` is session-scoped prior-turn context (see think.build_prompt's
    docstring for why this is kept separate from memory_store) -- pass None
    for a one-shot call like main.py's CLI beats; webapp.py keeps a real list
    across clicks in one browser session and passes it in each turn.

    `allow_hosted_call=False` is how webapp.py's daily request cap reaches
    this turn: the offline safety fast-path still speaks and flags
    exactly as it always does, and only the paid THINK continuation (and the
    AUDIT/extraction thread that would review it) is skipped. It is only valid
    for a transcript the fast-path answers -- anything else raises ValueError
    rather than producing a silent empty turn."""
    if not allow_hosted_call and not fastpath.check(transcript).triggered:
        raise ValueError(
            "allow_hosted_call=False needs a transcript the safety fast-path answers"
        )
    
    if is_proactive:
        # Pre-Flight Context Verification (Hallucination Risk)
        active_facts = memory_store.senior_profile_facts(time.time())
        caregiver_updates = memory_store.caregiver_schedule_updates(time.time())
        if trigger_type == "hobby" and not active_facts:
            return TurnResult(transcript, "[Proactive turn suppressed by policy: No hobbies in context]", is_fallback=True)
        if trigger_type == "reminder":
            if not caregiver_updates:
                return TurnResult(transcript, "[Proactive turn suppressed by policy: No caregiver updates in context]", is_fallback=True)
            # Delivery-aware deduplication (#132). There is no per-item "delivered"
            # marker in MemoryStore, so the only honest signal that a specific
            # reminder was already spoken is the session history: webapp.py appends
            # each proactive reply as an assistant turn. We therefore ask, per
            # schedule item, whether a recent assistant turn actually delivered
            # THAT item -- matching the item's own distinctive words against what
            # was said -- rather than pooling 2+ long words from any update and
            # looking for incidental overlap with chit-chat. Why this matters for
            # Principle #2 (the caregiver's instruction is respected, not just
            # logged): the old word-bag dropped a never-delivered, time-sensitive
            # reminder (e.g. "Sarah is dropping off groceries at 4 PM") whenever
            # recent small talk happened to reuse a couple of its words. We only
            # suppress when EVERY pending update has already been delivered; if any
            # item was never spoken, the reminder proceeds so it reaches the senior.
            if history:
                recent_ai = " ".join([h.get("content", "").lower() for h in history[-4:] if h.get("role") == "assistant"])

                def _already_delivered(item: str) -> bool:
                    # An item counts as delivered only when substantially all of
                    # its own meaningful words appear in recent assistant speech --
                    # a high per-item coverage test, not a pooled 2-of-N bag. This
                    # reuses MATCH_IGNORE_WORDS as the single stop-word source,
                    # which now contains every word from the old ad-hoc
                    # {today, tomorrow, about, there, their, would} set, so no
                    # separate stop-word list is needed.
                    item_words = [
                        w for w in re.findall(r"\b[a-z]{4,}\b", item.lower())
                        if w not in MATCH_IGNORE_WORDS
                    ]
                    if not item_words:
                        return False
                    hits = sum(1 for w in item_words if w in recent_ai)
                    return hits >= max(2, (len(item_words) * 3 + 3) // 4)

                if all(_already_delivered(u) for u in caregiver_updates):
                    return TurnResult(transcript, "[Proactive turn suppressed by policy: Reminder already delivered recently]", is_fallback=True)
            
        # Two-Strike Suppression Rule (History Bloat)
        if history and len(history) >= 2:
            if history[-1].get("role") == "assistant" and history[-2].get("role") == "assistant":
                return TurnResult(transcript, "[Proactive turn suppressed by policy: Too many consecutive AI turns]", is_fallback=True)

    t0 = time.monotonic()

    # Quiet mode must be checked before any proactive flagging. Otherwise a
    # suppressed proactive turn can persist a disclosure with no audio.
    t_now = time.time()
    raw_schedule = memory_store.caregiver_schedule_updates(now=t_now)
    quiet_breakthrough = False
    if is_proactive and memory_store.is_quiet_mode_active(now=t_now):
        urgent_updates = [u for u in raw_schedule if "[URGENT]" in u.upper()]
        if not urgent_updates:
            return TurnResult(
                transcript=transcript,
                reply_text="[Proactive turn suppressed by policy: Blocked by Quiet Mode]",
                audio_paths=[],
                audit_verdict="Blocked by Quiet Mode",
                is_fallback=True,
            )
        quiet_breakthrough = True

    fast = fastpath.check(transcript)
    # #192: on a non-fast-path turn where the senior states a plan to drive
    # himself, THINK's prompt gets a lift-first continuation note and every
    # spoken text on the turn is rewritten by enforce_driving_alternative()
    # before it reaches _speak_turn. On a fast-path (fall/crisis) turn the
    # canned line stays untouched -- see WHAT TO DO step 3 of #192.
    driving_guard = driving_plan(transcript) and not fast.triggered
    notify_threads: list[threading.Thread] = []  # outbound notifications sent from the turn thread (#201)
    immediate_audio_paths: list[Path] = []
    continuation_note = None
    if fast.triggered:
        # The emergency flag is recorded whether or not speech
        # works -- same rule as the perseveration branch below (RULE 4).
        # Synthesis is bounded by speak.TTS_TIMEOUT_S per tier, so a hung
        # Piper/espeak ends here as TimeoutExpired and the flag is written to
        # disk before THINK starts. disclosed_to_senior states the truth: True
        # only when the spoken disclosure produced audio; otherwise the
        # immediate reply still reaches the senior as text (reply_text below).
        fast_tracker = _AckTracker(on_chunk)
        try:
            _, immediate_audio_paths, first_audio_time = _speak_turn(
                iter([fast.immediate_reply]), audio_out_dir,
                on_chunk=fast_tracker if on_chunk is not None else None,
            )
        except Exception as exc:
            print(
                f"[orchestrator] fast-path disclosure TTS failed: {type(exc).__name__}",
                file=sys.stderr,
            )
            immediate_audio_paths, first_audio_time = [], None
        flag_text = fast.caregiver_flag
        if not immediate_audio_paths:
            flag_text += " (spoken disclosure failed; shown as text only)"
        fast_flag = flags.add(
            flag_text,
            severity=fast.severity,
            disclosed_to_senior=bool(immediate_audio_paths),
            source="fastpath",
        )
        _notify_in_background(
            flags, fast_flag, notify_threads,
            told=lambda paths=list(immediate_audio_paths), t=fast_tracker: t.attested(paths),
        )
        continuation_note = fast.continuation_note
    else:
        first_audio_time = None

    # #199: consume the one-turn crisis marker a previous turn's AUDIT left.
    # 988 budget for THINK's reply: 0 when the line was already given (by this
    # turn's fast-path, or by the carried marker), otherwise 1 (#191).
    carry_key = str(flags.path)
    think_tracker = None
    with _CRISIS_CARRY_LOCK:
        carried_given = _CRISIS_CARRY.get(carry_key)  # consumed only after a spoken reply
    hotline_budget = 1
    physical_911_turn = False
    if fast.triggered and fast.severity == "crisis" and immediate_audio_paths:
        # The canned line (with 988) was actually spoken.
        hotline_budget = 0
    elif fast.triggered and fast.severity == "crisis":
        # Its audio failed: THINK's one 988 is the only spoken one.
        continuation_note = f"{continuation_note} {CRISIS_FASTPATH_AUDIO_FAILED_NOTE}"
    elif carried_given is not None and not (fast.triggered and fast.severity == "crisis"):
        hotline_budget = 0 if carried_given else 1
        carry_note = CRISIS_CARRY_NOTE_GIVEN if carried_given else CRISIS_CARRY_NOTE_NOT_GIVEN
        continuation_note = f"{continuation_note} {carry_note}" if continuation_note else carry_note
    if (fast.triggered and fast.severity != "crisis" and getattr(fast, "calls_911", False)
            and carried_given is not False):
        # A physical emergency the fast path sent to 911 (#242): THINK's
        # continuation never adds the 988 crisis line. Any 988 sentence is
        # dropped, or loses only the number when it also carries 911 advice.
        # The one exception is a 988 line still owed from a previous turn's
        # crisis verdict (carried_given False), which keeps its budget of 1.
        hotline_budget = 0
        physical_911_turn = True

    intent = detect_intent(transcript)
    
    # Cognitive Drift: Perseveration Tracking -- off the public path by default
    # (webapp.py's DEV_MODE), while every enabled flag still requires an
    # actually delivered disclosure (#80 3.C3, #88).
    immediate_reply_text = fast.immediate_reply if fast.triggered else ""

    if enable_perseveration_flag and history:
        user_entries = [msg for msg in history if msg.get("role") == "user"]
        if len(user_entries) >= 2:
            prev1, prev2 = user_entries[-1], user_entries[-2]
            ts1, ts2 = prev1.get("ts"), prev2.get("ts")
            # A history entry with no 'ts' -- or a garbled one that isn't a
            # real number -- counts as outside the window -- that errs
            # toward no false confusion label (#139) rather than guessing a
            # timestamp for it or crashing the turn (Review finding on #139).
            within_window = (
                isinstance(ts1, (int, float)) and isinstance(ts2, (int, float))
                and (t_now - ts1) <= PERSEVERATION_WINDOW_S
                and (t_now - ts2) <= PERSEVERATION_WINDOW_S
            )
            is_repeat = (
                within_window
                and detect_intent(prev1["content"]) == intent
                and detect_intent(prev2["content"]) == intent
                and _is_repeat_question(prev1["content"], transcript)
                and _is_repeat_question(prev2["content"], transcript)
                and _is_repeat_question(prev1["content"], prev2["content"])
            )
            if is_repeat:
                persev_reply = "I'm going to make a note for your family that we've talked about this a few times today."
                persev_tracker = _AckTracker(on_chunk)
                try:
                    _, persev_paths, persev_first_time = _speak_turn(
                        iter([persev_reply]), audio_out_dir,
                        on_chunk=persev_tracker if on_chunk is not None else None,
                    )
                except Exception as exc:
                    print(
                        f"[orchestrator] perseveration disclosure failed: {type(exc).__name__}",
                        file=sys.stderr,
                    )
                    persev_paths, persev_first_time = [], None
                # Fixes #159 (RULE 4): the disclosure line is
                # already in the text reply (immediate_reply_text below), so
                # disclosed_to_senior stays True whether or not TTS actually
                # produced audio -- the flag must be recorded either way, not
                # only when audio exists.
                persev_flag = flags.add(
                    text=(
                        "Perseveration: the senior asked the same question "
                        f"3 times within {PERSEVERATION_WINDOW_S // 60} minutes."
                    ),
                    severity="confusion",
                    disclosed_to_senior=True,
                    source="perseveration",
                )
                _notify_in_background(
                    flags, persev_flag, notify_threads,
                    told=lambda paths=list(persev_paths), t=persev_tracker: t.attested(paths),
                )
                immediate_audio_paths.extend(persev_paths)
                if first_audio_time is None:
                    first_audio_time = persev_first_time
                    
                immediate_reply_text = (immediate_reply_text + " " + persev_reply).strip()
                
                persev_note = "The person has repeated this question multiple times. Answer them gently and concisely."
                if not continuation_note:
                    continuation_note = persev_note
                else:
                    continuation_note += f" {persev_note}"

    # ---------------------------------------------------------
    # AI RESTRAINT: QUIET MODE
    # ---------------------------------------------------------
    guardrails = memory_store.caregiver_guardrails()
    if quiet_breakthrough:
        # Allow Breakthroughs for explicit [URGENT] caregiver schedule updates
        urgent_updates = [u for u in raw_schedule if "[URGENT]" in u.upper()]
        raw_schedule = urgent_updates

        breakthrough_reply = f"I know you asked for some quiet time, but {caregiver_name} asked me to share something urgent."
        _, breakthrough_paths, breakthrough_first_time = _speak_turn(
            iter([breakthrough_reply]), audio_out_dir, on_chunk=on_chunk
        )
        immediate_audio_paths.extend(breakthrough_paths)
        if first_audio_time is None:
            first_audio_time = breakthrough_first_time

        immediate_reply_text = (immediate_reply_text + " " + breakthrough_reply).strip()
        continuation_note = "INSTRUCTION: You are breaking Quiet Mode to deliver this [URGENT] caregiver update. Deliver it gently and concisely. Do NOT apologize for interrupting, as you already apologized."
        intent = Intent.LOGISTICAL
    # ---------------------------------------------------------

    caregiver_updates = [_sanitize_caregiver_update(u, caregiver_name) for u in raw_schedule]
    profile_facts = memory_store.senior_profile_facts(now=t_now)
    recalled = [m.text for m in memory_store.search(transcript, now=t_now)]


    # History-aware anchor rotation: If an anchor (e.g. jazz) was used in the previous turn,
    # rotate unmentioned anchors to the front to prevent repetitive responses.
    if history and intent != Intent.MEMORY_REQUEST and profile_facts:
        recent_assistant_text = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                recent_assistant_text = msg.get("content", "").lower()
                break
        if recent_assistant_text:
            unmentioned = [
                f for f in profile_facts
                if not any(w in recent_assistant_text for w in re.findall(r"\b[a-zA-Z]{4,}\b", f.lower()) if w not in ("loves", "named", "with", "from"))
            ]
            if unmentioned:
                profile_facts = unmentioned + [f for f in profile_facts if f not in unmentioned]

    # Intent-aware context gating
    if intent == Intent.EMOTIONAL_SUPPORT:
        # Suppress logistical schedule updates completely on emotional disclosures
        filtered_schedule = []
        filtered_profile = profile_facts[:1]  # At most 1 gentle anchor
    elif intent == Intent.LOGISTICAL:
        # Prioritize caregiver schedule updates; suppress unrelated profile facts/hobbies.
        # A fact the question itself names stays (#245): "What's on today? And how
        # is my grandson doing?" must reach THINK with the grandson's briefed
        # facts, or the model is left to guess who he is and what he does.
        filtered_schedule = caregiver_updates
        filtered_profile = _find_matching_facts(transcript, profile_facts)[:2]
    elif intent == Intent.MEMORY_REQUEST:
        # Explicit user request for memories: permit multiple
        filtered_schedule = []
        filtered_profile = list(dict.fromkeys(profile_facts + recalled))
    elif intent == Intent.MIXED:
        filtered_schedule = caregiver_updates
        filtered_profile = profile_facts[:1]
    else:  # CASUAL
        # Zero-Memory Default: Ordinary conversational / factual queries must NOT force personalization.
        # Only inject a profile anchor if the senior's transcript explicitly mentions or relates to that topic.
        matching_facts = _find_matching_facts(transcript, profile_facts)
        filtered_schedule = []
        if is_topic_invitation(transcript):
            # The senior asked us to pick the subject (SYSTEM_PROMPT rule 21):
            # hand THINK one rotated anchor plus today's updates to offer from.
            filtered_schedule = caregiver_updates
            filtered_profile = profile_facts[:1]
        elif recalled:
            filtered_profile = recalled[:1]
        elif matching_facts:
            filtered_profile = matching_facts[:1]
        else:
            filtered_profile = []

    # Deduplicate facts and remove guardrails
    filtered_profile = [f for f in filtered_profile if f not in filtered_schedule and f not in guardrails]

    pending_conflicts = memory_store.get_pending_conflicts()
    # Only THINK asks a clarification; at the daily cap THINK never
    # runs, so the conflict must stay pending for a later turn to ask.
    if pending_conflicts and allow_hosted_call:
        memory_store.mark_conflicts_asked()

    recall_note = _session_recall_note(transcript, history)
    if recall_note:
        continuation_note = f"{continuation_note} {recall_note}" if continuation_note else recall_note
    if driving_guard:
        driving_note = (
            f"The person plans to drive himself. Offer, first, that {caregiver_name} "
            "or family could give him a lift or drive him; do not praise or "
            "encourage the drive; then rule 12."
        )
        continuation_note = f"{continuation_note} {driving_note}" if continuation_note else driving_note
    think_input = transcript if not continuation_note else f"{transcript}\n\n[{continuation_note}]"
    reply_text = ""
    think_audio_paths: list[Path] = []
    think_unavailable = False
    hosted_call_capped = False
    is_fallback = False
    if not allow_hosted_call:
        # Daily request cap: the same degraded continuation as the
        # NebiusNotConfigured branch below, without entering it -- the
        # fast-path above already spoke, disclosed and flagged; only the paid
        # THINK call (and the AUDIT/extraction thread after it) is withheld.
        hosted_call_capped = True
        think_unavailable = True
    else:
        try:
            visitor_answer = _visitor_answer(transcript, caregiver_updates, caregiver_name)
            # Only a plain logistics question gets the read-out; an emotional
            # "is anyone coming?" still goes to THINK for a warm reply.
            if visitor_answer is not None and not fast.triggered and intent == Intent.LOGISTICAL:
                token_stream = iter([visitor_answer])
            else:
                token_stream = think.stream_reply(
                    think_input,
                    filtered_profile,
                    guardrails=guardrails,
                    history=history,
                    caregiver_updates=filtered_schedule,
                    intent=intent.value,
                    current_hour=simulated_hour,
                    is_proactive=is_proactive,
                    pending_conflicts=pending_conflicts,
                )
            sentences = think.sentence_chunks(token_stream)
        
            physical_claim_pattern = re.compile(
                r"\b(i will|i'll|i am going to|i'm going to)\s+(bring|drop off|come over|visit|drive|pick up)\b",
                re.IGNORECASE,
            )
        
            dropped_hotline = []
            dropped_unbriefed = []
            # #245: what the family briefed (any active memory line, any
            # privacy: a name the caregiver wrote is not invented) and what the
            # senior said this session; a sentence naming a relative outside it
            # is dropped before it is spoken.
            known_household = household_corpus(
                [i.text for i in memory_store.all() if i.is_active(t_now)],
                transcript, history, caregiver_name,
            )
            # Fast-path crisis turn: the canned line already apologised, so
            # THINK's continuation never apologises again (it is shown as
            # text even when its audio failed); only the apology clause is
            # removed, so safety advice in the same sentence survives and a
            # 988 left in it still goes through hotline_budget below, which
            # is 0 once the canned line was spoken.
            drop_apology = fast.triggered and fast.severity == "crisis"

            def filter_sentences(s_iter):
                budget = hotline_budget
                follows_dropped = False
                for s in s_iter:
                    # Safety advice is never dropped for naming a relative. A
                    # sentence right after a dropped one that opens with a
                    # pronoun ("She is bringing soup.") is about the same
                    # invented person, so it goes too.
                    is_safety = _hotline_match(s) is not None or _OTHER_EMERGENCY_RE.search(s)
                    if not is_safety and (unbriefed_relative(s, known_household)
                                          or (follows_dropped and _PRONOUN_START_RE.match(s))):
                        dropped_unbriefed.append(s)
                        follows_dropped = True
                        continue
                    follows_dropped = False
                    if drop_apology and _APOLOGY_RE.search(s):
                        stripped = _strip_apology(s)
                        if not stripped:
                            dropped_hotline.append(s)
                            continue
                        s = stripped
                    first = _hotline_match(s)
                    if physical_911_turn and (first is not None or _CRISIS_LINE_WORDS_RE.search(s)):
                        # #242: the canned reply already gave 911, so a THINK
                        # sentence naming the crisis line is dropped whole --
                        # stripping only the number would still speak "call
                        # the crisis line or 911" for a physical emergency.
                        dropped_hotline.append(s)
                        continue
                    if first is not None:
                        # The 988 line is given once per episode (#191).
                        if budget <= 0:
                            dropped_hotline.append(s)
                            if _OTHER_EMERGENCY_RE.search(s):
                                s = _strip_hotline(s)  # keep 911 / emergency advice
                            else:
                                continue
                        else:
                            budget -= 1
                            s = s[:first.end()] + _sub_hotline(s[first.end():], "that number")
                    yield physical_claim_pattern.sub(f"{caregiver_name} will \\2", s)

            # Tracks whether THINK's own sentences (and any 988 in them) were
            # DELIVERED, so a refused 988 chunk is never carried as heard.
            think_tracker = _AckTracker(on_chunk) if on_chunk is not None else None
            if driving_guard:
                # enforce_driving_alternative() needs the whole reply before
                # anything is spoken (it may drop a sentence or prepend one),
                # so a driving-plan turn buffers THINK's full/partial stream
                # here instead of speaking it sentence-by-sentence.
                raw_text = " ".join(filter_sentences(sentences)).strip()
                guarded_text = enforce_driving_alternative(raw_text, caregiver_name) if raw_text else raw_text
                guarded_sentences = think.sentence_chunks(iter([guarded_text])) if guarded_text else iter(())
                reply_text, think_audio_paths, think_first_audio_time = _speak_turn(
                    guarded_sentences, audio_out_dir, on_chunk=think_tracker
                )
            else:
                reply_text, think_audio_paths, think_first_audio_time = _speak_turn(filter_sentences(sentences), audio_out_dir, on_chunk=think_tracker)
            if first_audio_time is None:
                first_audio_time = think_first_audio_time
            if dropped_unbriefed:
                print(f"[orchestrator] dropped {len(dropped_unbriefed)} sentence(s) naming an unbriefed relative (#245)",
                      file=sys.stderr)
            if dropped_unbriefed and not dropped_hotline and not reply_text.strip():
                # Every sentence named someone nobody briefed: say so honestly
                # instead of the "thoughts drifted" fallback. A driving-plan
                # turn still gets its lift-first line (#192), not family news.
                empty_line = (enforce_driving_alternative("I'm here with you.", caregiver_name)
                              if driving_guard else _UNBRIEFED_EMPTY_REPLY)
                reply_text, empty_paths, empty_first = _speak_turn(
                    iter([empty_line]), audio_out_dir, on_chunk=on_chunk
                )
                think_audio_paths.extend(empty_paths)
                if first_audio_time is None:
                    first_audio_time = empty_first
            if dropped_hotline and not reply_text.strip():
                # THINK said only the repeated line: speak a crisis-aware one
                # instead of the generic "thoughts drifted" fallback.
                reply_text, empty_paths, empty_first = _speak_turn(
                    iter([_CRISIS_EMPTY_REPLY]), audio_out_dir, on_chunk=on_chunk
                )
                think_audio_paths.extend(empty_paths)
                if first_audio_time is None:
                    first_audio_time = empty_first
        except NebiusNotConfigured:
            # Fast-path's immediate reply already completed the turn's safety-
            # critical part (spoken + disclosed + flagged). Without a key we
            # can't continue the conversation for real, but that's a degraded
            # continuation, not a reason to crash a turn that already succeeded.
            if not fast.triggered:
                raise
            think_unavailable = True
        except Exception as exc:
            # Unexpected network / provider error during conversation stream.
            # Log type + message only (never headers or keys) so a fallback is never silent (#78).
            print(f"[orchestrator] THINK stream failed, using fallback reply: {type(exc).__name__}: {exc}", file=sys.stderr)
            if not fast.triggered:
                is_fallback = True
                consecutive_errors += 1
                reply_text = FALLBACK_REPLY_2 if consecutive_errors >= 2 else FALLBACK_REPLY_1
                if driving_guard:
                    # Stream dropped (fully or partway through) on a
                    # driving-plan turn: the spoken fallback still needs the
                    # same guarantee as a normal reply.
                    reply_text = enforce_driving_alternative(reply_text, caregiver_name)
                _, fallback_paths, fallback_first_time = _speak_turn(iter([reply_text]), audio_out_dir, on_chunk=on_chunk)
                think_audio_paths.extend(fallback_paths)
                if first_audio_time is None:
                    first_audio_time = fallback_first_time

    # Zero-Silence Guarantee: If model returned an empty string or whitespace (token exhaustion)
    if not fast.triggered and not think_unavailable and not reply_text.strip() and not is_fallback:
        is_fallback = True
        consecutive_errors += 1
        reply_text = FALLBACK_REPLY_2 if consecutive_errors >= 2 else FALLBACK_REPLY_1
        if driving_guard:
            reply_text = enforce_driving_alternative(reply_text, caregiver_name)
        _, fallback_paths, fallback_first_time = _speak_turn(iter([reply_text]), audio_out_dir, on_chunk=on_chunk)
        think_audio_paths.extend(fallback_paths)
        if first_audio_time is None:
            first_audio_time = fallback_first_time
    elif not is_fallback:
        consecutive_errors = 0

    # The carried crisis marker is spent only by a turn that actually spoke:
    # a fallback or THINK failure leaves it for the next turn.
    if carried_given is not None and not is_fallback and (reply_text.strip() or immediate_audio_paths):
        with _CRISIS_CARRY_LOCK:
            if _CRISIS_CARRY.get(carry_key) == carried_given:
                _CRISIS_CARRY.pop(carry_key, None)

    result = TurnResult(
        transcript=transcript,
        reply_text=(immediate_reply_text + " " + reply_text).strip() if immediate_reply_text else reply_text,
        audio_paths=immediate_audio_paths + think_audio_paths,
        memories_used=filtered_profile + filtered_schedule,
        caregiver_flag=fast.caregiver_flag if fast.triggered else None,
        time_to_first_audio_s=first_audio_time,
        audit_verdict=(
            "skipped (fast-path disclosed directly; daily request cap reached)"
            if hosted_call_capped
            else "skipped (fast-path disclosed directly; continuation needs NEBIUS_API_KEY)"
            if think_unavailable
            else "skipped (fast-path disclosed directly)" if fast.triggered
            else "skipped (fallback turn)" if is_fallback
            else None
        ),
        is_fallback=is_fallback,
        consecutive_errors=consecutive_errors,
    )

    if not fast.triggered and not is_fallback:
        def background() -> None:
            try:
                status, verdict = audit.audit_reply(transcript, reply_text)
                result.audit_verdict = verdict
                if status in {"CRISIS", "DISTRESS", "UNSAFE"}:
                    disclosed = False
                    hotline_already_heard = False
                    caregiver_template = None
                    try:
                        reply_gave_988 = any(_hotline_match(x) for x in re.split(r'(?<=[.!?])\s+', reply_text))
                        # Heard, not merely generated: the reply's 988 counts only
                        # when its chunks were accepted, and a 988 already given
                        # this episode (the carried marker) counts too.
                        reply_988_heard = bool(
                            reply_gave_988 and think_tracker is not None
                            and bool(think_audio_paths)
                            and think_tracker.accepted_any(_hotline_match)
                        )
                        hotline_already_heard = reply_988_heard or bool(carried_given)
                        caregiver_template = (
                            (CRISIS_DISCLOSURE_LINE_NO_988 if hotline_already_heard else CRISIS_DISCLOSURE_LINE)
                            if status == "CRISIS" else DISCLOSURE_LINE
                        )
                        caregiver_text = caregiver_template.format(caregiver=caregiver_name)
                        extra_paths, disclosed = _speak_disclosure(
                            caregiver_text, audio_out_dir, on_chunk=on_chunk
                        )
                        result.audio_paths.extend(extra_paths)
                    except Exception:  # pragma: no cover - best-effort disclosure
                        disclosed = False
                    
                    # The flag text is a FIXED description of the
                    # trigger category -- never the auditor's one-sentence
                    # reason, which can carry health details, names or a bank
                    # PIN the senior said. The raw verdict still rides on
                    # result.audit_verdict (the dev/biomarker surface).
                    audit_flag = None
                    if status == "CRISIS":
                        audit_flag = flags.add(fastpath.CAREGIVER_FLAG_TEXT["audit_crisis"], severity="crisis", disclosed_to_senior=disclosed, source="audit")
                        # Carry into the next turn: was the 988 line actually given?
                        with _CRISIS_CARRY_LOCK:
                            # Only an attested disclosure counts as heard; a reply
                            # the consumer may have refused is not evidence.
                            _CRISIS_CARRY[carry_key] = hotline_already_heard or (
                                disclosed and caregiver_template is CRISIS_DISCLOSURE_LINE
                            )
                    elif status == "DISTRESS":
                        audit_flag = flags.add(fastpath.CAREGIVER_FLAG_TEXT["audit_distress"], severity="distress", disclosed_to_senior=disclosed, source="audit")
                    elif status == "UNSAFE":
                        audit_flag = flags.add(fastpath.CAREGIVER_FLAG_TEXT["audit_unsafe"], severity="audit", disclosed_to_senior=disclosed, source="audit")
                    if audit_flag is not None:
                        # Own daemon thread: a slow send must not delay memory
                        # extraction or the next turn's join. `disclosed` was
                        # attested by _speak_disclosure above.
                        _notify_in_background(flags, audit_flag, result.notify_threads)
            except Exception as exc:  # pragma: no cover - best-effort background task
                print(
                    f"[orchestrator] audit failed: {type(exc).__name__}",
                    file=sys.stderr,
                )
                result.audit_verdict = "unknown"

            try:
                active_facts = memory_store.senior_profile_facts()
                # Pass filtered_schedule to allow extraction of Caregiver vs Senior conflicts
                saved_cmd = think.extract_new_memory(transcript, reply_text, active_facts, caregiver_updates=filtered_schedule)
                if saved_cmd:
                    if saved_cmd.startswith("ADD:"):
                        fact = saved_cmd[4:].strip()
                        memory_store.add(fact, source="conversation_extract")
                        result.memory_saved = fact
                    elif saved_cmd.startswith("SUPERSEDE:") or saved_cmd.startswith("SUPERSESE:"):
                        parts = saved_cmd.split(":", 1)[-1].split("|")
                        if len(parts) == 2:
                            old_fact, new_fact = parts[0].strip(), parts[1].strip()
                            memory_store.supersede(old_fact, new_fact, source="conversation_extract")
                            result.memory_saved = f"Corrected: {new_fact}"
                    elif saved_cmd.startswith("DELETE:"):
                        old_fact = saved_cmd[7:].strip()
                        memory_store.delete(old_fact)
                        result.memory_saved = f"Forgot: {old_fact}"
                    elif saved_cmd.startswith("CONFLICT:"):
                        parts = saved_cmd.split(":", 1)[-1].split("|")
                        if len(parts) >= 2:
                            old_fact, new_fact = parts[0].strip(), parts[1].strip()
                            reason = parts[2].strip() if len(parts) >= 3 else "Potential contradiction or multiple entities."
                            memory_store.add_conflict(old_fact, new_fact, reason)
                            result.memory_saved = f"Pending Conflict: {old_fact} vs {new_fact}"
                    elif saved_cmd.startswith("QUIET_MODE"):
                        parts = saved_cmd.split(":")
                        hours = 4.0
                        if len(parts) > 1:
                            nums = re.findall(r"\d+(?:\.\d+)?", parts[1])
                            if nums:
                                try:
                                    hours = max(float(n) for n in nums)
                                    hours = max(1.0, min(hours, 24.0)) # clamp between 1 and 24 hours
                                except ValueError:
                                    hours = 4.0
                        memory_store.set_quiet_mode(hours=hours)
                        result.memory_saved = f"Activated Quiet Mode ({hours} hours)"
                    elif saved_cmd.startswith("EMOTION:"):
                        fact = saved_cmd.split(":", 1)[1].strip()
                        import time
                        memory_store.add(fact, source="conversation_extract", scope="emotional", expires_at=time.time() + 24 * 3600)
                        result.memory_saved = f"Emotion: {fact}"
                    elif saved_cmd.startswith("UNCERTAIN:"):
                        fact = saved_cmd.split(":", 1)[1].strip()
                        memory_store.add(fact, source="conversation_extract", scope="uncertain")
                        result.memory_saved = f"Uncertain: {fact}"
                    elif saved_cmd.startswith("LIFESTYLE:"):
                        parts = saved_cmd.split(":", 1)[1].split("|", 1)
                        if len(parts) == 2:
                            category = parts[0].strip().lower()
                            fact = parts[1].strip()
                            if category.upper() not in {"SLEEP", "APPETITE", "MOBILITY", "HYGIENE"} or not fact:
                                result.memory_saved = "Suppressed Lifestyle (invalid category or empty note)"
                                return
                            
                            # Synthesize and speak the disclosure
                            disclosed = False
                            try:
                                disclosure_text = f"I'm making a quick note for {caregiver_name} about your {category} so they know how you're feeling lately."
                                extra_paths, disclosed = _speak_disclosure(
                                    disclosure_text, audio_out_dir, on_chunk=on_chunk
                                )
                                result.audio_paths.extend(extra_paths)
                            except Exception:
                                disclosed = False
                                
                            if disclosed:
                                import time
                                # TTL of 7 days (604800 seconds)
                                expires_at = time.time() + (7 * 24 * 3600)
                                memory_store.add(
                                    fact,
                                    source="conversation_extract",
                                    scope="lifestyle",
                                    expires_at=expires_at,
                                    disclosure_attested=True,
                                )
                                result.memory_saved = f"Lifestyle ({category}): {fact}"
                            else:
                                result.memory_saved = f"Suppressed Lifestyle ({category}) due to disclosure failure"
                    else:
                        memory_store.add(saved_cmd, source="conversation_extract")
                        result.memory_saved = saved_cmd
                    
                    # If we got ANY command other than None or NONE, the senior engaged with the prompt.
                    memory_store.resolve_asked_conflicts()
                else:
                    # If saved_cmd is None, the senior likely ignored the clarification question.
                    memory_store.escalate_asked_conflicts(flags)
            except Exception:  # pragma: no cover - best-effort background extraction
                pass

        thread = threading.Thread(target=background, daemon=True)
        thread.start()
        result.background_thread = thread

    result.notify_threads.extend(notify_threads)

    return result
