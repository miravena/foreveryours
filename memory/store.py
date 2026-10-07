"""RECALL: minimal persistent memory store, scoped per senior profile.

Thin-slice version: JSON file instead of ChromaDB. Keyword overlap instead of
embeddings for conversation-derived memories. Swappable later behind the same
get/save/search interface once the vector-store step is worth the extra
latency budget.
"""
from __future__ import annotations

from enum import Enum
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

CAREGIVER_SOURCES = ("caregiver_memo", "caregiver_note")


class MemoryScope(str, Enum):
    PERMANENT = "permanent"     # Lifelong identity, family relations, enduring passions
    TEMPORARY = "temporary"     # Daily visits, schedule updates, errands
    HISTORICAL = "historical"   # Superseded preferences, past events
    EMOTIONAL = "emotional"
    UNCERTAIN = "uncertain"


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


class MemoryStore:
    def __init__(self, profile_id: str, data_dir: Path):
        self.profile_id = profile_id
        self.path = data_dir / f"{profile_id}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[MemoryItem] = self._load()

    def _load(self) -> list[MemoryItem]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text())
        items = []
        for d in raw:
            d.setdefault("scope", MemoryScope.PERMANENT.value)
            d.setdefault("privacy", PrivacyLevel.PUBLIC_TO_SENIOR.value)
            d.setdefault("expires_at", None)
            d.setdefault("status", "active")
            d.setdefault("superseded_by", None)
            items.append(MemoryItem(**d))
        return items

    def _flush(self) -> None:
        """Write-then-rename so a crash/Ctrl-C mid-write can't leave invalid
        JSON that would crash every later load."""
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps([item.__dict__ for item in self._items], indent=2)
        )
        os.replace(tmp_path, self.path)

    def add(
        self,
        text: str,
        source: str,
        scope: str = MemoryScope.PERMANENT.value,
        privacy: str = PrivacyLevel.PUBLIC_TO_SENIOR.value,
        expires_at: float | None = None,
    ) -> MemoryItem | None:
        """No-op (returns None) if this exact (text, source) is already active.
        Auto-infers TEMPORARY scope for schedule/time notes."""
        if any(i.text == text and i.source == source and i.status == "active" for i in self._items):
            return None
        if scope == MemoryScope.PERMANENT.value and any(m in text.lower() for m in ("today", "tomorrow", "tonight", "pm", "am")):
            scope = MemoryScope.TEMPORARY.value
            
        if scope == MemoryScope.TEMPORARY.value and expires_at is None:
            expires_at = time.time() + 86400
            
        item = MemoryItem(
            text=text,
            source=source,
            scope=scope,
            privacy=privacy,
            expires_at=expires_at,
        )
        self._items.append(item)
        self._flush()
        return item

    def add_conflict(self, old_fact: str, new_fact: str, reason: str) -> None:
        """Stores a pending memory conflict to be resolved on the next turn."""
        item = MemoryItem(
            text=f"{old_fact}|{new_fact}|{reason}",
            source="conversation_extract",
            status="conflict"
        )
        self._items.append(item)
        self._flush()

    def set_quiet_mode(self, hours: float = 4.0) -> None:
        import time
        expires_at = time.time() + (hours * 3600)
        self._items = [i for i in self._items if i.text != "[QUIET_MODE]"]
        self.add("[QUIET_MODE]", source="system", scope=MemoryScope.TEMPORARY.value, expires_at=expires_at)

    def is_quiet_mode_active(self, now: float | None = None) -> bool:
        import time
        current_time = now or time.time()
        for i in self._items:
            if i.text == "[QUIET_MODE]" and i.status == "active":
                if i.expires_at and current_time > i.expires_at:
                    i.status = "expired"
                    self._flush()
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
        for i in self._items:
            if i.status == "conflict":
                i.status = "conflict_asked"
        self._flush()

    def resolve_asked_conflicts(self) -> None:
        for i in self._items:
            if i.status == "conflict_asked":
                i.status = "deleted"
        self._flush()

    def escalate_asked_conflicts(self, flags) -> None:
        for i in self._items:
            if i.status == "conflict_asked":
                parts = i.text.split("|", 2)
                if len(parts) == 3:
                    flags.add(f"Unresolved Memory Ambiguity: {parts[0].strip()} vs {parts[1].strip()}", severity="info", disclosed_to_senior=False)
                i.status = "deleted"
        self._flush()

    def clear_conflicts(self) -> None:
        for i in self._items:
            if i.status == "conflict":
                i.status = "deleted"
        self._flush()

    def delete(self, text: str) -> None:
        """Marks an active memory as deleted (e.g. per user request)."""
        for item in self._items:
            if item.text.lower() == text.lower() and item.status == "active":
                item.status = "deleted"
        self._flush()

    def supersede(self, old_text: str, new_text: str, source: str = "conversation_extract") -> MemoryItem:
        """Evolves a memory: marks the old fact as superseded and introduces the new active fact.
        Fixes #34: inherits scope, privacy and expires_at from the original so that
        e.g. a 2-hour schedule update stays temporary after correction."""
        inherited_scope = MemoryScope.PERMANENT.value
        inherited_privacy = PrivacyLevel.PUBLIC_TO_SENIOR.value
        inherited_expires_at = None

        for item in self._items:
            if item.text.lower() == old_text.lower() and item.status == "active":
                item.status = "superseded"
                item.superseded_by = new_text
                # Inherit temporal and privacy properties from the original
                inherited_scope = item.scope
                inherited_privacy = item.privacy
                inherited_expires_at = item.expires_at

        new_item = MemoryItem(
            text=new_text,
            source=source,
            status="active",
            scope=inherited_scope,
            privacy=inherited_privacy,
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
            if item.source in CAREGIVER_SOURCES or not item.is_active(now):
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

    def senior_profile_facts(self, now: float | None = None) -> list[str]:
        """Extracts enduring biographical anchors, preferences, and relationships.
        Strictly excludes private caregiver-only items, expired items, and superseded facts."""
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
            elif item.text == "[QUIET_MODE]":
                pass
            else:
                facts.append(item.text)
        return facts

    def all(self) -> list[MemoryItem]:
        return list(self._items)
