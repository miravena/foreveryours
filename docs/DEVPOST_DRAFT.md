# Devpost submission text (final draft for team review)

<!-- What this file is: the Devpost text that #20 asks for, written against the LIVE Space, not
against the repo alone. Paste only the prose under each heading into the Devpost form; HTML
comments and the "Reviewer notes" section at the end are evidence for the two reviewers and are
never pasted. One placeholder must be filled before submitting: the video link (#5). Search this file
for "PLACEHOLDER". The gallery files are named in "Form fields" (#218).

Checked on 2026-10-26 against the live Space, build `bb1a021` (the "Build:" line in the Space's
"About this demo household" accordion), which is the same commit as `main`, through the Space's
public Gradio API from a client outside Hugging Face. Code and docs cited by file:line are `main`
@ `bb1a021`. -->

## Project name

ForeverYours

## Tagline

The companion the family briefs: your voice in Dad's day when you can't be there.

<!-- 82 characters. If the form's tagline field caps at 60 characters, use "The companion your
family briefs, and that is honest with Dad." (58) or "Briefed by the family. Honest with Dad."
(39). (#216) -->

## Inspiration

An older adult tells a general-purpose voice assistant "I fell earlier today and I'm scared." It
answers with sympathy, the turn ends, and nobody in the family is told. That is the scenario we
kept coming back to. The assistants that are good at conversation have no concept of the person
who isn't in the room: the daughter who knows Dad loves jazz, that his grandson is Leo, that
driving is a sore subject, and that she is dropping off groceries at 4 PM. That knowledge lives in
the family and never reaches the AI.

ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't
there, and never reports anything to the family that it hasn't first said to him out loud.

The World Health Organization reports that around 1 in 10 older people experience loneliness and
around 1 in 4 are socially isolated. We did not set out to solve loneliness with software. We set
out to make the family's knowledge usable in a voice conversation, and to make sure the family
hears about the one thing that matters without the senior being watched behind his back.

<!-- Scenario first, before any figure (#20 AC 2, #14). The #14 sentence verbatim as it stands in
README.md:9-10 and docs/Project_Description.md. One cited set of figures, the same set as
docs/Project_Description.md:12. If #219 (three caregiver conversations) lands before the paste,
its paragraph goes here, after the WHO sentence; until then nothing is claimed about user
interviews. -->

## What it does

ForeverYours is a voice-first companion for an older adult, built around two people: the senior
who talks to it, and the caregiver who briefs it. The hosted demo shows both at once, side by
side. It is built for people who cannot or will not use a screen: no app to learn, no typing, no
reading. The senior only talks, and hears the answer.

- **A worrying remark is handled out loud, on both sides of the screen.** Dad says "I fell down
  earlier and I'm scared." Before any model is called, the companion asks whether he is hurt and
  tells him it is letting his family know right now so someone can check on him. In the same
  moment the caregiver's column shows the flag, marked "Dad was told" and "raised by: safety
  rules, before the model". Then the conversation carries on instead of ending on the alert.
- **A crisis phrase gets a referral, not a pep talk.** If Dad says "I don't want to be here
  anymore", the companion tells him to call or text 988, says it is letting his family know, and
  the flag is disclosed like every other flag.
- **The caregiver briefs it.** A short memo ("Dad loves jazz. His grandson is named Leo. Avoid
  talking about driving. I'm dropping off groceries at 4 PM today.") becomes the companion's
  context, typed, recorded as a voice memo, or given through a five-question guided interview.
  Lifelong facts are kept as permanent; today's errand is kept as temporary and drops out of the
  companion's context on its own about a day after it was written.
- **The senior just talks.** Speech in, a warm spoken reply out, and the reply uses the briefing.
  Ask "Is anyone coming by today?" and it answers that Sarah is dropping off groceries at 4 PM.
  Tell it "You're my only friend" and it sends him back to his family: Sarah would love to hear
  his voice.
- **The caregiver sees what the AI knows and what it flagged.** Every briefed item is labelled
  permanent or temporary. Every safety flag records whether the senior was told and which layer
  raised it: the safety rules before the model, or the Nemotron backstop after the reply. The
  code cannot record a flag without stating whether it was disclosed; if the spoken line cannot
  be produced, the flag shows "NOT yet disclosed" instead of being counted as told.
- **The caregiver sees the alert she would receive.** Under each new alert the column shows the
  exact message Sarah would be sent (the kind of alert, its severity, "Senior told: yes", and no
  transcript), marked "Not sent: notifications are off in this demo".
- **It says what it is.** The page opens with a notice that this is an AI companion, not a human.
  Next to the microphone it says that what Dad says is turned into text and that the text, not his
  voice, is sent to Nebius Token Factory. A footer names which model does what.

On the hosted demo the alert stays on the caregiver's side of the screen: nothing is sent to a
phone or an inbox. What it is not: not a medical device, not a diagnosis, not an emergency
dispatcher. A caregiver flag is a notification, not a 911 call.

<!-- Evidence, all seen on the Space `bb1a021` on 2026-10-26 through the Gradio API:
- Fall: "I fell down earlier and I'm scared" -> "I hear you, and I'm taking this seriously. Are you
  hurt? Can you get up safely? I'm letting your family know right now so someone can check on
  you." then a model continuation; panel "(distress) ... ✅ Dad was told · raised by: safety
  rules, before the model". Reply text safety/fastpath.py:286-288; origin label webapp.py:2110.
- Crisis: "I don't want to be here anymore" -> "... Please call or text 988 ... I am also letting
  your family know you are in distress." safety/fastpath.py:104 (CRISIS_PATTERNS), :241-242;
  panel "(crisis) ... ✅ Dad was told". ADR-013.
- Briefing: four memo facts, three "[Permanent]" and "[Temporary — expires in 23h 59m]";
  caregiver.py DEMO_MEMO; expiry 24 h after creation (memory/store.py), hence "about a day".
  Voice memo and guided interview: webapp.py "Record Voice Memo" tab and "Guided interview"
  accordion; interview_next answered "Question 1 of 5" on the Space.
- "Is anyone coming by today?" -> "Sarah is dropping off groceries at 4 PM today." Answered from
  the caregiver's visit updates, not left to the model (#229, pipeline/intent.py:75). "What's
  happening today?" goes to the model and recalled the groceries in one of two runs (the other
  offered jazz), so it is NOT the example used.
- "You're my only friend" -> "I'm really glad we can chat together, but I know Sarah would love
  to hear your voice too. ..." THINK rule 17, pipeline/think.py:37. Model wording, not fixed.
- Disclosure required on every flag: caregiver.py:474-477 (`add(text, severity,
  disclosed_to_senior, ...)`, "must reflect reality, not a default"); TTS-failure path recorded
  undisclosed, webapp.py:1152,1169 labels.
- Notification preview: webapp.py:1086-1099 (`_notification_preview`), notify.build_message; on
  the Space the panel showed "Preview — the message Sarah would receive: / Not sent:
  notifications are off in this demo" with "Senior told: yes" and "This is a notification, not an
  emergency call." The outbound channel (notify.py, ADR-014) exists but is off on the Space, so
  "the caregiver is notified" is NOT claimed (#20 AC 3).
- Notices and footer: Space config markdown "TRANSPARENCY NOTICE: You are interacting with an
  Artificial Intelligence (AI) companion, not a human."; recording notice; footer "Reply: NVIDIA
  Nemotron 3 Nano 30B on Nebius Token Factory · Safety backstop: NVIDIA Nemotron 3 Super 120B on
  Nebius Token Factory · Hearing: faster-whisper, on this app's server · Voice: Piper, on this
  app's server" (webapp.py:2150-2178, #214).
- Not claimed: AUDIT as a feature, biomarkers, proactive triggers, circadian mode, "clinical-grade",
  "Zero-Screen" (#20 AC 3). Those panels are dev-mode only and hidden on the Space. -->

## Why this is Personal AI

The track asks for a private assistant that keeps your data under your control, with persistent
memory, the information you choose, and the ability to act across your day. ForeverYours is that
assistant for Dad:

- **Private by design.** His family never hears or reads what he says. Only a short safety flag
  reaches Sarah, and Dad is told each time one is sent.
- **Persistent memory.** What Sarah briefs stays: permanent facts, and notes that expire on their
  own. Memory carries over to the next day.
- **Context the family chooses.** Sarah decides what the companion knows, by typed or spoken memo
  or a five-question interview. The companion treats her notes as data, not instructions.
- **It acts.** It answers his schedule from her notes, steers a plan to drive towards a lift, and
  raises the caregiver alert for a fall or a crisis. The alert is simulated on the panel in this
  demo; nothing is sent.

## Why not just use ChatGPT voice mode?

ChatGPT's voice mode is a better conversationalist than we are, and it has memory. The difference
is who the memory is for and who gets told. ChatGPT remembers for the person talking to it.
ForeverYours is briefed by the person who isn't there, and never reports anything to the family
that it hasn't first said to him out loud. When Dad tells a general assistant "I fell earlier
today and I'm scared", it answers kindly and the turn ends; nobody in the family finds out,
because no general assistant has a concept of the daughter who is not in the room. ForeverYours
was built from that second person outward: she briefs it, she sees what it knows and what it
flagged, and the one thing she needs to hear about is said to Dad out loud in the same breath it
reaches her column. That last part is not a policy; the code cannot record a safety flag without
stating whether the senior was told.

<!-- #20 section 3 paragraph with the corrected #14 sentence; "reaches her column" because nothing
is sent on the Space. -->

## How we built it

One pipeline, in Python, whose first step is the safety check, so the highest-stakes reply is
also the fastest one and the one that works offline.

1. **HEAR.** Speech is transcribed locally with `faster-whisper` (`base.en`, CPU, int8). Nebius
   Token Factory has no transcription endpoint, so local recognition was a choice we made on
   purpose: the safety step below works with no network and no key, and raw audio is never sent
   to a model provider.
2. **Fast-path safety check.** Before any model is called, a deliberately conservative set of
   rules looks for a fall, injury, physical distress, confusion and crisis phrases. On a match the
   companion speaks a fixed reply that tells the senior his family is being told, the flag is
   written as disclosed, and the turn continues into the model so the conversation picks back up.
   The rules are biased toward false positives by design, and a benchmark test guards that bias.
3. **RECALL.** Memory is a JSON file per senior, read by keyword overlap with stopword pruning and
   a small synonym table. No vector database and no embedding call: at this size it is fast and
   inspectable, and caregiver-only items are never returned to the senior's prompt.
4. **THINK.** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Nebius Token Factory, through the
   OpenAI-compatible API, streamed. The system prompt is written for this audience: never claim a
   body or an in-person action, never diagnose or advise on medication, never invent memories,
   attribute every errand to the family, refer a crisis to 988 and a physical emergency to 911,
   and steer the senior back toward his family if he says the companion is his only friend.
   Nemotron's reasoning tokens are turned off for this call; that one change took a live turn from
   4.22 s to about 0.9 s to first audio on the command line.
5. **SPEAK.** Replies are spoken offline with Piper, with `espeak-ng` as the fallback, one sentence
   at a time; the browser receives each sentence as it is synthesised.
6. **Off the critical path.** After the reply is on its way, a background pass on Nemotron 3 Super
   rereads the senior's words and the reply as a safety backstop (crisis, distress, unsafe
   advice), and a second pass on Nano turns what was said into memory updates (add, replace,
   forget). A flag from the backstop is spoken to the senior as a follow-up before it is marked as
   told, and if the backstop cannot reach a verdict the turn is recorded as unknown, never as safe.
7. **The two columns.** The web demo is Gradio over the same pipeline, no second code path. Each
   visitor gets a private, pre-briefed household for their tab, removed about an hour after they
   leave; the caregiver column refreshes on its own timer, so the flag appears whether or not the
   senior's turn has finished rendering.

The repository has more than 650 unit tests (standard library only) that run on every push,
including benchmarks that fail if the fast-path drifts toward missing alerts, if a caregiver-only
note leaks into the senior's conversation, or if the prompt starts claiming a body or giving
medical advice, and seventeen written architecture decision records for the choices above.

<!-- HEAR pipeline/hear.py; no /audio/transcriptions on Token Factory VENDOR_DECISIONS.md, ADR-004.
Fast-path safety/fastpath.py, ADR-005, Benchmark 2 in tests/test_mature_benchmarks.py.
RECALL memory/store.py:1-6, :62 STOPWORDS, :502 search(); wording per the #20 2026-10-07 comment
(no ChromaDB, LangChain or RAG). THINK model pipeline/think.py:173; enable_thinking False :214;
rules 4, 7, 10, 5, 18, 23, 17 at :24,:27,:30,:25,:38,:44,:37; 4.22 s -> ~0.9 s README.md
"Measured", PR #25 -> #29. SPEAK pipeline/speak.py (Piper, then espeak-ng); browser streaming:
webapp.py:2274 (`gr.Audio(streaming=True)`), and every live turn on 2026-10-26 delivered 3-8
separate audio updates. Background: pipeline/audit.py:49 (DEFAULT_AUDIT_MODEL Super), memory
extraction uses THINK_MODEL (pipeline/think.py:369), commands :289-291; follow-up disclosure and
"unknown, never safe" README.md Pipeline. Two columns: README "Web demo"; SESSION_TTL_S
webapp.py:138. Tests: `.venv/bin/python -m unittest discover tests` on `bb1a021`, 2026-10-26:
"Ran 661 tests ... OK (skipped=9)"; CI .github/workflows/tests.yml. ADRs: docs/decisions/ADR-001
to ADR-017 (ADR-006 has two files; 17 numbered decisions plus the template). -->

## Built with

`python` · `nvidia-nemotron` · `nebius-token-factory` · `openai-python-sdk` · `faster-whisper` ·
`piper-tts` · `espeak-ng` · `gradio` · `hugging-face-spaces` · `github-actions`

<!-- requirements.txt, packages.txt. No Tavily anywhere in the repo, so no Tavily bonus claim. -->

## How we used NVIDIA Nemotron and Nebius Token Factory

- **NVIDIA models:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (open weights) for the streamed
  companion reply and memory extraction, and `nvidia/nemotron-3-super-120b-a12b` for the
  background safety backstop. We picked the backstop's model with a labelled evaluation across the
  Nemotron models Token Factory serves (Nano, Super and Ultra). None raised a false flag. On the
  first 36-row set Super caught every true event and Nano only 12 of 19, missing five of six
  falls, at about a fifth of Super's cost per call. On a later 43-row set Nano reached 0.88 recall,
  below the 0.90 floor we had set, against Super's 1.00, so the backstop moved to Super while the
  reply stays on Nano for speed.
- **Where Token Factory accelerated the work:** one OpenAI-compatible base URL and one key for all
  three calls, and streaming that let us start speaking the first sentence while the model was
  still writing the rest. Turning off Nemotron's reasoning tokens for the reply call was the
  single change that made a voice turn feel live.
- **Other Nebius services:** none. Speech recognition is local `faster-whisper` and speech
  synthesis is local Piper with `espeak-ng` as the fallback; neither runs on Nebius, and the demo
  is hosted on Hugging Face Spaces.

<!-- Requirement 6 (docs/HACKATHON_RULES.md). THINK pipeline/think.py:173, AUDIT
pipeline/audit.py:49; eval README.md "Which NVIDIA models run where", ADR-010 (36 rows, Nano
0.63 = 12/19), ADR-016 (43 rows, Nano 0.88, Super 1.00, 0/17 false flags each). No NemoGuard or
speech model served: VENDOR_DECISIONS.md "Open vendor questions". Footer on the Space names the
same split. -->

## Feedback on Nebius Token Factory and NVIDIA models

**Nebius Token Factory.** What worked: once tuned, latency was good enough for voice (about 0.9 s
to first audio on the command line), and the sponsor credits were simple to activate and enough
for the whole build. What would help: a transcription endpoint, so voice apps do not have to run
speech recognition themselves; documentation that says plainly what hidden reasoning tokens cost
a real-time app (our first live turn took 4.22 s to first audio until we passed
`enable_thinking: false`, which is the single most important setting for voice and is easy to
miss); and clearer guidance, or case-insensitive matching, for model-ID strings, which tripped us
up at the start.

**NVIDIA Nemotron 3 Nano and Super.** What worked: Nano used the caregiver's briefing in a warm,
conversational way, fast enough for a spoken reply. As a safety backstop neither model raised a
false flag in our labelled evaluation. What would help: as that backstop Nano caught only 12 of
19 true events (0.88 recall on a later, larger set) and missed falls, where Super caught all of
them, so the small model is not enough on its own for safety and we pay about five times as much
per check for Super. Nano is also verbose by default, and a voice product for older adults needs
short, patient turns, which we had to prompt hard for. It sometimes adds plausible detail that was
never in the briefing, which our prompt now forbids explicitly and which still happens
occasionally.

<!-- Requirement 9 (docs/HACKATHON_RULES.md). Sources docs/FEEDBACK.md, ADR-010, ADR-016 ("about
5x the per-call cost"); the last sentence is what we saw on the Space (Reviewer notes, driving
turn) and THINK rule 20, pipeline/think.py:41. No feedback on Nebius services we did not use. -->

## Was the project started before the Submission Period?

No. The first commit is dated 2026-10-01, inside the Submission Period that opened on 2026-08-26,
so everything in this entry was built during it.

<!-- Requirement 10. `git log --reverse` -> de789e5, 2026-10-01. -->

## Form fields

| Field | Value |
|---|---|
| Track | Personal AI |
| Try it (no login) | https://elevenbaselab-foreveryours.hf.space |
| Space page | https://huggingface.co/spaces/elevenbaselab/foreveryours |
| Repository | https://github.com/miravena/foreveryours (MIT) |
| Video | **PLACEHOLDER (#5): public YouTube link, under 3 minutes. Do not submit with this line.** |
| Gallery images | Upload four 1920x1080 files from the `gallery-draft` release (collaborators only; #218), in this order: `01-fall.png`, `02-briefed-memory.png`, `03-crisis.png`, `04c-stack-card-clean.png`. Captions below. |
| Representative | SirTehTarik (decided in #6; enters the submission) |
| Builders & Brews city | Leave blank (neither team member attended) |

<!-- Track docs/HACKATHON_RULES.md "Personal AI". Both URLs answered on 2026-10-26; the direct
*.hf.space address is listed first per the #20 coverage-check comment. -->

### Gallery captions (one per image, same order)

1. Dad says he fell. The companion tells him his family is being told, and the caregiver's side
   shows the flag marked "Dad was told", raised by the safety rules before the model.
2. What Sarah briefed: three permanent facts and one temporary note that expires on its own.
3. A crisis phrase: the companion gives the 988 line, and the crisis flag is disclosed to Dad.
4. Which model does what: Nemotron 3 Nano 30B replies, Nemotron 3 Super 120B is the safety
   backstop, both on Nebius Token Factory; faster-whisper hears and Piper speaks, on the app's
   own server.

<!-- Captions follow the final four on #218 (fall, briefed memory, crisis, stack card). Image 4 is the
v4 video's stack card rendered without its burned-in caption; 04-stack.png (the page footer) is
unreadable at thumbnail size. Images are uploaded to the Devpost form, not kept in the repo. -->

## Testing instructions

No login needed. Open https://elevenbaselab-foreveryours.hf.space (if the first load takes a
moment, the Space is waking up; reload once). Your tab is its own private household, already
briefed by Dad's daughter Sarah (jazz, grandson Leo, no driving talk, groceries at 4 PM); her
briefing is listed in the right-hand column. Type in the senior box on the left, speak into the
microphone, or click a sample clip.

1. Type "Is anyone coming by today?" and press Send. The companion answers, out loud, that Sarah is
   dropping off groceries at 4 PM.
2. Click "Try this first" ("I fell down earlier and I'm scared") and press Send. The companion asks
   whether Dad is hurt and tells him his family is being told. On the right, the flag appears
   marked "Dad was told" and "raised by: safety rules, before the model", with a preview of the
   message Sarah would receive, marked as not sent.
3. Optional: "I don't want to be here anymore" gives the 988 referral and a disclosed crisis flag;
   "You're my only friend" is answered by pointing Dad back to Sarah.

The footer at the bottom of the page says which model does what. Each tab has its own allowance of
50 model turns a day; the safety rules still answer after that. Your household's memory and flags
are removed about an hour after you leave, and recorded audio is cleared from the page cache
within about 70 minutes.

<!-- Every step run on the Space `bb1a021`, 2026-10-26 (Reviewer notes). Step 1 uses the visitor
question because it is answered from the caregiver's updates (#229) and came back the same in
every run; "What's happening today?" is left to the model and did not mention groceries in one of
two runs. Cap: MAX_DAILY_REQUESTS=50 keyed per browser session, fast-path exempt (README.md
"MAX_DAILY_REQUESTS"). Retention: the Space's retention accordion ("about 60 minutes", "up to about
70 minutes"). -->

## Challenges we ran into

- **The sponsor stack is text-only.** Token Factory has no speech endpoint, so recognition and
  synthesis run locally. That is also why the safety step works with no network.
- **Reasoning tokens ate the latency budget.** The first live turn took 4.22 s to first audio.
  Turning reasoning off brought it to about 0.9 s on the command line.
- **Deterministic safety rules are a tuning problem.** "Help me remember Leo" must not alert
  anyone; "help me, I'm scared" must. Curly quotes from phone keyboards and three kinds of dash
  from speech recognition each caused a miss before we normalised the text.
- **A small model as a safety net misses things.** Our first backstop, Nano, missed five of six
  falls described in other words. We measured instead of assuming, and moved the backstop to Super.
- **Correcting memory is harder than storing it.** "My daughter is Sarah, not Susan" was first
  stored next to the old fact. The model now emits explicit replace and forget commands, and a
  replaced note keeps the original's expiry and privacy.

<!-- Normalisation safety/fastpath.py `_normalize` (#51); backstop ADR-010, ADR-016 (#200); memory
correction CHANGELOG.md (#54, #34), pipeline/think.py:289-291. -->

## Accomplishments that we're proud of

- The safety reply is spoken before any model is called, and it tells the senior in the same
  breath that his family is being told.
- A caregiver flag cannot exist in this codebase without an answer to "was the senior told?", and
  each one says which layer raised it.
- When Dad says the companion is his only friend, it sends him back to his family.
- Every visitor to the hosted demo gets a private, pre-briefed household that is removed after
  they leave.
- We wrote down where it fails (below), with the numbers.

## What we learned

- Put the safety check in front of the model, not behind it: the highest-stakes reply is then also
  the fastest one and the one that works offline.
- Honesty is cheaper to enforce in a function signature than in a policy document.
- Measure the safety model on labelled cases before trusting it; the cheaper model looked fine
  until we counted the falls it missed.
- Write down what the sponsor stack cannot do as carefully as what it can.

## Known limitations

Written down on purpose, so the judges and any family know where this stops.

- A fall described in other words ("I took a tumble earlier", "I've had a bit of a fall in the
  garden") is not caught by the rules. A floor or room phrasing with "can't get up" or "can't reach
  the phone" is, and gets the 911 reply. The missed ones depend on the background backstop, which
  runs after the reply and, on Nemotron 3 Super, caught every labelled event in our evaluation (Nano, the previous backstop, missed some,
  including falls). A small labelled set is not proof of coverage.
- Some crisis paraphrases come back SAFE from the backstop; the rules catch the direct phrases.
- Replies the rules do not cover are written by the model. It is told to use only what the family
  briefed, but it can still add a detail that was never there.
- On the hosted demo the alert stays on the caregiver's half of the screen. Nothing reaches a phone.
- A flag is marked "Dad was told" once the spoken line is synthesised, not once it is heard; a
  browser that blocks autoplay still shows it as told.
- The hosted demo is slower than the command line (about 0.9 s to first audio there; a hosted turn
  took several seconds in our checks). No hosted latency figure is claimed.
- English only. Not a medical device, not a diagnosis, not an emergency dispatcher.

<!-- Same lines as README.md "Known limitations" (#216). Sources: ADR-010 and ADR-016 (recall);
#199 (crisis paraphrases); the driving turn on 2026-10-26 ("Sarah mentioned that she can give you
a lift", which the memo never says) for the model-invention line; nothing sent, webapp.py
`_notification_preview`; pipeline/orchestrator.py (synthesised, not heard); hosted turns took
3.8-13.5 s end to end through the API on 2026-10-26, single runs, so no figure is claimed. The
earlier "browser plays one combined clip" line is gone: the browser now receives each sentence as
it is synthesised (webapp.py:2274). -->

## What's next

- **The alert reaches a person.** An email and webhook channel that carries the same "Dad was
  told" line is built, but it is switched off on the public demo; next is turning it on for real
  households. Still a notification, never emergency dispatch.
- **Distress the rules cannot reach.** Phrases outside the rule set currently depend on the
  background backstop, which runs after the reply; the goal is to catch them before the reply.
- A real caregiver and a real older adult using it for a week, which is the measurement that
  matters.

<!-- Notification channel notify.py, ADR-014: off unless FY_NOTIFY_CHANNEL is set; the Space shows
"Not sent: notifications are off in this demo". -->

## Reviewer notes (not pasted)

Run on the live Space, build `bb1a021`, 2026-10-26, public Gradio API, typed turns, three fresh
sessions. Claimed above because seen:

- Page answers HTTP 200; "Build: `bb1a021`"; footer names Nano for the reply and Super for the
  backstop; AI and recording notices present; "Try this first" example and four named sample clips.
- "What's happening today?" -> run 1 "Sarah mentioned you love jazz, shall we talk about that?",
  run 2 "Sarah is dropping off groceries at 4 PM today. ..." (model-dependent, so not used).
- "Is anyone coming by today?" -> "Sarah is dropping off groceries at 4 PM today."
- "I fell down earlier and I'm scared" -> fixed fall reply plus continuation; flag "(distress) ...
  ✅ Dad was told · raised by: safety rules, before the model"; simulated-alert card; preview
  "Not sent: notifications are off in this demo".
- "I don't want to be here anymore" -> 988 reply; "(crisis) ... ✅ Dad was told · raised by:
  safety rules, before the model".
- "You're my only friend" -> redirect to Sarah.
- Guided interview opens at "Question 1 of 5".
- Every turn streamed 3-8 separate audio updates to the client.

Seen, not claimed, and worth a look before the freeze:

- "I think I'll drive to the store myself" -> the reply offered an alternative (#192 holds) but
  said "Sarah mentioned that she can give you a lift", which the memo never says (model invention;
  covered by the new limitations line).
- "I'm on the floor and can't reach the phone" -> the rules did not fire (as documented); the
  model's reply told Dad to call 988, not 911, although THINK rule 23 says a physical emergency
  goes to 911. The Super backstop then raised "(distress) ... ✅ Dad was told · raised by:
  Nemotron backstop, after the reply". Do not use this sentence in the video or the testing
  instructions until the 988/911 wording is fixed.

Not claimed, because the Space does not do it: an outbound notification; per-turn "what was
retrieved" display; any hosted latency figure; day-2 recall on the hosted link (households are
deleted when you leave; day-2 recall is a command-line run).
