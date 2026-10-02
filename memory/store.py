"""RECALL: minimal persistent memory store, scoped per senior profile.

Thin-slice version: JSON file instead of ChromaDB. Keyword overlap instead of
embeddings for conversation-derived memories. Swappable later behind the same
get/save/search interface once the vector-store step is worth the extra
latency budget.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

CAREGIVER_SOURCES = ("caregiver_memo", "caregiver_note")


@dataclass
class MemoryItem:
    text: str
    source: str  # "caregiver_memo" | "caregiver_note" | "conversation_extract"
    created_at: float = field(default_factory=time.time)


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
        return [MemoryItem(**item) for item in raw]

    def _flush(self) -> None:
        """Write-then-rename so a crash/Ctrl-C mid-write can't leave invalid
        JSON that would crash every later load."""
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps([item.__dict__ for item in self._items], indent=2)
        )
        os.replace(tmp_path, self.path)

    def add(self, text: str, source: str) -> MemoryItem | None:
        """No-op (returns None) if this exact (text, source) is already
        stored -- re-running beat1 or re-saying the same fact shouldn't pile
        up duplicates."""
        if any(i.text == text and i.source == source for i in self._items):
            return None
        item = MemoryItem(text=text, source=source)
        self._items.append(item)
        self._flush()
        return item

    def caregiver_context(self) -> list[MemoryItem]:
        """Every caregiver-supplied memo/note -- always injected into THINK's
        prompt, never subject to keyword-overlap search. There are only ever
        a handful of these per profile, and a caregiver's guardrail ("avoid
        talking about driving") must be present every turn, not just when
        its exact words happen to overlap with what the senior said."""
        return [i for i in self._items if i.source in CAREGIVER_SOURCES]

    def search(self, query: str, k: int = 5) -> list[MemoryItem]:
        """Scored memory retrieval with stopword pruning and semantic synonym
        expansion over conversation-derived memories. Caregiver context is
        returned separately, unconditionally, by caregiver_context().
        Direct matches are weighted higher than synonym matches."""
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
            if item.source in CAREGIVER_SOURCES:
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
        for item in self.caregiver_context():
            text_lower = item.text.lower()
            if any(marker in text_lower for marker in ("avoid", "don't", "do not", "never")):
                guardrails.append(item.text)
        return guardrails

    def caregiver_schedule_updates(self) -> list[str]:
        """Extracts time-bound updates or caregiver visit/errand notes."""
        schedule_patterns = (
            re.compile(r"\b(pm|am|a\.m\.|p\.m\.)\b", re.IGNORECASE),
            re.compile(r"\b(today|tomorrow|tonight|afternoon|morning|evening|o'clock)\b", re.IGNORECASE),
            re.compile(r"\b(groceries|appointment|doctor|dropping\s+off|visiting|visit)\b", re.IGNORECASE),
        )
        updates = []
        for item in self.caregiver_context():
            text_lower = item.text.lower()
            # Guardrails are handled separately
            if any(marker in text_lower for marker in ("avoid", "don't", "do not", "never")):
                continue
            if any(pattern.search(text_lower) for pattern in schedule_patterns):
                updates.append(item.text)
        return updates

    def senior_profile_facts(self) -> list[str]:
        """Extracts enduring biographical anchors, preferences, and relationships."""
        facts = []
        schedule_items = set(self.caregiver_schedule_updates())
        guardrail_items = set(self.caregiver_guardrails())
        for item in self._items:
            if item.text in schedule_items or item.text in guardrail_items:
                continue
            facts.append(item.text)
        return facts

    def all(self) -> list[MemoryItem]:
        return list(self._items)
