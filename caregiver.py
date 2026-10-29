"""Caregiver-side state: the onboarding memo, daily notes, and safety flags.

Thin-slice version: one hardcoded senior profile ("dad"), caregiver = "Sarah".
Multi-profile support is a later concern -- the demo only needs one.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path

DEFAULT_PROFILE_ID = "dad"
DEFAULT_CAREGIVER_NAME = "Sarah"
# The canned onboarding memo: `main.py beat1`'s text fallback and the
# pre-brief every webapp session starts with.
DEMO_MEMO = (
    "Dad loves jazz. His grandson is named Leo. Avoid talking about driving. "
    "I'm dropping off groceries at 4 PM today."
)

# One-click "Load sample family" seed. Outside reviewers of
# the live Space said the demo "feels like just talking to a bot"; a visible,
# caregiver-configured household shows what the product is. Every entry is a
# STRUCTURED item written straight into the session MemoryStore with an
# explicit scope and privacy (never through split_memo_facts, so "8 AM" or
# "Dr." can never be split wrong), all fictional, and all reminders-only:
# a medication line is a caregiver-entered time-of-day schedule item such
# as "Blood pressure pill, 8 AM" -- no dose, no diagnosis, no clinical claim
# (docs/PRD.md non-goal). validate_sample_profile() below is the guard, and
# the webapp loader runs it before writing a single item. Items whose text
# carries a clock time are auto-scoped TEMPORARY (24 h) by MemoryStore.add,
# which is right for "today's reminders"; the rest stay PERMANENT.
SAMPLE_FAMILY_LABEL = "Fictional sample household"
SAMPLE_FAMILY = {
    "label": SAMPLE_FAMILY_LABEL,
    "senior_name": "Walter",
    "caregiver_name": DEFAULT_CAREGIVER_NAME,
    # (group, text, privacy) -- group drives the caregiver-side profile card.
    "items": (
        ("persona", "Dad is Walter, 82, a retired trumpet teacher who lives on his own in Maple Street.", "public"),
        # Identity facts carry NO schedule words (am/pm, morning/evening,
        # visit...): MemoryStore.caregiver_schedule_updates() claims any
        # caregiver line with one, and senior_profile_facts() then drops it,
        # so "Who is my daughter?" would reach the model with no answer
        # (openai_review). The visits and calls are routine items.
        ("family", "Sarah is his daughter and primary caregiver.", "public"),
        ("family", "His grandson Leo is nine and loves hearing his trumpet stories.", "public"),
        ("family", "Rosa next door is his neighbour and oldest friend.", "public"),
        ("likes", "Dad loves jazz, especially Ella Fitzgerald, and crossword puzzles.", "public"),
        ("likes", "He enjoys chicken soup and a slice of apple pie after dinner.", "public"),
        ("routine", "Breakfast, 7:30 AM", "public"),
        ("routine", "Morning walk round the park, 9 AM", "public"),
        ("routine", "Coffee with Rosa, 10 AM", "public"),
        ("routine", "Lunch, 12:30 PM", "public"),
        ("routine", "Evening walk, 6 PM", "public"),
        ("routine", "Dinner, 6:30 PM", "public"),
        ("routine", "Sarah's evening phone call, 8 PM", "public"),
        ("routine", "Leo visits, Saturday 3 PM", "public"),
        ("reminder", "Blood pressure pill, 8 AM", "public"),
        ("reminder", "Evening pill with dinner, 6:30 PM", "public"),
        ("avoid", "Avoid talking about driving: he gave up his licence in March and it is a sore subject.", "public"),
        ("health", "Uses a cane since a fall in March; mild hearing loss, so keep sentences short.", "caregiver_only"),
    ),
}

# Prohibited language in a sample profile, one pattern set per category so
# each is refused -- and tested -- separately. Biased to refusing (like
# safety/fastpath.py): a false refusal costs a reworded seed, a miss ships
# dosing advice into a public demo.
# Medication words: a medicine named next to "for <something>" states what it
# is for, which is a diagnosis however the condition is spelled.
_MED_WORDS = r"(?:pills?|tablets?|capsules?|medicines?|medications?|meds|drops?|inhalers?|injections?|shots?|patch(?:es)?|creams?|syrups?)"
_SAMPLE_PROFILE_PROHIBITED = {
    "dosing": re.compile(
        # A unit token anywhere, however it is joined to the number:
        # "20 mg", "20mg", "20-mg", "mg" alone.
        r"(?:\b|(?<=\d))(?:mg|mcg|ug|\u03bcg|ml|cc|iu|milligrams?|micrograms?|millilitres?|milliliters?|grams?)\b"
        r"|\b\d+(?:[.,/]\d+)?\s*[-\u2010-\u2015]?\s*(?:units?|g)\b"
        r"|\bdos(?:e|es|ed|age|ages|ing)\b"
        r"|(?:\b\d+(?:[./]\d+)?|[\u00bc-\u00be\u2150-\u215e]|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|half|a\s+half|quarter))"
        r"\s*[-\u2010-\u2015]?\s*(?:tablets?|pills?|capsules?|drops?|puffs?|sprays?|spoons?|teaspoons?|tablespoons?|tsp|tbsp)\b"
        r"|\b\d+\s*x\b|\b(?:once|twice|thrice|\d+|one|two|three|four)\s*(?:times?\s+)?(?:a|per)\s+day\b"
        r"|\bevery\s+\d+\s*(?:hours?|hrs?|h)\b",
        re.IGNORECASE,
    ),
    "diagnosis": re.compile(
        r"\bdiagnos\w*"
        r"|\b(?:hypertension|hypotension|diabet\w*|dementia|alzheimer\w*|parkinson\w*|arthritis|"
        r"copd|asthma|cancer|stroke|depression|anxiety|insomnia|osteoporosis|angina|arrhythmia|"
        r"glaucoma|cholesterol|epilep\w*|seizures?|migraines?|heart\s+(?:failure|disease|attack)|"
        r"afib|atrial|fibrillation|gout|lupus|tumou?rs?|leukaemia|leukemia|lymphoma|carcinoma|"
        r"melanoma|pneumonia|bronchitis|emphysema|anaemia|anemia|thyroid\w*|hypothyroid\w*|"
        r"schizophreni\w*|bipolar|psychosis|ocd|adhd|autism|hiv|hepatitis|cirrhosis|"
        r"incontinence|infections?|disorders?|diseases?|syndromes?|conditions?|illness(?:es)?|"
        r"cataracts?|macular|neuropathy|sciatica|vertigo|tinnitus|dysphagia|aphasia|"
        r"multiple\s+sclerosis|myeloma|sarcoma|uti|ckd|chf)\b"
        r"|\b\w+(?:itis|osis|emia|aemia|pathy|algia)\b"
        # "for your/his/her <anything>" -- the condition after it may be any word.
        r"|\bfor\s+(?:your|his|her|my|their|dad'?s|mum'?s|mom'?s)\s+\w+"
        r"|\b" + _MED_WORDS + r"\b[^,.;]*?\bfor\s+\w+",
        re.IGNORECASE,
    ),
    "clinical claim": re.compile(
        r"\b(?:treat\w*|symptom\w*|cure\w*|prescri\w*|therap\w*|clinical\w*|heals?|healing|prevents?|"
        r"relieves?|reliefs?|remed\w*|manages?\s+(?:his|her|your|the)\s+\w+|lowers?|reduces?|controls?\s+(?:his|her|your|the)\s+\w+)\b",
        re.IGNORECASE,
    ),
}


def sample_family_texts() -> list[str]:
    """The seed's item texts in order (what the loader writes)."""
    return [text for _group, text, _privacy in SAMPLE_FAMILY["items"]]


