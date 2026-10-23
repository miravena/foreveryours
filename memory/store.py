"""RECALL: minimal persistent memory store, scoped per senior profile.

Thin-slice version: JSON file instead of ChromaDB. Keyword overlap instead of
embeddings for conversation-derived memories. Swappable later behind the same
get/save/search interface once the vector-store step is worth the extra
latency budget.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from enum import Enum
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from caregiver import fact_subject_key, normalize_fact_text
from memory.profile_io import atomic_write_json, profile_lock

CAREGIVER_SOURCES = ("caregiver_memo", "caregiver_note")


class MemoryScope(str, Enum):
    PERMANENT = "permanent"     # Lifelong identity, family relations, enduring passions
    TEMPORARY = "temporary"     # Daily visits, schedule updates, errands
    HISTORICAL = "historical"   # Superseded preferences, past events
    EMOTIONAL = "emotional"
    UNCERTAIN = "uncertain"
    LIFESTYLE = "lifestyle"


class PrivacyLevel(str, Enum):
    PUBLIC_TO_SENIOR = "public"        # Spoken in dialogue
    CAREGIVER_ONLY = "caregiver_only"  # Private caregiver coordination; NEVER spoken to senior
    SAFETY_RELEVANT = "safety"         # Safety fast-path / alerts


@dataclass
class MemoryItem:
    text: str
    source: str  # "caregiver_memo" | "caregiver_note" | "conversation_extract"
    created_at: float = field(default_factory=time.time)
    scope: str = MemoryScope.PERMANENT.value
    privacy: str = PrivacyLevel.PUBLIC_TO_SENIOR.value
    disclosure_attested: bool = False
    expires_at: float | None = None
    status: str = "active"  # "active" | "superseded" | "expired"
    superseded_by: str | None = None

    def is_active(self, now: float | None = None) -> bool:
        if self.status != "active":
            return False
        if self.expires_at is not None:
            t = now if now is not None else time.time()
            if t >= self.expires_at:
                return False
        return True


STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "my", "your", "i", "you",
    "he", "she", "it", "we", "they", "in", "on", "at", "to", "for", "with",
    "of", "and", "or", "what", "where", "who", "when", "why", "how", "tell",
    "about", "me", "do", "did", "does", "have", "had", "has", "s", "t", "d",
}

DOMAIN_SYNONYMS: dict[str, set[str]] = {
    "grandson": {"grandson", "grandchild", "grandkid", "granddaughter"},
    "granddaughter": {"granddaughter", "grandchild", "grandkid", "grandson"},
    "grandchild": {"grandchild", "grandkid", "grandson", "granddaughter"},
    "grandkid": {"grandkid", "grandchild", "grandson", "granddaughter"},
    "son": {"son", "child", "boy"},
    "daughter": {"daughter", "child", "girl"},
    "wife": {"wife", "spouse", "married", "partner"},
    "husband": {"husband", "spouse", "married", "partner"},
    "driving": {"driving", "drive", "car", "vehicle", "automobile"},
    "drive": {"driving", "drive", "car", "vehicle", "automobile"},
    "car": {"car", "driving", "drive", "vehicle", "automobile"},
    "vehicle": {"car", "driving", "drive", "vehicle", "automobile"},
    "doctor": {"doctor", "physician", "appointment", "clinic", "hospital"},
    "physician": {"doctor", "physician", "appointment", "clinic", "hospital"},
    "medicine": {"medicine", "medication", "pills", "prescription"},
    "medication": {"medicine", "medication", "pills", "prescription"},
    "pills": {"medicine", "medication", "pills", "prescription"},
    "music": {"music", "jazz", "song", "tunes"},
    "jazz": {"jazz", "music", "song", "tunes"},
    "groceries": {"groceries", "food", "shopping", "market"},
    "food": {"groceries", "food", "dinner", "lunch", "breakfast"},
}

# Matches a day/time-of-day word that should auto-infer TEMPORARY scope:
# whole words ("today", "tomorrow", "tonight") or "am"/"pm" as a clock marker
# -- standalone ("4 PM") or glued to a digit ("4pm", "10am"). The lookbehind
# blocks "am"/"pm" as a substring of a name or word (e.g. "Liam", "name"):
# digits aren't letters, so "4pm" still matches, but "Liam" and "name" don't
# because a letter precedes the "am".
_TEMPORAL_MARKER_RE = re.compile(r"\b(?:today|tomorrow|tonight)\b|(?<![a-z])(?:am|pm)\b")


class MemoryStore:
    """One senior profile's memories, persisted to `<data_dir>/<profile>.json`.

    Concurrency: every write runs as a transaction under the
    profile's one lock (`memory.profile_io.profile_lock`) that RELOADS the
    file from disk before mutating and flushes through a unique temp file,
    so two instances on the same profile never overwrite each other's items.

    `_items` is a SNAPSHOT: taken at construction and refreshed at the start
    of each of this instance's own write transactions. Read-only methods
    (`all`, `search`, `caregiver_context`, ...) read that snapshot without the
    lock, so an instance that performs no further transaction can miss any
    number of other writers' commits. A caller that needs current data
    constructs a fresh instance (every webapp handler already does, per call).
    """

    def __init__(self, profile_id: str, data_dir: Path, timezone_str: str = "UTC"):
        self.profile_id = profile_id
        self.path = data_dir / f"{profile_id}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = profile_lock(self.path)
        self._txn_depth = 0
        import zoneinfo
        import logging
        try:
            zoneinfo.ZoneInfo(timezone_str)
            self.timezone_str = timezone_str
        except zoneinfo.ZoneInfoNotFoundError:
            logging.warning(f"Invalid timezone_str '{timezone_str}'. Falling back to UTC.")
            self.timezone_str = "UTC"
        self._items: list[MemoryItem] = self._load()
        if self._load_mutated:
            # Persist the load-time lifestyle expiry under the lock, applied to
            # the latest committed state (the transaction reloads).
            with self._transaction():
                if self._load_mutated:
                    self._flush()

    @contextmanager
    def _transaction(self):
        """One read-modify-write on this profile. Holds the
        profile lock for the whole body; the OUTERMOST entry reloads `_items`
        from disk so the mutation applies to the latest committed state, never
        to a stale snapshot. A nested entry (a write method called from inside
        another, e.g. `set_quiet_mode` -> `add`) does NOT reload, or it would
        discard the outer transaction's uncommitted mutation."""
        with self._lock:
            if self._txn_depth == 0:
                self._items = self._adopt(self._load())
            self._txn_depth += 1
            try:
                yield
            finally:
                self._txn_depth -= 1

    def _adopt(self, fresh: list[MemoryItem]) -> list[MemoryItem]:
        """Disk state wins, but an item this instance already handed out
        (`add` and `supersede` return the live MemoryItem, and callers keep
        reading it) keeps its identity: a fresh item whose (created_at, source)
        matches exactly one snapshot item is copied INTO that object. Any
        ambiguous key uses the fresh object; a snapshot item no longer on disk
        is dropped."""
        def key(i: MemoryItem) -> tuple[float, str]:
            return (i.created_at, i.source)

        old_counts = Counter(key(i) for i in self._items)
        fresh_counts = Counter(key(i) for i in fresh)
        by_key = {key(i): i for i in self._items if old_counts[key(i)] == 1}
        adopted = []
        for item in fresh:
            old = by_key.get(key(item)) if fresh_counts[key(item)] == 1 else None
            if old is None:
                adopted.append(item)
            else:
                old.__dict__.update(item.__dict__)
                adopted.append(old)
        return adopted

    def _persist_maintenance(self, pass_fn) -> bool:
        """Lazy upkeep that read paths do (emotion decay, lifestyle/quiet-mode
        expiry). `pass_fn(items) -> bool` mutates a list in place and says
        whether it changed anything; it must be deterministic and idempotent.
        It is applied to this instance's snapshot (so the caller's view
        reflects it, exactly as before) and, only if that changed something,
        persisted under the profile lock by re-applying it to a FRESH load of
        the file -- the same reload-inside-lock rule as `_transaction`, so a
        read never flushes a stale snapshot over another writer's commit.
        The snapshot itself is not replaced, so an instance's in-memory view
        stays stable across a read. Returns whether the snapshot
        changed."""
        if not pass_fn(self._items):
            return False
        with self._lock:
            if self._txn_depth:
                # Inside our own transaction: the snapshot IS the fresh state.
                self._flush()
                return True
            fresh = self._load()
            if pass_fn(fresh) or self._load_mutated:
                atomic_write_json(self.path, [item.__dict__ for item in fresh])
        return True

    def _load(self) -> list[MemoryItem]:
        self._load_mutated = False
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text())
        items = []
        now = time.time()
        for d in raw:
            d.setdefault("scope", MemoryScope.PERMANENT.value)
            d.setdefault("privacy", PrivacyLevel.PUBLIC_TO_SENIOR.value)
            d.setdefault("disclosure_attested", False)
            d.setdefault("expires_at", None)
            d.setdefault("status", "active")
            d.setdefault("superseded_by", None)
            item = MemoryItem(**d)
            if item.scope == MemoryScope.LIFESTYLE.value:
                if item.expires_at is None:
                    item.expires_at = item.created_at + (7 * 24 * 3600)
                    self._load_mutated = True
                if item.status == "active" and now >= item.expires_at:
                    item.status = "expired"
                    item.text = "[EXPIRED]"
                    self._load_mutated = True
            items.append(item)
        return items

    def _flush(self) -> None:
        """Write-then-rename through a unique temp file so a crash/Ctrl-C
        mid-write can't leave invalid JSON that would crash every later load,
        and two flushes never share a temp file. Callers hold the
        profile lock (they run inside `_transaction`)."""
        atomic_write_json(self.path, [item.__dict__ for item in self._items])

    def add(
        self,
        text: str,
        source: str,
        scope: str = MemoryScope.PERMANENT.value,
        privacy: str = PrivacyLevel.PUBLIC_TO_SENIOR.value,
        expires_at: float | None = None,
        disclosure_attested: bool = False,
        keep_texts: tuple[str, ...] | list[str] = (),
        supersede: bool = True,
    ) -> MemoryItem | None:
        """No-op (returns None) if this exact (text, source) is already active.
        Auto-infers TEMPORARY scope for schedule/time notes.

        A caregiver memo/note whose subject key
        (caregiver.fact_subject_key) equals an active item's of the same
        source and privacy, but whose text differs by more than case,
        punctuation or whitespace, is an UPDATE: that item is marked
        superseded (superseded_by = this text) before this one is appended,
        provided the matches are all ONE fact (restatements included; two
        different matching facts = ambiguous, nothing is superseded),
        in the same single _flush(). `keep_texts` are the other facts saved
        in the same memo/seed: an item whose text is one of them is never
        superseded, so "Blood pressure pill, 8 AM" and "..., 8 PM" written
        together are two reminders, not a correction. A seed (the demo
        pre-brief, the sample family) passes supersede=False: canned data
        never replaces what a caregiver wrote."""
        with self._transaction():
            if scope == MemoryScope.LIFESTYLE.value and not disclosure_attested:
                raise ValueError("Lifestyle memory requires delivered disclosure attestation")
            if scope == MemoryScope.LIFESTYLE.value:
                expires_at = expires_at or (time.time() + 7 * 24 * 3600)
                privacy = PrivacyLevel.CAREGIVER_ONLY.value
            if any(i.text == text and i.source == source and i.status == "active" for i in self._items):
                return None
            replaced: list[MemoryItem] = []
            if supersede and source in CAREGIVER_SOURCES:
                key = fact_subject_key(text)
                norm = normalize_fact_text(text)
                kept = {normalize_fact_text(t) for t in keep_texts}
                matches = [
                    (normalize_fact_text(i.text), i) for i in self._items
                    if i.source == source
                    and i.is_active()  # an expired fact is not live: never counted, never touched
                    and i.privacy == privacy
                    and fact_subject_key(i.text) == key
                ]
                replaced = [i for n, i in matches if n != norm and n not in kept]
                if any(n == norm for n, _ in matches):
                    # A restatement of a live fact ("pill, 8:00 am" beside "pill,
                    # 8 AM") changes nothing: it must not supersede a DIFFERENT
                    # same-subject fact ("pill, 8 PM") either (Codex P1).
                    replaced = []
                elif len({normalize_fact_text(i.text) for i in replaced}) > 1:
                    # Ambiguous: two different live facts share this subject
                    # ("pill, 8 AM" and "pill, 8 PM"). Which one the caregiver meant
                    # to change is unknowable, and silently dropping a reminder is
                    # worse than listing one extra, so supersede none. Restatements
                    # of ONE fact ("4 PM" / "4 pm.") are one fact and go together
                    # (Codex review).
                    replaced = []
            if scope == MemoryScope.PERMANENT.value and _TEMPORAL_MARKER_RE.search(text.lower()):
                scope = MemoryScope.TEMPORARY.value
            
            if scope == MemoryScope.TEMPORARY.value and expires_at is None:
                expires_at = time.time() + 86400
            
            item = MemoryItem(
                text=text,
                source=source,
                scope=scope,
                privacy=privacy,
                disclosure_attested=disclosure_attested,
                expires_at=expires_at,
            )
            for old in replaced:
                old.status = "superseded"
                old.superseded_by = text
            self._items.append(item)
            self._flush()
            return item

    def add_conflict(self, old_fact: str, new_fact: str, reason: str) -> None:
        """Stores a pending memory conflict to be resolved on the next turn."""
        with self._transaction():
            item = MemoryItem(
                text=f"{old_fact}|{new_fact}|{reason}",
                source="conversation_extract",
                status="conflict"
            )
            self._items.append(item)
            self._flush()

    def set_quiet_mode(self, hours: float = 4.0) -> None:
        # The OUTER transaction: it drops the old [QUIET_MODE] item before
        # `add` runs nested (no reload) -- if only `add` were transactional,
        # its reload would bring the old item back and refuse the renewal as a
        # duplicate.
        with self._transaction():
            expires_at = time.time() + (hours * 3600)
            self._items = [i for i in self._items if i.text != "[QUIET_MODE]"]
            self.add("[QUIET_MODE]", source="system", scope=MemoryScope.TEMPORARY.value, expires_at=expires_at)

    @staticmethod
    def _expire_quiet_mode_pass(items: list[MemoryItem], current_time: float) -> bool:
        """Marks the first active [QUIET_MODE] item expired if its time is up."""
        for i in items:
            if i.text == "[QUIET_MODE]" and i.status == "active":
                if i.expires_at and current_time > i.expires_at:
                    i.status = "expired"
                    return True
                return False
        return False

    def is_quiet_mode_active(self, now: float | None = None) -> bool:
        current_time = now or time.time()
        for i in self._items:
            if i.text == "[QUIET_MODE]" and i.status == "active":
                if i.expires_at and current_time > i.expires_at:
                    self._persist_maintenance(
                        lambda items: self._expire_quiet_mode_pass(items, current_time)
                    )
                    return False
                return True
        return False

    def get_pending_conflicts(self) -> list[dict]:
        conflicts = []
        for i in self._items:
            if i.status == "conflict":
                parts = i.text.split("|", 2)
                if len(parts) == 3:
                    conflicts.append({
                        "old_fact": parts[0].strip(),
                        "new_fact": parts[1].strip(),
                        "reason": parts[2].strip()
                    })
        return conflicts

    def mark_conflicts_asked(self) -> None:
        with self._transaction():
            for i in self._items:
                if i.status == "conflict":
                    i.status = "conflict_asked"
            self._flush()

    def resolve_asked_conflicts(self) -> None:
        with self._transaction():
            for i in self._items:
                if i.status == "conflict_asked":
                    i.status = "deleted"
                    i.text = "[DELETED]"
            self._flush()

    def escalate_asked_conflicts(self, flags) -> None:
        """Adds exactly one content-free flag per escalated conflict. The old
        fact, new fact, reason and any category word (e.g. "emotional") are
        never included -- we cannot reliably tell which side of a conflict is
        private, and a content-free flag needs no source lookup (#156, #158,
        #165 and duplicates)."""
        with self._transaction():
            for i in self._items:
                if i.status == "conflict_asked":
                    flags.add(
                        "Unresolved Memory Ambiguity: a memory question was asked and left unanswered.",
                        severity="info",
                        disclosed_to_senior=False,
                    )
                    i.status = "deleted"
                    i.text = "[DELETED]"
            self._flush()

    def clear_conflicts(self) -> None:
        with self._transaction():
            for i in self._items:
                if i.status == "conflict":
                    i.status = "deleted"
                    i.text = "[DELETED]"
            self._flush()

    def delete(self, text: str) -> None:
        """Marks an active memory as deleted (e.g. per user request)."""
        with self._transaction():
            text = text.replace("[UNVERIFIED/UNCERTAIN]: ", "").replace("[EMOTIONAL STATE]: ", "")
            # Strip date prefix like [2026-10-09] 
            text = re.sub(r"^\[\d{4}-\d{2}-\d{2}\]\s+", "", text)
            for item in self._items:
                if item.text.lower() == text.lower() and item.status == "active":
                    item.status = "deleted"
                    item.text = "[DELETED]" # Erase from disk
            self._flush()

    def supersede(self, old_text: str, new_text: str, source: str = "conversation_extract") -> MemoryItem:
        """Evolves a memory: marks the old fact as superseded and introduces the new active fact.
        Fixes #34: inherits scope, privacy and expires_at from the original so that
        e.g. a 2-hour schedule update stays temporary after correction."""
        with self._transaction():
            old_text = old_text.replace("[UNVERIFIED/UNCERTAIN]: ", "").replace("[EMOTIONAL STATE]: ", "")
            new_text = new_text.replace("[UNVERIFIED/UNCERTAIN]: ", "").replace("[EMOTIONAL STATE]: ", "")
        
            # Strip date prefix like [2026-10-09]
            old_text = re.sub(r"^\[\d{4}-\d{2}-\d{2}\]\s+", "", old_text)
            new_text = re.sub(r"^\[\d{4}-\d{2}-\d{2}\]\s+", "", new_text)
        
            inherited_scope = MemoryScope.PERMANENT.value
            inherited_privacy = PrivacyLevel.PUBLIC_TO_SENIOR.value
            inherited_disclosure_attested = False
            inherited_expires_at = None

            for item in self._items:
                if item.text.lower() == old_text.lower() and item.status == "active":
                    item.status = "superseded"
                    # Inherit temporal and privacy properties from the original
                    inherited_scope = item.scope
                    inherited_privacy = item.privacy
                    # A senior's correction of a caregiver-authored
                    # fact never inherits a disclosure attestation from it; only a
                    # senior-derived original can pass its own attestation on.
                    inherited_disclosure_attested = (
                        item.disclosure_attested and item.source not in CAREGIVER_SOURCES
                    )
                    inherited_expires_at = item.expires_at

                    if inherited_scope == MemoryScope.UNCERTAIN.value:
                        inherited_scope = MemoryScope.PERMANENT.value

                    # Fixes #140 follow-up (Codex review, scripts/openai_review.sh):
                    # _decay_emotions() ages a 24h-expired EMOTIONAL item to
                    # HISTORICAL scope but keeps its still-private text behind a
                    # "[PAST EMOTION - <date>]" prefix. Without carrying that
                    # prefix forward, a correction to a decayed emotional memory
                    # would inherit the plain HISTORICAL scope and surface as an
                    # ordinary fact in caregiver-facing views -- undoing the
                    # privacy boundary decay was already respecting.
                    if item.text.startswith("[PAST EMOTION"):
                        prefix = item.text.split(":", 1)[0] + ": "
                        if not new_text.startswith(prefix):
                            new_text = f"{prefix}{new_text}"

                    item.superseded_by = new_text

            new_item = MemoryItem(
                text=new_text,
                source=source,
                status="active",
                scope=inherited_scope,
                privacy=inherited_privacy,
                disclosure_attested=inherited_disclosure_attested,
                expires_at=inherited_expires_at,
            )
            self._items.append(new_item)
            self._flush()
            return new_item

    def caregiver_context(self, now: float | None = None, include_private: bool = True) -> list[MemoryItem]:
        """Every caregiver-supplied memo/note that is active and non-expired.
        Set include_private=False to enforce the senior-facing privacy firewall."""
        items = []
        for i in self._items:
            if i.source in CAREGIVER_SOURCES and i.is_active(now):
                if not include_private and i.privacy == PrivacyLevel.CAREGIVER_ONLY.value:
                    continue
                items.append(i)
        return items

    def search(self, query: str, k: int = 5, now: float | None = None) -> list[MemoryItem]:
        """Scored memory retrieval with stopword pruning and semantic synonym
        expansion over active, public conversation-derived memories."""
        self._decay_emotions(now)
        raw_query = set(re.findall(r"[a-z0-9]+", query.lower()))
        meaningful_query = {t for t in raw_query if t not in STOPWORDS and len(t) > 1}
        if not meaningful_query:
            meaningful_query = raw_query

        expanded_query = set(meaningful_query)
        for term in meaningful_query:
            if term in DOMAIN_SYNONYMS:
                expanded_query.update(DOMAIN_SYNONYMS[term])

        synonym_only = expanded_query - meaningful_query

        scored = []
        for item in self._items:
            if (
                item.source in CAREGIVER_SOURCES
                or item.scope == MemoryScope.LIFESTYLE.value
                or not item.is_active(now)
            ):
                continue
            if item.privacy == PrivacyLevel.CAREGIVER_ONLY.value:
                continue
            item_terms = set(re.findall(r"[a-z0-9]+", item.text.lower()))
            meaningful_item_terms = {t for t in item_terms if t not in STOPWORDS and len(t) > 1} or item_terms
            direct_hits = len(meaningful_query & meaningful_item_terms)
            synonym_hits = len(synonym_only & meaningful_item_terms)
            score = (direct_hits * 2) + synonym_hits
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:k]]

    def caregiver_guardrails(self) -> list[str]:
        """Extracts topics the caregiver explicitly requested the companion avoid."""
        guardrails = []
        for item in self.caregiver_context(include_private=True):
            text_lower = item.text.lower()
            if any(marker in text_lower for marker in ("avoid", "don't", "do not", "never")):
                guardrails.append(item.text)
        return guardrails

    def caregiver_schedule_updates(self, now: float | None = None) -> list[str]:
        """Extracts active time-bound updates or caregiver visit/errand notes.
        Excludes expired events and private caregiver coordination."""
        schedule_patterns = (
            re.compile(r"\b(pm|am|a\.m\.|p\.m\.)\b", re.IGNORECASE),
            re.compile(r"\b(today|tomorrow|tonight|afternoon|morning|evening|o'clock)\b", re.IGNORECASE),
            re.compile(r"\b(groceries|appointment|doctor|dropping\s+off|visiting|visit)\b", re.IGNORECASE),
        )
        updates = []
        for item in self.caregiver_context(now=now, include_private=False):
            text_lower = item.text.lower()
            if any(marker in text_lower for marker in ("avoid", "don't", "do not", "never")):
                continue
            if any(pattern.search(text_lower) for pattern in schedule_patterns):
                updates.append(item.text)
        return updates

    def _decay_emotions(self, now: float | None = None):
        current_time = now or time.time()
        self._persist_maintenance(lambda items: self._decay_emotions_pass(items, current_time))

    def _decay_emotions_pass(self, items: list[MemoryItem], current_time: float) -> bool:
        import datetime
        import zoneinfo
        mutated = False
        for i in items:
            if i.scope == MemoryScope.EMOTIONAL.value and i.status == "active" and i.expires_at:
                if current_time >= i.expires_at:
                    i.scope = MemoryScope.HISTORICAL.value
                    dt_utc = datetime.datetime.fromtimestamp(i.created_at, tz=datetime.timezone.utc)
                    try:
                        dt_local = dt_utc.astimezone(zoneinfo.ZoneInfo(self.timezone_str))
                    except Exception:
                        dt_local = dt_utc
                    date_str = dt_local.strftime('%b %d, %Y')
                    i.text = f"[PAST EMOTION - {date_str}]: {i.text}"
                    i.expires_at = None
                    mutated = True
        return mutated

    def senior_profile_facts(self, now: float | None = None) -> list[str]:
        """Extracts enduring biographical anchors, preferences, and relationships.
        Strictly excludes private caregiver-only items, expired items, and superseded facts."""
        self._decay_emotions(now)
        facts = []
        schedule_items = set(self.caregiver_schedule_updates(now=now))
        guardrail_items = set(self.caregiver_guardrails())
        for item in self._items:
            if not item.is_active(now):
                continue
            if item.privacy == PrivacyLevel.CAREGIVER_ONLY.value:
                continue
            if item.text in schedule_items or item.text in guardrail_items:
                continue
            if item.scope == MemoryScope.UNCERTAIN.value:
                facts.append(f"[UNVERIFIED/UNCERTAIN]: {item.text}")
            elif item.scope == MemoryScope.EMOTIONAL.value:
                facts.append(f"[EMOTIONAL STATE]: {item.text}")
            elif item.scope == MemoryScope.LIFESTYLE.value:
                continue  # Never leak lifestyle logs into senior-facing context!
            elif item.text == "[QUIET_MODE]":
                pass
            else:
                facts.append(item.text)
        return facts

    def all(self) -> list[MemoryItem]:
        return list(self._items)

    @staticmethod
    def _expire_lifestyle_pass(items: list[MemoryItem], current_time: float) -> bool:
        mutated = False
        for i in items:
            if i.scope == MemoryScope.LIFESTYLE.value and i.status == "active":
                # Expire after 7 days
                if i.expires_at and current_time >= i.expires_at:
                    i.status = "expired"
                    i.text = "[EXPIRED]" # Remove text from disk per privacy requirements
                    mutated = True
        return mutated

    def caregiver_lifestyle_logs(self, now: float | None = None) -> list[str]:
        import datetime
        import zoneinfo
        current_time = now or time.time()
        self._persist_maintenance(lambda items: self._expire_lifestyle_pass(items, current_time))
        logs = []
        for i in self._items:
            if i.scope == MemoryScope.LIFESTYLE.value and i.status == "active":
                dt_utc = datetime.datetime.fromtimestamp(i.created_at, tz=datetime.timezone.utc)
                try:
                    dt_local = dt_utc.astimezone(zoneinfo.ZoneInfo(self.timezone_str))
                except Exception:
                    dt_local = dt_utc
                date_str = dt_local.strftime("%Y-%m-%d")
                logs.append(f"[{date_str}] {i.text}")
        return logs
