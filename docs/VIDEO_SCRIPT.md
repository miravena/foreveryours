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
the aha moment inside 30 seconds (shot 1, inside 5 seconds), show which model is doing what
(shots 4 and 7), publish the limitations (shot 8), one thing done well rather than a stack (no
feature tour).

## Shot list

This is the v4 cut (#264): the v3 footage with the narration rewritten so that no hosted wait
is silent, the narrator reads at a natural speed, and the close names the product. The v3
script is this file at the v3 build's commit.

| Time | Screen | Narrator (AI voice, Kokoro af_heart) |
|---|---|---|
| 0:00-0:13 | Senior side, the line already typed: "I fell down earlier and I'm scared.", sent at 0:01. The Caregiver side lights up at 0:04 (3.9 s): the safety flag, labelled a simulated caregiver alert shown on this demo panel (no message leaves the demo), and **✅ Dad was told**. The companion's reply is cut after "I'm letting your family know right now so someone can check on you." | (silent; the companion's voice carries the shot) |
| 0:13-0:29 | Hold on the split screen, then a slow zoom on the panel's own "Dad was told" line. | "ForeverYours is a voice companion for Dad, briefed by his family. When his safety is at stake, it raises a flag for his daughter, and tells him first, out loud. Everything else he says stays between them." |
| 0:29-0:41 | Caregiver side: the daughter types the memo "Dad has a check-up with Dr. Tan on Thursday at 10 AM." and clicks Save Text Memo. The briefed memory shows it added. The narrator speaks over the typing. | "His daughter briefs it once, from work. One line: a check-up with Dr. Tan on Thursday. Nothing to set up on Dad's side." |
| 0:41-1:03 | Same session, Senior side: the senior types the line from "Senior line" below and clicks Send. "Companion is thinking..." for about nine seconds (the real wait, not cut); the narrator's first sentence plays as the split screen is framed and the rest over the wait, then the reply names Dr. Tan, Thursday, 10 AM. | "When Dad asks, it already knows what she typed. The reply is written by NVIDIA Nemotron on Nebius Token Factory. This is the real hosted wait, uncut." |
| 1:03-1:43 | Senior side: the narrator's first sentence, then "I feel lonely since my wife died." The companion answers warmly; the Caregiver side shows no new flag and does not show what he said. A short freeze with the second sentence, then: "I want to end my life." The safety fast path answers with the 988 referral and the Caregiver side shows the crisis flag; the reply is cut after "I am also letting your family know you are in distress." | "What he says in private stays private. Danger is different." |
| 1:43-1:51 | Day 2 (8 seconds): a new visit asks "I forgot, what is my grandson's name?" and the companion answers with Leo from yesterday's briefing. The Space keeps memory for one browser session, so this is `python main.py beat4` in a fresh process, labelled as a local test. The one output line that prints a synthesis time is left out of the rendered terminal, and the clip ends before the audit line. | "Next day, in a local test, it's still briefed." |
| 1:51-2:07 | Plain screen, text only: "Replies: NVIDIA Nemotron 3 Nano · Safety backstop: NVIDIA Nemotron 3 Super, both on Nebius Token Factory" · "Hearing and voice: on the app's own server". No diagram, no logos. | "Two models on Nebius Token Factory: Nemotron 3 Nano writes the replies, and Nemotron 3 Super is the safety backstop. Hearing and voice run on the app's own server, so his voice recording never goes to Nebius." |
| 2:07-2:18 | Plain screen: "ForeverYours", "The companion the family briefs", the Space URL, https://elevenbaselab-foreveryours.hf.space, and "Known limitations: in the README". | "It doesn't catch everything; the README lists what it misses. Try it yourself, no login, at the link on screen." |

Total: about 2:18, well under 3:00. The companion's replies are cut only at the end of a
sentence and never overlap the narrator. Times are the plan; the assembler prints the real
shot boundaries.

**Footage.** Shots 1, 2 and 5 are real browser sessions on the live Space at build `ed85efc`,
captured for v2 and reused unchanged: the fall reply asks "Are you hurt? Can you get up
safely?", the 988 line is spoken once, and the alert is labelled simulated on the panel itself.
Shots 3-4 were re-captured on the live Space for #261, so the briefed memo shows "expires Thu
23:59" (three fresh-session runs, 3 of 3 passed). Shot 6 is one local run. How each clip is
captured: [`video/v2/README.md`](../video/v2/README.md); how v4 is cut:
[`video/v4/README.md`](../video/v4/README.md).

**Narration pace.** Every line is rendered at one Kokoro speed, 0.9, with a 0.4 s gap between
sentences (`wpm` per line in `video/v4/lines.json`). v3 reached 150-160 wpm by slowing the
voice to 0.76-0.83, which drags; v4 keeps the voice natural and shortens the lines instead.
The waits that were silent in v3 (the memo being typed, the nine-second hosted reply) now carry
the narration, so the video has no stretch of dead air longer than the companion's own pauses.

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
| 0:00-1:43 | **LIVE HOSTED SPACE**, small, top right, on every shot recorded on the Space |
| 0:04-0:13 | **Dad was told**, once, from the frame the caregiver flag appears; no other overlay repeats it |
| 1:09-1:27 | **Not shown to the family** over the unchanged Caregiver side after the private line |
| 1:43-1:51 | **LOCAL PERSISTENCE TEST** on the day-2 terminal |
| 1:51-2:18 | The card text is the caption; narrator caption below it |

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

- Opens on the product moment within 5 seconds: the line is sent at 0:01 and the caregiver flag and "Dad was told" are on screen at 0:04; no title card.
- Narrative order: fall hook, one-sentence thesis, caregiver briefing, ordinary recall, private boundary, crisis/988, next-day recall, stack/privacy/URL close.
- No broad claim about other assistants: the thesis says what this one does (briefed by his family, raises a flag for his daughter when his safety is at stake, tells him first); no product is named.
- The alert is described as a flag raised for his daughter, which is what the panel shows (a simulated alert; nothing is sent in the demo), not as a message delivered.
- One "Dad was told" overlay, aligned with the flag; the crisis shot relies on the panel's own line.
- Hosted and local evidence labelled where they appear: LIVE HOSTED SPACE on shots 1-5, LOCAL PERSISTENCE TEST on shot 6.
- Day-2 shot 15 seconds or less: 8 seconds, and it ends before the local run's audit line.
- No AUDIT, biomarkers, proactive triggers, phone-notification shot, latency figure or music; the only names on screen are the sponsors' (NVIDIA, Nebius) in plain text. The narration voice is Kokoro (Apache-2.0).
- Privacy wording matches PRIVACY.md: speech runs on the app's own server and the voice recording never goes to Nebius.
- Limitations stated: the last card points at the README's "Known limitations".
- The product's name is on screen in the last card, with the URL.
