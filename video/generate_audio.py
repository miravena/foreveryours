"""Generate one gTTS voiceover MP3 per beat for the ForeverYours demo video.

Ported approach from competitions/agents-for-humans/video/generate_audio.py
(same gTTS, one MP3 per beat). Narration follows app/docs/DEMO_SCRIPT.md.
Honest framing throughout: this says explicitly what's real (beat1/beat3/
day2, no key needed) and what's still pending (the full conversational
turn, which needs a live Nebius key nobody has tried yet).
"""
import os
from gtts import gTTS

OUTPUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT, exist_ok=True)

BEATS = [
    ("problem", (
        "Caregivers of older adults juggle two jobs at once: staying present "
        "for their parent, and not missing a warning sign from far away. "
        "ForeverYours is a voice companion a caregiver briefs once, so the "
        "senior gets a warm conversation that actually uses that context, and "
        "the caregiver gets honest safety flags -- never silent surveillance. "
        "This video shows the proof-of-concept exactly as it runs today, with "
        "no editing of what you'll see on screen."
    )),
    ("pipeline", (
        "The pipeline: speech to text, then a rule-based safety check that "
        "runs before anything else, instantly, with no API key needed. Then "
        "memory recall, scoped to what the caregiver actually briefed. Then "
        "an open-weight NVIDIA model, via Nebius Token Factory, generates the "
        "reply. Then text to speech. And in the background, a safety audit "
        "and memory extraction run without slowing down the reply."
    )),
    ("beat1", (
        "First, the caregiver briefing. One memo -- Dad loves jazz, his "
        "grandson is Leo, avoid talking about driving, and a note about "
        "groceries today. This is the real command-line tool, running live, "
        "right now. Watch the memory panel underneath: those facts are saved "
        "and ready to be recalled in conversation."
    )),
    ("beat3", (
        "Now, the moment that's actually the point of this product. The "
        "senior says something worrying -- 'I fell down earlier and I'm "
        "scared.' A rule-based safety check catches this instantly, no model "
        "call needed. The companion speaks an immediate, honest reassurance, "
        "and tells him, out loud, in this exact sentence, that it's letting "
        "his family know right now. Not a silent log file. A caregiver flag "
        "is recorded as disclosed, because it was -- in the conversation you "
        "just heard."
    )),
    ("day2", (
        "One more thing worth proving: memory has to survive more than one "
        "conversation. This command runs as a completely separate process, "
        "with no memory of the one that ran a moment ago -- and it still "
        "recalls everything the caregiver briefed, read straight from disk. "
        "That's not a trick; that's just what persistence means."
    )),
    ("close", (
        "What you didn't see here yet: the full back-and-forth conversation, "
        "powered by that open-weight NVIDIA model -- we're still waiting on "
        "a live Nebius Token Factory key to light that part up for real, and "
        "we'd rather show you the honest, working parts than fake the rest. "
        "A browser version of this exists too, with both the senior's side "
        "and the caregiver's side on screen at once, updating live. That's "
        "next. Thanks for watching."
    )),
]


def main():
    for key, text in BEATS:
        out_path = os.path.join(OUTPUT, f"beat_{key}.mp3")
        print(f"Generating beat_{key}.mp3 ...")
        gTTS(text=text, lang="en", tld="com", slow=False).save(out_path)
        print(f"  Saved {out_path}")
    print("All audio generated.")


if __name__ == "__main__":
    main()
