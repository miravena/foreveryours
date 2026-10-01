"""SPEAK: text-to-speech, streamed sentence-by-sentence.

pyttsx3 runs fully offline (no API key, no network) and produces real audio
on this box -- good enough for the thin-slice demo and for the <2s-to-
first-audio measurement, since it has no network round-trip latency of its
own. Swap for a Nebius-hosted open-weight TTS model once voice quality
matters more than latency-proving.

Needs the `espeak-ng` system package on Linux (`apt install espeak-ng`) --
pyttsx3.init() raises OSError without it.
"""
from __future__ import annotations

import itertools
import time
from collections.abc import Iterator
from pathlib import Path

import pyttsx3

_turn_counter = itertools.count()


def speak_sentences(sentences: Iterator[str], out_dir: Path) -> Iterator[tuple[str, Path]]:
    """Consume the WHOLE sentence stream for one turn in a single call --
    each call gets its own turn id, so calling this once per sentence (as
    opposed to once per turn) would silently make every file collide on the
    same name. One call per turn is the contract."""
    out_dir.mkdir(parents=True, exist_ok=True)
    turn_id = f"{int(time.time())}-{next(_turn_counter)}"
    engine = pyttsx3.init()
    for i, sentence in enumerate(sentences):
        out_path = out_dir / f"reply_{turn_id}_{i:03d}.wav"
        engine.save_to_file(sentence, str(out_path))
        engine.runAndWait()
        yield sentence, out_path
