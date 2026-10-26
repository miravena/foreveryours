# Video script and shot list (under 3:00)

The demo video for the submission. It follows the issue #5 rules and the requirements in
[`HACKATHON_RULES.md`](HACKATHON_RULES.md) item 7: less than 3 minutes, public on YouTube, no
third-party trademarks or copyrighted music. Rehearse locally (`python webapp.py`); record on
the hosted Space, https://elevenbaselab-foreveryours.hf.space, so a judge can repeat every shot.

**Setup:** one browser window on the Space, split screen, Senior side on the left and
Caregiver side on the right, 1080p. Narration is AI-generated: Kokoro TTS (Apache-2.0), voice
af_heart, one WAV per shot, so a human narrator can replace the track shot by shot without
re-editing the picture (`video/v2/README.md`). The companion's voice is the Space's own reply
audio. No title card, no statistics, no music, no diagram.

**What the judges said they score** (Devpost "Will It Ship?" session, 2026-10-20, applied here):
the aha moment inside 30 seconds (shot 1), show which model is doing what (shot 7), publish the
limitations (shot 8), one thing done well rather than a stack (no feature tour).

## Shot list

| Time | Screen | Narrator (AI voice, Kokoro af_heart) |
|---|---|---|
| 0:00-0:26 | Senior side, typed: "I fell down earlier and I'm scared." (sent at 0:02). The companion speaks its fall reply in full (the sentence both builds share: "I'm letting your family know right now so someone can check on you."). The Caregiver side lights up at the same moment (0:05): the safety flag, labelled a simulated caregiver alert shown on this demo panel (no message leaves the demo), and **✅ Dad was told**. | (silent; the companion's voice carries the shot) |
| 0:26-0:45 | Hold on the split screen, then a slow zoom on "Dad was told". | "Tell a general assistant you fell and you're scared, and you get sympathy, and nobody in your family hears about it. ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't there, and never reports anything to the family that it hasn't first said to him out loud." |
| 0:45-0:58 | Caregiver side: the daughter types the memo "Dad has a check-up with Dr. Tan on Thursday at 10 AM." and clicks Save Text Memo. The briefed memory shows it added under the sample household's pre-brief, with the Permanent and Temporary labels in frame. | "His daughter briefs it once, from work. What lasts is kept; today's errand expires on its own." |
| 0:58-1:16 | Same session, Senior side: the senior types the line from "Senior line" below and clicks Send. The companion's reply names Dr. Tan, Thursday, 10 AM. | "So when Dad talks, it already knows what matters to him, and what to stay away from." |
| 1:16-2:09 | Senior side: "I feel lonely since my wife died." The companion answers warmly; the Caregiver side shows no new flag and does not show what he said. Then: "I want to end my life." The safety fast path answers with the 988 referral and the Caregiver side shows the crisis flag with **✅ Dad was told**. Both replies play in full. | "What he tells it in private stays private, unless he's in danger. And in a crisis it answers instantly with real help." |
| 2:09-2:19 | Day 2 (10 seconds): a new visit asks "I forgot, what is my grandson's name?" and the companion answers with Leo from yesterday's briefing. The Space keeps memory for one browser session, so this is `python main.py beat4` in a fresh process (the repo's day-2 recall beat), captioned as a local run. The one output line that prints a synthesis time is left out of the rendered terminal. | "Next day, it's still briefed." |
| 2:19-2:40 | Plain screen, text only, three lines: "Reply: NVIDIA Nemotron 3 Nano · Safety backstop: NVIDIA Nemotron 3 Super, both on Nebius Token Factory" · "Hearing: faster-whisper, on the app's own server" · "Voice: Piper, on the app's own server". No diagram, no logos. | "NVIDIA Nemotron 3 Nano on Nebius Token Factory writes every reply, and Nemotron 3 Super runs the safety backstop. Hearing and voice run on the app's own server, so your voice recording never goes to Nebius, and a session is removed about an hour after you close the tab, not kept." |
| 2:40-2:49 | Plain screen, text only: "Known limitations: in the README". | "It doesn't catch everything. A fall said in other words relies on a slower backstop. We wrote the failure cases down." |
| 2:49-2:57 | The Space URL on screen: https://elevenbaselab-foreveryours.hf.space | "Try it yourself, no login: elevenbaselab-foreveryours.hf.space." |

Total: 2:57. Shots are cut to fit the narration and the companion's replies, which play in full
and never overlap the narrator; the narration wording is fixed. If the cut ever runs past 3:00,
the day-2 shot is the first cut: it is the only shot a judge cannot repeat on the Space.

**Footage.** Shots 1-5 are real browser sessions on the live Space (shots 1, 2 and 5 at build
`ed85efc`, shots 3-4 at `f768c65`, whose change only touches 911 turns): the fall reply asks
"Are you hurt? Can you get up safely?", the 988 line is spoken once, and the alert is labelled
simulated. Shot 6 is one local run. How each clip is captured and the video is
assembled: [`video/v2/README.md`](../video/v2/README.md).

## Senior line (0:58-1:16)

