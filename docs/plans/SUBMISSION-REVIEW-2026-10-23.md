# Submission review against the judges' own advice, 2026-10-23

This page is **reasoning plus a dated snapshot**, not a tracker. Work state lives on GitHub
Issues and milestones (`HOW_TO_WORK_HERE.md`); if a row here and GitHub disagree, GitHub is right.
Companion to [`FINAL-WEEK-PLAN-2026-10-23.md`](FINAL-WEEK-PLAN-2026-10-23.md), which ranks the
open issues; this page judges the *submission artefacts* (text, video, hosted page, repo front
page) against what the hackathon's judges said they score.

**Source.** Devpost's "Will It Ship?" session (recorded 2026-10-20; six judges from Nebius, Tavily
and NVIDIA walked the four criteria and reviewed four entries live). The organisers' summary of what
came up most:

1. Solve a real problem for a real audience. Talk to a few potential users before locking the project.
2. Get to the aha moment fast: two minutes into the project, 30 seconds into the demo.
3. One thing done well beats a big stack. Every integration should support the main story.
4. Put the action first. Add a little onboarding. Show which model is doing what.
5. Publish your limitations. Documented failure cases read as rigour. Built for accessibility? Say so.
6. Budget extra time for packaging. The write-up and demo take longer than expected.

