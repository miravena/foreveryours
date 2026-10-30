# Video script and shot list (under 3:00)

The demo video for the submission. It follows the issue #5 rules and the requirements in
[`HACKATHON_RULES.md`](HACKATHON_RULES.md) item 7: less than 3 minutes, public on YouTube, no
third-party trademarks or copyrighted music. Rehearse locally (`python webapp.py`); record on
the hosted Space, https://elevenbaselab-foreveryours.hf.space, so a judge can repeat every shot.

**Setup:** one browser window on the Space, split screen, Senior side on the left and
Caregiver side on the right, 1080p. Narration is AI-generated: Kokoro TTS (Apache-2.0), voice
af_heart, one WAV per shot, so a human narrator can replace the track shot by shot without
re-editing the picture (`video/v4/README.md`). The companion's voice is the Space's own reply
audio. No title card, no statistics, no music, no diagram.

**What the judges said they score** (Devpost "Will It Ship?" session, 2026-10-20, applied here):
the aha moment inside 30 seconds (shot 1, inside 10 seconds), show which model is doing what
(shots 4 and 7), publish the limitations (shot 8), one thing done well rather than a stack (no
feature tour).

## Shot list

This is the v6 cut (#304): the v5 shot order and labels (#275) with Dad speaking every line into
the live Space's microphone instead of typing it, and the narrator over every hearing and model
wait. How it is built: [`video/v6/README.md`](../video/v6/README.md).

| Time | Screen | Narrator (AI voice, Kokoro af_heart) |
|---|---|---|
| 0:00-0:19 | Senior side: Record is clicked and Dad says "I fell down earlier and I'm scared." (his voice is heard). Stop, Send; the Space hears him and the transcript shows "Dad said: ...". The Caregiver side lights up at 0:10: the safety flag, labelled a simulated caregiver alert shown on this demo panel, and **✅ Dad was told**. The companion's reply is cut after "I'm letting your family know right now so someone can check on you." | Over the hearing wait: "That was Dad, speaking out loud. He can also type, if he prefers." |
| 0:19-0:33 | Hold on the split screen, then a slow zoom on the panel's own "Dad was told" line. | "ForeverYours is a voice companion for Dad, briefed by his family. When his safety is at stake, it raises a flag for his daughter, and tells him first, out loud. Everything else he says stays between them." |
| 0:33-0:42 | Caregiver side: the daughter types the memo "Dad has a check-up with Dr. Tan on Thursday at 10 AM." and clicks Save Text Memo. The briefed memory shows it added. The narrator speaks over the typing. | "His daughter briefs it once, from work. One line: a check-up with Dr. Tan on Thursday. Nothing to set up on Dad's side." |
| 0:42-1:02 | Same session, split screen: Dad asks aloud "Do I have any doctor's appointments this week?", then the real hearing and model wait, uncut; the reply names Dr. Tan, Thursday, 10 AM. | Before he asks: "When Dad asks, it already knows what she typed." Over the wait: "The reply is written by NVIDIA Nemotron on Nebius Token Factory." |
| 1:02-1:40 | Senior side: Dad says "I feel lonely since my wife died." The companion answers warmly; the Caregiver side shows no new flag and none of his words. A short freeze, then he says "I want to end my life." The safety fast path answers with the 988 referral and the Caregiver side shows the crisis flag; the reply is cut after "I am also letting your family know you are in distress." | Over the first wait: "What he says in private stays private. His daughter sees no flag, and none of his words." Over the second: "Here, the safety rules answer before any model is called." |
| 1:40-1:50 | Day 2: a clean card reading "Local persistence test - not the hosted Space." with the line "Day 2: a fresh local run still remembers yesterday's briefing". Dad's question "I forgot, what is my grandson's name?" and the answer "Leo. Sarah mentioned your grandson Leo." are heard and captioned; behind the card is `python main.py beat4 --audio` with his recorded question, in a fresh process. | "In a fresh local run the next day, it remembers yesterday's briefing." |
| 1:50-2:07 | Plain screen, text only: "Replies: NVIDIA Nemotron 3 Nano · Safety backstop: NVIDIA Nemotron 3 Super, both on Nebius Token Factory" · "Hearing and voice: on the app's own server". No diagram, no logos. | "Two models on Nebius Token Factory: Nemotron 3 Nano writes the replies, and Nemotron 3 Super is the safety backstop. Hearing and voice run on the app's own server, so his voice recording never goes to Nebius." |
| 2:07-2:19 | Plain screen: "ForeverYours", "The companion the family briefs", the Space URL, https://elevenbaselab-foreveryours.hf.space, and "Known limitations: in the README". | "This is a prototype: it can miss nuance, so it does not replace human judgment or emergency services. Try it yourself, no login, at the link on screen." |

Total: 2:19, under 2:50. The companion's replies are cut only at the end of a
sentence and never overlap the narrator. Times are the plan; the assembler prints the real
shot boundaries.

**Footage.** Shots 1-5 are real browser sessions on the live Space, re-captured for v6 on
2026-10-30 after the #198 deploy, so the replies are the current build's. Dad's lines are spoken:
Kokoro voice am_michael, played into the browser microphone, heard by the Space's own speech
recognition. Shot 6 is one local run that hears the same voice. How each clip is captured and
cut: [`video/v6/README.md`](../video/v6/README.md).

**Narration pace.** Every line is rendered at one Kokoro speed, 0.9, with a 0.4 s gap between
sentences (`wpm` per line in `video/v4/lines.json`). v3 reached 150-160 wpm by slowing the
voice to 0.76-0.83, which drags; v4 keeps the voice natural and shortens the lines instead.
Every wait (the memo being typed, the Space hearing Dad, the hosted reply) carries the narration;
the v6 build stops if the mix has a silence of 1.5 s or more outside the companion's own pauses.

## Senior line (0:41-1:03)

The sample household is pre-briefed (jazz, Leo, no driving, groceries at 4 PM), so shot 3 adds a
fact it does not already hold, and shot 4 asks about that fact. The shot uses only a senior line
that has passed this check on the live Space: in a fresh session the memo "Dad has a check-up
with Dr. Tan on Thursday at 10 AM." is saved, then the line is sent; three such sessions, and
every reply names Dr. Tan, Thursday and 10 AM and states nothing absent from the briefed memory.
Transcripts of each check are in [`WORK_LOG.md`](WORK_LOG.md) under "VIDEO_SCRIPT appointment
line check".

Senior line: "Do I have any doctor's appointments this week?" (3 of 3 runs passed)

Verified reply (v3 take, re-captured for #261): "You have a check-up with Dr. Tan on Thursday at 10 AM." The other two runs: "Yes. Sarah mentioned you have a check-up with Dr. Tan on Thursday at 10 AM." and "You have a check-up with Dr. Tan on Thursday at 10 a.m. Let me know if you'd like a reminder."

(The groceries visit is in the sample household's pre-brief, so the reply invents nothing.)

These lines were checked and do not qualify:

- "Do I have any appointments this week?" (2 of 3: the third reply said "no appointments listed"
  with the memo saved)
- "I was listening to some music earlier." (the original jazz clip), "I was thinking about my
  family today. Is anyone coming by?", "Is anyone coming by today? I miss the little ones.",
  and other open lines against the earlier memo: replies named the 4 PM groceries but not
  reliably Leo, and some invented family facts (#245).

## Captions

The video must make sense with the sound off. Every narrator line and every companion line is
burned in verbatim as spoken, plus the senior's lines. Captions break at sentence ends, never
after an abbreviation such as "Dr." (a v3 caption read "...check-up with Dr." / "Tan on
Thursday..."). On-screen labels:

| Time | Label |
|---|---|
| 0:00-1:40 | **LIVE HOSTED SPACE**, a small burned-in badge, top right, on every shot recorded on the Space; in the SRT it is one 4-second cue at the start of each hosted shot, never one long cue |
| 0:10-0:19 | **Dad was told · simulated alert, nothing sent**, once, from the frame the caregiver flag appears; no other overlay repeats it (v6b) |
| 1:13-1:20 | **Not shown to the family** over the unchanged Caregiver side after the private line; it ends when the freeze before the crisis line starts, so it is never on screen over "I want to end my life." |
| 1:29-1:40 | **Crisis: 988 offered · simulated alert, nothing sent** from the frame the crisis flag appears to the end of the shot, so the video never implies the crisis is hidden from the family |
| 1:40-1:50 | The day-2 card, whose text is the label: **Local persistence test - not the hosted Space.** (the SRT carries it too) |
| 1:50-2:19 | The card text is the caption; narrator caption below it |

The same captions and labels ship as a sidecar `.srt` built from the same timeline.

## Recording tips

1. **Resolution:** 1080p browser capture at about 110% zoom so the flag and "Dad was told" are
   readable on a phone.
2. **Audio:** the narrator track is one WAV per shot (AI voice, or a human recording dropped in
   under the same file names); let the companion's voice play in full in the fall and crisis
   shots. No background music.
3. **Cursor:** slow, deliberate clicks. Pause two seconds on the split-screen flag so both
   sides can be read.
4. **Keep the Space awake** before recording; a cold first click can hang.
5. **Full-screen the browser** (F11) so the address bar and the hosting site's header are out of
   frame; the URL appears once, as text, in the last shot. The phone-first recording checklist
   (narration first, one continuous take, edit, public upload with a caption file) is on issue #5.

## Compliance checklist

Checked against #264's criteria, the issue #5 rules, [`SELF_JUDGING.md`](SELF_JUDGING.md) and
[`PRIVACY.md`](PRIVACY.md).

- Opens on the product moment: Dad speaks at 0:01 and the caregiver flag and "Dad was told" are on screen at 0:10 (v5, typed: 0:04); no title card.
- Narrative order: fall hook, one-sentence thesis, caregiver briefing, ordinary recall, private boundary, crisis/988, next-day recall, stack/privacy/URL close.
- No broad claim about other assistants: the thesis says what this one does (briefed by his family, raises a flag for his daughter when his safety is at stake, tells him first); no product is named.
- The alert is described as a flag raised for his daughter, which is what the panel shows (a simulated alert; nothing is sent in the demo), not as a message delivered.
- One "Dad was told" overlay, aligned with the flag; the crisis shot relies on the panel's own line.
- Hosted and local evidence labelled where they appear: LIVE HOSTED SPACE (corner badge) on shots 1-5, "Local persistence test - not the hosted Space." on the shot 6 card.
- Captions and the SRT use straight quotes only: a player that reads the SRT as cp1252 turns a curly apostrophe into mojibake (#275).
- The crisis shot says what the panel shows: 988 offered, a simulated family alert; no claim that anyone is contacted or that a notification is delivered.
- Day-2 shot 15 seconds or less: 10 seconds, on a clean card with no terminal and no audit line.
- No AUDIT, biomarkers, proactive triggers, phone-notification shot, latency figure or music; the only names on screen are the sponsors' (NVIDIA, Nebius) in plain text. The narration voice is Kokoro (Apache-2.0).
- Privacy wording matches PRIVACY.md: speech runs on the app's own server and the voice recording never goes to Nebius.
- Limitations stated: the closing line is self-contained ("This is a prototype: it can miss nuance, so it does not replace human judgment or emergency services."), and the last card still points at the README's "Known limitations".
- The product's name is on screen in the last card, with the URL.
