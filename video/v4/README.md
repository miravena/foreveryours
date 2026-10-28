# Demo video v4

The v3 cut (#264) with the narration rewritten and re-timed, described shot by shot in
[`docs/VIDEO_SCRIPT.md`](../../docs/VIDEO_SCRIPT.md). The footage is unchanged from v3: shots
1, 2 and 5 are the v2 browser sessions on the live Space, shots 3-4 the #261 re-capture, shot 6
the v2 local day-2 run. See [`../v2/README.md`](../v2/README.md) for how clips are captured and
[`../v3/README.md`](../v3/README.md) for the v3 edit rules, which still apply. What v4 changes:

- **No silent hosted waits.** v3 had 56 s of silence in 145 s: 12 s while the memo was typed,
  14 s on "Companion is thinking...", 6 s on the day-2 terminal after the Leo line. The narrator
  now speaks over the memo (shot 3) and over the real nine-second hosted wait (shot 4), naming the
  model and the wait rather than hiding it with a jump cut.
- **Natural narration speed.** One Kokoro speed, 0.9, with a 0.4 s gap between sentences, for
  every line (v3 slowed four lines to 0.76-0.83 to hit a words-per-minute target, which drags).
  Lines were shortened instead.
- **Shot 5 narration split**: "What he says in private stays private." plays before the private
  line is sent; "Danger is different." on the freeze before the crisis line.
- **Day-2 terminal ends at 7.6 s**, three seconds after the Leo line and before the local run's
  audit line (the #5 rules keep AUDIT out of the day-2 beat).
- **Captions never break after "Dr."** (v3 read "...check-up with Dr." / "Tan on Thursday...").
- **The last card names the product**: "ForeverYours", the tagline, the URL, and the
  limitations line. v3 never showed the name except inside the URL.

Build outputs stay outside git in `$FY_VIDEO_BUILD` (default `../video-build`):
`foreveryours_demo_v4.mp4`, `foreveryours_demo_v4.srt`, work files in `_assemble_v4/`.

## Rebuild

From the repo root, with the v2/v3 captures and `capture/manifest.json` already in the build dir:

1. **Narration** (a venv with kokoro-onnx, soundfile and numpy; the model files in
   `<build>/kokoro/`, see [`../v2/narration/README.md`](../v2/narration/README.md)):

   ```bash
   cd video/v2/narration && FY_NARR_DIR=narration_v4 FY_LINES_JSON=../../v4/lines.json \
     FY_NARR_GAP=0.4 FY_NARR_SPEEDS='{"2":0.9,"3":0.9,"4":0.9,"5":0.9,"6":0.9,"7":0.9,"8":0.9}' \
     <kokoro-venv>/bin/python render.py render
   ```

   `render.py candidates` with `FY_NARR_CANDIDATES=af_heart,am_michael,...` renders the shot 2
   line in several Kokoro voices into `narration_v4/candidates/` for choosing by ear.

2. **Assemble:** `.venv/bin/python video/v4/assemble.py [<build_dir>]`. It prints the shot
   boundaries and the flag time, and writes them with the audio spans and labels to
   `_assemble_v4/timeline.json`. Captions (ASS burned in, SRT sidecar) come from the same
   timeline, so the SRT always matches the cut.

## Human narrator

Record each line as `narration_v4/shotN.wav` (any sample rate; loudness is matched per file) and
keep `shotN.caption.txt` as the words actually said, then re-run step 2 after deleting
`_assemble_v4/align.json`. Shot 5 must stay two sentences (the assembler splits the file at the
end of the first). The assembler stops if a line would overlap the companion's voice.

## Checking a build

As for v3: `ffprobe` the duration, extract a frame at 0:00, at the flag and at each label, and
transcribe `_assemble_v4/mix.wav` with faster-whisper to confirm every line is intelligible and
nobody talks over anybody. `ffmpeg -af silencedetect=noise=-40dB:d=1.5` lists the remaining
silent stretches; none should be longer than a companion pause.

Word timings are cached by WAV path in `_assemble_v4/align.json`; delete that file after
re-rendering narration or re-capturing a clip, or the captions keep the old timings.
