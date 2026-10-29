"""Assemble the v5 demo video: the v4 cut with the captions and labels fixed for #275.

Same inputs and helpers as v4 (video/v2/assemble.py is imported). Over v4:
  - captions and cards use straight quotes only (the Space's replies carry U+2019, which a player
    that reads the SRT as cp1252 shows as mojibake); the build stops if any curly quote is left;
  - LIVE HOSTED SPACE is a small burned-in corner badge on shots 1-5, and a 4 s SRT cue at the start
    of each hosted shot, instead of one cue for 0:00-1:43;
  - "Not shown to the family" ends when the freeze before the crisis line starts, and a separate
    crisis label ("Crisis: 988 offered, simulated family alert") covers the 988 reply;
  - the day-2 shot is a clean card reading "Local persistence test - not the hosted Space."
    (v4 showed the terminal), with the same text as an SRT cue;
  - the closing narration is the self-contained prototype line (narration_v5/shot8.wav), kept as
    one caption and SRT cue so the limitation reads as a whole sentence.
Shots, footage and the other seven narration files are v4's.
Output: <build>/foreveryours_demo_v5.mp4 and .srt, timeline in <build>/_assemble_v5/.

Usage (from the repo root):  .venv/bin/python video/v5/assemble.py [<build_dir>]
"""
import importlib.util
import json
import math
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("v2asm", os.path.join(HERE, "..", "v2", "assemble.py"))
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)

ROOT, BUILD, W, H, SR, TARGET_LUFS = v2.ROOT, v2.BUILD, v2.W, v2.H, v2.SR, v2.TARGET_LUFS
CAP = os.path.join(BUILD, "capture")
NARR = os.path.join(BUILD, "narration_v5")
WORK = os.path.join(BUILD, "_assemble_v5")
FINAL = os.path.join(BUILD, "foreveryours_demo_v5.mp4")
SRT = os.path.join(BUILD, "foreveryours_demo_v5.srt")
MAX_SECONDS = 169.0     # leave margin below 3:00
FLAG_BY = 5.0           # the caregiver flag must be on screen before this many seconds

STACK_LINES = [
    "Replies: NVIDIA Nemotron 3 Nano ·\nSafety backstop: NVIDIA Nemotron 3 Super,\nboth on Nebius Token Factory",
    "Hearing and voice: on the app's own server",
]
LIVE = "LIVE HOSTED SPACE"
LOCAL = "Local persistence test - not the hosted Space."
CRISIS_LBL = "Crisis: 988 offered,\\Nsimulated family alert"   # \N is an ASS line break
CURLY = "\u2018\u2019\u201c\u201d"
KEEP_WHOLE = ("This is a prototype: it can miss nuance, so it does not replace human judgment or emergency services.",)
HOSTED_CUE_S = 4.0      # one short SRT cue per hosted shot
TAG = (1730, 34)        # top right, beside the "Caregiver side (live)" heading
LBL = (1427, 178)       # the empty band above "Today:" on the Caregiver side

ASS_HEAD = v2.ASS_HEAD.replace("\n[Events]", "Style: Tag,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00303030,"
                            "&H00303030,1,0,0,0,100,100,1,0,3,10,0,5,0,0,0,1\n"
                            "Style: Crisis,DejaVu Sans,40,&H00FFFFFF,&H00FFFFFF,&H001E1ECC,"
                            "&H001E1ECC,1,0,0,0,100,100,0,0,3,14,0,5,0,0,0,1\n\n[Events]")