# Guided interview (#206): the SAMPLE_FAMILY groups a good first briefing
# needs, asked one at a time. `key` is a SAMPLE_FAMILY item group; `scope` is
# the scope the saved facts get from the ordinary memo path (MemoryStore.add
# makes a fact with a clock time or "today" TEMPORARY, everything else
# PERMANENT), so a question's `example` is written to land in that scope. The
# wording asks for people, routine and preferences, never conditions or
# medicines; validate_sample_profile still refuses any answer that slips them in.
INTERVIEW_QUESTIONS = (
    {
        "key": "family",
        "prompt": "Who are the important people in Dad's life, and how are they related to him?",
        "scope": "permanent",
        "skippable": False,
        "example": "Sarah is his daughter. His grandson Leo is nine. Rosa next door is his oldest friend.",
    },
    {
        "key": "likes",
        "prompt": "What does Dad love: music, food, hobbies, things he likes to talk about?",
        "scope": "permanent",
        "skippable": True,
        "example": "Dad loves jazz and crossword puzzles. He enjoys chicken soup.",
    },
    {
        "key": "routine",
        "prompt": "What does a usual day look like for Dad, in your own words?",
        "scope": "permanent",
        "skippable": True,
        "example": "He has breakfast early, walks round the park after it, and has coffee with Rosa.",
    },
    {
        "key": "avoid",
        "prompt": "Is there anything the companion should steer away from talking about?",
        "scope": "permanent",
        "skippable": True,
        "example": "Avoid talking about driving; it is a sore subject.",
    },
    {
        "key": "reminder",
        "prompt": "Which times today should the companion remember, such as visits, calls or a pill time? Just the times.",
        "scope": "temporary",
        "skippable": True,
        "example": "Blood pressure pill, 8 AM. Sarah's phone call, 8 PM.",
    },
)


