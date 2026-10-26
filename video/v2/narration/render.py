#!/usr/bin/env python3
"""Render narrator lines from docs/VIDEO_SCRIPT.md with Kokoro TTS (Apache-2.0) on CPU.

Run with a venv holding kokoro-onnx, soundfile and numpy:
    <venv>/bin/python render.py [candidates|render|all]
Needs system libespeak-ng + espeak-ng-data (aarch64 paths below; adjust for x86_64).
Model files and outputs live outside git in the build directory ($FY_VIDEO_BUILD, default
../video-build next to the repo checkout): kokoro/ (model) and narration/ (WAVs, captions).
"""
import json, os, re, subprocess, sys
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from kokoro_onnx.config import EspeakConfig
import phonemizer.backend.espeak.api as A

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.environ.get("FY_VIDEO_BUILD", os.path.join(HERE, "../../../../video-build")))
OUT = f"{BUILD}/narration"
SCRIPT = os.path.join(HERE, "../../../docs/VIDEO_SCRIPT.md")
VOICE, SPEED = "af_heart", 0.95   # chosen voice (see README.md)
CANDIDATES = ["af_heart", "am_michael", "bf_emma"]

# Phonetic respelling applied to the render input ONLY; captions stay verbatim.
RESPELL = [
    (r"elevenbaselab-foreveryours\.hf\.space", "eleven base lab, for ever yours, dot H F, dot space"),
    (r"faster-whisper", "faster whisper"),
    (r"\b988\b", "nine eight eight"),
    (r"Nemotron 3 ", "Nemo-tron three "),  # "3 Nano" was heard as "3.0"
    (r"Nebius", "Nebius"), (r"Nemotron", "Nemotron"), (r"Piper", "Piper"),
]
GAP = 0.25  # seconds between sentences

_o = A.EspeakAPI.__init__
A.EspeakAPI.__init__ = lambda self, lib, dp: _o(self, lib, "/usr/lib/aarch64-linux-gnu/espeak-ng-data")
K = Kokoro(f"{BUILD}/kokoro/kokoro-v1.0.onnx", f"{BUILD}/kokoro/voices-v1.0.bin",
           espeak_config=EspeakConfig("/usr/lib/aarch64-linux-gnu/libespeak-ng.so.1",
                                      "/usr/lib/aarch64-linux-gnu/espeak-ng-data"))

def parse():
    """Shot table rows -> {shot: (start, end, window_s, text)}; shot 1 is silent."""
    shots = {}
    for row in re.findall(r"^\| (\d+:\d+)-(\d+:\d+) \|.*\| \"(.*)\" \|$", open(SCRIPT).read(), re.M):
        pass
    rows = [l for l in open(SCRIPT).read().splitlines() if re.match(r"\| \d+:\d+-\d+:\d+ \|", l)]
    for i, l in enumerate(rows[:9], 1):
        t0, t1 = re.match(r"\| (\d+:\d+)-(\d+:\d+)", l).groups()
        sec = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1])
        cell = l.rsplit("|", 2)[1].strip()
        if cell.startswith("(silent"): continue
        shots[i] = dict(window=sec(t1) - sec(t0), window_label=f"{t0}-{t1}", text=cell.strip('"'))
    return shots

def spoken(text):
    for a, b in RESPELL: text = re.sub(a, b, text)
    return text

def synth(text, voice, speed=SPEED):
    parts = []
    for s in re.split(r"(?<=[.?!])\s+", spoken(text)):
        if s.strip():
            a, _ = K.create(s, voice=voice, speed=speed, lang="en-us")
            parts += [a.astype(np.float32), np.zeros(int(24000 * GAP), np.float32)]
    return np.concatenate(parts[:-1])

def norm(raw, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1", dst], check=True)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    shots = parse(); os.makedirs(f"{OUT}/candidates", exist_ok=True)
    if mode in ("candidates", "all"):
        for v in CANDIDATES:
            raw = f"/tmp/cand_{v}.wav"
            sf.write(raw, synth(shots[2]["text"], v), 24000)
            norm(raw, f"{OUT}/candidates/shot2_{v}.wav")
    if mode in ("render", "all"):
        meta = {}
        for n, s in shots.items():
            raw = f"/tmp/shot{n}_raw.wav"; dst = f"{OUT}/shot{n}.wav"
            sf.write(raw, synth(s["text"], VOICE), 24000); norm(raw, dst)
            d = sf.info(dst).duration
            meta[str(n)] = dict(text=s["text"], spoken_text=spoken(s["text"]), file=os.path.relpath(dst, BUILD),
                                duration_s=round(d, 2), window_s=s["window"],
                                window=s["window_label"], fits=d <= s["window"], voice=VOICE, speed=SPEED)
            open(f"{OUT}/shot{n}.caption.txt", "w").write(s["text"] + "\n")
        json.dump(meta, open(os.path.join(HERE, "lines.json"), "w"), indent=2)
        for n, m in meta.items(): print(n, m["duration_s"], "/", m["window_s"], "OK" if m["fits"] else "OVER")

main()