def straighten(text):
    """Straight quotes and apostrophes only (#275): U+2018/2019 -> ', U+201C/201D -> "."""
    return text.translate({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'})


_clean = v2.clean
v2.clean = lambda text: straighten(_clean(text))   # every caption, and the card text, goes through clean


SENT_END = r"(?<=[.!?])(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bMrs\.)\s+"


def split_sentences(text):
    return re.split(SENT_END, text)


def chunk_text(text, limit=84):
    """v2.chunk_text, but a sentence does not end at an abbreviation such as "Dr."."""
    out = []
    for sent in split_sentences(v2.clean(text)):
        pieces = [sent]
        while sent not in KEEP_WHOLE and any(len(p) > limit for p in pieces):
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


v2.chunk_text = chunk_text   # timed_chunks (captions) looks it up on the module


def norm_word(w):
    return re.sub(r"[^a-z0-9]", "", w.lower().replace("\u2019", "'"))


def trim_reply(wav, text, n_sentences, out, cache):
    """Cut a companion reply after its first n sentences, at the whisper end time of the last
    word of those sentences; returns (trimmed wav, kept text)."""
    sents = split_sentences(v2.clean(text))
    kept = " ".join(sents[:n_sentences])
    ws = v2.words_of(wav, cache)
    n_kept, n_all = len(kept.split()), len(v2.clean(text).split())
    guess = min(len(ws) - 1, math.ceil(n_kept * len(ws) / n_all) - 1)
    last = norm_word(kept.split()[-1])
    hits = [i for i in range(max(0, guess - 4), min(len(ws), guess + 5)) if norm_word(ws[i]["w"]) == last]
    if not hits:
        sys.exit(f"cannot find the cut word {last!r} near word {guess} of {wav}")
    i = min(hits, key=lambda k: abs(k - guess))
    cut = ws[i]["e"] + 0.15
    if i + 1 < len(ws):
        cut = min(cut, ws[i + 1]["s"] - 0.02)
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-t", f"{cut:.3f}",
            "-af", f"afade=t=out:st={max(0.0, cut - 0.08):.3f}:d=0.08", out])
    return out, kept


def split_narration(wav, first_sentence_last_word, expect_index, out_a, out_b, cache):
    """Cut a narration WAV into two files at the whisper end time of the first sentence's last
    word (plus a short tail); returns (out_a, out_b)."""
    ws = v2.words_of(wav, cache)
    hits = [i for i, w in enumerate(ws) if norm_word(w["w"]) == norm_word(first_sentence_last_word)]
    if not hits:
        sys.exit(f"cannot find {first_sentence_last_word!r} in {wav}")
    i = min(hits, key=lambda k: abs(k - expect_index))   # the sentence-final one, not an earlier repeat
    cut_a = ws[i]["e"] + 0.12                     # end of part a, just after the last word
    cut_b = cut_a                                 # part b keeps a lead-in so its first consonant is not clipped
    if i + 1 < len(ws):
        cut_a = min(cut_a, ws[i + 1]["s"] - 0.02)
        cut_b = max(cut_a - 0.3, ws[i]["e"] + 0.02, min(cut_a, ws[i + 1]["s"] - 0.15))
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-t", f"{cut_a:.3f}", out_a])
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{cut_b:.3f}", "-i", wav, out_b])
    return out_a, out_b


