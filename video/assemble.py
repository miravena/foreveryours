"""Assemble the final ForeverYours demo MP4 from the per-beat assets.

Ported approach from competitions/agents-for-humans/video/assemble.py (same
ffmpeg slide->video / overlay-audio / concat, plus an ffprobe check).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
SLIDES = os.path.join(OUT, "slides")
TERM = os.path.join(OUT, "terminal")
WORK = os.path.join(OUT, "_beats")
FINAL = os.path.join(OUT, "foreveryours_poc_demo.mp4")

TAIL = 0.6
MAX_SECONDS = 300.0

BEATS = [
    ("problem",  "slide", os.path.join(SLIDES, "slide_problem.png")),
    ("pipeline", "slide", os.path.join(SLIDES, "slide_pipeline.png")),
    ("beat1",    "term",  os.path.join(TERM, "live_beat1.mp4")),
    ("beat3",    "term",  os.path.join(TERM, "live_beat3.mp4")),
    ("day2",     "term",  os.path.join(TERM, "live_day2.mp4")),
    ("close",    "slide", os.path.join(SLIDES, "slide_close.png")),
]


def probe_duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", path]).decode().strip()
    return float(out)


def probe_stream(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", path]).decode()
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def build_beat(key, kind, asset, seg_dur):
    out = os.path.join(WORK, f"beat_{key}.mp4")
    audio = os.path.join(OUT, f"beat_{key}.mp3")
    common_v = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p")
    if kind == "slide":
        vin = ["-loop", "1", "-i", asset]
        vf = common_v
    else:
        vin = ["-i", asset]
        vf = f"tpad=stop_mode=clone:stop_duration={TAIL + 2},{common_v}"
    cmd = [
        "ffmpeg", "-y", *vin, "-i", audio,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]apad[a]",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{seg_dur:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k",
        out,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def main():
    os.makedirs(WORK, exist_ok=True)
    beat_files = []
    total = 0.0
    for key, kind, asset in BEATS:
        if not os.path.exists(asset):
            sys.exit(f"missing asset for beat '{key}': {asset}")
        audio_dur = probe_duration(os.path.join(OUT, f"beat_{key}.mp3"))
        seg = audio_dur + TAIL
        print(f"  beat {key:10s} audio={audio_dur:6.2f}s -> segment {seg:6.2f}s")
        beat_files.append(build_beat(key, kind, asset, seg))
        total += seg
    print(f"  sum of segments: {total:.2f}s")

    listfile = os.path.join(WORK, "concat.txt")
    with open(listfile, "w") as fh:
        for bf in beat_files:
            fh.write(f"file '{bf}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
        "-c", "copy", FINAL,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    dur = probe_duration(FINAL)
    w, h = probe_stream(FINAL)
    mm, ss = divmod(dur, 60)
    print(f"\nFINAL: {FINAL}")
    print(f"  resolution : {w}x{h}")
    print(f"  duration   : {dur:.2f}s  ({int(mm)}:{ss:05.2f})")
    ok_res = (w, h) == (1920, 1080)
    ok_dur = dur <= MAX_SECONDS
    print(f"  1920x1080  : {'OK' if ok_res else 'FAIL'}")
    print(f"  <= 5:00    : {'OK' if ok_dur else 'FAIL'}")
    if not (ok_res and ok_dur):
        sys.exit("final video failed checks")


if __name__ == "__main__":
    main()
