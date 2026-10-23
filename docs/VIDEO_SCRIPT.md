# Video script and shot list (under 3:00)

The demo video for the submission. It follows the issue #5 rules and the requirements in
[`HACKATHON_RULES.md`](HACKATHON_RULES.md) item 7: less than 3 minutes, public on YouTube, no
third-party trademarks or copyrighted music. Rehearse locally (`python webapp.py`); record on
the hosted Space, https://elevenbaselab-foreveryours.hf.space, so a judge can repeat every shot.

**Setup:** one browser window on the Space, split screen, Senior side on the left and
Caregiver side on the right, 1080p. One human narrator (a team member, chosen at recording).
The companion is the only synthetic voice. No title card, no statistics, no music, no diagram.

## Shot list

| Time | Screen | Narrator (one human) |
|---|---|---|
| 0:00-0:12 | Senior side, typed or spoken: "I fell down earlier and I'm scared." The companion speaks: "I hear you, and I'm taking this seriously. I'm letting your family know right now so someone can check on you. I'll only tell them if I'm worried about your safety." The Caregiver side lights up at the same moment: the HIGH PRIORITY safety alert, labelled a simulated caregiver alert shown on this demo panel (no message leaves the demo), and **✅ Dad was told**. | (silent; the companion's voice carries the shot) |
| 0:12-0:30 | Hold on the split screen, then zoom on "Dad was told". | "Tell a general assistant you fell and you're scared, and you get sympathy, and nobody in your family hears about it. ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't there, and never tells the senior anything it hasn't already told him." |
| 0:30-1:00 | Caregiver side: the daughter records or types the memo "Dad loves jazz. His grandson is named Leo. Avoid talking about driving. Sarah is dropping off groceries at 4 PM." and saves it. The memory panel shows it saved. Keep the frame on the saved memo, not the full memory list. | "His daughter briefs it once, by voice, from work." |
| 1:00-1:35 | Senior side: the senior line from "Senior line" below. The companion's reply brings up Leo and the 4 PM groceries and never raises driving. | "So when Dad talks, it already knows what matters to him, and what to stay away from." |
| 1:35-2:05 | Senior side: "I feel lonely since my wife died." The companion answers warmly; the Caregiver side shows no new flag and does not show what he said. Then: "I want to end my life." The safety fast path answers with the 988 referral and the Caregiver side shows the crisis flag with **✅ Dad was told**. | "What he tells it in private stays private, unless he's in danger. And in a crisis it answers instantly with real help." |
| 2:05-2:20 | Day 2 (15 seconds): a new visit asks "I forgot, what is my grandson's name?" and the companion answers with Leo from yesterday's briefing. The Space keeps memory for one browser session, so record this as `python main.py beat4` in a fresh process (the repo's day-2 recall beat), captioned as a local run. | "Next day, it's still briefed." |
| 2:20-2:40 | Plain screen, text only: "NVIDIA Nemotron on Nebius Token Factory" and "Speech recognition runs locally". No diagram, no logos. | "NVIDIA Nemotron on Nebius Token Factory does the thinking; speech recognition runs locally; a session is removed about an hour after you close the tab, not kept." |
| 2:40-2:50 | The Space URL on screen: https://elevenbaselab-foreveryours.hf.space | "Try it yourself, no login: elevenbaselab-foreveryours.hf.space." |

Total: 2:50. Re-time after a full rehearsal on the Space and trim narration, not shots, if it
runs long.

## Senior line (1:00-1:35)

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
| 0:00-0:12 | Senior: "I fell down earlier and I'm scared." Companion caption: the reply quoted in the shot list. Label over the Caregiver side: **Dad was told** |
| 0:12-0:30 | The #14 narration, captioned in full. Zoom label: **Dad was told** |
| 0:30-1:00 | Narrator caption. The memo text is visible on screen as typed. |
| 1:00-1:35 | Senior line and the companion's reply, verbatim. Narrator caption. |
| 1:35-2:05 | Both senior lines, the companion's replies, verbatim. Label: **Not shown to the family** over the unchanged Caregiver side, then **Dad was told** on the crisis flag. Narrator caption. |
| 2:05-2:20 | Label: **Day 2 (local run)**. Question, reply and narrator caption. |
| 2:20-2:40 | The stack text on screen is the caption; narrator caption below it. |
| 2:40-2:50 | The URL, large, plus the narrator caption. |

## Recording tips

1. **Resolution:** 1080p browser capture at about 110% zoom so the flag and "Dad was told" are
   readable on a phone.
2. **Audio:** one human narrator, recorded clean; let the companion's voice play in full in
   the fall and crisis shots. No background music.
3. **Cursor:** slow, deliberate clicks. Pause two seconds on the split-screen flag so both
   sides can be read.
4. **Keep the Space awake** before recording; a cold first click can hang.

## Compliance checklist

Checked line by line against the issue #5 rules, the shot list above, [`SELF_JUDGING.md`](SELF_JUDGING.md)
and [`PRIVACY.md`](PRIVACY.md).

- PASS: Opening shot within 10s with the narrator silent: 0:00-0:12 opens on the fall moment, with no title card, and the narrator column says silent.
- PASS: Issue #5 narration used for each shot: every Narrator (one human) cell is the agreed draft wording; the only change is the 2:20-2:40 session line, reworded to match PRIVACY.md.
- PASS: #14 sentence at 0:12-0:30: said in full over the hold and zoom on "Dad was told".
- PASS: Day-2 shot 15 seconds or less: 2:05-2:20 is 15 seconds.
- PASS: Captions cover every narrator and companion line: see Captions, one row per shot, plus the Dad was told label.
- PASS: No AUDIT, biomarkers or proactive triggers: no shot shows them or names them.
- PASS: No phone-notification shot: the Caregiver side in the browser is the only family-facing view shown.
- PASS: No third-party music or trademarks (HACKATHON_RULES.md item 7): no music, no logos, no screenshots of other products; the only names on screen are the sponsors' (NVIDIA, Nebius); ChatGPT is named once, in words only, in the #14 comparison sentence.
- PASS: Session wording matches PRIVACY.md: the 2:20-2:40 line says a session is removed about an hour after the tab closes.
- PASS: Under 3:00: the last shot ends at 2:50.
