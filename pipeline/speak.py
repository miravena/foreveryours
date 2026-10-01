"""SPEAK: text-to-speech, streamed sentence-by-sentence.

pyttsx3 runs fully offline (no API key, no network) and produces real audio
on this box -- good enough for the thin-slice demo and for the <2s-to-
first-audio measurement, since it has no network round-trip latency of its
own. Swap for a Nebius-hosted open-weight TTS model (AC2 mentions this) once
voice quality matters more than latency-proving.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pyttsx3


def speak_sentences(sentences: Iterator[str], out_dir: Path) -> Iterator[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = pyttsx3.init()
    for i, sentence in enumerate(sentences):
        out_path = out_dir / f"reply_{i:03d}.wav"
        engine.save_to_file(sentence, str(out_path))
        engine.runAndWait()
        yield out_path
