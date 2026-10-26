# Narration (video v2)

Narrator lines for the demo video, rendered with Kokoro TTS (kokoro-onnx, Apache-2.0 model and
code, so fine for a public video) on CPU. Voice af_heart at speed 0.95, loudnorm to -16 LUFS
(I=-16:TP=-1.5:LRA=11), 48 kHz mono WAV. Audio lives outside git in the build directory
(`$FY_VIDEO_BUILD`, default `../video-build` next to the repo checkout), under `narration/`
(`shotN.wav`, `shotN.caption.txt`, `candidates/`).

Reproduce: `<venv>/bin/python render.py [candidates|render|all]` from a venv with kokoro-onnx,
soundfile and numpy (needs system libespeak-ng and espeak-ng-data; the model files
`kokoro-v1.0.onnx` and `voices-v1.0.bin` go in `<build>/kokoro/`). The text is read from the
narrator column of `docs/VIDEO_SCRIPT.md`; Kokoro reads respelled text for a few names
(`RESPELL`), the captions keep the script's wording.

**Swapping in a human narrator:** record each line as `narration/shotN.wav` (any sample rate;
`video/v2/assemble.py` matches loudness per file) and keep `shotN.caption.txt` as the wording
actually said. Shots 2 and 7-9 are timed from the WAV lengths, so a slower read
lengthens them; in shots 3-6 the line sits in a gap of the footage, and the assembler stops with
an error if any line would overlap the companion's voice or the video would pass 2:58.
`lines.json` maps shot number to verbatim text, spoken (respelled) text, file and duration.
