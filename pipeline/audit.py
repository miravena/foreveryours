"""AUDIT: secondary lightweight LLM pass checking the senior-facing reply for
medical-hallucination / unsafe-advice risk.

Deliberately NOT on the critical path to first audio: the orchestrator fires
this after SPEAK has already started streaming, and only retracts/flags if it
comes back positive (rare). Cheap small model, short output.
"""
from __future__ import annotations

import os

from .nebius_client import get_client

AUDIT_SYSTEM_PROMPT = """\
You review a voice-companion's reply to an older adult for safety issues only:
medical advice/diagnosis, dangerous instructions, or anything that could be
unsafe if acted on. Reply with exactly one word: SAFE or UNSAFE, then if
UNSAFE a one-sentence reason.
"""


def audit_reply(reply: str) -> tuple[bool, str]:
    client = get_client()
    model = os.environ.get("AUDIT_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
            {"role": "user", "content": reply},
        ],
        max_tokens=60,
        temperature=0.0,
    )
    text = (response.choices[0].message.content or "").strip()
    is_safe = text.upper().startswith("SAFE")
    return is_safe, text