**What was reviewed.** `docs/DEVPOST_DRAFT.md` (main `cfa1b33`), `docs/VIDEO_SCRIPT.md`,
`docs/DEMO_SCRIPT.md`, `docs/FEEDBACK.md`, `README.md`, `docs/HACKATHON_RULES.md`, the live Space
(build `e5d436e`, loaded headless at 1920x1080 and read through its Gradio config), the live judge
check from the `e5d436e` deploy (16 of 21 turns pass; T09, T11, T12, T16 red) and GitHub (#5, #20,
#37, #183). No video exists yet; the proof-of-concept MP4 under `video/` is a terminal recording and
is not the submission.

## The story holds. Keep it.

One sentence carries the entry and it is already everywhere it needs to be:

> ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't
> there, and never reports anything to the family that it hasn't first said to him out loud.

The scene that proves it (Dad says he fell and is scared; the companion tells him out loud that his
family is being told; the caregiver column lights up in the same moment, marked "Dad was told") is
built, hosted, and opens the video at 0:00. That is the "30 seconds into the demo" the judges asked
for. Nothing below changes the story. Everything below removes what gets in its way.

## Where each piece of judge advice lands on us

| Judge advice | Where we stand | Change |
|---|---|---|
| Real problem, real audience; talk to users first | The text cites WHO figures and a scenario. No caregiver or older adult has been spoken to; "a real caregiver and a real older adult for a week" sits under *What's next*. | Three 15-minute conversations with caregivers this week (founder's network). One paragraph "What three caregivers told us" in *Inspiration*, quoting what surprised us, plus the one thing we changed because of it. Zero conversations is the gap a judge will probe on Impact. |
| Aha in 2 min / 30 s | Video: yes (fall at 0:00). Text: *Inspiration* opens on the scenario, good, but *What it does* reaches the disclosure moment in bullet 3. Space: the first 300 px are three notices and a privacy paragraph; the only hint of what to try is a clause in a sentence. | Text: make the disclosure moment bullet 1 of *What it does*. Space: one bold line above the input, "Try this first: *I fell down earlier and I'm scared*", as a clickable example that fills the box; fold the recording paragraph to one line with a link. |
| One thing done well beats a stack | The README opens with a five-noun feature list ("life-context memory, proactive companionship, caregiver coordination, safety-aware escalation, privacy-preserving family connection"), the opposite of the Devpost text. "Proactive companionship" is not shown anywhere a judge can reach (triggers are dev-mode only). The live page shows a "Simulated Time of Day" dropdown and a "(Beat 1 Onboarding)" label, neither part of the story. | README opens with the same two sentences as the Devpost *Inspiration*. Drop "proactive companionship" from judge-facing copy. Hide the time-of-day dropdown behind dev mode (or label it "Evening mode: shorter, calmer replies" if it stays). Remove "Beat 1 Onboarding" from the memo accordion. |
| Action first, light onboarding, show which model does what | On the Space the line naming Nemotron is inside a `DEV_MODE`-only accordion (`webapp.py`, "Model & Pipeline Info"), so a judge never sees which model is doing what. The caregiver flag does not say whether the rules or the model raised it. | A one-line footer, always visible: "Reply and safety backstop: NVIDIA Nemotron 3 Nano 30B on Nebius Token Factory · Hearing: faster-whisper, local · Voice: Piper, local". On each flag, "raised by: safety rules (before the model)" or "raised by: Nemotron backstop". Both are true and both are what criterion 1 scores. |
| Publish limitations; call out accessibility | Limitations exist but are scattered (ADR-010 recall 12 of 19, *What's next*, Reviewer notes). Neither the Devpost text nor the README has a "Known limitations" heading. The word "accessibility" appears nowhere in the Devpost text or README, although voice-first for older adults is the accessibility case. | A **Known limitations** section in the Devpost text and README, same six lines (below). One sentence in *What it does*: "Built for people who cannot or will not use a screen: no app to learn, no typing, no reading; the senior only talks." |
| Budget time for packaging | Video unrecorded with seven days left, founder-owned, and it must be shot on the Space *after* the next publish (fall and crisis wording, simulated-alert labels). Devpost text awaits the teammate's review. No image gallery planned, and the rules say judges may score from text, images and video alone. | Record 2026-10-25 at the latest on whatever build is live; re-shoot only the shots whose labels changed. Four captioned 1080p screenshots for the Devpost gallery (list below). Founder gets edit access to the Devpost team project so the paste does not depend on one person on 10-29. |

### Known limitations (the six lines, for both the Devpost text and the README)

- A fall described in other words ("I'm on the floor and can't reach the phone") is not caught by
  the rules; it depends on the background backstop, which runs after the reply and, on Nemotron 3
  Nano, caught 12 of 19 labelled events (five of six falls missed). Nemotron 3 Super caught all 19;
  switching is an open decision (ADR-010).
- Some crisis paraphrases return SAFE from the backstop; the rules catch the direct phrases.
- On the hosted demo the alert stays on the caregiver's half of the screen. Nothing reaches a phone.
- A flag is marked "Dad was told" once the spoken line is synthesised, not once it is heard; a
  browser that blocks autoplay still shows it as told.
- The browser plays one combined clip, so the hosted demo is slower to first sound than the
  command line (about 0.9 s there; several seconds hosted). No hosted latency figure is claimed.
- English only. Not a medical device, not a diagnosis, not an emergency dispatcher.

## Artefact by artefact

**Devpost text (`docs/DEVPOST_DRAFT.md`).** Strongest artefact. Scenario first, honest, every claim
checked on the live build. Changes: (a) reorder *What it does* so the disclosure bullet is first;
(b) add the accessibility sentence; (c) add *Known limitations* as its own heading; (d) add the
user-conversation paragraph once it exists; (e) check the tagline length on the form. The draft's
tagline is 82 characters; if the field caps at 60, candidates under 60: "The companion your family
briefs, and that is honest with Dad." (58) or "Briefed by the family. Honest with Dad." (39).
(f) *How we built it* lists seven stages; keep them, but open the section with one sentence that
says what the whole pipeline is for ("one pipeline whose first step is the safety check, so the
highest-stakes reply is also the fastest and the one that works offline"), then the list.

**README.** The front page a judge reads for two minutes. Changes: (a) replace the opening bold
feature list with the Devpost *Inspiration* opening; (b) beat 2 still promises "a live memory
panel showing exactly what was retrieved and what's new", which the column does not do (recorded in
`SELF_JUDGING.md` Gaps), reword to "the caregiver column shows what it was briefed and what it
flagged"; (c) add *Known limitations*; (d) the "Demo video" section points at the proof-of-concept
MP4 until the YouTube link exists; swap on upload (#204 retires `video/`).

**Hosted Space (build `e5d436e`).** What a judge sees above the fold: title, two AI notices, a
four-line recording paragraph, mic widget showing "No microphone found", type box, Send, four sample
clips named `senior_jazz.wav` style. Right: a privacy paragraph, "Today: 0 conversations · Calm", the
briefed memory with Permanent/Temporary labels (good, legible, the story in one glance), "Load
sample family", a memo accordion. Changes, all small: the "Try this first" line; one-line notices with
links; footer naming the models; flag source on each flag; human names for the sample clips ("Dad
asks about his grandson"); drop "(Beat 1 Onboarding)"; hide or relabel the time-of-day dropdown; the
first-turn "household was reset" note only when a session really expired (already in Gaps). The
dev-mode panels (telemetry, biomarkers, triggers) are hidden on the live build, confirmed via the
Gradio config, so the earlier #5 gap-list blockers are cleared.

**Video script (`docs/VIDEO_SCRIPT.md`).** Right shape: fall at 0:00, one human narrator, no
slides, no latency claim, 2:50. Two changes and one call:

- The 2:20-2:40 stack card should say which model does what, in the judges' words: "Reply and
  safety backstop: NVIDIA Nemotron 3 Nano on Nebius Token Factory. Hearing: faster-whisper, local.
  Voice: Piper, local." Still text only, no logos.
- Add a five-second limitations line, because no other entry will have one and the judges said it
  reads as rigour. Narration: "It doesn't catch everything. A fall said in other words relies on a
  slower backstop. We wrote the failure cases down." Fit it by trimming the 0:12-0:30 narration (the
  ChatGPT comparison can be the two sentences of the #14 line alone) and by holding the day-2 shot
  to 10 seconds.
- Founder call: the day-2 shot is the only one a judge cannot repeat on the Space (it is a local
  `beat4` run, captioned as such). It shows the track's "persistent memory" requirement, so it earns
  its place, but it must be captioned "local run" exactly as the script says, and it is the first
  cut if the video runs over 3:00.

**Images (new).** Devpost shows a gallery before the text. Four 1080p screenshots from the live
Space, each with a one-line caption: (1) the split screen at the fall moment, "Dad was told" visible;
(2) the briefed memory with Permanent and Temporary labels; (3) the crisis turn with the 988 line and
the flag; (4) the stack card text. Taken after the next publish so labels match the video.

**Feedback section.** `docs/FEEDBACK.md` is good and specific (missing transcription endpoint,
reasoning tokens vs latency, model-ID casing, Nano verbosity and recall). It is already restated
in the Devpost draft. Add the two findings from this week: Nano's backstop recall numbers against
Super, and that `enable_thinking: false` is the single most important flag for voice and is not
prominent in the docs. Complete feedback is also the Most Valuable Feedback prize entry.

## Rules check (`docs/HACKATHON_RULES.md`)

| Requirement | State |
|---|---|
| Runs on Token Factory, uses an NVIDIA open model | Yes: Nemotron 3 Nano for every model call |
| Working demo URL | Yes, no login, HTTP 200 on 2026-10-23 |
| Text description | Draft done, awaiting team review on #20 |
| Public repo, licence visible in About | Yes: GitHub detects MIT; topics set |
| README with setup | Yes |
| How NVIDIA/Nebius were used | Yes, own section in the draft |
| Video under 3:00, public on YouTube, no third-party music or marks | **Not recorded** (#5) |
| Track named | Personal AI |
| Feedback section | Yes |
| Started before the period? | No; first commit 2026-10-01 |

## Seven-day plan, by owner

Dates are the plan; the live state is each Issue's milestone and labels.

**Founder** (only a human can do these)
- 10-24/25: three caregiver conversations (15 min each, by phone). Notes to the fleet; the fleet
  writes the paragraph.
- 10-25 latest: record narration and the screen take per `docs/VIDEO_SCRIPT.md` on the live build.
  Public YouTube upload. If the publish that follows changes a label in frame, re-shoot that shot only.
- 10-24: confirm edit access to the Devpost team project, so either member can paste on 10-29.
- Decide: day-2 shot stays (recommended, captioned "local run") or goes if the cut runs long.

**Fleet**
- 10-24: Space copy changes (try-first line, one-line notices, model footer, flag source, sample clip
  names, remove dev jargon). One PR, so the video and screenshots record the final labels.
- 10-24: Devpost draft edits (a)-(c), (e), (f); README (a)-(c); *Known limitations* in both.
- 10-24: publish batch and redeploy; live judge check; red turns on Issues (unchanged from the
  final-week plan: T09/T11 Dr. Tan recall, T12 driving, T16 988 twice).
- 10-26: four gallery screenshots from the redeployed Space.
- 10-26: user-conversation paragraph into the draft and README once the founder's notes arrive.
- 10-29: v1.0.0, final scorecard, as in the final-week plan.

**Teammate** (Devpost Representative)
- 10-26: review the Devpost text on #20; 10-29: paste and submit, confirmation on #37.

## Self-judging effect, predicted

Against the 2026-10-23 row in `SELF_JUDGING.md` (13/20): the model footer and flag source move
Technological Implementation; the try-first line, tidy page and the video move Design; the caregiver
conversations and the limitations section move Impact; nothing here changes Quality of the Idea,
which was already the highest score. Re-score after the redeploy and the video, both members
independently, as that file asks.
