"""Generate 1920x1080 PNG slides for the non-terminal beats.

Ported approach from competitions/agents-for-humans/video/generate_slides.py
(Pillow, DejaVu Sans Mono, GitHub-dark palette). The beat1/beat3/day2 beats
are NOT slides -- they're real recorded terminal segments (render_terminal.py).
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_SLIDES = os.path.join(os.path.dirname(__file__), "output/slides")
os.makedirs(OUTPUT_SLIDES, exist_ok=True)

W, H = 1920, 1080
BG = (13, 17, 23)
WHITE = (230, 237, 243)
YELLOW = (255, 215, 0)
CYAN = (86, 182, 194)
GREEN = (87, 242, 135)
GRAY = (139, 148, 158)
ORANGE = (255, 123, 114)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(MONO_BOLD if bold else MONO, size)


def new_img():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def center_x(draw, text, y, fnt, color=WHITE):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, y), text, font=fnt, fill=color)


def save(img, name):
    path = os.path.join(OUTPUT_SLIDES, name)
    img.save(path)
    print(f"  Saved {path}")


# ── problem ──────────────────────────────────────────────────────────────────
print("Generating slide_problem.png ...")
img, d = new_img()
center_x(d, "ForeverYours", 90, font(80, bold=True), WHITE)
center_x(d, "The companion the family briefs -- your voice in Dad's day", 200, font(36), GRAY)
center_x(d, "when you can't be there.", 248, font(36), GRAY)

box_x0, box_y0, box_x1, box_y1 = 300, 340, W - 300, 680
d.rectangle([(box_x0, box_y0), (box_x1, box_y1)], outline=GRAY, width=2)
d.rectangle([(box_x0, box_y0), (box_x1, box_y0 + 44)], fill=(30, 36, 45))
d.text((box_x0 + 20, box_y0 + 8), "The caregiver's problem", font=font(26, bold=True), fill=YELLOW)

lines = [
    "A caregiver can't be there for every conversation.",
    "A general chatbot remembers for whoever's talking to it --",
    "it has no concept of the person who ISN'T there.",
    "",
    "ForeverYours is briefed by the caregiver, and never reports",
    "anything to the family it hasn't first said to him out loud.",
]
ly = box_y0 + 74
for line in lines:
    d.text((box_x0 + 30, ly), line, font=font(30), fill=WHITE)
    ly += 46

center_x(d, "This is a proof-of-concept, shown exactly as it runs -- nothing staged.",
         box_y1 + 60, font(30), CYAN)
save(img, "slide_problem.png")


# ── pipeline ─────────────────────────────────────────────────────────────────
print("Generating slide_pipeline.png ...")
img, d = new_img()
center_x(d, "The pipeline", 70, font(56, bold=True), WHITE)

stages = [
    ("HEAR", "speech to text", CYAN),
    ("fast-path safety check", "rule-based, instant, no API key needed", ORANGE),
    ("RECALL", "memory, scoped to what the caregiver briefed", CYAN),
    ("THINK", "open-weight NVIDIA model via Nebius Token Factory", GREEN),
    ("SPEAK", "text to speech, streamed", CYAN),
    ("AUDIT (background)", "safety re-check + memory extraction, off the critical path", GRAY),
]
y = 220
for name, sub, color in stages:
    d.rectangle([(280, y), (W - 280, y + 110)], outline=color, width=3)
    d.text((320, y + 16), name, font=font(36, bold=True), fill=color)
    d.text((320, y + 64), sub, font=font(24), fill=GRAY)
    y += 130
save(img, "slide_pipeline.png")


# ── close ────────────────────────────────────────────────────────────────────
print("Generating slide_close.png ...")
img, d = new_img()
center_x(d, "What's next", 70, font(56, bold=True), WHITE)

points = [
    "Full conversation (THINK) -- waiting on a live Nebius Token Factory key.",
    "Browser demo: senior side + caregiver side, both live, side by side.",
    "Hosted link, for anyone to try -- not just this recording.",
]
y = 220
for p in points:
    d.text((300, y), "•  " + p, font=font(34), fill=CYAN)
    y += 70

d.line([(240, 480), (W - 240, 480)], fill=GRAY, width=2)
center_x(d, "What's true right now", 520, font(44, bold=True), WHITE)

d.rectangle([(300, 610), (W - 300, 710)], outline=GREEN, width=3)
d.text((340, 632), "Disclosure is a hard invariant, not a policy promise.", font=font(30, bold=True), fill=GREEN)
d.text((340, 672), "Every safety flag is marked disclosed only if the senior was actually told.", font=font(24), fill=GRAY)

d.rectangle([(300, 740), (W - 300, 840)], outline=ORANGE, width=3)
d.text((340, 762), "Memory survives across separate process runs.", font=font(30, bold=True), fill=ORANGE)
d.text((340, 802), "Not in-memory-per-run -- proven with a genuinely separate process.", font=font(24), fill=GRAY)

center_x(d, "github.com/miravena/foreveryours", 920, font(34, bold=True), WHITE)
save(img, "slide_close.png")

print("All slides generated.")
