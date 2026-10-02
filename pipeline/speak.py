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

import contextlib
import io
import itertools
import sys
import time
from collections.abc import Iterator
from pathlib import Path

_turn_counter = itertools.count()


def _get_tts_engine():
    if sys.platform == "win32":
        # On Windows, pyttsx3 SAPI5 deadlocks when engine.runAndWait() is called
        # repeatedly across multiple sentences in the same process. PowerShell's
        # native System.Speech handles multi-sentence synthesis reliably.
        return None
    try:
        import pyttsx3

        return pyttsx3.init()
    except Exception:
        return None


def _synthesize_file(sentence: str, out_path: Path, engine) -> None:
    if engine is not None:
        engine.save_to_file(sentence, str(out_path))
        # pyttsx3's espeak driver prints "Audio saved to <absolute path>" to
        # stdout from its own _onSynth callback -- not something we call
        # directly, so it can't be fixed by changing our own print calls.
        # Suppressed here rather than left to leak the real filesystem path
        # into anything that captures this process's stdout (e.g. a terminal
        # recording meant for public release).
        with contextlib.redirect_stdout(io.StringIO()):
            engine.runAndWait()
        return

    if sys.platform == "win32":
        import subprocess

        safe_sentence = sentence.replace("'", " ").replace('"', ' ')
        # Also strip curly/smart quotes and apostrophes that LLMs love to produce
        for ch in "\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f":
            safe_sentence = safe_sentence.replace(ch, " ")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = -1; "
            f"$s.SetOutputToWaveFile('{out_path.as_posix()}'); "
            f"$s.Speak('{safe_sentence}'); "
            f"$s.Dispose()"
        )
        subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True)
        return

    raise RuntimeError("pyttsx3 is required for speech synthesis: pip install pyttsx3")


def speak_sentences(sentences: Iterator[str], out_dir: Path) -> Iterator[tuple[str, Path]]:
    """Consume the WHOLE sentence stream for one turn in a single call --
    each call gets its own turn id, so calling this once per sentence (as
    opposed to once per turn) would silently make every file collide on the
    same name. One call per turn is the contract."""
    out_dir.mkdir(parents=True, exist_ok=True)
    turn_id = f"{int(time.time())}-{next(_turn_counter)}"
    engine = _get_tts_engine()

    for i, sentence in enumerate(sentences):
        out_path = out_dir / f"reply_{turn_id}_{i:03d}.wav"
        _synthesize_file(sentence, out_path, engine)
        yield sentence, out_path

