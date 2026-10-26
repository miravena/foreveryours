"""Assemble the v2 demo video from the live-Space captures, the narration and text cards.

Inputs (outside git, see README.md here):
  <build>/capture/manifest.json   per-shot clips, key moments, companion reply audio and text
  <build>/narration/shotN.wav     narrator lines (shots 2-9), shotN.caption.txt verbatim captions
Output:
  <build>/foreveryours_demo_v2.mp4 (1920x1080, 30 fps, H.264 + AAC 48 kHz, loudness -16 LUFS,
  true peak at most -1.5 dBTP) and <build>/foreveryours_demo_v2.srt (the same captions).

Usage (from the repo root):  .venv/bin/python video/v2/assemble.py [<build_dir>]
(the day-2 terminal is re-rendered by video/render_terminal.py under $FY_TERM_PYTHON, default
python3, which needs pyte and Pillow)
<build_dir> defaults to $FY_VIDEO_BUILD or ../video-build next to the repo checkout.

How it works: every shot becomes a silent 30 fps segment (clip trims, a freeze frame, a slow
zoom rendered with Pillow, or a Pillow text card); the segments are joined; captions are one
ASS file burned in by libass; the audio is mixed in numpy from the narrator WAVs and the
companion's real reply audio, each laid at its on-screen moment and never overlapping, then
normalised with ffmpeg loudnorm (two passes). Caption timing comes from faster-whisper word
timestamps of each WAV; caption text is the verbatim narration or reply text.
"""
import json
import math
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUILD = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "FY_VIDEO_BUILD", os.path.join(ROOT, "..", "video-build")))
CAP = os.path.join(BUILD, "capture")
NARR = os.path.join(BUILD, "narration")
WORK = os.path.join(BUILD, "_assemble")
FINAL = os.path.join(BUILD, "foreveryours_demo_v2.mp4")
SRT = os.path.join(BUILD, "foreveryours_demo_v2.srt")

W, H, FPS, SR = 1920, 1080, 30, 48000
MAX_SECONDS = 178.0
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TARGET_LUFS = -16.0

STACK_LINES = [   # the script's three lines; the first is long, so it breaks at its own separators
    "Reply: NVIDIA Nemotron 3 Nano ·\nSafety backstop: NVIDIA Nemotron 3 Super,\nboth on Nebius Token Factory",
    "Hearing: faster-whisper, on the app's own server",
    "Voice: Piper, on the app's own server",
]
LIMITS_TEXT = "Known limitations: in the README"
URL = "https://elevenbaselab-foreveryours.hf.space"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe_duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode())


def clean(text):
    """Caption-safe text: the Space's narrow no-break spaces and no-break hyphens as plain ones."""
    return re.sub(r"\s+", " ", text.replace("\u202f", " ").replace("\u00a0", " ").replace("\u2011", "-")).strip()


# ---------------------------------------------------------------- video segments
VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]
NORM = f"scale={W}:{H},setsar=1,fps={FPS},format=yuv420p"


def seg_clip(out, src, a, b, extra_vf=""):
    """Trim src to [a, b] seconds; past the clip's end the last frame is held."""
    dur = probe_duration(src)
    hold = max(0.0, b - dur) + 0.2
    vf = f"tpad=stop_mode=clone:stop_duration={hold:.3f},{NORM}" + (f",{extra_vf}" if extra_vf else "")
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-i", src, "-vf", vf,
         "-t", f"{b - a:.3f}", *VENC, out])
    return b - a


def grab_frame(src, t, png):
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", png])
    return png


def seg_still(out, png, dur):
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-vf", NORM,
         "-t", f"{dur:.3f}", *VENC, out])
    return dur


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def seg_zoom(out, png, dur, rect, t0, t1):
    """Slow zoom from the full frame to rect=(x, y, w, h) between t0 and t1 (sub-pixel smooth)."""
    im = Image.open(png).convert("RGB")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *VENC, out], stdin=subprocess.PIPE)
    n = int(round(dur * FPS))
    for i in range(n):
        k = ease((i / FPS - t0) / (t1 - t0))
        x = rect[0] * k
        y = rect[1] * k
        w = W + (rect[2] - W) * k
        h = H + (rect[3] - H) * k
        fr = im.transform((W, H), Image.Transform.EXTENT, (x, y, x + w, y + h), Image.Resampling.BICUBIC)
        proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit("zoom render failed")
    return n / FPS


