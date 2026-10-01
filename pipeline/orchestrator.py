"""One voice turn, end to end: HEAR -> fast-path check -> RECALL -> THINK
(streamed) -> SPEAK (streamed, sentence-by-sentence) -> async AUDIT +
async memory-extraction.

Latency design (AC2): SPEAK starts on the first sentence of THINK's stream,
not the full completion. AUDIT and memory-extraction run in a background
thread after the first sentence is already on its way to audio -- neither
blocks time-to-first-audio. The rule-based fast-path in safety/fastpath.py
runs synchronously but is regex-only (microseconds), so it doesn't cost
anything on the common path, and skips the LLM call entirely on the rare
distress/confusion path.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from caregiver import CaregiverFlags  # noqa: E402
from memory.store import MemoryStore  # noqa: E402
from safety import fastpath  # noqa: E402

from . import audit, speak, think  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class TurnResult:
    transcript: str
    reply_text: str
    audio_paths: list[Path] = field(default_factory=list)
    memories_used: list[str] = field(default_factory=list)
    memory_saved: str | None = None
    caregiver_flag: str | None = None
    time_to_first_audio_s: float | None = None
    audit_verdict: str | None = None  # filled in async, may arrive after return


def run_turn(
    profile_id: str,
    transcript: str,
    memory_store: MemoryStore,
    flags: CaregiverFlags,
    audio_out_dir: Path,
) -> TurnResult:
    t0 = time.monotonic()

    fast = fastpath.check(transcript)
    if fast.triggered:
        flags.add(fast.caregiver_flag, severity=fast.severity)
        audio_paths = list(speak.speak_sentences(iter([fast.reply_text]), audio_out_dir))
        return TurnResult(
            transcript=transcript,
            reply_text=fast.reply_text,
            audio_paths=audio_paths,
            memories_used=[],
            caregiver_flag=fast.caregiver_flag,
            time_to_first_audio_s=time.monotonic() - t0,
            audit_verdict="skipped (fast-path)",
        )

    recalled = memory_store.search(transcript)
    memory_texts = [m.text for m in recalled]

    token_stream = think.stream_reply(transcript, memory_texts)
    sentences = think.sentence_chunks(token_stream)

    audio_paths: list[Path] = []
    full_reply_parts: list[str] = []
    first_audio_time: float | None = None
    for sentence_batch in _collect_and_speak(sentences, audio_out_dir):
        for sentence, audio_path in sentence_batch:
            full_reply_parts.append(sentence)
            audio_paths.append(audio_path)
            if first_audio_time is None:
                first_audio_time = time.monotonic() - t0

    reply_text = " ".join(full_reply_parts)
    result = TurnResult(
        transcript=transcript,
        reply_text=reply_text,
        audio_paths=audio_paths,
        memories_used=memory_texts,
        time_to_first_audio_s=first_audio_time,
    )

    def background() -> None:
        try:
            is_safe, verdict = audit.audit_reply(reply_text)
            result.audit_verdict = verdict
            if not is_safe:
                flags.add(f"AUDIT flagged a reply as unsafe: {verdict}", severity="audit")
        except Exception as exc:  # pragma: no cover - best-effort background task
            result.audit_verdict = f"audit error: {exc}"

        saved = think.extract_new_memory(transcript, reply_text)
        if saved:
            memory_store.add(saved, source="conversation_extract")
            result.memory_saved = saved

    threading.Thread(target=background, daemon=True).start()
    return result


def _collect_and_speak(sentences, audio_out_dir):
    """Pairs each sentence with its synthesized audio path, yielded as a
    single-item batch so run_turn can track first-audio timing per sentence."""
    for sentence in sentences:
        audio_path = next(speak.speak_sentences(iter([sentence]), audio_out_dir))
        yield [(sentence, audio_path)]
