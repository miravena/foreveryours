# Video script and shot list (under 3:00)

The demo video for the submission. It follows the issue #5 rules and the requirements in
[`HACKATHON_RULES.md`](HACKATHON_RULES.md) item 7: less than 3 minutes, public on YouTube, no
third-party trademarks or copyrighted music. Rehearse locally (`python webapp.py`); record on
the hosted Space, https://elevenbaselab-foreveryours.hf.space, so a judge can repeat every shot.

**Setup:** one browser window on the Space, split screen, Senior side on the left and
Caregiver side on the right, 1080p. One human narrator (a team member, chosen at recording).
The companion is the only synthetic voice. No title card, no statistics, no music, no diagram.

**What the judges said they score** (Devpost "Will It Ship?" session, 2026-10-20, applied here):
the aha moment inside 30 seconds (shot 1), show which model is doing what (shot 7), publish the
limitations (shot 8), one thing done well rather than a stack (no feature tour).

## Shot list

| Time | Screen | Narrator (one human) |
|---|---|---|
| 0:00-0:12 | Senior side, typed or spoken: "I fell down earlier and I'm scared." The companion speaks its fall reply (the sentence both builds share: "I'm letting your family know right now so someone can check on you."). The Caregiver side lights up at the same moment: the safety flag, labelled a simulated caregiver alert shown on this demo panel (no message leaves the demo), and **✅ Dad was told**. | (silent; the companion's voice carries the shot) |
| 0:12-0:28 | Hold on the split screen, then zoom on "Dad was told". | "Tell a general assistant you fell and you're scared, and you get sympathy, and nobody in your family hears about it. ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't there, and never reports anything to the family that it hasn't first said to him out loud." |
| 0:28-0:58 | Caregiver side: the daughter types the memo "Dad loves jazz. His grandson is named Leo. Avoid talking about driving. Sarah is dropping off groceries at 4 PM." and saves it. The briefed memory shows it saved, three items labelled Permanent and the groceries labelled Temporary. Keep the frame on the saved memo, not the full memory list. | "His daughter briefs it once, from work. What lasts is kept; today's errand expires on its own." |
| 0:58-1:33 | Senior side: the senior line from "Senior line" below. The companion's reply brings up Leo and the 4 PM groceries and never raises driving. | "So when Dad talks, it already knows what matters to him, and what to stay away from." |
| 1:33-2:03 | Senior side: "I feel lonely since my wife died." The companion answers warmly; the Caregiver side shows no new flag and does not show what he said. Then: "I want to end my life." The safety fast path answers with the 988 referral and the Caregiver side shows the crisis flag with **✅ Dad was told**. | "What he tells it in private stays private, unless he's in danger. And in a crisis it answers instantly with real help." |
| 2:03-2:13 | Day 2 (10 seconds): a new visit asks "I forgot, what is my grandson's name?" and the companion answers with Leo from yesterday's briefing. The Space keeps memory for one browser session, so record this as `python main.py beat4` in a fresh process (the repo's day-2 recall beat), captioned as a local run. | "Next day, it's still briefed." |
| 2:13-2:30 | Plain screen, text only, three lines: "Reply and safety backstop: NVIDIA Nemotron 3 Nano on Nebius Token Factory" · "Hearing: faster-whisper, on the app's own server" · "Voice: Piper, on the app's own server". No diagram, no logos. | "NVIDIA Nemotron 3 Nano on Nebius Token Factory writes every reply and runs the safety backstop. Hearing and voice run on the app's own server, so your voice recording never goes to Nebius, and a session is removed about an hour after you close the tab, not kept." |
| 2:30-2:37 | Plain screen, text only: "Known limitations: in the README". | "It doesn't catch everything. A fall said in other words relies on a slower backstop. We wrote the failure cases down." |
| 2:37-2:47 | The Space URL on screen: https://elevenbaselab-foreveryours.hf.space | "Try it yourself, no login: elevenbaselab-foreveryours.hf.space." |

Total: 2:47. Re-time after a full rehearsal on the Space and trim narration, not shots, if it
runs long. If the cut still runs past 3:00, the day-2 shot (2:03-2:13) is the first cut: it is the
only shot a judge cannot repeat on the Space.

