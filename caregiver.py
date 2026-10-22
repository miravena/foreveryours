"""Caregiver-side state: the onboarding memo, daily notes, and safety flags.

Thin-slice version: one hardcoded senior profile ("dad"), caregiver = "Sarah".
Multi-profile support is a later concern -- the demo only needs one.
"""
from __future__ import annotations

import json
import os
import re
import time
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

# One sentence boundary for every memo path (#23215). Each caller used to
# split on its own rule ("." + space here, [.!?\n]+ there), so the same memo
# dictated once and typed once produced different texts -- MemoryStore.add's
# exact (text, source) dedupe cannot see those as the same fact, and a
# transcript with "!"/"?"/no space after "." was stored as one whole-memo
# item beside its own fragments. A "." followed by a digit is a decimal
# point ("Give 1.5 mg"), never a boundary (openai_review on #23215).
_MEMO_FACT_BOUNDARY_RE = re.compile(r"(?:[!?\n]|\.(?!\d))+")


def split_memo_facts(memo: str | None) -> list[str]:
    """Split a caregiver memo (typed, dictated or canned) into one stripped
    fact per sentence, dropping empties. The ONLY splitter any memo path may
    use, so a memo saved by any route yields identical items."""
    return [part.strip() for part in _MEMO_FACT_BOUNDARY_RE.split(memo or "") if part.strip()]


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
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps([f.__dict__ for f in self._flags], indent=2))
        os.replace(tmp_path, self.path)

    def add(self, text: str, severity: str, disclosed_to_senior: bool) -> CaregiverFlag:
        """`disclosed_to_senior` must reflect reality, not a default: only
        True when the senior was actually told, in the conversation, that
        this flag was raised. See safety/fastpath.py (always discloses, part
        of the immediate reply) and pipeline/orchestrator.py's AUDIT path
        (discloses via a follow-up spoken line; False only if that fails)."""
        flag = CaregiverFlag(text=text, severity=severity, disclosed_to_senior=disclosed_to_senior)
        self._flags.append(flag)
        self._flush()
        return flag

    def all(self) -> list[CaregiverFlag]:
        return list(self._flags)