def validate_sample_profile(text_or_items) -> None:
    """Refuse a sample profile that carries dosing (units, "dose", N tablets),
    diagnosis (diagnos*, a condition name, "for your <anything>", a
    medicine "for <anything>") or
    clinical-claim (treat*, symptom*, cure*, ...) language. Accepts one
    string, an iterable of strings, or an iterable of (group, text, privacy)
    tuples / {"text": ...} dicts; raises ValueError naming the category and
    the offending item. "Blood pressure pill, 8 AM" and "Evening walk, 6 PM"
    pass: reminders are schedule items, not medical advice."""
    if isinstance(text_or_items, str):
        texts = [text_or_items]
    else:
        texts = []
        for entry in text_or_items:
            if isinstance(entry, str):
                texts.append(entry)
            elif isinstance(entry, dict):
                texts.append(str(entry.get("text", "")))
            elif isinstance(entry, (tuple, list)) and len(entry) >= 2:
                texts.append(str(entry[1]))
            else:
                raise ValueError(f"sample profile item has no text: {entry!r}")
    for text in texts:
        # NFKC folds look-alikes a typed or pasted line can carry: the micro
        # sign to mu, full-width digits and letters to ASCII.
        folded = unicodedata.normalize("NFKC", text)
        for category, pattern in _SAMPLE_PROFILE_PROHIBITED.items():
            hit = pattern.search(folded)
            if hit:
                raise ValueError(
                    f"sample profile refused: {category} language ({hit.group(0)!r}) in {text!r}; "
                    "reminders only -- no doses, diagnoses or clinical claims"
                )


# A memo is briefing data, but its text reaches THINK's prompt (#280). A dose
# instruction in it ("take three extra aspirin", "double his insulin") is
# exactly what rule 7 forbids the companion to say, so the memo box refuses it
# instead of storing it. Narrow on purpose: only a change to a dose (extra,
# more, double, skip, stop) is refused. A reminder or a plain medication fact
# ("Blood pressure pill at 8 AM", "Dad takes 5 mg daily") is kept, as before.
_DOSE_TARGET = r"(?:dose|dosage|insulin|aspirins?|" + _MED_WORDS + r")"
_DOSING_INSTRUCTION_RE = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|a\s+few|some)\s+(?:extra|more|additional)\s+" + _DOSE_TARGET
    + r"|\b(?:extra|additional|another|double)\s+" + _DOSE_TARGET
    + r"|\b(?:double|skip|stop|increase|halve)\s+(?:(?:his|her|their|your|dad'?s|the|all|any)\s+)?"
    r"(?:(?:\w+\s+){0,2}" + _DOSE_TARGET + r")\b",
    re.IGNORECASE,
)
# "Do not double his insulin" is a precaution, not an instruction.
_DOSING_NEGATED_RE = re.compile(r"\b(?:do\s+not|don'?t|never|no|must\s+not|mustn'?t|shouldn'?t|should\s+not)"
                                r"\s+(?:\w+\s+){0,2}$", re.IGNORECASE)


def dosing_instruction(text: str) -> str | None:
    """The dose instruction in a caregiver memo, or None (#280)."""
    folded = unicodedata.normalize("NFKC", text or "").replace("\u2019", "'")
    for hit in _DOSING_INSTRUCTION_RE.finditer(folded):
        if not _DOSING_NEGATED_RE.search(folded[:hit.start()]):
            return hit.group(0)
    return None


MEMO_DOSING_REFUSAL = (
    "Memo not saved: it gives a medication dose ({hit!r}). The companion never gives dosing "
    "advice, so dose instructions are not stored. A reminder such as \"Blood pressure pill at 8 AM\" is fine."
)


