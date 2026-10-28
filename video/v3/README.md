# Demo video v3

The v2 footage recut for judge clarity (#264), described shot by shot in
[`docs/VIDEO_SCRIPT.md`](../../docs/VIDEO_SCRIPT.md). Nothing is re-captured: shots 1-5 are the
v2 browser sessions on the live Space and shot 6 the v2 local day-2 run (see
[`../v2/README.md`](../v2/README.md) for how they were captured). What changes is the edit:

- the fall clip starts with the line already typed, so the caregiver flag and the single
  "Dad was told" label are on screen at 0:04; the assembler stops if the flag would appear
  later than 0:05;
- the fall and crisis replies are cut at the end of their disclosure sentence ("I'm letting
  your family know right now..." / "I am also letting your family know you are in distress.");
- LIVE HOSTED SPACE on every Space shot, LOCAL PERSISTENCE TEST on the day-2 terminal;
- shorter narration and two closing cards; hard stop at 2:50.

Build outputs stay outside git in `$FY_VIDEO_BUILD` (default `../video-build`):
`foreveryours_demo_v3.mp4`, `foreveryours_demo_v3.srt`, work files in `_assemble_v3/`.

## Rebuild

From the repo root, with the v2 captures and `capture/manifest.json` already in the build dir:

1. **Narration** (Kokoro venv, see [`../v2/narration/README.md`](../v2/narration/README.md)):

   ```bash
   cd video/v2/narration && FY_NARR_DIR=narration_v3 FY_LINES_JSON=../../v3/lines.json \
     <kokoro-venv>/bin/python render.py render
   ```

2. **Assemble:** `.venv/bin/python video/v3/assemble.py [<build_dir>]`. It prints the shot
   boundaries and the flag time, and writes them with the audio spans and labels to
   `_assemble_v3/timeline.json`. Captions (ASS burned in, SRT sidecar) come from the same
   timeline, so the SRT always matches the cut.

## Checking a build

As for v2: `ffprobe` the duration, extract a frame at 0:00, at the flag and at each label, and
transcribe `_assemble_v3/mix.wav` with faster-whisper to confirm every line is intelligible and
nobody talks over anybody.
