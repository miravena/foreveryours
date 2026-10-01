"""HEAR: speech-to-text.

ASR_BACKEND=whisper_local (default, no key needed) uses faster-whisper on CPU.
ASR_BACKEND=nebius tries an NVIDIA ASR model (Parakeet/Canary) hosted on Nebius
Token Factory if/when the account has one provisioned -- preferred per the
hackathon's sponsor-stack judging criterion (see README.md). Not yet wired
into main.py's demo beats, which take text input -- see open GitHub Issues.
"""
from __future__ import annotations

import os
from pathlib import Path

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        size = os.environ.get("ASR_MODEL", "base.en")
        _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


def transcribe(audio_path: Path) -> str:
    backend = os.environ.get("ASR_BACKEND", "whisper_local")
    if backend == "whisper_local":
        model = _get_whisper_model()
        segments, _info = model.transcribe(str(audio_path))
        return " ".join(seg.text.strip() for seg in segments)
    if backend == "nebius":
        from .nebius_client import get_client

        client = get_client()
        model_name = os.environ.get("ASR_NEBIUS_MODEL", "nvidia/parakeet-tdt-1.1b")
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(model=model_name, file=f)
        return result.text
    raise ValueError(f"unknown ASR_BACKEND: {backend}")