def main():
    os.makedirs(WORK, exist_ok=True)
    man = json.load(open(os.path.join(CAP, "manifest.json")))["shots"]
    cache_p = os.path.join(WORK, "align.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    tl = v2.Timeline()
    seg = lambda name: os.path.join(WORK, f"seg_{len(tl.segments):02d}_{name}.mp4")  # noqa: E731

    def narr(n, at, wav=None, text=None):
        wav = wav or os.path.join(NARR, f"shot{n}.wav")
        text = text or open(os.path.join(NARR, f"shot{n}.caption.txt")).read()
        tl.audio.append((at, wav, "narrator"))
        for s, e, c in v2.timed_chunks(text, wav, cache):
            tl.caps.append((at + s, at + e, "Narrator", c))
        return v2.probe_duration(wav)

    def narr_split(n, at_a, at_b):
        """Shot n's narration in two parts: the first sentence at at_a, the rest at at_b."""
        text = open(os.path.join(NARR, f"shot{n}.caption.txt")).read().strip()
        sents = split_sentences(v2.clean(text))
        assert len(sents) >= 2, f"shot {n} narration must be at least two sentences, got {sents}"
        wa, wb = split_narration(os.path.join(NARR, f"shot{n}.wav"), sents[0].split()[-1],
                                 len(sents[0].split()) - 1, os.path.join(WORK, f"narr{n}a.wav"),
                                 os.path.join(WORK, f"narr{n}b.wav"), cache)
        da = narr(n, at_a, wa, sents[0])
        assert at_a + da <= at_b, f"shot {n}: first narration part runs into the second"
        return da, narr(n, at_b, wb, " ".join(sents[1:]))

    def companion(wav, text, at):
        tl.audio.append((at, wav, "companion"))
        for s, e, c in v2.timed_chunks(text, wav, cache):
            tl.caps.append((at + s, at + e, "Companion", "Companion: " + c))
        return v2.probe_duration(wav)

    def senior(text, a, b):
        tl.caps.append((a, b, "Senior", "Dad: " + v2.clean(text)))

    badges, srt_only = [], []   # ASS-only events (the corner badge), SRT-only cues (label text for the sidecar)

    def hosted(a, b):
        """A hosted shot: the corner badge stays on for the whole shot; the SRT gets one short cue."""
        badges.append((a, b))
        srt_only.append((a, min(b, a + HOSTED_CUE_S), "Tag", f"[{LIVE}]"))

    # Shot 1: the fall, from just before Send; the reply runs to its disclosure sentence.
    s1 = man["1_fall"]
    km = s1["key_moments"]
    A = km["fall_send_clicked"] - 0.8
    ra = s1["reply_audio"][0]
    fall_wav, fall_text = trim_reply(ra["path"], s1["companion_reply"], 4, os.path.join(WORK, "fall_reply_cut.wav"), cache)
    end = ra["starts_playing_at"] + v2.probe_duration(fall_wav) + 0.6
    start = tl.t
    senior(s1["senior_text"], start, start + ra["starts_playing_at"] - A)
    companion(fall_wav, fall_text, start + ra["starts_playing_at"] - A)
    flag_at = start + km["fall_flag_visible"] - A
    if flag_at >= FLAG_BY:
        sys.exit(f"the caregiver flag appears at {flag_at:.2f}s, not before {FLAG_BY}s")
    tl.labels.append((flag_at, start + end - A, "Label", *LBL, "Dad was told"))
    tl.add(seg("fall"), v2.seg_clip(seg("fall"), s1["clip"], A, end))
    tl.shots.append((1, start, tl.t))
    hosted(start, tl.t)

    # Shot 2: still of the split screen, slow zoom onto the panel's own "Dad was told" line.
    start = tl.t
    png = v2.grab_frame(s1["clip"], min(km["hold_end"] - 0.5, s1["duration"] - 0.5), os.path.join(WORK, "hold.png"))
    im = Image.open(png).convert("RGB")
    ImageDraw.Draw(im).rounded_rectangle((1525, 615, 1640, 647), radius=7, outline=(38, 122, 30), width=3)
    im.save(os.path.join(WORK, "hold_marked.png"))
    dur2 = 0.4 + v2.probe_duration(os.path.join(NARR, "shot2.wav")) + 0.8
    narr(2, start + 0.4)
    tl.add(seg("zoom"), v2.seg_zoom(seg("zoom"), os.path.join(WORK, "hold_marked.png"), dur2,
                                    (1010, 330, 864, 486), 1.0, 6.0))
    tl.shots.append((2, start, tl.t))
    hosted(start, tl.t)

    # Shot 3: the caregiver saves the appointment memo.
    s3, s4 = man["3_memo"], man["4_senior_line"]
    if not s4.get("verified") or not s4.get("take") or not next(
            (r["check"]["pass"] for r in s4.get("runs", []) if r["tag"] == s4["take"]), False):
        sys.exit("shot 4 is not verified; re-run the appt capture, see video/v2/README.md")
    k3, k4 = s3["key_moments"], s4["key_moments"]
    A3, B3 = 2.4, k3["memo_framed"] + 2.3    # v3 held to memo_hold_end (3 s of silence more)
    start = tl.t
    narr(3, start + 0.6)
    tl.add(seg("memo"), v2.seg_clip(seg("memo"), s3["clip"], A3, B3))
    tl.shots.append((3, start, tl.t))
    hosted(start, tl.t)

    # Shot 4: same session; the senior asks, the reply names the appointment.
    ra = s4["reply_audio"][0]
    A4, B4 = B3, ra["starts_playing_at"] + ra["duration"] + 0.6
    start = tl.t
    _, n4b = narr_split(4, start + (k4["split_framed"] + 0.2 - A4), start + (k4["senior_send_clicked"] + 0.3 - A4))
    assert start + (k4["senior_send_clicked"] + 0.3 - A4) + n4b < start + ra["starts_playing_at"] - A4, \
        "shot 4 narration overlaps the reply"
    senior(s4["senior_text"], start + (k4["split_framed"] + 1.0 - A4), start + ra["starts_playing_at"] - A4)
    companion(ra["path"], s4["companion_reply"], start + ra["starts_playing_at"] - A4)
    tl.add(seg("ask"), v2.seg_clip(seg("ask"), s4["clip"], A4, B4))
    tl.shots.append((4, start, tl.t))
    hosted(start, tl.t)

    # Shot 5: a private line (no flag), a short freeze for the narrator, then the crisis line,
    # whose reply runs to its disclosure sentence.
    s5 = man["5_private_then_crisis"]
    k5 = s5["key_moments"]
    r1, r2 = s5["reply_audio"]
    crisis_wav, crisis_text = trim_reply(r2["path"], s5["companion_reply"][1], 3,
                                         os.path.join(WORK, "crisis_reply_cut.wav"), cache)
    A5, CUT, FREEZE = 2.9, r1["starts_playing_at"] + r1["duration"] + 0.05, 1.2
    B5 = r2["starts_playing_at"] + v2.probe_duration(crisis_wav) + 0.8
    start = tl.t
    g = lambda t: start + (t - A5) + (FREEZE if t >= CUT else 0.0)  # noqa: E731
    senior(s5["senior_text"][0], start, g(r1["starts_playing_at"]))
    companion(r1["path"], s5["companion_reply"][0], g(r1["starts_playing_at"]))
    # The privacy label ends when the freeze before the crisis line starts, well before the crisis
    # line's caption (g(CUT)); the crisis label below takes over from the moment the flag appears.
    assert g(k5["lonely_reply_text_visible"]) < g(CUT) - FREEZE, "private label would not fit"
    tl.labels.append((g(k5["lonely_reply_text_visible"]), g(CUT) - FREEZE, "LabelGrey", *LBL,
                      "Not shown to the family"))
    tl.labels.append((g(k5["crisis_flag_visible"]), g(B5), "Crisis", LBL[0], LBL[1] - 28, CRISIS_LBL))
    n5a, n5 = narr_split(5, start + 0.2, g(CUT) - FREEZE + 0.1)
    assert start + 0.2 + n5a < g(r1["starts_playing_at"]), "shot 5 first line overlaps the private reply"
    senior(s5["senior_text"][1], g(CUT), g(r2["starts_playing_at"]))
    companion(crisis_wav, crisis_text, g(r2["starts_playing_at"]))
    tl.add(seg("lonely"), v2.seg_clip(seg("lonely"), s5["clip"], A5, CUT))
    tl.add(seg("freeze"), v2.seg_still(seg("freeze"), v2.grab_frame(s5["clip"], CUT, os.path.join(WORK, "cut.png")), FREEZE))
    tl.add(seg("crisis"), v2.seg_clip(seg("crisis"), s5["clip"], CUT, B5))
    tl.shots.append((5, start, tl.t))
    hosted(start, tl.t)
    assert g(CUT) - FREEZE + 0.1 + n5 < g(r2["starts_playing_at"]), "shot 5 narration overlaps the crisis reply"

    # Shot 6: day 2, the local run, shown as a clean card (v4 showed the terminal). The words are
    # the captions; the card says what this is and is not (#275).
    s6 = man["6_day2_local"]
    card6 = v2.card(os.path.join(WORK, "card6.png"), [
        (LOCAL, 72, True),
        ("Day 2: a fresh local run still remembers yesterday's briefing", 46, False),
    ])
    start = tl.t
    DAY2_END = 7.6      # the answer lands ~4.5 s in; the local run's audit line is not part of the shot
    narr(6, start + 0.6)
    senior(s6["senior_text"], start + 0.8, start + 4.4)
    tl.caps.append((start + 4.4, start + DAY2_END, "Companion", "Companion: " + v2.clean(s6["companion_reply"])))
    srt_only.append((start, start + DAY2_END, "Tag", f"[{LOCAL}]"))
    tl.add(seg("day2"), v2.seg_still(seg("day2"), card6, DAY2_END))
    tl.shots.append((6, start, tl.t))

    # Shots 7-8: plain text cards.
    for n, png, tail in (
        (7, v2.card(os.path.join(WORK, "card7.png"), [(ln, 54, False) for ln in STACK_LINES]), 1.0),
        (8, v2.card(os.path.join(WORK, "card8.png"), [("ForeverYours", 118, True),
                                                       ("The companion the family briefs", 54, False),
                                                       ("Try it yourself, no login", 48, False),
                                                       (v2.URL, 70, True),
                                                       ("Known limitations: in the README", 46, False)]), 2.0),
    ):
        start = tl.t
        dur = 0.5 + v2.probe_duration(os.path.join(NARR, f"shot{n}.wav")) + tail
        narr(n, start + 0.5)
        tl.add(seg(f"card{n}"), v2.seg_still(seg(f"card{n}"), png, dur))
        tl.shots.append((n, start, tl.t))

    json.dump(cache, open(cache_p, "w"), indent=1)
    total = tl.t
    print(f"timeline: {total:.2f}s")
    for n, a, b in tl.shots:
        print(f"  shot {n}: {a:6.2f} - {b:6.2f}  ({b - a:5.2f}s)")
    print(f"  caregiver flag + 'Dad was told' at {flag_at:.2f}s")
    if total > MAX_SECONDS:
        sys.exit(f"timeline {total:.2f}s is over {MAX_SECONDS}s")

    # ---- audio: per-source gain to the same loudness, laid on the timeline, no overlaps
    mix = np.zeros(int((total + 1) * SR), dtype=np.float32)
    spans = []
    for at, wav, kind in tl.audio:
        x = v2.load_wav(wav)
        gain = 10 ** ((TARGET_LUFS - 2.0 - v2.loudness(wav)) / 20)
        i = int(round(at * SR))
        mix[i:i + len(x)] += x * gain
        spans.append((at, at + len(x) / SR, kind, os.path.basename(wav)))
    spans.sort()
    for p, q in zip(spans, spans[1:]):
        if q[0] < p[1] - 0.02:
            sys.exit(f"audio overlap: {p} and {q}")
    mix = mix[:int(total * SR)]
    raw = os.path.join(WORK, "mix_raw.wav")
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
            "-c:a", "pcm_f32le", raw], input=mix.tobytes())
    ln = f"loudnorm=I={TARGET_LUFS}:TP=-2.0:LRA=11"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", raw, "-af", ln + ":print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    mixed = os.path.join(WORK, "mix.wav")
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
            f"{ln}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", mixed])

    # ---- captions: ASS (burned in) and SRT (sidecar), both from this timeline
    events = sorted(tl.caps)
    ass = os.path.join(WORK, "captions.ass")
    with open(ass, "w") as fh:
        fh.write(ASS_HEAD)
        for a, b, style, text in events:
            fh.write(f"Dialogue: 0,{v2.ts_ass(a)},{v2.ts_ass(b)},{style},,0,0,0,,{text}\n")
        for a, b, style, x, y, text in tl.labels:
            fh.write(f"Dialogue: 1,{v2.ts_ass(a)},{v2.ts_ass(b)},{style},,0,0,0,,{{\\pos({x},{y})}}{text}\n")
        for a, b in badges:
            fh.write(f"Dialogue: 1,{v2.ts_ass(a)},{v2.ts_ass(b)},Tag,,0,0,0,,{{\\pos({TAG[0]},{TAG[1]})}}{LIVE}\n")
    srt = sorted(events + srt_only + [(a, b, style, "[" + text.replace("\\N", " ") + "]")
                                      for a, b, style, _, _, text in tl.labels])
    with open(SRT, "w", encoding="utf-8", newline="\n") as fh:
        for i, (a, b, _, text) in enumerate(srt, 1):
            fh.write(f"{i}\n{v2.ts_srt(a)} --> {v2.ts_srt(b)}\n{text}\n\n")
    for path in (SRT, ass):
        bad = sorted({c for c in open(path, encoding="utf-8").read() if c in CURLY})
        if bad:
            sys.exit(f"{path} still has curly quotes: {bad}")
    hosted_cues = [b - a for a, b, _, t in srt if LIVE in t]
    if max(hosted_cues) > 6.0:
        sys.exit(f"a LIVE HOSTED SPACE cue runs {max(hosted_cues):.1f} s")

    # ---- join, burn captions, mux
    lst = os.path.join(WORK, "concat.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p, _ in tl.segments)
    joined = os.path.join(WORK, "joined.mp4")
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    v2.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", mixed,
            "-vf", f"ass={ass}:fontsdir=/usr/share/fonts/truetype/dejavu",
            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", str(v2.FPS), "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
            "-movflags", "+faststart", "-t", f"{total:.3f}", FINAL])

    dur = v2.probe_duration(FINAL)
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", FINAL, "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    json.dump({"duration": dur, "flag_at": flag_at, "shots": tl.shots, "audio": spans, "labels": tl.labels,
               "lufs": lufs, "true_peak": peak}, open(os.path.join(WORK, "timeline.json"), "w"), indent=1)
    print(f"\nFINAL {FINAL}\n  duration {dur:.2f}s ({int(dur // 60)}:{dur % 60:05.2f})"
          f"\n  loudness {lufs} LUFS, true peak {peak} dBTP\nSRT {SRT}")
    if dur >= MAX_SECONDS + 1 or peak > -1.5 or abs(lufs - TARGET_LUFS) > 1.0:
        sys.exit("final video failed checks")


if __name__ == "__main__":
    main()