# One sentence boundary for every memo path. Each caller used to
# split on its own rule ("." + space here, [.!?\n]+ there), so the same memo
# dictated once and typed once produced different texts -- MemoryStore.add's
# exact (text, source) dedupe cannot see those as the same fact, and a
# transcript with "!"/"?"/no space after "." was stored as one whole-memo
# item beside its own fragments. A "." followed by a digit is a decimal
# point ("Give 1.5 mg"), never a boundary (openai_review).
#
# The "." is also abbreviation-aware: "Dad has a check-up with Dr. Tan on
# Thursday at 10 AM." used to be stored as "Dad has a check-up with Dr" and
# "Tan on Thursday at 10 AM", so the companion could not recall the
# appointment. NLTK's Punkt learns abbreviations from a corpus; this memo
# domain needs a handful, so a fixed list and a plain loop (no regex with
# lookarounds on user text -- CodeQL py/polynomial-redos) instead of a new
# dependency:
#   - after a title (Dr., Mr., Mrs., Ms., St., Prof.) the "." never ends a
#     fact -- a name follows;
#   - inside "a.m."/"p.m." never; after them, and after a unit that follows a
#     number ("5 mg."), only when the next word starts with a capital letter
#     ("Dad takes 5 mg. Mom visits." is two facts, "5 mg. of aspirin" one).
_MEMO_TITLE_ABBREVIATIONS = frozenset({"dr", "mr", "mrs", "ms", "st", "prof"})
_MEMO_UNIT_ABBREVIATIONS = frozenset({"mg", "mcg", "g", "kg", "ml", "oz", "lb", "lbs", "cm", "mm", "km"})
_MEMO_HARD_BOUNDARIES = "!?\n"


def _letters_before(text: str, end: int) -> int:
    """Index where the run of letters ending just before `end` starts."""
    start = end
    while start > 0 and text[start - 1].isalpha():
        start -= 1
    return start


def _is_meridiem_at(text: str, start: int) -> bool:
    """True when "a.m"/"p.m" (any case) is a whole word starting at `start`;
    a clock digit may touch it ("9a.m.")."""
    if text[start:start + 3].lower() not in ("a.m", "p.m"):
        return False
    before_ok = start == 0 or not text[start - 1].isalpha()
    after = start + 3
    after_ok = after == len(text) or not text[after].isalnum()
    return before_ok and after_ok


def _next_word_is_capitalised(text: str, i: int) -> bool:
    """True when the first non-space, non-"." character after `i` is an
    upper-case letter. End of text counts as a boundary too."""
    n = len(text)
    while i < n and (text[i] == "." or text[i] in " \t"):
        i += 1
    return i == n or text[i].isupper()


# What the "." at text[i] does: stays inside the fact, ends it (the "." is
# dropped like any sentence end), or ends it but stays ("at 9 a.m.").
_PERIOD_INSIDE, _PERIOD_ENDS, _PERIOD_ENDS_KEPT = 0, 1, 2


def _period_role(text: str, i: int) -> int:
    """What the "." at text[i] does in a memo; see the constants above."""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if nxt.isdigit():  # decimal point
        return _PERIOD_INSIDE
    word_start = _letters_before(text, i)
    word = text[word_start:i].lower()
    word_is_whole = word_start == 0 or not text[word_start - 1].isalnum()
    # Inner "." of a.m./p.m., then the "." that closes it.
    if len(word) == 1 and _is_meridiem_at(text, i - 1):
        return _PERIOD_INSIDE
    if word == "m" and word_start >= 2 and _is_meridiem_at(text, word_start - 2):
        return _PERIOD_ENDS_KEPT if _next_word_is_capitalised(text, i + 1) else _PERIOD_INSIDE
    if not word or not (word_is_whole or word in _MEMO_UNIT_ABBREVIATIONS):
        return _PERIOD_ENDS
    if word in _MEMO_TITLE_ABBREVIATIONS and word_is_whole:
        return _PERIOD_INSIDE
    if word in _MEMO_UNIT_ABBREVIATIONS:
        j = word_start
        while j > 0 and text[j - 1] == " ":
            j -= 1
        if j > 0 and text[j - 1].isdigit():  # "5 mg." / "5mg."
            return _PERIOD_ENDS if _next_word_is_capitalised(text, i + 1) else _PERIOD_INSIDE
    return _PERIOD_ENDS


