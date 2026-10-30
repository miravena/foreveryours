#!/usr/bin/env python3
"""Render the v6 narrator lines (video/v6/lines.json) in the v4/v5 narrator voice.

Same voice and settings as v5: Kokoro af_heart, speed 0.9, 0.4 s between sentences, loudnorm
to -16 LUFS, 48 kHz mono, and the same respellings as video/v2/narration/render.py (which runs
on import, so its settings are repeated here). Lines whose "reuse" names a v5 file are copied,
not re-rendered.

    <kokoro-venv>/bin/python video/v6/narration.py [<build_dir>] [slot,...]
Writes <build>/narration_v6/<slot>.wav and <slot>.caption.txt.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf
import phonemizer.backend.espeak.api as A
from kokoro_onnx import Kokoro
from kokoro_onnx.config import EspeakConfig

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "../../../video-build"))
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 else []
OUT = os.path.join(BUILD, "narration_v6")
VOICE, SPEED, GAP = "af_heart", 0.9, 0.4
RESPELL = [
    (r"\b988\b", "nine eight eight"),
    (r"\bDr\. ", "Doctor "),
    (r"Nemotron 3 ", "Nemo-tron three "),
    (r"\bNemotron\b", "Nemo-tron"),
]
ESPEAK = "/usr/lib/aarch64-linux-gnu"
_o = A.EspeakAPI.__init__
A.EspeakAPI.__init__ = lambda self, lib, dp: _o(self, lib, f"{ESPEAK}/espeak-ng-data")


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = json.load(open(os.path.join(HERE, "lines.json")))
    k = None
    for slot, ln in lines.items():
        if ONLY and slot not in ONLY:
            continue
        wav = os.path.join(OUT, f"{slot}.wav")
        if ln.get("reuse"):
            shutil.copy(os.path.join(BUILD, ln["reuse"]), wav)
        else:
            if k is None:
                k = Kokoro(f"{BUILD}/kokoro/kokoro-v1.0.onnx", f"{BUILD}/kokoro/voices-v1.0.bin",
                           espeak_config=EspeakConfig(f"{ESPEAK}/libespeak-ng.so.1", f"{ESPEAK}/espeak-ng-data"))
            spoken = ln["text"]
            for a, b in RESPELL:
                spoken = re.sub(a, b, spoken)
            parts = []
            for s in re.split(r"(?<=[.?!])\s+", spoken):
                if s.strip():
                    a, sr = k.create(s, voice=VOICE, speed=SPEED, lang="en-us")
                    parts += [a.astype(np.float32), np.zeros(int(sr * GAP), np.float32)]
            raw = wav + ".raw.wav"
            sf.write(raw, np.concatenate(parts[:-1]), sr)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                            "-ar", "48000", "-ac", "1", wav], check=True)
            os.remove(raw)
        open(os.path.join(OUT, f"{slot}.caption.txt"), "w").write(ln["text"])
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                                 capture_output=True, text=True).stdout)
        print(f"{slot}: {d:.2f}s  {ln['text']}")


if __name__ == "__main__":
    main()
