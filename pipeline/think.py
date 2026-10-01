"""THINK: senior-facing reply, grounded in caregiver-supplied memory, streamed.

Streams tokens so SPEAK can start synthesizing audio on the first sentence
instead of waiting for the full completion -- this is the main lever for the
<2s-to-first-audio target. extract_new_memory() runs separately and async
(see orchestrator.py), never blocking the reply.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterator

from .nebius_client import get_client

SYSTEM_PROMPT = """\
You are a warm, patient voice companion for an older adult. Speak in short,
simple sentences. Use the MEMORY block below -- names, preferences, and
caregiver notes -- naturally, without announcing that you're "using notes."
Never give medical advice or diagnoses. If the person says something that
sounds distressing, respond honestly and warmly; do not pretend nothing
happened.
"""


def build_prompt(transcript: str, memories: list[str]) -> list[dict]:
    memory_block = "\n".join(f"- {m}" for m in memories) or "(no memories yet)"
    return [
        {"role": "system", "content": SYSTEM_PROMPT + f"\nMEMORY:\n{memory_block}"},
        {"role": "user", "content": transcript},
    ]


def stream_reply(transcript: str, memories: list[str]) -> Iterator[str]:
    client = get_client()
    model = os.environ.get("THINK_MODEL", "nvidia/Llama-3_1-Nemotron-70B-Instruct-HF")
    stream = client.chat.completions.create(
        model=model,
        messages=build_prompt(transcript, memories),
        stream=True,
        max_tokens=200,
        temperature=0.6,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def sentence_chunks(token_stream: Iterator[str]) -> Iterator[str]:
    """Buffer streamed tokens into sentence-sized chunks for streamed TTS."""
    buf = ""
    for token in token_stream:
        buf += token
        parts = SENTENCE_END.split(buf)
        if len(parts) > 1:
            for sentence in parts[:-1]:
                if sentence.strip():
                    yield sentence.strip()
            buf = parts[-1]
    if buf.strip():
        yield buf.strip()


def extract_new_memory(transcript: str, reply: str) -> str | None:
    """Background extraction: does this turn contain a durable fact worth
    saving (name, preference, event)? Runs off the critical path -- see
    orchestrator.py's async call. Thin-slice heuristic now; swap for a cheap
    LLM extraction call once latency budget allows a second THINK-sized call
    per turn without affecting first-audio time."""
    durable_markers = ("my name is", "i like", "i love", "my grandson", "my daughter", "my son")
    lowered = transcript.lower()
    for marker in durable_markers:
        if marker in lowered:
            return transcript.strip()
    return None
