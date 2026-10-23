"""HEAR: speech-to-text.

ASR_BACKEND=whisper_local (default) uses faster-whisper on CPU, no key needed.
ASR_BACKEND=nebius uses an NVIDIA ASR model hosted on Nebius Token Factory,
with local faster-whisper as an automatic dependency/outage fallback.

The CLI default stays whisper_local on purpose, not because the decision
changed: safety/fastpath.py's immediate reassurance must keep working with
no NEBIUS_API_KEY set (see pipeline/orchestrator.py), and HEAR runs before
the fast-path check. Set ASR_BACKEND=nebius explicitly once hosting (Issue
#11) has a key configured server-side. A hosted failure falls back locally
before the transcript reaches the safety fast-path.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

_whisper_model = None
# Turns from different visitors now run concurrently: without this,
# two first calls could each load a WhisperModel. Only the lazy load is
# guarded; transcribe() itself stays unlocked so one visitor's ASR never
# queues another's (CTranslate2 models accept concurrent calls).
_whisper_model_lock = threading.Lock()


class AudioInputError(ValueError):
    """The audio file could not be decoded (corrupt or unsupported)."""


def probe_duration(audio_path: Path) -> float:
    """Decoded length of `audio_path` in seconds, read from the container
    header with PyAV (installed with gradio) -- no ASR, no full decode. Returns
    0.0 when the file carries no duration information rather than guessing;
    raises AudioInputError for anything PyAV cannot open."""
    try:
        import av

        container = av.open(str(audio_path))
        try:
            if container.duration is not None:
                return container.duration / av.time_base
            for stream in container.streams.audio:
                if stream.duration is not None and stream.time_base is not None:
                    return float(stream.duration * stream.time_base)
            return 0.0
        finally:
            container.close()
    except Exception as exc:
        raise AudioInputError("could not decode audio") from exc


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_model_lock:
        return _load_whisper_model_locked()


def _load_whisper_model_locked():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Run `pip install -r requirements.txt` "
                "or configure NEBIUS_API_KEY and set ASR_BACKEND=nebius for hosted ASR."
            ) from exc

        size = os.environ.get("ASR_MODEL", "base.en")
        _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


def warm_up() -> None:
    """Load the local Whisper model now, at startup, instead of on the first
    judge's audio click (#81 B4). A no-op when ASR_BACKEND=nebius (nothing to
    warm up locally), and best-effort otherwise -- a failed download here
    must not crash a text-only/no-mic session; `transcribe()` will raise the
    real error if and when audio actually needs it (Codex review, PR #90)."""
    if os.environ.get("ASR_BACKEND", "whisper_local") != "whisper_local":
        return
    try:
        _get_whisper_model()
    except Exception as exc:
        print(f"[hear] Whisper warm-up failed ({exc}); will retry on first transcribe() call.")


def _transcribe_local(audio_path: Path, return_metrics: bool):
    model = _get_whisper_model()
    segments, _info = model.transcribe(str(audio_path), vad_filter=True, word_timestamps=True)

    words = []
    text = ""
    for seg in segments:
        text += seg.text.strip() + " "
        if seg.words:
            words.extend(seg.words)
    text = text.strip()

    metrics = {"wpm": 0.0, "avg_pause_s": 0.0}
    if words and len(words) > 1:
        duration_minutes = (words[-1].end - words[0].start) / 60.0
        if duration_minutes > 0:
            metrics["wpm"] = round(len(words) / duration_minutes, 1)

        pauses = []
        for i in range(1, len(words)):
            pause = words[i].start - words[i - 1].end
            if pause > 0:
                pauses.append(pause)
        if pauses:
            metrics["avg_pause_s"] = round(sum(pauses) / len(pauses), 2)

    return (text, metrics) if return_metrics else text


def transcribe(audio_path: Path, return_metrics: bool = False):
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        return ("", {}) if return_metrics else ""

    backend = os.environ.get("ASR_BACKEND", "whisper_local")
    if backend == "whisper_local":
        return _transcribe_local(audio_path, return_metrics)
    if backend == "nebius":
        from .nebius_client import get_client

        try:
            client = get_client()
            model_name = os.environ.get("ASR_NEBIUS_MODEL", "nvidia/parakeet-tdt-1.1b")
            with open(audio_path, "rb") as f:
                result = client.audio.transcriptions.create(model=model_name, file=f)
            return (result.text, {"wpm": 0.0, "avg_pause_s": 0.0}) if return_metrics else result.text
        except Exception as hosted_exc:
            print(
                f"[hear] hosted ASR failed ({type(hosted_exc).__name__}); "
                "trying local Whisper fallback",
                file=sys.stderr,
            )
            try:
                return _transcribe_local(audio_path, return_metrics)
            except Exception as local_exc:
                raise RuntimeError(
                    "hosted ASR and local Whisper fallback both failed "
                    f"({type(hosted_exc).__name__}, {type(local_exc).__name__})"
                ) from local_exc
    raise ValueError(f"unknown ASR_BACKEND: {backend}")
