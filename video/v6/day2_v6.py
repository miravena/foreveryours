"""Shot 6 (day 2) for v6: the local persistence test with Dad SPEAKING.

As video/v2/capture/day2.py, in a throwaway copy of the committed app (git archive HEAD: no
data/, out/ or .env): `main.py beat1` briefs the household (no key), then a NEW process runs
`main.py beat4 --audio <build>/dad_v6/dad_grandson.wav`, so the app's own local speech
recognition hears Dad's question. The live key goes only to that command, through
scripts/with_key.sh. v6 shows a card, not the terminal, so nothing is recorded on screen; the
run's output and the reply audio the app synthesised are kept for the card's captions and sound.

Usage (from the repo root):  KEY_ENV_FILE=.env .venv/bin/python video/v6/day2_v6.py [<build_dir>]
Writes <build>/capture_v6/day2.json and day2_reply.wav.
"""
import glob
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUILD = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "video-build"))
OUT = os.path.join(BUILD, "capture_v6")
WAV = os.path.join(BUILD, "dad_v6", "dad_grandson.wav")
PY = os.path.join(ROOT, ".venv", "bin", "python")


def main():
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ, KEY_ENV_FILE=os.path.abspath(os.environ.get("KEY_ENV_FILE", os.path.join(ROOT, ".env"))))
    app = tempfile.mkdtemp(prefix="foreveryours-day2-v6-")
    subprocess.run(f"git -C {shlex.quote(ROOT)} archive HEAD | tar -x -C {shlex.quote(app)}", shell=True, check=True)
    subprocess.run([PY, "main.py", "beat1", "--no-play"], cwd=app, check=True, stdout=subprocess.DEVNULL)
    res = subprocess.run([os.path.join(ROOT, "scripts", "with_key.sh"), PY, "main.py", "beat4", "--audio", WAV,
                          "--no-play"], cwd=app, env=env, capture_output=True, text=True, check=True)
    out = res.stdout
    said = re.search(r'Senior said: "(.*)"', out)
    reply = re.search(r'Companion replied: "(.*)"', out)
    chunks = re.search(r"Audio chunks: \[(.*)\]", out)
    if not (said and reply and chunks):
        sys.exit("beat4 output lacks the heard line, the reply or its audio:\n" + out)
    names = re.findall(r"'([^']+\.wav)'", chunks.group(1))
    files = [next(iter(glob.glob(os.path.join(app, "out", "**", n), recursive=True)), None) for n in names]
    if not names or None in files:
        sys.exit(f"reply audio not found: {names}")
    dst = os.path.join(OUT, "day2_reply.wav")
    # Decode and join (the concat filter); the byte-level concat: protocol would stop after the
    # first WAV's header length.
    ins = [x for f in files for x in ("-i", f)]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex",
                    "".join(f"[{i}:a]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1", dst],
                   check=True)
    json.dump({"shot": "day2", "local_run": "main.py beat4 --audio dad_grandson.wav (fresh process)",
               "source_wav": WAV, "heard": said.group(1), "companion_reply": reply.group(1),
               "reply_audio": dst, "live_key_banner": "LIVE Nebius key in use" in (res.stderr + out),
               "stdout": out}, open(os.path.join(OUT, "day2.json"), "w"), indent=1)
    print("heard:", said.group(1)); print("reply:", reply.group(1))


if __name__ == "__main__":
    main()