def fit_font(text, path, size, max_w):
    while size > 20:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(path, size)


def wrap(text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def card(png, blocks, top=None):
    """A plain light card: blocks = [(text, size, bold)], centred, wrapped, no logos."""
    im = Image.new("RGB", (W, H), (247, 245, 240))
    d = ImageDraw.Draw(im)
    laid = []
    for text, size, bold in blocks:
        f = fit_font(max(text.split("\n"), key=len), FONT_BOLD if bold else FONT, size, W - 260)
        for part in text.split("\n"):
            for ln in wrap(part, f, W - 260):
                laid.append((ln, f, int(size * 1.35)))
        laid.append(("", f, int(size * 0.7)))
    laid.pop()
    total = sum(h for _, _, h in laid)
    y = top if top is not None else (H - 260 - total) // 2 + 40
    for ln, f, h in laid:
        if ln:
            d.text(((W - f.getlength(ln)) / 2, y), ln, font=f, fill=(29, 29, 31))
        y += h
    im.save(png)
    return png


# ---------------------------------------------------------------- audio
def load_wav(path):
    raw = subprocess.check_output(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                                   "-f", "f32le", "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])


# ---------------------------------------------------------------- caption timing
_model = None


def words_of(path, cache):
    if path in cache:
        return cache[path]
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = _model.transcribe(path, word_timestamps=True, beam_size=5, language="en")
    ws = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in s.words]
    cache[path] = ws
    return ws


def chunk_text(text, limit=84):
    """Split text into caption chunks of at most ~limit characters: whole sentences where they
    fit, otherwise balanced pieces broken at a comma or dash near the middle, else at a space."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", clean(text)):
        pieces = [sent]
        while any(len(p) > limit for p in pieces):
            p = next(p for p in pieces if len(p) > limit)
            k = math.ceil(len(p) / limit)
            target = len(p) / k
            stops = [m.end() for m in re.finditer(r"[,;\u2014\u2013] ", p)]
            near = [c for c in stops if abs(c - target) <= target * 0.35]
            cut = min(near, key=lambda c: abs(c - target)) if near else min(
                (m.start() + 1 for m in re.finditer(" ", p)), key=lambda c: abs(c - target))
            i = pieces.index(p)
            pieces[i:i + 1] = [p[:cut].strip(), p[cut:].strip()]
        out += [p for p in pieces if p]
    return out


def timed_chunks(text, wav, cache):
    """[(start, end, chunk)] in seconds from the WAV start, aligned on whisper word times."""
    ws = words_of(wav, cache)
    chunks = chunk_text(text)
    n_t = sum(len(c.split()) for c in chunks)
    n_w = len(ws)
    res, a = [], 0
    for c in chunks:
        b = a + len(c.split())
        i = min(n_w - 1, int(a * n_w / n_t))
        j = min(n_w - 1, max(i, math.ceil(b * n_w / n_t) - 1))
        res.append([ws[i]["s"], ws[j]["e"], c])
        a = b
    for k in range(len(res) - 1):                 # no gaps and no overlaps between chunks
        res[k][1] = res[k + 1][0]
    res[0][0] = 0.0
    res[-1][1] += 0.4
    return res


# ---------------------------------------------------------------- ASS / SRT
def ts_ass(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ts_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narrator,DejaVu Sans,46,&H00FFFFFF,&H00FFFFFF,&H28000000,&H28000000,0,0,0,0,100,100,0,0,3,14,0,2,150,150,46,1
Style: Companion,DejaVu Sans,46,&H0080F0FF,&H0080F0FF,&H28000000,&H28000000,0,0,0,0,100,100,0,0,3,14,0,2,150,150,46,1
Style: Senior,DejaVu Sans,46,&H00FFE0B0,&H00FFE0B0,&H28000000,&H28000000,0,0,0,0,100,100,0,0,3,14,0,2,150,150,46,1
Style: Label,DejaVu Sans,52,&H00FFFFFF,&H00FFFFFF,&H00267A1E,&H00267A1E,1,0,0,0,100,100,0,0,3,16,0,5,0,0,0,1
Style: LabelGrey,DejaVu Sans,52,&H00FFFFFF,&H00FFFFFF,&H00505050,&H00505050,1,0,0,0,100,100,0,0,3,16,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


class Timeline:
    def __init__(self):
        self.t = 0.0
        self.segments = []      # (path, duration)
        self.audio = []         # (start, path, kind)
        self.caps = []          # (start, end, style, text)
        self.labels = []        # (start, end, style, x, y, text)
        self.shots = []         # (n, start, end)

    def add(self, path, dur):
        self.segments.append((path, dur))
        self.t += dur


def main():
    os.makedirs(WORK, exist_ok=True)
    man = json.load(open(os.path.join(CAP, "manifest.json")))["shots"]
    cache_p = os.path.join(WORK, "align.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    tl = Timeline()
    seg = lambda name: os.path.join(WORK, f"seg_{len(tl.segments):02d}_{name}.mp4")  # noqa: E731

    def narr(n, at):
        wav = os.path.join(NARR, f"shot{n}.wav")
        text = open(os.path.join(NARR, f"shot{n}.caption.txt")).read()
        tl.audio.append((at, wav, "narrator"))
        for s, e, c in timed_chunks(text, wav, cache):
            tl.caps.append((at + s, at + e, "Narrator", c))
        return probe_duration(wav)

    def companion(wav, text, at):
        tl.audio.append((at, wav, "companion"))
        for s, e, c in timed_chunks(text, wav, cache):
            tl.caps.append((at + s, at + e, "Companion", "Companion: " + c))
        return probe_duration(wav)

    def senior(text, a, b):
        tl.caps.append((a, b, "Senior", "Dad: " + clean(text)))

    LBL = (1427, 178)   # the empty band above "Today:" on the Caregiver side

    # Shot 1: the fall, from the moment it is being typed; the companion plays in full.
    s1 = man["1_fall"]
    km, A = s1["key_moments"], 3.8
    ra = s1["reply_audio"][0]
    end = ra["starts_playing_at"] + ra["duration"] + 0.5
    start = tl.t
    senior(s1["senior_text"], start + 0.0, start + ra["starts_playing_at"] - A)
    companion(ra["path"], s1["companion_reply"], start + ra["starts_playing_at"] - A)
    tl.labels.append((start + km["fall_flag_visible"] - A, start + end - A, "Label", *LBL, "Dad was told"))
    tl.add(seg("fall"), seg_clip(seg("fall"), s1["clip"], A, end))
    tl.shots.append((1, start, tl.t))

    # Shot 2: hold on the split screen, then a slow zoom on "Dad was told" (a still of the hold).
    start = tl.t
    png = grab_frame(s1["clip"], min(km["hold_end"] - 0.5, s1["duration"] - 0.5), os.path.join(WORK, "hold.png"))
    im = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1525, 615, 1640, 647), radius=7, outline=(38, 122, 30), width=3)
    im.save(os.path.join(WORK, "hold_marked.png"))
    dur2 = 0.4 + probe_duration(os.path.join(NARR, "shot2.wav")) + 0.8
    narr(2, start + 0.4)
    tl.labels.append((start, start + 1.6, "Label", *LBL, "Dad was told"))
    tl.labels.append((start + 7.0, start + dur2, "Label", 960, 80, "Dad was told"))
    tl.add(seg("zoom"), seg_zoom(seg("zoom"), os.path.join(WORK, "hold_marked.png"), dur2,
                                 (1010, 330, 864, 486), 1.6, 7.0))
    tl.shots.append((2, start, tl.t))

    # Shot 3: the caregiver types the appointment memo and saves it; memory shows it added.
    s3, s4 = man["3_memo"], man["4_senior_line"]
    k3, k4 = s3["key_moments"], s4["key_moments"]
    A3, B3 = 2.4, k3["memo_hold_end"]
    start = tl.t
    narr(3, start + 1.2)
    tl.add(seg("memo"), seg_clip(seg("memo"), s3["clip"], A3, B3))
    tl.shots.append((3, start, tl.t))

    # Shot 4: same session; the senior asks, the reply names the appointment.
    ra = s4["reply_audio"][0]
    A4, B4 = B3, ra["starts_playing_at"] + ra["duration"] + 0.6
    start = tl.t
    narr(4, start + (k4["split_framed"] + 0.2 - A4))
    senior(s4["senior_text"], start + (k4["split_framed"] + 1.0 - A4), start + ra["starts_playing_at"] - A4)
    companion(ra["path"], s4["companion_reply"], start + ra["starts_playing_at"] - A4)
    tl.add(seg("ask"), seg_clip(seg("ask"), s4["clip"], A4, B4))
    tl.shots.append((4, start, tl.t))

    # Shot 5: a private line (no flag), then the crisis line; a short freeze between them makes
    # room for the narrator so nobody talks over the companion.
    s5 = man["5_private_then_crisis"]
    k5 = s5["key_moments"]
    r1, r2 = s5["reply_audio"]
    A5, CUT, FREEZE = 2.9, r1["starts_playing_at"] + r1["duration"] + 0.05, 1.2
    B5 = r2["starts_playing_at"] + r2["duration"] + 0.6
    start = tl.t
    g = lambda t: start + (t - A5) + (FREEZE if t >= CUT else 0.0)  # noqa: E731
    senior(s5["senior_text"][0], start, g(r1["starts_playing_at"]))
    companion(r1["path"], s5["companion_reply"][0], g(r1["starts_playing_at"]))
    tl.labels.append((g(k5["lonely_reply_text_visible"]), g(k5["crisis_send_clicked"]), "LabelGrey", *LBL,
                      "Not shown to the family"))
    n5 = narr(5, g(CUT) - FREEZE + 0.1)
    senior(s5["senior_text"][1], g(CUT), g(r2["starts_playing_at"]))
    companion(r2["path"], s5["companion_reply"][1], g(r2["starts_playing_at"]))
    tl.labels.append((g(k5["crisis_flag_visible"]), g(B5), "Label", *LBL, "Dad was told"))
    tl.add(seg("lonely"), seg_clip(seg("lonely"), s5["clip"], A5, CUT))
    tl.add(seg("freeze"), seg_still(seg("freeze"), grab_frame(s5["clip"], CUT, os.path.join(WORK, "cut.png")), FREEZE))
    tl.add(seg("crisis"), seg_clip(seg("crisis"), s5["clip"], CUT, B5))
    tl.shots.append((5, start, tl.t))
    assert g(CUT) - FREEZE + 0.1 + n5 < g(r2["starts_playing_at"]), "shot 5 narration overlaps the crisis reply"

    # Shot 6: day 2, a local run. No timing figure may be shown, and the terminal's lines sit too
    # close to cover one with a box, so the terminal is re-rendered from the recorded cast with
    # that single output line ("Time to first WAV written ...") removed; everything else is as run.
    s6 = man["6_day2_local"]
    cast_clean = os.path.join(WORK, "day2_clean.cast")
    with open(s6["cast"]) as fh, open(cast_clean, "w") as out:
        for i, line in enumerate(fh):
            if i and line.strip():
                ev = json.loads(line)
                ev[2] = re.sub(r"Time to first WAV written[^\r\n]*\r?\n", "", ev[2])
                line = json.dumps(ev, ensure_ascii=False) + "\n"
            out.write(line)
    day2_clip = os.path.join(WORK, "day2_clean.mp4")
    run([os.environ.get("FY_TERM_PYTHON", "python3"), os.path.join(ROOT, "video", "render_terminal.py"), cast_clean, day2_clip,
         str(s6["duration"])], stdout=subprocess.DEVNULL)
    start = tl.t
    narr(6, start + 0.6)
    senior(s6["senior_text"], start + 0.8, start + 3.6)
    tl.caps.append((start + 3.6, start + s6["duration"], "Companion", "Companion: " + clean(s6["companion_reply"])))
    tl.labels.append((start, start + s6["duration"], "Label", 1500, 820, "Day 2 (local run)"))
    tl.add(seg("day2"), seg_clip(seg("day2"), day2_clip, 0.0, s6["duration"]))
    tl.shots.append((6, start, tl.t))

    # Shots 7-9: plain text cards.
    for n, png, tail in (
        (7, card(os.path.join(WORK, "card7.png"), [(ln, 54, False) for ln in STACK_LINES]), 1.0),
        (8, card(os.path.join(WORK, "card8.png"), [(LIMITS_TEXT, 72, True)]), 0.8),
        (9, card(os.path.join(WORK, "card9.png"), [("Try it yourself, no login", 56, False),
                                                    (URL, 74, True)]), 2.6),
    ):
        start = tl.t
        dur = 0.5 + probe_duration(os.path.join(NARR, f"shot{n}.wav")) + tail
        narr(n, start + 0.5)
        tl.add(seg(f"card{n}"), seg_still(seg(f"card{n}"), png, dur))
        tl.shots.append((n, start, tl.t))

    json.dump(cache, open(cache_p, "w"), indent=1)
    total = tl.t
    print(f"timeline: {total:.2f}s")
    for n, a, b in tl.shots:
        print(f"  shot {n}: {a:6.2f} - {b:6.2f}  ({b - a:5.2f}s)")
    if total > MAX_SECONDS:
        sys.exit(f"timeline {total:.2f}s is over {MAX_SECONDS}s")

    # ---- audio: per-source gain to the same loudness, laid on the timeline, no overlaps
    mix = np.zeros(int((total + 1) * SR), dtype=np.float32)
    spans = []
    for at, wav, kind in tl.audio:
        x = load_wav(wav)
        gain = 10 ** ((TARGET_LUFS - 2.0 - loudness(wav)) / 20)
        i = int(round(at * SR))
        mix[i:i + len(x)] += x * gain
        spans.append((at, at + len(x) / SR, kind, os.path.basename(wav)))
    spans.sort()
    for p, q in zip(spans, spans[1:]):
        if q[0] < p[1] - 0.02:
            sys.exit(f"audio overlap: {p} and {q}")
    mix = mix[:int(total * SR)]
    raw = os.path.join(WORK, "mix_raw.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
         "-c:a", "pcm_f32le", raw], input=mix.tobytes())
    ln = f"loudnorm=I={TARGET_LUFS}:TP=-2.0:LRA=11"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", raw, "-af", ln + ":print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    mixed = os.path.join(WORK, "mix.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
         f"{ln}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
         f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", mixed])

    # ---- captions: ASS (burned in) and SRT (sidecar)
    events = sorted(tl.caps)
    with open(os.path.join(WORK, "captions.ass"), "w") as fh:
        fh.write(ASS_HEAD)
        for a, b, style, text in events:
            fh.write(f"Dialogue: 0,{ts_ass(a)},{ts_ass(b)},{style},,0,0,0,,{text}\n")
        for a, b, style, x, y, text in tl.labels:
            fh.write(f"Dialogue: 1,{ts_ass(a)},{ts_ass(b)},{style},,0,0,0,,{{\\pos({x},{y})}}{text}\n")
    with open(SRT, "w") as fh:
        for i, (a, b, _, text) in enumerate(events, 1):
            fh.write(f"{i}\n{ts_srt(a)} --> {ts_srt(b)}\n{text}\n\n")

    # ---- join, burn captions, mux
    lst = os.path.join(WORK, "concat.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p, _ in tl.segments)
    joined = os.path.join(WORK, "joined.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", mixed,
         "-vf", f"ass={os.path.join(WORK, 'captions.ass')}:fontsdir=/usr/share/fonts/truetype/dejavu",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
         "-movflags", "+faststart", "-t", f"{total:.3f}", FINAL])

    dur = probe_duration(FINAL)
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", FINAL, "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    json.dump({"duration": dur, "shots": tl.shots, "audio": spans, "lufs": lufs, "true_peak": peak},
              open(os.path.join(WORK, "timeline.json"), "w"), indent=1)
    print(f"\nFINAL {FINAL}\n  duration {dur:.2f}s ({int(dur // 60)}:{dur % 60:05.2f})"
          f"\n  loudness {lufs} LUFS, true peak {peak} dBTP\nSRT {SRT}")
    if dur >= 180 or peak > -1.5 or abs(lufs - TARGET_LUFS) > 1.0:
        sys.exit("final video failed checks")


if __name__ == "__main__":
    main()
