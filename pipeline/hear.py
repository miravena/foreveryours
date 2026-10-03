"""HEAR: speech-to-text.

ASR_BACKEND=whisper_local (default) uses faster-whisper on CPU, no key needed.
ASR_BACKEND=nebius uses an NVIDIA ASR model hosted on Nebius Token Factory --
the DECIDED primary backend for a real/hosted deployment (docs/ROADMAP.md),
leaning into the sponsor stack the hackathon judges on.

The CLI default stays whisper_local on purpose, not because the decision
changed: safety/fastpath.py's immediate reassurance must keep working with
no NEBIUS_API_KEY set (see pipeline/orchestrator.py), and HEAR runs before
the fast-path check. Set ASR_BACKEND=nebius explicitly once hosting (Issue
#11) has a key configured server-side.
"""
from __future__ import annotations

import os
from pathlib import Path

_whisper_model = None


def _get_whisper_model():
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


def transcribe(audio_path: Path, return_metrics: bool = False):
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        return ("", {}) if return_metrics else ""

    backend = os.environ.get("ASR_BACKEND", "whisper_local")
    if backend == "whisper_local":
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
                pause = words[i].start - words[i-1].end
                if pause > 0:
                    pauses.append(pause)
            if pauses:
                metrics["avg_pause_s"] = round(sum(pauses) / len(pauses), 2)

        return (text, metrics) if return_metrics else text
    if backend == "nebius":
        from .nebius_client import get_client

        client = get_client()
        model_name = os.environ.get("ASR_NEBIUS_MODEL", "nvidia/parakeet-tdt-1.1b")
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(model=model_name, file=f)
        return (result.text, {"wpm": 0.0, "avg_pause_s": 0.0}) if return_metrics else result.text
    raise ValueError(f"unknown ASR_BACKEND: {backend}")
