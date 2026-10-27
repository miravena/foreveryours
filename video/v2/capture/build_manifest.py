"""Merge the per-shot JSON written by capture.mjs and day2.py into <out_dir>/manifest.json.

Usage: python3 video/v2/capture/build_manifest.py <out_dir>
Shots 3 and 4 come from the appt_t<n>.json runs (memo saved, then the senior question, one
session each); shot 4 is marked verified only when all of at least three fresh-session runs
passed (docs/VIDEO_SCRIPT.md, "Senior line").
"""
import glob
import json
import os
import re
import sys


def load(out, tag):
    p = os.path.join(out, f"{tag}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def audio(d):
    return [{"path": a["path"], "duration": a["duration"], "starts_playing_at": a["starts_playing_at"],
             "first_served_at": a["first_served_at"]} for a in d.get("reply_audio", [])]


def main():
    out = os.path.abspath(sys.argv[1])
    shots = {}
    fall = load(out, "fall")
    if fall:
        shots["1_fall"] = {"clip": fall["clip"], "duration": fall["duration"],
                           "key_moments": fall["key_moments"], "senior_text": fall["senior_text"],
                           "companion_reply": fall["reply"], "reply_audio": audio(fall)}
        shots["2_hold_on_flag"] = {"clip": fall["clip"], "same_clip_as": "1_fall",
                                   "use_from": fall["key_moments"]["fall_flag_visible"],
                                   "use_to": fall["key_moments"]["hold_end"],
                                   "note": "steady hold of the split screen; zoom on 'Dad was told' at assembly"}
    # Shots 3 and 4 come from one session (capture.mjs shot "appt"): the appointment memo is
    # saved, then the senior asks about it. Each appt_t<n>.json is one fresh-session run; the
    # line counts as verified only when every run (at least three) passed. The take used is
    # APPT_TAKE (default: the last passing run).
    runs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, "appt_t*.json")))]
    if runs:
        passes = [r for r in runs if r["check"]["pass"]]
        verified = len(runs) >= 3 and len(passes) == len(runs)
        take = next((r for r in runs if r["tag"] == os.environ.get("APPT_TAKE")), passes[-1] if passes else runs[-1])
        km = take["key_moments"]
        shots["3_memo"] = {"clip": take["clip"], "duration": take["duration"], "take": take["tag"],
                           "key_moments": {k: km[k] for k in ("ready", "memo_saved_clicked", "memo_visible",
                                                             "memo_framed", "memo_hold_end")},
                           "memo_text": take["memo_text"]}
        shots["4_senior_line"] = {
            "verified": verified, "passes": f"{len(passes)}/{len(runs)}", "take": take["tag"],
            "clip": take["clip"], "same_clip_as": "3_memo", "duration": take["duration"],
            "key_moments": {k: km[k] for k in ("split_framed", "senior_send_clicked", "senior_reply_text_visible",
                                              "senior_reply_text_complete", "hold_end")},
            "senior_text": take["senior_text"], "companion_reply": take["reply"], "reply_audio": audio(take),
            "runs": [{"tag": r["tag"], "check": r["check"], "toasts": r["toasts"], "companion_reply": r["reply"]}
                     for r in runs]}
    crisis = load(out, "crisis")
    if crisis:
        shots["5_private_then_crisis"] = {
            "clip": crisis["clip"], "duration": crisis["duration"], "key_moments": crisis["key_moments"],
            "senior_text": crisis["senior_text"], "companion_reply": crisis["reply"],
            "reply_audio": audio(crisis),
            "no_new_flag_after_lonely": "Dad was told" not in crisis["panel_after_lonely"]}
    day2 = load(out, "day2")
    if day2:
        shots["6_day2_local"] = {"clip": day2["clip"], "duration": day2["duration"], "cast": day2["cast"],
                                 "senior_text": day2["senior_text"],
                                 "companion_reply": re.search(r'Companion replied: "(.*?)"',
                                                              day2["terminal_output"]).group(1),
                                 "caption": "Day 2 (local run)"}
    manifest = {"space": "https://elevenbaselab-foreveryours.hf.space",
                "times_are": "seconds from the start of each clip", "shots": shots}
    with open(os.path.join(out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    print(os.path.join(out, "manifest.json"))


if __name__ == "__main__":
    main()
