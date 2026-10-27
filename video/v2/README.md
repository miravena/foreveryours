# Demo video v2

The submission video (under 3:00) described shot by shot in
[`docs/VIDEO_SCRIPT.md`](../../docs/VIDEO_SCRIPT.md). Everything on screen is real: shots 1-5
are browser sessions on the live Space, https://elevenbaselab-foreveryours.hf.space (shots 1, 2
and 5 at build `ed85efc`, shots 3-4 at build `f768c65`), recorded by a script that types and
clicks; shot 6 is one local run of
`python main.py beat4` in a fresh process; shots 7-9 are plain text cards. The companion's voice
is the reply audio the Space served in those sessions. The narrator is an AI voice, Kokoro TTS
(kokoro-onnx, Apache-2.0 model and code), voice af_heart; see [`narration/`](narration/README.md)
for how to swap in a human recording.

Nothing built here is committed: clips, WAVs, the MP4 and the SRT live in a build directory
outside the repo, `$FY_VIDEO_BUILD` (default `../video-build` next to the repo checkout).

## Rebuild

From the repo root, in order:

1. **Capture the Space** (Node with Playwright, a Chromium build, ffmpeg):

   ```bash
   export PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs CHROME_PATH=/path/to/chrome
   B=${FY_VIDEO_BUILD:-../video-build}
   node video/v2/capture/capture.mjs $B/capture fall      # shots 1-2
   node video/v2/capture/capture.mjs $B/capture crisis    # shot 5
   for t in 1 2 3; do SHOT_TAG=appt_t$t node video/v2/capture/capture.mjs $B/capture appt; done  # shots 3-4
   ```

   Each `appt` run is a fresh session: the memo "Dad has a check-up with Dr. Tan on Thursday at
   10 AM." is saved, then the senior asks "Do I have any doctor's appointments this week?". A run
   passes when the reply names Dr. Tan, Thursday and 10 AM and no error toast appeared; also read
   each reply for anything not in the briefed memory. The line is used only if all three pass.

2. **Day 2** (local, live key through `scripts/with_key.sh`):
   `KEY_ENV_FILE=.env python video/v2/capture/day2.py $B/capture`

3. **Manifest:** `python3 video/v2/capture/build_manifest.py $B/capture` writes
   `manifest.json` (per-shot clip, key moments in seconds, reply audio and its on-screen start,
   verbatim texts). `APPT_TAKE=appt_tN` picks the shot 3-4 take (default: the last passing run).

4. **Narration:** `video/v2/narration/render.py` (see its README) writes `narration/shotN.wav`
   and `shotN.caption.txt`.

5. **Assemble:** `.venv/bin/python video/v2/assemble.py $B` writes
   `foreveryours_demo_v2.mp4` (1920x1080, 30 fps, H.264 + AAC 48 kHz) and
   `foreveryours_demo_v2.srt`. It trims each clip at the manifest's key moments, lays every
   narrator line and companion reply at its on-screen moment without overlaps, burns in captions
   (narrator, companion verbatim, the senior's lines, and the labels "Dad was told", "Not shown
   to the family", "Day 2 (local run)"), normalises to -16 LUFS with true peak at most -1.5 dBTP,
   and stops if the result would pass 2:58. Caption timing uses faster-whisper word timestamps
   from the repo `.venv`; the day-2 terminal is re-rendered by `video/render_terminal.py`
   (needs pyte; interpreter `$FY_TERM_PYTHON`, default `python3`) without its one timing line.

## Checking a build

Extract a frame at each shot's key moment and look at it (captions legible, nothing cropped, no
error toasts, no timing figures, "Dad was told" readable), and transcribe the final mix with
faster-whisper to confirm every line is intelligible and nobody talks over anybody. The
assembler prints the shot boundaries and writes them, with the audio spans, to
`<build>/_assemble/timeline.json`.
