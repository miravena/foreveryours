#!/usr/bin/env python3
"""Render Dad's spoken lines for the v6 demo video with Kokoro TTS (Apache-2.0), one WAV per line.

The v6 hosted shots feed these WAVs to the live Space through Chromium's fake microphone
(--use-file-for-fake-audio-capture), so the Space's own speech recognition hears Dad. The
committed samples/*.wav were made with the Windows speech synthesizer, which cannot run here,
so every Dad line in v6, the fall line included, is rendered here in one voice, and Dad sounds
like one person throughout. Voice am_michael, a male voice distinct from the narrator's
af_heart. Each WAV has 0.6 s of silence before and 1.2 s after the line, so the recorder never
clips a word.

Run with the Kokoro venv (see ../v2/narration/README.md):
    <kokoro-venv>/bin/python video/v6/dad_voice.py [<build_dir>]
Writes <build>/dad_v6/<name>.wav (48 kHz mono, -16 LUFS) and lines.json.
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf
import phonemizer.backend.espeak.api as A
from kokoro_onnx import Kokoro
from kokoro_onnx.config import EspeakConfig

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "FY_VIDEO_BUILD", os.path.join(HERE, "../../../video-build")))
OUT = os.path.join(BUILD, "dad_v6")
VOICE, SPEED = os.environ.get("FY_DAD_VOICE", "am_michael"), float(os.environ.get("FY_DAD_SPEED", "0.85"))
LEAD, TAIL = 0.6, 1.2

LINES = {
    "dad_fall": "I fell down earlier and I'm scared.",
    "dad_appt": "Do I have any doctor's appointments this week?",
    "dad_lonely": "I feel lonely since my wife died.",
    "dad_crisis": "I want to end my life.",
    "dad_grandson": "I forgot, what is my grandson's name?",   # day 2, the local run (day2_v6.py)
}

ESPEAK = "/usr/lib/aarch64-linux-gnu"
_o = A.EspeakAPI.__init__
A.EspeakAPI.__init__ = lambda self, lib, dp: _o(self, lib, f"{ESPEAK}/espeak-ng-data")


def main():
    os.makedirs(OUT, exist_ok=True)
    k = Kokoro(f"{BUILD}/kokoro/kokoro-v1.0.onnx", f"{BUILD}/kokoro/voices-v1.0.bin",
               espeak_config=EspeakConfig(f"{ESPEAK}/libespeak-ng.so.1", f"{ESPEAK}/espeak-ng-data"))
    meta = {}
    for name, text in LINES.items():
        a, sr = k.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        a = np.concatenate([np.zeros(int(sr * LEAD), np.float32), a.astype(np.float32),
                            np.zeros(int(sr * TAIL), np.float32)])
        raw = os.path.join(OUT, f"_{name}_raw.wav")
        sf.write(raw, a, sr)
        dst = os.path.join(OUT, f"{name}.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", dst], check=True)
        os.remove(raw)
        meta[name] = {"text": text, "file": dst, "voice": VOICE, "speed": SPEED,
                      "speech_s": round(len(a) / sr - LEAD - TAIL, 2), "lead_s": LEAD, "tail_s": TAIL}
        print(name, meta[name]["speech_s"], "s")
    json.dump(meta, open(os.path.join(OUT, "lines.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