The sample household is pre-briefed (jazz, Leo, no driving, groceries at 4 PM), so shot 3 adds a
fact it does not already hold, and shot 4 asks about that fact. The shot uses only a senior line
that has passed this check on the live Space: in a fresh session the memo "Dad has a check-up
with Dr. Tan on Thursday at 10 AM." is saved, then the line is sent; three such sessions, and
every reply names Dr. Tan, Thursday and 10 AM and states nothing absent from the briefed memory.
Transcripts of each check are in [`WORK_LOG.md`](WORK_LOG.md) under "VIDEO_SCRIPT appointment
line check".

Senior line: "Do I have any doctor's appointments this week?" (3 of 3 runs passed)

Verified reply: "You have a check-up with Dr. Tan on Thursday at 10 AM. Sarah will be dropping off groceries at 4 PM today."

(The groceries visit is in the sample household's pre-brief, so the reply invents nothing.)

These lines were checked and do not qualify:

- "Do I have any appointments this week?" (2 of 3: the third reply said "no appointments listed"
  with the memo saved)
- "I was listening to some music earlier." (the original jazz clip), "I was thinking about my
  family today. Is anyone coming by?", "Is anyone coming by today? I miss the little ones.",
  and other open lines against the earlier memo: replies named the 4 PM groceries but not
  reliably Leo, and some invented family facts (#245).

## Captions

The video must make sense with the sound off. Burn in a caption for every narrator line and
every companion line, verbatim as spoken, plus the senior's lines. On-screen text:

| Time | On-screen text |
|---|---|
| 0:00-0:26 | Senior: "I fell down earlier and I'm scared." Companion caption: the reply as spoken. Label over the Caregiver side: **Dad was told** |
| 0:26-0:45 | The #14 narration, captioned in full. Zoom label: **Dad was told** |
| 0:45-0:58 | Narrator caption. The memo text is visible on screen as typed; the Permanent and Temporary labels are in frame. |
| 0:58-1:16 | Senior line and the companion's reply, verbatim. Narrator caption. |
| 1:16-2:09 | Both senior lines, the companion's replies, verbatim. Label: **Not shown to the family** over the unchanged Caregiver side, then **Dad was told** on the crisis flag. Narrator caption. |
| 2:09-2:19 | Label: **Day 2 (local run)**. Question, reply and narrator caption. |
| 2:19-2:40 | The three stack lines on screen are the caption; narrator caption below them. |
| 2:40-2:49 | "Known limitations: in the README" is the caption; narrator caption below it. |
| 2:49-2:57 | The URL, large, plus the narrator caption. |

The same captions ship as a sidecar `.srt` for the upload.

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

Checked line by line against the issue #5 rules, the shot list above, [`SELF_JUDGING.md`](SELF_JUDGING.md)
and [`PRIVACY.md`](PRIVACY.md).

- PASS: Opening shot within 10s with the narrator silent: 0:00-0:26 opens on the fall being typed, sent at 0:02, with the flag and "Dad was told" on screen by 0:06; no title card, and the narrator column says silent.
- PASS: Issue #5 narration used for each shot: every narrator cell is the agreed draft wording, spoken by an AI voice (Kokoro af_heart) instead of a team member; the changes are the 2:19-2:40 stack line (names which model does what, and the session wording matches PRIVACY.md), the 2:40-2:49 limitations line, and the memo line's second sentence.
- PASS: #14 sentence at 0:26-0:45: said in full over the hold and zoom on "Dad was told", in the corrected wording ("never reports anything to the family that it hasn't first said to him out loud"), the same sentence as README.md and docs/DEVPOST_DRAFT.md.
- PASS: Day-2 shot 15 seconds or less: 2:09-2:19 is 10 seconds.
- PASS: Captions cover every narrator and companion line: see Captions, one row per shot, plus the Dad was told label; the same lines are in the `.srt`.
- PASS: No AUDIT, biomarkers or proactive triggers: no shot shows them; the backstop is named once, in the stack text, as what the model runs.
- PASS: No phone-notification shot: the Caregiver side in the browser is the only family-facing view shown.
- PASS: No third-party music or trademarks (HACKATHON_RULES.md item 7): no music, no logos, no screenshots of other products; the only names on screen are the sponsors' (NVIDIA, Nebius) and the open-source components (faster-whisper, Piper) in plain text; ChatGPT is named once, in words only, in the #14 comparison sentence. The narration voice is Kokoro (Apache-2.0).
- PASS: Session and audio wording match PRIVACY.md and the page copy: the 2:19-2:40 line says speech runs on the app's own server and the voice recording never goes to Nebius (the hosted Space transcribes and synthesises server-side; "on the device" would be false there, Codex review 2026-10-23), and that a session is removed about an hour after the tab closes.
- PASS: No latency figure or hosted timing is spoken or shown: the day-2 terminal is rendered without its synthesis-time line.
- PASS: Limitations stated (judges' advice): the 2:40-2:49 line, pointing at the README's "Known limitations" section.
- PASS: Under 3:00: the last shot ends at 2:57.
