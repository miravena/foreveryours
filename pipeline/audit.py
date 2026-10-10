"""AUDIT: secondary lightweight LLM pass checking the senior-facing reply for
medical-hallucination / unsafe-advice risk.

Not on the critical path to first audio: the orchestrator fires this after
SPEAK has already started streaming, and only flags if it comes back
UNSAFE (rare). Cheap small model, short output. It cannot retract a reply
that's already been spoken -- see orchestrator.py's disclosure follow-up.
"""
from __future__ import annotations

import os
import re

from .nebius_client import get_client

AUDIT_SYSTEM_PROMPT = """\
You review a voice-companion's reply to an older adult for safety issues, AND you review the older adult's transcript for signs of distress.

You have three failure modes to look for:
1. UNSAFE: The companion's reply contains medical advice/diagnosis, dangerous instructions, or anything that could be unsafe if acted on.
2. CRISIS: The senior's transcript expresses suicidal ideation, a desire to die, or severe crisis (e.g. "I don't want to be here anymore", "wish I was dead").
3. DISTRESS: The senior's transcript expresses physical distress, fear, a fall, or inability to move (e.g. "I hit the floor", "my legs gave way", "I'm terrified", "I feel dizzy").

Reply with exactly one word first (SAFE, UNSAFE, CRISIS, or DISTRESS), then a one-sentence reason. If multiple apply, prefer CRISIS over DISTRESS, and DISTRESS over UNSAFE.
"""


def audit_reply(transcript: str, reply: str) -> tuple[str, str]:
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
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    text = (response.choices[0].message.content or "").strip()
    match = re.match(r"^\s*[*_`\"']*(SAFE|UNSAFE|CRISIS|DISTRESS)\b", text, re.IGNORECASE)
    if not match:
        status = "UNKNOWN"
    else:
        status = match.group(1).upper()

    return status, text
