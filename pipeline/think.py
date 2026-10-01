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
simple sentences. Use the FACTS below -- names, preferences, events -- \
naturally, without announcing that you're "using notes." Never bring up
anything listed under DO NOT RAISE, even if it seems relevant -- those are
topics the caregiver asked you to avoid, not things to explain or justify.
Never give medical advice or diagnoses. If the person says something that
sounds distressing, respond honestly and warmly; do not pretend nothing
happened.
"""


def build_prompt(
    transcript: str,
    facts: list[str],
    guardrails: list[str] | None = None,
    history: list[dict] | None = None,
) -> list[dict]:
    """`history` is prior (user, assistant) turns from THIS session only --
    never persisted to disk, never loaded from memory_store. Deliberately
    separate from RECALL: history is "what we just said," memory is "what
    the caregiver told us was durably true." Conflating them would mean a
    throwaway remark ("I'm a bit tired") outliving the conversation it was
    said in. See issue #16 -- without this, a judge talking to the hosted
    demo for 3+ turns meets a companion that forgets the last sentence."""
    facts_block = "\n".join(f"- {f}" for f in facts) or "(none yet)"
    guardrails = guardrails or []
    guardrails_block = "\n".join(f"- {g}" for g in guardrails) or "(none)"
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + f"\nFACTS:\n{facts_block}\n\nDO NOT RAISE:\n{guardrails_block}",
        },
    ]
    messages.extend(history or [])
    messages.append({"role": "user", "content": transcript})
    return messages


def stream_reply(
    transcript: str,
    facts: list[str],
    guardrails: list[str] | None = None,
    history: list[dict] | None = None,
) -> Iterator[str]:
    client = get_client()
    # nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B: compact MoE, better latency fit for our
    # <2s-to-first-audio budget than a dense 70B model. Exact casing/availability
    # from third-party aggregators, not Nebius's own docs -- verify against the
    # live Token Factory model list once a key is in hand (see IMPLEMENTATION_PLAN.md).
    model = os.environ.get("THINK_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
    stream = client.chat.completions.create(
        model=model,
        messages=build_prompt(transcript, facts, guardrails, history),
        stream=True,
        max_tokens=200,
        temperature=0.6,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


SENTENCE_BOUNDARY = re.compile(r"([.!?])(\s+)")
# Words that commonly precede a "." without actually ending a sentence.
# Not exhaustive -- covers the cases that would otherwise cut a TTS chunk
# mid-title ("Dr. Smith") or mid-time ("4 P.M. today").
ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "jr", "sr", "vs", "etc", "a.m", "p.m"}


def _is_real_sentence_end(text_before_punct: str) -> bool:
    word_match = re.search(r"([A-Za-z.]+)$", text_before_punct)
    if not word_match:
        return True
    word = word_match.group(1).lower().rstrip(".")
    if len(word) <= 1:
        return False  # single letter before the period, e.g. "P" in "P.M."
    return word not in ABBREVIATIONS


def sentence_chunks(token_stream: Iterator[str]) -> Iterator[str]:
    """Buffer streamed tokens into sentence-sized chunks for streamed TTS,
    skipping false sentence-ends after common abbreviations/initials."""
    buf = ""
    emitted_up_to = 0
    for token in token_stream:
        buf += token
        search_from = emitted_up_to
        while True:
            match = SENTENCE_BOUNDARY.search(buf, search_from)
            if not match:
                break
            if _is_real_sentence_end(buf[: match.start() + 1]):
                sentence = buf[emitted_up_to : match.end()].strip()
                if sentence:
                    yield sentence
                emitted_up_to = match.end()
                search_from = emitted_up_to
            else:
                search_from = match.end()
    tail = buf[emitted_up_to:].strip()
    if tail:
        yield tail


DURABLE_MARKERS = (
    # \b on both sides -- word-boundary matching, not substring containment,
    # is what keeps "my son" from matching "my song" and "i like" from
    # matching "i likely" (the original bug used plain `in` substring checks).
    r"\bmy name is\b",
    r"\bi love\b",
    r"\bmy grandson\b",
    r"\bmy daughter\b",
    r"\bmy son\b",
    r"\bi like\b",
)


def extract_new_memory(transcript: str, reply: str) -> str | None:
    """Background extraction: does this turn contain a durable fact worth
    saving (name, preference, event)? Runs off the critical path -- see
    orchestrator.py's async call. Thin-slice heuristic now; swap for a cheap
    LLM extraction call once latency budget allows a second THINK-sized call
    per turn without affecting first-audio time."""
    lowered = transcript.lower()
    for pattern in DURABLE_MARKERS:
        if re.search(pattern, lowered):
            return transcript.strip()
    return None
