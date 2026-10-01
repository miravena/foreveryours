"""One-command rebuild of the ForeverYours demo video.

Ported from competitions/agents-for-humans/video/run_pipeline.py. Runs, in order:

  1. generate_audio.py   gTTS narration, one MP3 per beat
  2. generate_slides.py  Pillow 1920x1080 slides for the non-terminal beats
  3. record_run.py       REAL asciinema recording of `python main.py <beat>`
                         against an isolated copy of app/ (never the live
                         webapp.py session) -- see record_run.py's docstring
  4. render_terminal.py  replay each recorded cast to a 1920x1080 mp4
  5. assemble.py         concat slides + terminal beats + narration; ffprobe-check

Output: output/foreveryours_poc_demo.mp4 (1920x1080, <= 5:00).

record_run.py never fakes a terminal: if a live run fails, it exits non-zero
and this pipeline stops.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
OUT = os.path.join(HERE, "output")

TERMINAL_BEATS = [
    ("live_beat1", "beat1"),
    ("live_beat3", "beat3"),
    ("live_day2", "day2"),
]


def run(script, *args):
    print(f"\n=== {script} {' '.join(args)} ===")
    subprocess.run([PY, os.path.join(HERE, script), *args], check=True)


def probe_duration(path):
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", path]).decode().strip())


def main():
    run("generate_audio.py")
    run("generate_slides.py")
    run("record_run.py")

    term_dir = os.path.join(OUT, "terminal")
    os.makedirs(term_dir, exist_ok=True)
    for cast_name, audio_key in TERMINAL_BEATS:
        cast = os.path.join(HERE, "casts", f"{cast_name}.cast")
        mp4 = os.path.join(term_dir, f"{cast_name}.mp4")
        dur = probe_duration(os.path.join(OUT, f"beat_{audio_key}.mp3"))
        run("render_terminal.py", cast, mp4, f"{dur:.3f}")

    run("assemble.py")
    print("\nPipeline complete: output/foreveryours_poc_demo.mp4")


if __name__ == "__main__":
    main()
