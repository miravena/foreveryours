"""Assemble the v6 demo video (#304): the v5 cut with Dad SPEAKING and no dead air.

New footage, same shape as v5. Every hosted shot was re-captured on the live Space by
video/v6/capture_v6.mjs, with each senior line spoken into the browser microphone (Dad's WAVs,
video/v6/dad_voice.py), so the transcript line on screen is what the Space heard. Day 2 is a
local run that hears the same voice (video/v6/day2_v6.py). Over v5:
  - Dad's voice is in the mix, at the moment the microphone played it, and his caption is the
    line the Space (or, on day 2, the local run) heard;
  - the narrator speaks over every hearing and model wait (narration_v6/, video/v6/lines.json);
    the one line "He can also type, if he prefers." says that typing works too;
  - two jump cuts remove only script idle time (the memo hold and scroll, the pause before the
    crisis line), never a wait for the Space: every send-to-reply wait is uncut;
  - the build stops if any silence in the mix is 1.5 s or longer outside the companion's own
    pauses, and writes video/v6/timeline.json (every Dad turn with its spoken source, and the
    companion-pause windows) for video/v6/check_v6.py.
Kept from v5 (#275): straight quotes only, the LIVE HOSTED SPACE corner badge plus a 4 s SRT
cue per hosted shot, the privacy label ending before the crisis line with a separate crisis
label, the clean day-2 card, the closing line, about -16 LUFS, no music.

Usage (from the repo root):  .venv/bin/python video/v6/assemble.py [<build_dir>]
Output: <build>/foreveryours_demo_v6.mp4 and .srt, work files in <build>/_assemble_v6/.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("v5asm", os.path.join(HERE, "..", "v5", "assemble.py"))
v5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v5)   # patches v2's clean/chunk_text (straight quotes, "Dr." stays whole)
v2 = v5.v2

BUILD, SR, TARGET_LUFS = v2.BUILD, v2.SR, v2.TARGET_LUFS
CAP = os.path.join(BUILD, "capture_v6")
DAD = os.path.join(BUILD, "dad_v6")
NARR = os.path.join(BUILD, "narration_v6")
WORK = os.path.join(BUILD, "_assemble_v6")
FINAL = os.path.join(BUILD, "foreveryours_demo_v6.mp4")
SRT = os.path.join(BUILD, "foreveryours_demo_v6.srt")
TIMELINE = os.path.join(HERE, "timeline.json")
MAX_SECONDS = 169.0     # under 2:50
FLAG_BY = 12.0          # the fall flag; v5's 5 s cannot hold once Dad speaks the line and it is heard
MAX_GAP = 1.5           # no silence this long outside the companion's own pauses
LIVE, LOCAL, CRISIS_LBL, CURLY = v5.LIVE, v5.LOCAL, v5.CRISIS_LBL, v5.CURLY
TAG, LBL = v5.TAG, v5.LBL
APPT_TAKE = os.environ.get("APPT_TAKE", "appt_t1")


def silences(wav, db=-40, d=MAX_GAP):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                          f"silencedetect=noise={db}dB:d={d}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends + [v2.probe_duration(wav)] * (len(starts) - len(ends))))


def main():
    os.makedirs(WORK, exist_ok=True)
    shots = {k: json.load(open(os.path.join(CAP, f"{k}.json"))) for k in ("fall", APPT_TAKE, "crisis", "day2")}
    dad_meta = json.load(open(os.path.join(DAD, "lines.json")))
    cache_p = os.path.join(WORK, "align.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    tl = v2.Timeline()
    seg = lambda name: os.path.join(WORK, f"seg_{len(tl.segments):02d}_{name}.mp4")  # noqa: E731
    dad_turns, pauses, badges, srt_only = [], [], [], []

    def replies(s):
        """The companion's reply streams of a capture (the other audio is the recorded clip echoed back)."""
        return [r for r in s["reply_audio"] if "/stream/" in r["playlist_url"]]

    def speech(turn):
        """(start, end) of Dad's words in clip seconds: the WAV's lead silence, then the line."""
        m = dad_meta[os.path.basename(turn["source_wav"])[:-4]]
        a = turn["mic_audio_start"] + m["lead_s"]
        return a, a + m["speech_s"]

    def narr(slot, at):
        wav = os.path.join(NARR, f"{slot}.wav")
        text = open(os.path.join(NARR, f"{slot}.caption.txt")).read()
        tl.audio.append((at, wav, "narrator"))
        for s, e, c in v2.timed_chunks(text, wav, cache):
            tl.caps.append((at + s, at + e, "Narrator", c))
        return v2.probe_duration(wav)

    def narr_between(slot, a, b, name):
        """A narration line centred in the gap [a, b] (timeline seconds); stops if it does not fit."""
        d = v2.probe_duration(os.path.join(NARR, f"{slot}.wav"))
        if d > b - a - 0.5:
            sys.exit(f"{name}: narration {slot} ({d:.2f}s) does not fit the {b - a:.2f}s wait")
        narr(slot, a + (b - a - d) / 2)

    def companion(wav, text, at):
        tl.audio.append((at, wav, "companion"))
        for s, e, c in v2.timed_chunks(text, wav, cache):
            tl.caps.append((at + s, at + e, "Companion", "Companion: " + c))
        for s, e in silences(wav, d=0.3):    # the companion's own pauses, as placed on the timeline
            pauses.append((round(at + s, 2), round(at + e, 2)))
        return v2.probe_duration(wav)

    def dad(turn, at, caption_end, hosted=True):
        """Dad's spoken line: his WAV at the moment the microphone played it, his caption = what was heard."""
        tl.audio.append((at, turn["source_wav"], "dad"))
        m = dad_meta[os.path.basename(turn["source_wav"])[:-4]]
        a = at + m["lead_s"]
        # On screen while he speaks, off before the narrator's caption comes up under it.
        tl.caps.append((a, min(caption_end, a + m["speech_s"] + 0.3), "Senior", "Dad: " + v2.clean(turn["heard"])))
        dad_turns.append({"heard": v2.clean(turn["heard"]), "intended": turn["intended"],
                          "source_wav": "dad_v6/" + os.path.basename(turn["source_wav"]),
                          "input": "live Space, browser microphone" if hosted else "local run, beat4 --audio",
                          "speech": [round(a, 2), round(a + m["speech_s"], 2)]})

    def hosted(a, b):
        badges.append((a, b))
        srt_only.append((a, min(b, a + v5.HOSTED_CUE_S), "Tag", f"[{LIVE}]"))

    # Shot 1: the fall, spoken. From just before Record; the narrator covers the hearing wait.
    s1 = shots["fall"]
    km, t1 = s1["key_moments"], s1["dad_turns"][0]
    ra = replies(s1)[0]
    A = km["fall_record_clicked"] - 0.5
    fall_wav, fall_text = v5.trim_reply(ra["path"], s1["reply"], 4, os.path.join(WORK, "fall_reply_cut.wav"), cache)
    end = ra["starts_playing_at"] + v2.probe_duration(fall_wav) + 0.6
    start = tl.t
    g1 = lambda t: start + t - A  # noqa: E731
    dad(t1, g1(t1["mic_audio_start"]), g1(ra["starts_playing_at"]))
    narr_between("n1", g1(speech(t1)[1]), g1(ra["starts_playing_at"]), "shot 1")
    companion(fall_wav, fall_text, g1(ra["starts_playing_at"]))
    flag_at = g1(km["fall_flag_visible"])
    if flag_at >= FLAG_BY:
        sys.exit(f"the caregiver flag appears at {flag_at:.2f}s, not before {FLAG_BY}s")
    tl.labels.append((flag_at, g1(end), "Label", *LBL, "Dad was told"))
    tl.add(seg("fall"), v2.seg_clip(seg("fall"), s1["clip"], A, end))
    tl.shots.append((1, start, tl.t))
    hosted(start, tl.t)

    # Shot 2: still of the split screen, slow zoom onto the panel's own "Dad was told" line.
    start = tl.t
    png = v2.grab_frame(s1["clip"], min(km["hold_end"] - 0.5, s1["duration"] - 0.5), os.path.join(WORK, "hold.png"))
    im = Image.open(png).convert("RGB")
    box = os.environ.get("FY_TOLD_BOX")
    if box:
        ImageDraw.Draw(im).rounded_rectangle(tuple(int(x) for x in box.split(",")), radius=7,
                                             outline=(38, 122, 30), width=3)
    im.save(os.path.join(WORK, "hold_marked.png"))
    dur2 = 0.4 + v2.probe_duration(os.path.join(NARR, "n2.wav")) + 0.6
    narr("n2", start + 0.4)
    zoom = tuple(int(x) for x in os.environ.get("FY_ZOOM_RECT", "1010,330,864,486").split(","))
    tl.add(seg("zoom"), v2.seg_zoom(seg("zoom"), os.path.join(WORK, "hold_marked.png"), dur2, zoom, 1.0, 6.0))
    tl.shots.append((2, start, tl.t))
    hosted(start, tl.t)

    # Shot 3: the caregiver types and saves the appointment memo (her typing, under the narrator).
    s4 = shots[APPT_TAKE]
    if not s4.get("check", {}).get("pass"):
        sys.exit(f"{APPT_TAKE} did not pass its check: {s4.get('check')}")
    k4 = s4["key_moments"]
    A3, B3 = 2.4, k4["memo_framed"] + 1.0
    start = tl.t
    if 0.6 + v2.probe_duration(os.path.join(NARR, "n3.wav")) > B3 - A3 - 0.2:
        sys.exit("shot 3 narration runs past the memo shot")
    narr("n3", start + 0.6)
    tl.add(seg("memo"), v2.seg_clip(seg("memo"), s4["clip"], A3, B3))
    tl.shots.append((3, start, tl.t))
    hosted(start, tl.t)

    # Shot 4: same session, a jump cut past the memo hold to the split screen; Dad asks aloud.
    t4 = s4["dad_turns"][0]
    ra = replies(s4)[0]
    A4, B4 = k4["split_framed"] - 1.2, ra["starts_playing_at"] + ra["duration"] + 0.15
    start = tl.t
    g4 = lambda t: start + t - A4  # noqa: E731
    n4a = v2.probe_duration(os.path.join(NARR, "n4a.wav"))
    if start + 0.2 + n4a > g4(speech(t4)[0]) - 0.2:
        sys.exit("shot 4: the first narration line runs into Dad's question")
    narr("n4a", start + 0.2)
    dad(t4, g4(t4["mic_audio_start"]), g4(ra["starts_playing_at"]))
    narr_between("n4b", g4(speech(t4)[1]), g4(ra["starts_playing_at"]), "shot 4")
    companion(ra["path"], s4["reply"], g4(ra["starts_playing_at"]))
    tl.add(seg("ask"), v2.seg_clip(seg("ask"), s4["clip"], A4, B4))
    tl.shots.append((4, start, tl.t))
    hosted(start, tl.t)

    # Shot 5: a private line (no flag), a short freeze, a jump cut to the crisis line.
    s5 = shots["crisis"]
    k5 = s5["key_moments"]
    tl5, tc5 = s5["dad_turns"]
    r1, r2 = replies(s5)
    crisis_wav, crisis_text = v5.trim_reply(r2["path"], s5["reply"][1], 3,
                                            os.path.join(WORK, "crisis_reply_cut.wav"), cache)
    A5 = k5["lonely_record_clicked"] - 0.1
    CUT, FREEZE = r1["starts_playing_at"] + r1["duration"] + 0.05, 0.25
    RESUME = k5["crisis_record_clicked"]
    B5 = r2["starts_playing_at"] + v2.probe_duration(crisis_wav) + 0.8
    start = tl.t
    g = lambda t: start + (t - A5) if t < CUT else start + (CUT - A5) + FREEZE + (t - RESUME)  # noqa: E731
    dad(tl5, g(tl5["mic_audio_start"]), g(r1["starts_playing_at"]))
    narr_between("n5a", g(speech(tl5)[1]), g(r1["starts_playing_at"]), "shot 5 private")
    companion(r1["path"], s5["reply"][0], g(r1["starts_playing_at"]))
    # The privacy label ends when the freeze before the crisis line starts.
    tl.labels.append((g(k5["lonely_reply_text_visible"]), g(CUT - 0.001), "LabelGrey", *LBL,
                      "Not shown to the family"))
    tl.labels.append((g(k5["crisis_flag_visible"]), g(B5), "Crisis", LBL[0], LBL[1] - 28, CRISIS_LBL))
    dad(tc5, g(tc5["mic_audio_start"]), g(r2["starts_playing_at"]))
    narr_between("n5b", g(speech(tc5)[1]), g(r2["starts_playing_at"]), "shot 5 crisis")
    companion(crisis_wav, crisis_text, g(r2["starts_playing_at"]))
    tl.add(seg("lonely"), v2.seg_clip(seg("lonely"), s5["clip"], A5, CUT))
    tl.add(seg("freeze"), v2.seg_still(seg("freeze"), v2.grab_frame(s5["clip"], CUT, os.path.join(WORK, "cut.png")), FREEZE))
    tl.add(seg("crisis"), v2.seg_clip(seg("crisis"), s5["clip"], RESUME, B5))
    tl.shots.append((5, start, tl.t))
    hosted(start, tl.t)

    # Shot 6: day 2, the local run, on a clean card; Dad's question and the reply are its own audio.
    s6 = shots["day2"]
    card6 = v2.card(os.path.join(WORK, "card6.png"), [
        (LOCAL, 72, True),
        ("Day 2: a fresh local run still remembers yesterday's briefing", 46, False),
    ])
    start = tl.t
    n6 = narr("n6", start + 0.4)
    turn6 = {"source_wav": s6["source_wav"], "heard": s6["heard"], "intended": s6["heard"]}
    at_dad = start + 0.4 + n6 + 0.4 - dad_meta["dad_grandson"]["lead_s"]
    dad_end = at_dad + dad_meta["dad_grandson"]["lead_s"] + dad_meta["dad_grandson"]["speech_s"]
    rep6_wav, rep6_text = v5.trim_reply(s6["reply_audio"], s6["companion_reply"], 1,
                                        os.path.join(WORK, "day2_reply_cut.wav"), cache)
    at_rep = dad_end + 0.5
    dad(turn6, at_dad, at_rep, hosted=False)
    day2_end = at_rep + companion(rep6_wav, rep6_text, at_rep) + 0.6 - start
    srt_only.append((start, start + day2_end, "Tag", f"[{LOCAL}]"))
    tl.add(seg("day2"), v2.seg_still(seg("day2"), card6, day2_end))
    tl.shots.append((6, start, tl.t))

    # Shots 7-8: plain text cards.
    for n, png, tail in (
        (7, v2.card(os.path.join(WORK, "card7.png"), [(ln, 54, False) for ln in v5.STACK_LINES]), 0.5),
        (8, v2.card(os.path.join(WORK, "card8.png"), [("ForeverYours", 118, True),
                                                       ("The companion the family briefs", 54, False),
                                                       ("Try it yourself, no login", 48, False),
                                                       (v2.URL, 70, True),
                                                       ("Known limitations: in the README", 46, False)]), 1.2),
    ):
        start = tl.t
        dur = 0.4 + v2.probe_duration(os.path.join(NARR, f"n{n}.wav")) + tail
        narr(f"n{n}", start + 0.4)
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
    # Dad's WAVs carry lead/tail silence, so compare the spoken parts only.
    def voiced(sp):
        a, b, kind, name = sp
        if kind == "dad":
            m = dad_meta[name[:-4]]
            return a + m["lead_s"], a + m["lead_s"] + m["speech_s"]
        return a, b
    vs = sorted((*voiced(sp), sp[2], sp[3]) for sp in spans)
    for p, q in zip(vs, vs[1:]):
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
    gaps = [(a, b) for a, b in silences(mixed)
            if not any(pa - 0.05 <= a and b <= pb + 0.05 for pa, pb in pauses)]
    if gaps:
        sys.exit(f"dead air (>= {MAX_GAP}s at -40 dB) outside the companion's pauses: {gaps}")

    # ---- captions: ASS (burned in) and SRT (sidecar), both from this timeline
    events = sorted(tl.caps)
    ass = os.path.join(WORK, "captions.ass")
    with open(ass, "w") as fh:
        fh.write(v5.ASS_HEAD)
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
    r2f = lambda xs: [round(x, 2) for x in xs]  # noqa: E731
    json.dump({
        "video": "foreveryours_demo_v6.mp4", "duration": round(dur, 2), "lufs": lufs, "true_peak": peak,
        "flag_at": round(flag_at, 2),
        "captures": {k: shots[k].get("captured_at", "local run") for k in shots},
        "shots": [[n, round(a, 2), round(b, 2)] for n, a, b in tl.shots],
        "dad_turns": dad_turns,
        "companion_pauses": [list(p) for p in sorted(set(pauses))],
        "labels": [[round(a, 2), round(b, 2), text.replace("\\N", " ")] for a, b, _, _, _, text in tl.labels],
        "audio": [[*r2f(sp[:2]), sp[2], sp[3]] for sp in spans],
    }, open(TIMELINE, "w"), indent=1)
    print(f"\nFINAL {FINAL}\n  duration {dur:.2f}s ({int(dur // 60)}:{dur % 60:05.2f})"
          f"\n  loudness {lufs} LUFS, true peak {peak} dBTP\nSRT {SRT}\nTIMELINE {TIMELINE}")
    if dur >= MAX_SECONDS + 1 or peak > -1.5 or abs(lufs - TARGET_LUFS) > 1.0:
        sys.exit("final video failed checks")


if __name__ == "__main__":
    main()
