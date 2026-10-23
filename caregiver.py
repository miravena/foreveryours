"""Caregiver-side state: the onboarding memo, daily notes, and safety flags.

Thin-slice version: one hardcoded senior profile ("dad"), caregiver = "Sarah".
Multi-profile support is a later concern -- the demo only needs one.
"""
from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
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
_SAMPLE_PROFILE_PROHIBITED = {
    "dosing": re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|units?|milligrams?|millilitres?|milliliters?)\b"
        r"|\bdos(?:e|es|age|ages|ing)\b"
        r"|\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|half)\s+(?:tablets?|pills?|capsules?|drops?|puffs?)\b",
        re.IGNORECASE,
    ),
    "diagnosis": re.compile(
        r"\bdiagnos\w*"
        r"|\b(?:hypertension|hypotension|diabet\w*|dementia|alzheimer\w*|parkinson\w*|arthritis|"
        r"copd|asthma|cancer|stroke|depression|anxiety|insomnia|osteoporosis|angina|arrhythmia|"
        r"glaucoma|cholesterol)\b"
        r"|\b\w+(?:itis|osis|emia|aemia|pathy|algia)\b"
        r"|\bfor\s+(?:your|his|her|dad's|the)\s+(?:high\s+|low\s+)?(?:blood\s+pressure|heart|sugar|thyroid|kidneys?|liver|lungs?|memory|nerves|pain)\b",
        re.IGNORECASE,
    ),
    "clinical claim": re.compile(
        r"\b(?:treat\w*|symptom\w*|cure\w*|prescri\w*|therap\w*|clinical\w*|heals?|healing|prevents?|relieves?)\b",
        re.IGNORECASE,
    ),
}


def sample_family_texts() -> list[str]:
    """The seed's item texts in order (what the loader writes)."""
    return [text for _group, text, _privacy in SAMPLE_FAMILY["items"]]


def validate_sample_profile(text_or_items) -> None:
    """Refuse a sample profile that carries dosing (units, "dose", N tablets),
    diagnosis (diagnos*, a condition name, "for your <condition>") or
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
        for category, pattern in _SAMPLE_PROFILE_PROHIBITED.items():
            hit = pattern.search(text)
            if hit:
                raise ValueError(
                    f"sample profile refused: {category} language ({hit.group(0)!r}) in {text!r}; "
                    "reminders only -- no doses, diagnoses or clinical claims"
                )


# One sentence boundary for every memo path. Each caller used to
# split on its own rule ("." + space here, [.!?\n]+ there), so the same memo
# dictated once and typed once produced different texts -- MemoryStore.add's
# exact (text, source) dedupe cannot see those as the same fact, and a
# transcript with "!"/"?"/no space after "." was stored as one whole-memo
# item beside its own fragments. A "." followed by a digit is a decimal
# point ("Give 1.5 mg"), never a boundary (openai_review).
_MEMO_FACT_BOUNDARY_RE = re.compile(r"(?:[!?\n]|\.(?!\d))+")


def split_memo_facts(memo: str | None) -> list[str]:
    """Split a caregiver memo (typed, dictated or canned) into one stripped
    fact per sentence, dropping empties. The ONLY splitter any memo path may
    use, so a memo saved by any route yields identical items."""
    return [part.strip() for part in _MEMO_FACT_BOUNDARY_RE.split(memo or "") if part.strip()]


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
        return [CaregiverFlag(**item) for item in raw]

    def _flush(self) -> None:
        from memory.profile_io import atomic_write_json

        atomic_write_json(self.path, [f.__dict__ for f in self._flags])

    def add(self, text: str, severity: str, disclosed_to_senior: bool) -> CaregiverFlag:
        """`disclosed_to_senior` must reflect reality, not a default: only
        True when the senior was actually told, in the conversation, that
        this flag was raised. See safety/fastpath.py (always discloses, part
        of the immediate reply) and pipeline/orchestrator.py's AUDIT path
        (discloses via a follow-up spoken line; False only if that fails)."""
        with self._transaction():
            flag = CaregiverFlag(text=text, severity=severity, disclosed_to_senior=disclosed_to_senior)
            self._flags.append(flag)
            self._flush()
            return flag

    def all(self) -> list[CaregiverFlag]:
        return list(self._flags)
