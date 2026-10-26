"""Shot 6 (day 2): record `python main.py beat4` in a fresh process and render it 1920x1080.

The Space keeps memory for one browser session only, so the day-2 recall is a local run, in a
throwaway copy of the committed app (never the checkout's own data/):
`python main.py beat1` briefs the household first (no key, not recorded), then a NEW
process runs `beat4` ("I forgot, what is my grandson's name?") with the live key, through
scripts/with_key.sh so the key never reaches the terminal or the cast. The recording and
rendering reuse video/record_run.py (asciinema in a pty) and video/render_terminal.py
(pyte + Pillow), so nothing on screen is typed by hand.

Usage (from the repo root):
    KEY_ENV_FILE=/path/to/.env python video/v2/capture/day2.py <out_dir> [<seconds>]
Writes <out_dir>/day2_beat4.cast, <out_dir>/day2.mp4 and <out_dir>/day2.json.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "video"))
# with_key.sh reads KEY_ENV_FILE relative to its cwd, which is the copy below: pin it here.
os.environ["KEY_ENV_FILE"] = os.path.abspath(os.environ.get("KEY_ENV_FILE", os.path.join(ROOT, ".env")))
# Run in a throwaway copy of the committed app (git archive HEAD: no data/, out/ or .env), so the
# recording never reads or writes the checkout's own household data and shows only the demo brief.
APP = tempfile.mkdtemp(prefix="foreveryours-day2-")
subprocess.run(f"git -C {shlex.quote(ROOT)} archive HEAD | tar -x -C {shlex.quote(APP)}", shell=True,
               check=True)
os.environ["FOREVERYOURS_RECORD_APP"] = APP
os.environ.setdefault("FOREVERYOURS_RECORD_PY", os.path.join(ROOT, ".venv", "bin", "python"))
import record_run  # noqa: E402  (reads the two variables above at import time)

QUESTION = "I forgot, what is my grandson's name?"


def main():
    out_dir = os.path.abspath(sys.argv[1])
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    os.makedirs(out_dir, exist_ok=True)
    py = record_run.PY
    # Day 1: the caregiver brief, written to data/ (gitignored). Not part of the shot.
    subprocess.run([py, "main.py", "beat1", "--no-play"], cwd=APP, check=True,
                   stdout=subprocess.DEVNULL)
    # Day 2: a fresh process. Library noise on stderr is dropped (it carries local paths);
    # with_key.sh's own "live key in use" banner goes to its stderr and is dropped too.
    inner = f"{shlex.quote(py)} main.py beat4 --no-play 2>/dev/null"
    real = f"{shlex.quote(os.path.join(ROOT, 'scripts', 'with_key.sh'))} bash -c {shlex.quote(inner)} 2>/dev/null"
    record_run.CASTS = out_dir
    cast = record_run._record("day2_beat4", "python main.py beat4", real)
    mp4 = os.path.join(out_dir, "day2.mp4")
    subprocess.run([sys.executable, os.path.join(ROOT, "video", "render_terminal.py"), cast, mp4,
                    str(seconds)], check=True)
    text = ""
    with open(cast) as fh:
        for ln in fh.read().splitlines()[1:]:
            if ln.strip():
                text += json.loads(ln)[2]
    with open(os.path.join(out_dir, "day2.json"), "w") as fh:
        json.dump({"shot": "day2", "clip": mp4, "cast": cast, "duration": seconds,
                   "senior_text": QUESTION, "terminal_output": text}, fh, indent=2)
    shutil.rmtree(APP, ignore_errors=True)
    print(text)


if __name__ == "__main__":
    main()
