"""AUDIT: secondary lightweight LLM pass checking the senior-facing reply for
medical-hallucination / unsafe-advice risk.

Not on the critical path to first audio: the orchestrator fires this after
SPEAK has already started streaming, and only flags if it comes back
UNSAFE (rare). Cheap small model, short output. It cannot retract a reply
that's already been spoken -- see orchestrator.py's disclosure follow-up.
"""
from __future__ import annotations

import os

from .nebius_client import get_client

AUDIT_SYSTEM_PROMPT = """\
You review a voice-companion's reply to an older adult for safety issues only:
medical advice/diagnosis, dangerous instructions, or anything that could be
unsafe if acted on -- taking the conversation so far into account, since a
reply like "yes, take two more" is only unsafe in context. Reply with
exactly one word first, UNSAFE or SAFE, then if UNSAFE a one-sentence reason.
"""


def audit_reply(transcript: str, reply: str) -> tuple[bool, str]:
    client = get_client()
    model = os.environ.get("AUDIT_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Person said: {transcript}\nCompanion replied: {reply}"},
        ],
        max_tokens=300,
        temperature=0.0,
    )
    text = (response.choices[0].message.content or "").strip()
    # Check UNSAFE first: a safe reply that happens to mention the word
    # "SAFE" mid-sentence (e.g. "The reply is SAFE") must not be misread as
    # starting with SAFE by coincidence -- it already does, since we check
    # the literal prefix, but checking UNSAFE first keeps that the
    # deciding word regardless of phrasing drift.
    is_safe = not text.upper().startswith("UNSAFE")
    return is_safe, text
