#!/usr/bin/env python3
"""Check the v6 demo video as UPLOADED (#304): download the release assets into a fresh empty
directory and test them against video/v6/timeline.json.

Fails (exit 1) when:
  - an asset cannot be downloaded or the MP4 does not decode cleanly;
  - the video is 2:50 or longer, or the SRT is not UTF-8 or has a curly quote;
  - silencedetect (-40 dB, 1.5 s) finds a silence that is not inside a recorded companion pause;
  - a Dad turn in timeline.json has no spoken source WAV, or no "Dad:" / "Dad said" SRT cue
    with the words that were heard;
  - the privacy label does not end before the crisis line's cue starts.
It also prints loudness, every label cue, and (with --frames) extracts a frame inside each label.
--transcribe runs faster-whisper on the downloaded mix and prints the transcript.

Usage (from the repo root):
    .venv/bin/python video/v6/check_v6.py --release video-v6-draft [--frames] [--transcribe]
    .venv/bin/python video/v6/check_v6.py --local <dir with the mp4 and srt>   # before upload
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "miravena/foreveryours"
MP4, SRT = "foreveryours_demo_v6.mp4", "foreveryours_demo_v6.srt"
MAX_S = 170.0
CURLY = "\u2018\u2019\u201c\u201d"
failures = []


def fail(msg):
    failures.append(msg)
    print("FAIL", msg)


def ok(msg):
    print("ok  ", msg)


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("\u2019", "'").replace("'", "")).split()


def secs(ts):
    h, m, s = ts.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_srt(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.splitlines()
        if len(lines) >= 3 and "-->" in lines[1]:
            a, b = (secs(x.strip()) for x in lines[1].split("-->"))
            cues.append((a, b, " ".join(lines[2:])))
    return cues


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--release", help="release tag, e.g. video-v6-draft")
    src.add_argument("--local", help="a directory already holding the two files")
    ap.add_argument("--timeline", default=os.path.join(HERE, "timeline.json"))
    ap.add_argument("--frames", action="store_true", help="extract a frame inside each label")
    ap.add_argument("--transcribe", action="store_true", help="faster-whisper transcript of the mix")
    args = ap.parse_args()
    tl = json.load(open(args.timeline))

    if args.release:
        d = tempfile.mkdtemp(prefix="fy-v6-check-")
        assert not os.listdir(d)
        r = subprocess.run(["gh", "release", "download", args.release, "-R", REPO, "-D", d, "-p", MP4, "-p", SRT],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"FAIL download: {r.stderr.strip()}")
    else:
        d = args.local
    print("files in", d)
    mp4, srt = os.path.join(d, MP4), os.path.join(d, SRT)
    for p in (mp4, srt):
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            sys.exit(f"FAIL missing or empty: {p}")

    # decode the whole file; any decoder message fails it
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-"], capture_output=True, text=True)
    if r.returncode != 0 or r.stderr.strip():
        fail(f"decode: {r.stderr.strip()[:300]}")
    else:
        ok("decodes with no errors")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                               capture_output=True, text=True).stdout)
    (ok if dur < MAX_S else fail)(f"duration {dur:.2f}s ({int(dur // 60)}:{dur % 60:05.2f}), limit 2:50")

    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    (ok if abs(lufs + 16) <= 1.0 else fail)(f"loudness {lufs} LUFS (target -16), true peak {peak} dBTP")

    raw = open(srt, "rb").read()
    try:
        text = raw.decode("utf-8")
        ok("SRT is UTF-8")
    except UnicodeDecodeError as e:
        fail(f"SRT is not UTF-8: {e}")
        text = raw.decode("utf-8", "replace")
    bad = sorted({c for c in text if c in CURLY})
    (fail if bad else ok)(f"curly quotes in SRT: {[hex(ord(c)) for c in bad] or 'none'}")
    cues = parse_srt(text)

    # silences: each must lie inside a recorded companion pause
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "silencedetect=noise=-40dB:d=1.5",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)] + [dur]
    pauses = tl["companion_pauses"]
    print(f"     silencedetect -40 dB d=1.5: {len(starts)} interval(s); {len(pauses)} companion pause(s) recorded")
    for a, b in zip(starts, ends):
        inside = any(pa - 0.1 <= a and b <= pb + 0.1 for pa, pb in pauses)
        (ok if inside else fail)(f"silence {a:.2f}-{b:.2f}s ({b - a:.2f}s) {'inside' if inside else 'OUTSIDE'} a companion pause")
    if not starts:
        ok("no silence of 1.5 s or more anywhere")

    # Dad turns: a spoken source and a matching cue
    dad_cues = [c for c in cues if re.match(r"\s*(Dad:|Dad said)", c[2])]
    for t in tl["dad_turns"]:
        if not t.get("source_wav", "").endswith(".wav"):
            fail(f"Dad turn {t.get('heard')!r} has no spoken source")
            continue
        words = norm(t["heard"])
        hit = next((c for c in dad_cues if norm(re.sub(r"^\s*(Dad:|Dad said:?)", "", c[2])) == words), None)
        (ok if hit else fail)(f"Dad turn {t['heard']!r} <- {t['source_wav']} ({t['input']}); cue "
                              + (f"{hit[0]:.2f}-{hit[1]:.2f}s" if hit else "MISSING"))

    # labels
    for a, b, t in cues:
        if t.startswith("["):
            print(f"     label {a:7.2f}-{b:7.2f}s  {t}")
    priv = [c for c in cues if "Not shown to the family" in c[2]]
    crisis_line = [c for c in dad_cues if "end my life" in c[2]]
    crisis_lbl = [c for c in cues if c[2].startswith("[Crisis")]
    if priv and crisis_line and crisis_lbl:
        (ok if priv[0][1] < crisis_line[0][0] else fail)(
            f"privacy label ends {priv[0][1]:.2f}s, crisis line starts {crisis_line[0][0]:.2f}s, crisis label {crisis_lbl[0][0]:.2f}s")
    else:
        fail("privacy label, crisis line or crisis label cue missing")
    live = [b - a for a, b, t in cues if "LIVE HOSTED SPACE" in t]
    (ok if live and max(live) <= 6.0 else fail)(f"{len(live)} LIVE HOSTED SPACE cue(s), longest {max(live or [0]):.1f}s")
    (ok if any("Local persistence test" in t for _, _, t in cues) else fail)("local persistence cue present")
    (ok if any("type" in t.lower() and "prefer" in t.lower() for _, _, t in cues) else fail)("typing-also-works line present")

    if args.frames:
        fdir = os.path.join(d, "frames")
        os.makedirs(fdir, exist_ok=True)
        for i, (a, b, t) in enumerate(c for c in cues if c[2].startswith("[")):
            png = os.path.join(fdir, f"label_{i:02d}_{(a + b) / 2:06.2f}s.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{(a + b) / 2:.2f}", "-i", mp4,
                            "-frames:v", "1", png], check=True)
        print("     frames in", fdir)

    if args.transcribe:
        from faster_whisper import WhisperModel
        segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(mp4, beam_size=5, language="en")
        for s in segs:
            print(f"     [{s.start:6.1f}-{s.end:6.1f}] {s.text.strip()}")

    print(f"\n{'FAILED: ' + str(len(failures)) + ' check(s)' if failures else 'ALL CHECKS PASSED'}  ({d})")
    if args.release and not failures and not args.frames:
        shutil.rmtree(d)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
