# Demo video v6

The v5 cut ([`../v5/README.md`](../v5/README.md)) with Dad **speaking** (#304). All hosted
footage is new: shots 1-5 were re-captured on the live Space, https://elevenbaselab-foreveryours.hf.space,
on 2026-10-30 (after the #198 deploy), and every senior line is spoken input, not typed.

- **Dad speaks.** `capture_v6.mjs` (the v2 capture script plus a microphone) clicks Record, the
  browser microphone plays one of Dad's WAVs, then it clicks Stop and Send; the Space's own speech
  recognition writes the "Dad said" line on screen. Chromium's file-fed fake microphone restarts its
  file on every recording, so one file cannot carry the two lines of the crisis shot; an init script
  answers the recorder's `getUserMedia` with a stream playing the next queued WAV instead. The
  Space gets an ordinary microphone recording either way. The device dropdown, which reads "Fake
  Default Audio Input", is hidden in the recording.
- **Dad's voice.** `dad_voice.py` renders his five lines with Kokoro `am_michael` (speed 0.85), one
  male voice for all of them. The committed `samples/*.wav` came from the Windows speech
  synthesizer, which does not run on the build box, so the sample-clip buttons are not used: they
  would give Dad two voices. Every Dad line was heard verbatim by the Space (and by the local run on day 2).
- **Day 2 hears him too.** `day2_v6.py` runs `main.py beat4 --audio dad_v6/dad_grandson.wav` in a
  fresh local process (live key through `scripts/with_key.sh`). The shot is still the clean card;
  its sound is his question and the start of the reply the app synthesised ("Leo, that's his name.").
- **No dead air.** The narrator speaks over every hearing and model wait. Every wait from Send to
  the reply is uncut. Two jump cuts remove only idle time from the capture script: the memo hold
  and scroll between shots 3 and 4, and the pause before the crisis line. `assemble.py` stops if the
  mix has a silence of 1.5 s or more at -40 dB outside the companion's own pauses. There are none.
- **Typing too.** The narrator says "He can also type, if he prefers." over the fall shot's wait,
  with the Type box on screen.
- Kept from v5 (#275): straight quotes only, the corner badge plus a 4 s cue per hosted shot, the
  privacy label ending before the crisis line plus the red crisis label, the day-2 card, the
  closing line, the narrator voice (`af_heart`, 0.9, 0.4 s gaps; shots 2, 3, 6, 7 and 8 reuse the v5
  files), the `quiet_after()` reply trim, about -16 LUFS, no music.
- The fall flag now appears at 9.8 s (v5: 4 s), because the line is now spoken and heard before
  the safety rules run. That is still inside the judges' 30-second "aha" window.

`timeline.json` is the committed record of the build: every Dad turn with its spoken source WAV
and the words heard, the companion-pause windows, the labels and the audio spans.

## Rebuild

From the repo root; build outputs stay in `$FY_VIDEO_BUILD` (default `../video-build`).

```bash
K=<kokoro-venv>/bin/python; B=${FY_VIDEO_BUILD:-../video-build}
$K video/v6/dad_voice.py $B            # dad_v6/*.wav
$K video/v6/narration.py $B            # narration_v6/ (new lines rendered, v5 lines copied)
export PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs DAD_DIR=$B/dad_v6
node video/v6/capture_v6.mjs $B/capture_v6 fall
SHOT_TAG=appt_t1 node video/v6/capture_v6.mjs $B/capture_v6 appt   # must pass its Dr. Tan check
node video/v6/capture_v6.mjs $B/capture_v6 crisis
KEY_ENV_FILE=.env .venv/bin/python video/v6/day2_v6.py $B
FY_TOLD_BOX=1548,616,1666,646 .venv/bin/python video/v6/assemble.py $B
```

`FY_TOLD_BOX` draws the green box around the panel's own "Dad was told" in shot 2 (pixel box in
the capture). `APPT_TAKE` picks a different appointment take.

## Checking a build

`.venv/bin/python video/v6/check_v6.py --release video-v6-draft --frames --transcribe` downloads the
release assets into a fresh empty directory. It fails on a download or decode error, a length of
2:50 or more, a curly quote or non-UTF-8 SRT, any silencedetect interval (-40 dB, 1.5 s) outside a
recorded companion pause, a Dad turn with no spoken source or no matching "Dad:" cue, or a privacy
label that does not end before the crisis line. It prints the loudness and every label cue, extracts
a frame inside each label, and prints a faster-whisper transcript of the mix. `--local <dir>` runs
the same checks before upload.
