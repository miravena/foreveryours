# ForeverYours demo video — build pipeline

Auto-generated, not personally recorded: narration via gTTS, slides via
Pillow, and the three terminal beats are **real recordings** of
`python main.py beat1 / beat3 / day2` — captured with asciinema, replayed
through a VT100 emulator (pyte), and rasterized frame-by-frame. Nothing on
screen is typed by hand or faked; if a live run fails, the recording step
exits non-zero and writes no cast (see `record_run.py`'s docstring).

This exists so the team has something to actually watch before anyone
personally records anything -- a concrete proof-of-concept, not a promise.

## Why these three beats, and not the full conversation

`beat1` (caregiver memo), `beat3` (fast-path safety disclosure), and `day2`
(cross-process memory persistence) all run with **zero Nebius API key** —
the fast path and memory layer are pure Python, no network call. The full
THINK conversation (the open-weight NVIDIA model via Nebius Token Factory)
is the one piece nobody has a live key for yet, so it's honestly described
as "what's next" in the closing slide rather than faked.

## Rebuild it

```bash
cd competitions/nebius-foreveryours/video
python3 generate_audio.py
python3 generate_slides.py

# IMPORTANT: point this at an ISOLATED copy of app/, never the real one --
# record_run.py resets data/ and out/, which would clobber a live webapp.py
# session's state. See record_run.py's docstring.
FOREVERYOURS_RECORD_APP=/path/to/an/isolated/copy/of/app python3 record_run.py

mkdir -p output/terminal
for pair in live_beat1:beat1 live_beat3:beat3 live_day2:day2; do
  cast="${pair%%:*}"; key="${pair##*:}"
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "output/beat_${key}.mp3")
  python3 render_terminal.py "casts/${cast}.cast" "output/terminal/${cast}.mp4" "$dur"
done

python3 assemble.py
```

Output: `output/foreveryours_poc_demo.mp4` (1920x1080, under 5:00).

## What's committed vs. regenerated

- Committed: the scripts, the recorded `.cast` files (the actual proof —
  these are what's real), this README, and the final MP4 itself (so the
  teammate can watch it without rebuilding anything).
- Gitignored / regenerable: everything else under `output/` — narration
  MP3s, slide PNGs, per-beat terminal MP4s and their frame dumps. All of it
  rebuilds deterministically from the casts via the commands above.
