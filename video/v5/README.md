# Demo video v5

The v4 cut ([`../v4/README.md`](../v4/README.md)) with the caption and label problems from #275
fixed. Same footage, shot order, narrator voice (Kokoro `af_heart`, speed 0.9, 0.4 s gap) and
timing as v4; shots 2-7 use v4's narration files unchanged. What v5 changes:

- **Straight quotes only.** The Space's replies carry U+2019; a player that reads the SRT as
  cp1252 shows it as mojibake. `assemble.py` straightens U+2018/2019/201C/201D in every caption
  and stops if any survive in the SRT or the burned-in ASS.
- **LIVE HOSTED SPACE is a corner badge** (burned in, shots 1-5) plus one 4 s SRT cue at the
  start of each hosted shot. v4 had one cue for 0:00-1:43.
- **Privacy vs crisis.** "Not shown to the family" ends when the freeze before the crisis line
  starts (1:24.2); "Dad: I want to end my life." starts at 1:25.4. A separate red label, "Crisis:
  988 offered, simulated family alert", runs from the frame the crisis flag appears to the end of
  the shot. It says "simulated" because the panel does.
- **Day 2 is a clean card** reading "Local persistence test - not the hosted Space." (v4 showed
  the terminal); the SRT carries the same text. The question and answer are captions, as before.
- **Closing line:** "This is a prototype: it can miss nuance, so it does not replace human
  judgment or emergency services. Try it yourself, no login, at the link on screen." Only that
  file was re-rendered; the card still points at the README's "Known limitations".

Build outputs stay outside git in `$FY_VIDEO_BUILD` (default `../video-build`):
`foreveryours_demo_v5.mp4`, `.srt`, work files in `_assemble_v5/`.

## Rebuild

1. Copy `narration_v4/` to `narration_v5/` in the build dir, then re-render the closing line only
   (needs the Kokoro venv, see [`../v2/narration/README.md`](../v2/narration/README.md)):

   ```bash
   cd video/v2/narration && FY_NARR_DIR=narration_v5 FY_LINES_JSON=../../v5/lines.json \
     FY_NARR_ONLY=8 FY_NARR_GAP=0.4 FY_NARR_SPEEDS='{"8":0.9}' <kokoro-venv>/bin/python render.py render
   ```

   `FY_NARR_ONLY` takes a comma-separated list of shots; the other entries of `lines.json` are kept.

2. `.venv/bin/python video/v5/assemble.py [<build_dir>]`. The first run aligns every WAV with
   faster-whisper (about 9 minutes on a 2-core ARM box) and caches the result in
   `_assemble_v5/align.json`; delete that file after re-rendering narration.

## Checking a build

As for v4, plus: grep the SRT for U+2018/2019/201C/201D, list the `[LIVE HOSTED SPACE]` cue
lengths (none over 6 s), compare the end of `[Not shown to the family]` with the start of
`Dad: I want to end my life.`, and extract a frame inside the day-2 card.
