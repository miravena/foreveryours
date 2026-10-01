"""Caregiver-side state: the onboarding memo, daily notes, and safety flags.

Thin-slice version: one hardcoded senior profile ("dad"), caregiver = "Sarah".
Multi-profile support is a later concern -- the demo only needs one.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROFILE_ID = "dad"
DEFAULT_CAREGIVER_NAME = "Sarah"


@dataclass
class CaregiverFlag:
    text: str
    severity: str
    created_at: float = field(default_factory=time.time)
    disclosed_to_senior: bool = False


class CaregiverFlags:
    def __init__(self, profile_id: str, data_dir: Path):
        self.path = data_dir / f"{profile_id}.flags.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flags: list[CaregiverFlag] = self._load()

    def _load(self) -> list[CaregiverFlag]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text())
        return [CaregiverFlag(**item) for item in raw]

    def _flush(self) -> None:
        self.path.write_text(json.dumps([f.__dict__ for f in self._flags], indent=2))

    def add(self, text: str, severity: str) -> CaregiverFlag:
        flag = CaregiverFlag(text=text, severity=severity, disclosed_to_senior=True)
        self._flags.append(flag)
        self._flush()
        return flag

    def all(self) -> list[CaregiverFlag]:
        return list(self._flags)
