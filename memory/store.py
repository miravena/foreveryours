"""RECALL: minimal persistent memory store, scoped per senior profile.

Thin-slice version: JSON file instead of ChromaDB. Keyword overlap instead of
embeddings. Swappable later behind the same get/save/search interface once
the vector-store step is worth the extra latency budget.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MemoryItem:
    text: str
    source: str  # "caregiver_memo" | "caregiver_note" | "conversation_extract"
    created_at: float = field(default_factory=time.time)


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
        self.path.write_text(
            json.dumps([item.__dict__ for item in self._items], indent=2)
        )

    def add(self, text: str, source: str) -> MemoryItem:
        item = MemoryItem(text=text, source=source)
        self._items.append(item)
        self._flush()
        return item

    def search(self, query: str, k: int = 5) -> list[MemoryItem]:
        """Keyword-overlap scoring. Good enough for the demo's small memo set;
        swap for embeddings + ChromaDB if memory volume grows past a few dozen
        items per profile."""
        query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored = []
        for item in self._items:
            item_terms = set(re.findall(r"[a-z0-9]+", item.text.lower()))
            overlap = len(query_terms & item_terms)
            if overlap:
                scored.append((overlap, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:k]]

    def all(self) -> list[MemoryItem]:
        return list(self._items)
