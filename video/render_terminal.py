"""Render a real asciinema v2 cast into a 1920x1080 terminal MP4.

Ported near-verbatim from competitions/agents-for-humans/video/render_terminal.py
(generic cast-to-mp4 rendering, no Claims-Copilot-specific content). Replays the
ACTUAL recorded cast (video/casts/*.cast) through pyte (a VT100 emulator) and
rasterises the visible screen with Pillow -- nothing here is typed or mocked;
every character on screen came out of the recorded `python main.py <beat>` run.

Usage: render_terminal.py <cast_path> <out_mp4> <duration_seconds>
"""
import json
import os
import subprocess
import sys

import pyte
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 15
BG = (13, 17, 23)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

_FONT_CACHE = {}


def _font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]

COLORS = {
    "default": (230, 237, 243), "black": (48, 54, 61), "red": (255, 123, 114),
    "green": (87, 242, 135), "brown": (255, 215, 0), "yellow": (255, 215, 0),
    "blue": (121, 192, 255), "magenta": (210, 168, 255), "cyan": (86, 182, 194),
    "white": (230, 237, 243), "brightblack": (139, 148, 158),
}


def color_for(name, default=(230, 237, 243)):
    if not name or name == "default":
        return default
    if isinstance(name, str) and len(name) == 6:
        try:
            return tuple(int(name[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return COLORS.get(name, default)


def load_cast(path):
    with open(path) as fh:
        lines = fh.read().splitlines()
    header = json.loads(lines[0])
    cols = int(header.get("width", 100))
    rows = int(header.get("height", 32))
    events = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        t, kind, data = json.loads(ln)
        if kind == "o":
            events.append((float(t), data))
    return cols, rows, events


def fit_font(cols, rows):
    margin_x, margin_top = 60, 80
    for size in range(30, 9, -1):
        f = ImageFont.truetype(FONT_PATH, size)
        bbox = f.getbbox("M")
        cw = f.getlength("M")
        ch = (bbox[3] - bbox[1]) + 6
        if cols * cw <= (W - 2 * margin_x) and rows * ch <= (H - margin_top - 40):
            return size, cw, ch
    return 10, ImageFont.truetype(FONT_PATH, 10).getlength("M"), 18


def render_screen(screen, size, cw, ch):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f = _font(FONT_PATH, size)
    fb = _font(FONT_BOLD, size)
    d.rectangle([(0, 0), (W, 46)], fill=(30, 36, 45))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([(24 + i * 34, 14), (44 + i * 34, 34)], fill=c)
    title = "foreveryours demo"
    d.text(((W - fb.getlength(title)) / 2, 12), title, font=_font(FONT_BOLD, 22),
           fill=(180, 190, 200))

    margin_x, margin_top = 60, 70
    y = margin_top
    for row in range(screen.lines):
        line = screen.buffer[row]
        x = margin_x
        for col in range(screen.columns):
            ch_cell = line[col]
            char = ch_cell.data or " "
            if char != " ":
                color = color_for(ch_cell.fg)
                font = fb if ch_cell.bold else f
                d.text((x, y), char, font=font, fill=color)
            x += cw
        y += ch
    return img


def main():
    cast_path, out_mp4, duration = sys.argv[1], sys.argv[2], float(sys.argv[3])
    frames_dir = out_mp4.replace(".mp4", "_frames")
    os.makedirs(frames_dir, exist_ok=True)
    for old in os.listdir(frames_dir):
        os.remove(os.path.join(frames_dir, old))

    cols, rows, events = load_cast(cast_path)
    size, cw, ch = fit_font(cols, rows)
    print(f"  cast {cols}x{rows}, font {size}px, {len(events)} output events")

    cast_dur = events[-1][0] if events else 1.0
    total_frames = int(duration * FPS)
    play_frames = int(min(duration, max(duration * 0.82, duration - 2)) * FPS)

    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)
    ev_idx = 0
    prev_signature = None
    prev_path = None
    for fi in range(total_frames):
        if fi < play_frames:
            cast_t = (fi / max(1, play_frames - 1)) * cast_dur
        else:
            cast_t = cast_dur
        changed = False
        while ev_idx < len(events) and events[ev_idx][0] <= cast_t:
            stream.feed(events[ev_idx][1])
            ev_idx += 1
            changed = True
        path = os.path.join(frames_dir, f"frame_{fi:05d}.png")
        signature = tuple(screen.display) if hasattr(screen, "display") else None
        if prev_path is not None and signature == prev_signature and not changed:
            try:
                os.link(prev_path, path)
            except OSError:
                render_screen(screen, size, cw, ch).save(path)
        else:
            render_screen(screen, size, cw, ch).save(path)
        prev_signature = signature
        prev_path = path
        if fi % 100 == 0:
            print(f"  frame {fi}/{total_frames}")

    print("  encoding ...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", out_mp4,
    ], check=True)
    print(f"  done: {out_mp4}")


if __name__ == "__main__":
    main()