**Record after the next publish.** The fall reply, the crisis reply and the caregiver-side alert
labels change with the publish that follows build `e5d436e` (the fall reply gains "Are you hurt? Can
you get up safely?", the 988 line is spoken once, the alert is labelled simulated). Shots 1, 2 and 5
must show the published wording, so the recording date is the first day after that deploy's
`Build:` line changes.

## Senior line (0:58-1:33)

The shot uses only a senior line that has passed this check on the live Space: with the memo
above saved, the line is sent three times in fresh sessions, and every reply names Leo and the
4 PM groceries and none raises driving. The passing line and one of its real replies go here,
on a line of their own that starts with "Verified reply" followed by a colon. No reply is
written here unless it came from a passing run. Transcripts of each check are in
[`WORK_LOG.md`](WORK_LOG.md) under "VIDEO_SCRIPT senior line check".

These lines were checked and do not qualify (the replies named the 4 PM groceries but not Leo):

- "I was listening to some music earlier." (the original jazz clip)
- "I was thinking about my family today. Is anyone coming by?"
- "Is anyone coming by today? I miss the little ones."

## Captions

The video must make sense with the sound off. Burn in a caption for every narrator line and
every companion line, verbatim as spoken, plus the senior's lines. On-screen text:

| Time | On-screen text |
|---|---|
| 0:00-0:12 | Senior: "I fell down earlier and I'm scared." Companion caption: the reply as spoken. Label over the Caregiver side: **Dad was told** |
| 0:12-0:28 | The #14 narration, captioned in full. Zoom label: **Dad was told** |
| 0:28-0:58 | Narrator caption. The memo text is visible on screen as typed; the Permanent and Temporary labels are in frame. |
| 0:58-1:33 | Senior line and the companion's reply, verbatim. Narrator caption. |
| 1:33-2:03 | Both senior lines, the companion's replies, verbatim. Label: **Not shown to the family** over the unchanged Caregiver side, then **Dad was told** on the crisis flag. Narrator caption. |
| 2:03-2:13 | Label: **Day 2 (local run)**. Question, reply and narrator caption. |
| 2:13-2:30 | The three stack lines on screen are the caption; narrator caption below them. |
| 2:30-2:37 | "Known limitations: in the README" is the caption; narrator caption below it. |
| 2:37-2:47 | The URL, large, plus the narrator caption. |

## Recording tips

1. **Resolution:** 1080p browser capture at about 110% zoom so the flag and "Dad was told" are
   readable on a phone.
2. **Audio:** one human narrator, recorded clean; let the companion's voice play in full in
   the fall and crisis shots. No background music.
3. **Cursor:** slow, deliberate clicks. Pause two seconds on the split-screen flag so both
   sides can be read.
4. **Keep the Space awake** before recording; a cold first click can hang.
5. **Full-screen the browser** (F11) so the address bar and the hosting site's header are out of
   frame; the URL appears once, as text, in the last shot. The phone-first recording checklist
   (narration first, one continuous take, edit, public upload with a caption file) is on issue #5.

## Compliance checklist

Checked line by line against the issue #5 rules, the shot list above, [`SELF_JUDGING.md`](SELF_JUDGING.md)
and [`PRIVACY.md`](PRIVACY.md).

- PASS: Opening shot within 10s with the narrator silent: 0:00-0:12 opens on the fall moment, with no title card, and the narrator column says silent.
- PASS: Issue #5 narration used for each shot: every Narrator (one human) cell is the agreed draft wording; the changes are the 2:13-2:30 stack line (names which model does what, and the session wording matches PRIVACY.md), the new 2:30-2:37 limitations line, and the memo line's second sentence.
- PASS: #14 sentence at 0:12-0:28: said in full over the hold and zoom on "Dad was told", in the corrected wording ("never reports anything to the family that it hasn't first said to him out loud"), the same sentence as README.md and docs/DEVPOST_DRAFT.md.
- PASS: Day-2 shot 15 seconds or less: 2:03-2:13 is 10 seconds.
- PASS: Captions cover every narrator and companion line: see Captions, one row per shot, plus the Dad was told label.
- PASS: No AUDIT, biomarkers or proactive triggers: no shot shows them; the backstop is named once, in the stack text, as what the model runs.
- PASS: No phone-notification shot: the Caregiver side in the browser is the only family-facing view shown.
- PASS: No third-party music or trademarks (HACKATHON_RULES.md item 7): no music, no logos, no screenshots of other products; the only names on screen are the sponsors' (NVIDIA, Nebius) and the open-source components (faster-whisper, Piper) in plain text; ChatGPT is named once, in words only, in the #14 comparison sentence.
- PASS: Session and audio wording match PRIVACY.md and the page copy: the 2:13-2:30 line says speech runs on the app's own server and the voice recording never goes to Nebius (the hosted Space transcribes and synthesises server-side; "on the device" would be false there, Codex review 2026-10-23), and that a session is removed about an hour after the tab closes.
- PASS: No latency figure or hosted timing is spoken or shown.
- PASS: Limitations stated (judges' advice): the 2:30-2:37 line, pointing at the README's "Known limitations" section.
- PASS: Under 3:00: the last shot ends at 2:47.