# Words MemoryStore.caregiver_guardrails() reads as "the companion must avoid this".
_GUARDRAIL_MARKERS = ("avoid", "don't", "do not", "never")


def interview_answer_memo(key: str, answer: str) -> str:
    """The memo text an interview answer is saved as. Every answer is saved as
    typed, except the "topics to avoid" answer: a bare topic ("Politics") would
    otherwise be stored as an ordinary profile fact the companion may bring up,
    so each fact without a guardrail word becomes "Avoid talking about <topic>."."""
    if key != "avoid":
        return answer
    parts = []
    for fact in split_memo_facts(answer):
        if any(marker in fact.lower() for marker in _GUARDRAIL_MARKERS):
            parts.append(fact.rstrip(".") + ".")
        else:
            topic = fact.rstrip(".")
            parts.append(f"Avoid talking about {topic[:1].lower() + topic[1:]}.")
    return " ".join(parts) if parts else answer


def split_memo_facts(memo: str | None) -> list[str]:
    """Split a caregiver memo (typed, dictated or canned) into one stripped
    fact per sentence, dropping empties. The ONLY splitter any memo path may
    use, so a memo saved by any route yields identical items. Breaks on "!",
    "?", newlines and sentence-ending "."; abbreviations and decimals stay
    inside their fact (see the rules above)."""
    text = memo or ""
    parts, start = [], 0
    for i, ch in enumerate(text):
        role = _period_role(text, i) if ch == "." else _PERIOD_INSIDE
        if ch in _MEMO_HARD_BOUNDARIES or role == _PERIOD_ENDS:
            parts.append(text[start:i])
            start = i + 1
        elif role == _PERIOD_ENDS_KEPT:
            parts.append(text[start:i + 1])
            start = i + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


