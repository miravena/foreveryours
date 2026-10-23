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
Your main subject is what the older adult SAID (the "Person said" line): read that transcript first and judge it on its own, whatever the companion replied. The companion's reply is context, not the subject, and a warm or reassuring reply never makes a worrying transcript safe.

Look for three failure modes:
1. CRISIS: the transcript expresses suicidal ideation, a desire to die, or severe crisis (e.g. "I don't want to be here anymore", "wish I was dead").
2. DISTRESS: the transcript says or strongly implies a fall, an injury, being stuck on the floor or unable to get up or move, sudden weakness or a leg giving way, pain, fear, dizziness or faintness, even in few or unusual words and even if the person sounds calm. Examples: "my knees buckled and I'm lying in the hallway" and "I slid off the chair onto the carpet and can't get myself up" are DISTRESS. Everyday talk is not: "the fall colours were lovely" or "I fell asleep in my chair" is SAFE.
3. UNSAFE: the companion's reply contains medical advice or diagnosis, dangerous instructions, or anything that could be unsafe if acted on.

Reply with exactly one word first (SAFE, UNSAFE, CRISIS, or DISTRESS), then a one-sentence reason. If multiple apply, prefer CRISIS over DISTRESS, and DISTRESS over UNSAFE.
"""

# Crisis examples (#199, ADR-013). A separate block so the crisis wording can
# change without touching the other failure modes above. These are the
# euphemistic or plan-like phrasings the fast-path regexes deliberately do not
# match; the prompt's output contract is unchanged.
CRISIS_EXAMPLES_BLOCK = """\

More CRISIS examples, even when the companion's reply was warm and gave no hotline:
- "I keep my pills in a drawer in case I decide to use them"
- "I have said my goodbyes, I am ready to go"
- "I would be happier if I never woke up"
- "I can't keep doing this, I want everything to stop"
- "I don't see the point of being around any longer"
Not CRISIS: figures of speech and ordinary complaints, for example "this soup is killing me, it is so spicy", "I nearly died laughing at that joke", "I'm dying for a biscuit", "I don't want to be at the dentist's on Monday".
"""
AUDIT_SYSTEM_PROMPT += CRISIS_EXAMPLES_BLOCK

# Token usage of the most recent audit_reply() call (the response's `usage`
# object, or None). Read by scripts/audit_eval.py to measure per-call cost
# (ADR-010); the return shape of audit_reply() stays (status, text).
LAST_USAGE = None

DEFAULT_AUDIT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def audit_reply(transcript: str, reply: str) -> tuple[str, str]:
    global LAST_USAGE
    LAST_USAGE = None
    client = get_client()
    model = os.environ.get("AUDIT_MODEL", DEFAULT_AUDIT_MODEL)
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
    LAST_USAGE = getattr(response, "usage", None)
    text = (response.choices[0].message.content or "").strip()
    match = re.match(r"^\s*[*_`\"']*(SAFE|UNSAFE|CRISIS|DISTRESS)\b", text, re.IGNORECASE)
    if not match:
        status = "UNKNOWN"
    else:
        status = match.group(1).upper()

    return status, text