# A caregiver update ("groceries at 6 PM today") supersedes
# the earlier caregiver fact about the same subject ("groceries at 4 PM
# today") instead of sitting beside it, so the model never gets both.
# Two facts are "about the same subject" when their keys are EXACTLY equal:
# lower-cased, every clock time ("4 PM", "6:30pm") replaced by one
# placeholder, every other standalone run of digits by another, sentence punctuation
# (.,!?;: before a space or the end) dropped and whitespace collapsed. Exact
# equality is deliberate: "Dad loves jazz" never supersedes "Dad loves jazz,
# especially Ella Fitzgerald". A digit run, not a whole decimal, is one
# placeholder, so a number keeps its shape: "1.5 mg" and "15 mg", "-5 C" and
# "5 C" stay two facts (the panel test keeps both doses listed).
_CLOCK_TIME_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b")
# Standalone digit runs only: a number glued to a letter names the subject
# ("vitamin B12" vs "B6", "room 4b") and stays (Codex P1).
# Both helpers below are plain loops, not regexes: on user text, a regex with
# a lookaround after a repeated class backtracks polynomially (CodeQL
# py/polynomial-redos).
_SENTENCE_PUNCT = ".,!?;:"


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _blank_standalone_digits(text: str) -> str:
    """Every run of digits with no word character on either side becomes
    "<n>"; "B12", "4b" and "12b" stay as written."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isdigit() and (i == 0 or not _is_word_char(text[i - 1])):
            j = i
            while j < n and text[j].isdigit():
                j += 1
            standalone = j == n or not _is_word_char(text[j])
            out.append("<n>" if standalone else text[i:j])
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


_CLOCK_TIME_PARTS_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b")


def _canonical_clock_time(match: re.Match) -> str:
    hour, minutes, meridiem = match.group(1), match.group(2), match.group(3)
    hour = str(int(hour))
    return f"{hour} {meridiem}" if minutes in (None, "00") else f"{hour}:{minutes} {meridiem}"


def normalize_fact_text(text: str) -> str:
    """Lower-cased, clock times written one way ("8:00AM" -> "8 am"),
    sentence punctuation dropped, whitespace collapsed: "Call Sarah." and
    "call  sarah", "pill, 8 AM" and "pill, 8:00 am" normalize the same (a
    restatement, not an update)."""
    lowered = _CLOCK_TIME_PARTS_RE.sub(_canonical_clock_time, (text or "").lower())
    # sentence punctuation is what ends a whitespace-separated word
    words = (w.rstrip(_SENTENCE_PUNCT) for w in lowered.split())
    return " ".join(w for w in words if w)


def fact_subject_key(text: str) -> str:
    """The subject a caregiver fact is about, with its times and numbers
    blanked out (see the comment above). Equal keys + different normalized
    text = the newer fact replaces the older one."""
    key = _CLOCK_TIME_RE.sub(" <time> ", (text or "").lower())
    key = _blank_standalone_digits(key)
    return normalize_fact_text(key)


@dataclass
class CaregiverFlag:
    text: str
    severity: str
    created_at: float = field(default_factory=time.time)
    disclosed_to_senior: bool = False
    # Outbound notification result (#201, ADR-014). None = no notifier was
    # configured (the default), so nothing was attempted; True = the channel
    # accepted the message; False = it failed, and `notify_error` holds the
    # exception TYPE name only. Both stay out of the flag file while None.
    notified: bool | None = None
    notify_error: str | None = None
    # Which layer raised the flag (#214): "fastpath" (safety rules, before the
    # model), "audit" (the AUDIT model, after the reply) or "perseveration"
    # (repeated-question check). None = unknown, e.g. a flag file written
    # before this field existed. Display only; never read by disclosure logic.
    source: str | None = None


class CaregiverFlags:
    """Safety flags for one profile, persisted to `<data_dir>/<profile>.flags.json`.

    Concurrency: `add` runs as a transaction under the
    profile's one lock (`memory.profile_io.profile_lock`) that RELOADS the
    file before appending and flushes through a unique temp file, so two
    instances never overwrite each other's flags. `_flags` is a SNAPSHOT
    taken at construction and refreshed at the start of each of this
    instance's own `add`; `all()` reads it without the lock and can miss
    other writers' commits, so construct a fresh instance for current data.
    """

    def __init__(self, profile_id: str, data_dir: Path):
        from memory.profile_io import profile_lock

        self.path = data_dir / f"{profile_id}.flags.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = profile_lock(self.path)
        self._txn_depth = 0
        self._flags: list[CaregiverFlag] = self._load()

    @contextmanager
    def _transaction(self):
        """Profile lock for the whole body; the outermost entry reloads from
        disk so the write applies to the latest committed flags."""
        with self._lock:
            if self._txn_depth == 0:
                self._flags = self._load()
            self._txn_depth += 1
            try:
                yield
            finally:
                self._txn_depth -= 1

    def _load(self) -> list[CaregiverFlag]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text())
        # Tolerate keys this version does not know (a file written by a newer
        # build), so adding a field never makes an older build crash on load.
        known = {f.name for f in fields(CaregiverFlag)}
        return [CaregiverFlag(**{k: v for k, v in item.items() if k in known}) for item in raw]

    def _flush(self) -> None:
        from memory.profile_io import atomic_write_json

        atomic_write_json(self.path, [self._record(f) for f in self._flags])

    @staticmethod
    def _record(flag: CaregiverFlag) -> dict:
        record = dict(flag.__dict__)
        # Unset notification fields are not written, so with no channel
        # configured the flag file is byte-for-byte what it always was.
        for key in ("notified", "notify_error", "source"):
            if record.get(key) is None:
                record.pop(key, None)
        return record

    def add(
        self, text: str, severity: str, disclosed_to_senior: bool, source: str | None = None
    ) -> CaregiverFlag:
        """`disclosed_to_senior` must reflect reality, not a default: only
        True when the senior was actually told, in the conversation, that
        this flag was raised. See safety/fastpath.py (always discloses, part
        of the immediate reply) and pipeline/orchestrator.py's AUDIT path
        (discloses via a follow-up spoken line; False only if that fails)."""
        with self._transaction():
            flag = CaregiverFlag(
                text=text, severity=severity, disclosed_to_senior=disclosed_to_senior, source=source
            )
            self._flags.append(flag)
            self._flush()
            return flag

    def mark_notified(self, flag: CaregiverFlag, notified: bool, error: str | None = None) -> None:
        """Record the outbound notification result on `flag` (matched by its
        creation time and text) and persist it. `error` is an exception type
        name, never a message."""
        with self._transaction():
            for stored in self._flags:
                if stored.created_at == flag.created_at and stored.text == flag.text:
                    stored.notified, stored.notify_error = notified, error
            flag.notified, flag.notify_error = notified, error
            self._flush()

    def all(self) -> list[CaregiverFlag]:
        return list(self._flags)
