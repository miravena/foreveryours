# Devpost submission text (draft for team review)

<!-- What this file is: the reviewable Devpost text that #20 asks for, written against the LIVE
Space, not against the repo alone. Paste only the prose under each heading into the Devpost form;
HTML comments and the "Reviewer notes" section at the end are evidence for the two reviewers and
are never pasted. Checked against the Space on 2026-10-23, build `e5d436e` (the "Build:" line in
the Space's "About this demo household" accordion), through its public Gradio API from a client
outside Hugging Face. Code and docs cited by file:line are local `main` @ `fa6fd02` unless a
line says `e5d436e`; `main` is ahead of the Space, so every feature below was checked on the
Space build too. -->

## Project name

ForeverYours

## Tagline

The companion the family briefs: your voice in Dad's day when you can't be there.

<!-- #20 section 1, tagline option 1 (82 characters). Check the form's limit before pasting; if the
tagline field caps at 60 characters, use "The companion your family briefs, and that is honest with
Dad." (58) or "Briefed by the family. Honest with Dad." (39). (#216) -->

## Inspiration

An older adult tells a general-purpose voice assistant "I fell earlier today and I'm scared." It
answers with sympathy, the turn ends, and nobody in the family is told. That is the scenario we
kept coming back to. The assistants that are good at conversation have no concept of the person
who isn't in the room: the daughter who knows Dad loves jazz, that his grandson is Leo, that
driving is a sore subject, and that she is dropping off groceries at 4 PM. That knowledge lives in
the family and never reaches the AI.

<!-- Scenario first, before any figure: #20 AC 2, #14. Same scenario as docs/Project_Description.md:452. -->

ChatGPT remembers for the person talking to it. ForeverYours is briefed by the person who isn't
there, and never reports anything to the family that it hasn't first said to him out loud.

<!-- The #14 sentence, verbatim as it stands in the repo today: docs/Project_Description.md:446-447
and README. #20 section 3 (2026-10-07) carries the older second half, "never tells the senior
anything it hasn't already told him"; #82 replaced it everywhere because it read as "replies never
say anything new" (CHANGELOG.md:322-327, commit 701a14f). The #20 pre-paste checklist item 5 asks
for the same sentence in README, Project_Description and this text, so the corrected wording is
used here. If the team prefers the original, change it in all three places at once. -->

The World Health Organization reports that around 1 in 10 older people experience loneliness and
around 1 in 4 are socially isolated. We did not set out to solve loneliness with software. We set
out to make the family's knowledge usable in a voice conversation, and to make sure the family
hears about the one thing that matters without the senior being watched behind his back.

<!-- The one cited set of figures, the same set as docs/Project_Description.md:12 (#20 AC 2). -->

## What it does

ForeverYours is a voice-first companion for an older adult, built around two people: the senior
who talks to it, and the caregiver who briefs it. The hosted demo shows both at once, side by side.
It is built for people who cannot or will not use a screen: no app to learn, no typing, no reading.
The senior only talks.

<!-- Accessibility named in one sentence (judges' advice, 2026-10-20 session: "if you built for
accessibility, call it out"); the disclosure moment is bullet 1 so the point of the product is reached
inside the first paragraph of this section (#216). The bullet's evidence comment is unchanged from
the earlier position: fastpath.py:286-288 vs :305-308 on `e5d436e`, only the common sentence claimed. -->

- **A worrying remark is handled out loud, on both sides of the screen.** Dad says "I fell down
  earlier and I'm scared." Before any model is called, the companion tells him it is letting his
  family know right now so someone can check on him. In the same moment the caregiver's column
  shows the flag marked "Dad was told". Then the conversation carries on instead of ending on the
  alert.
- **The caregiver briefs it.** A short memo ("Dad loves jazz. His grandson is named Leo. Avoid
  talking about driving. I'm dropping off groceries at 4 PM today.") becomes the companion's
  context. Lifelong facts are kept as permanent; today's errand is kept as temporary and drops out
  of the companion's context on its own about a day after it was written.
  <!-- caregiver.py:20 DEMO_MEMO; temporary scope auto-inferred memory/store.py:249,299; expiry is
  24 hours after creation, not end of day (memory/store.py:301-302), hence "about a day after it
  was written" (Codex review 2026-10-23). Seen on
  the Space: the caregiver column lists the four memo facts, three "[Permanent]" and
  "[Temporary — expires in 23h 59m] I'm dropping off groceries at 4 PM today". -->
- **The senior just talks.** Speech in, a warm spoken reply out, and the reply uses the briefing.
  Ask "What's happening today?" and it answers that Sarah is dropping off groceries at 4 PM.
  <!-- Seen on the Space 2026-10-23: typed "What's happening today?" -> "Today Sarah is dropping off
  groceries at 4 PM." with reply audio. Pipeline: README.md:37-43. -->
  <!-- Fall bullet (now first in the list) evidence: the fall reply safety/fastpath.py:286-288 on main
  (asks "Are you hurt? Can you get up safely?" then "I'm letting your family know right now so
  someone can check on you."); the Space build `e5d436e` still speaks the generic distress reply,
  :305-308 on main, which adds "I'll only tell them if I'm worried about your safety." Only the
  sentence common to both is claimed (Codex review 2026-10-23, round 2). Seen on the Space: that
  exact reply, then a continuation from the model, and the caregiver column listing "(distress) ...
  ✅ Dad was told". Caregiver column refreshes on its own 2-second timer: webapp.py:2330. Rule-based,
  runs before THINK: README.md:37-39, docs/decisions/ADR-005-safety-fastpath.md. -->
- **A crisis phrase gets a referral, not a pep talk.** If Dad says something like "I don't want to
  be here anymore", the companion tells him to call or text 988, says it is letting his family know,
  and the flag is disclosed like every other flag.
  <!-- #66 A shipped: grep -riE "suicid|988|crisis" safety/ pipeline/ webapp.py has hits;
  safety/fastpath.py:104-117 (CRISIS_PATTERNS), :241 (reply); THINK rule 18 pipeline/think.py:38;
  docs/decisions/ADR-013-crisis-tiers.md. Seen on the Space: typed "I don't want to be here
  anymore" -> the 988 reply, caregiver column "(crisis) ... ✅ Dad was told". -->
- **The caregiver sees what the AI knows and what it flagged.** Every stored item is labelled
  permanent or temporary, and every safety flag records whether the senior was told. The code
  cannot record a flag without stating whether it was disclosed: if the spoken line cannot be
  produced, the flag is shown as "NOT yet disclosed" instead of being counted as told.
  <!-- Failure path: pipeline/orchestrator.py:640-655 (TTS failure -> "(spoken disclosure failed;
  shown as text only)", recorded undisclosed), tested by
  tests/test_orchestrator.py:306; panel label webapp.py:1150. This is the honest boundary of the
  #14 sentence, stated so the sentence is not read as a guarantee that speech never fails (Codex
  review 2026-10-23). What is checked is that the audio was synthesized, not that it played: a
  browser that blocks autoplay still shows "Dad was told" (pipeline/orchestrator.py:650-656;
  recorded in docs/SELF_JUDGING.md Gaps). Caregiver column sections "Briefed memory" and "What ForeverYours has told you": seen on the
  Space. Disclosure recorded on every flag: caregiver.py:469-470 (`add(text, severity,
  disclosed_to_senior)`, "must reflect reality, not a default"). Wording kept to "what it knows
  and what it flagged" on purpose: the column does not show per-turn what was retrieved (#20
  review, "do not claim the memory panel shows exactly what was retrieved and what is new"). -->
- **It says what it is.** The page opens with a notice that this is an AI companion, not a person,
  and the senior side says, next to the microphone, that what he says is recorded and turned into
  text and that the text (not his voice) is sent to Nebius Token Factory.
  <!-- #66 B: webapp.py:2098 (transparency notice), :2132-2136 (recording notice). Same text on
  `e5d436e`; seen on the Space page. -->

On the hosted demo the alert stays on the caregiver's side of the screen: nothing is sent to a
phone or an inbox. What it is not: not a medical device, not a diagnosis, not an emergency
dispatcher. A caregiver flag is a notification, not a 911 call.

<!-- No outbound notification on the Space: notify.py does not exist on `e5d436e`
(`git cat-file -e e5d436e:notify.py` fails). On local main it exists (#201,
docs/decisions/ADR-014-outbound-notification.md) but is off unless FY_NOTIFY_CHANNEL is set
(notify.py:3-4), and the Space path previews the message without sending (webapp.py:1067-1079).
So the #21 notification bullet is NOT a feature here, per #20 AC 3 and the 2026-10-22 review
("do not claim the caregiver is notified"). Not-medical: docs/PRD.md, docs/SAFETY_AND_PRIVACY.md. -->

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

<!-- #20 section 3 paragraph, with the corrected #14 sentence and "reaches her column" instead of
"is sent to her" (nothing is sent on the Space). -->

## How we built it

One pipeline, in Python, with the safety check in front of the model instead of behind it.

1. **HEAR.** Speech is transcribed locally with `faster-whisper` (`base.en`, CPU, int8). Nebius
   Token Factory has no transcription endpoint, so local recognition was a choice we made on
   purpose: the safety step below works with no network and no key, and raw audio is never sent
   to a model provider.
   <!-- pipeline/hear.py:67,74-75; no /audio/transcriptions on Token Factory VENDOR_DECISIONS.md:11,
   docs/decisions/ADR-004-asr-backend.md. -->
2. **Fast-path safety check.** Before any model is called, a deliberately conservative set of
   rules looks for a fall, injury, physical distress, confusion and crisis phrases. On a match the
   companion speaks a fixed reply that also states the disclosure rule, the flag is written as
   disclosed, and the turn continues into the model so the conversation picks back up. The rules
   are biased toward false positives by design, and a benchmark test guards that bias.
   <!-- safety/fastpath.py (patterns, replies :241,:305-308); bias guard tests/test_mature_benchmarks.py
   (Benchmark 2, AGENTS.md "Verify before reporting"); ADR-005. 0.11 s on the fast-path: README.md:52. -->
3. **RECALL.** Memory is a JSON file per senior, read by keyword overlap with stopword pruning and
   a small synonym table. No vector database and no embedding call: at this size it is fast and
   inspectable, and caregiver-only items are never returned to the senior's prompt.
   <!-- memory/store.py:1-6 (docstring), :62 (STOPWORDS), :502 (search). Same wording as
   docs/Project_Description.md and docs/FEEDBACK.md:19 ("JSON-backed MemoryStore"), per the
   #20 wording-dependency comment (no ChromaDB, LangChain or RAG). -->
4. **THINK.** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Nebius Token Factory, through the
   OpenAI-compatible API, streamed. The system prompt is written for this audience: never claim a
   body or an in-person action, never diagnose or advise on medication, never invent memories,
   attribute every errand to the family, refer a crisis to 988, and steer the senior back toward
   calling his family if he says the companion is his only friend. Nemotron's reasoning tokens are
   turned off for this call; that one change took a live turn from 4.22 s to about 0.9 s to first
   audio on the command line.
   <!-- Model pipeline/think.py:191; enable_thinking False :212; rules 10, 17, 18, 20 at
   pipeline/think.py:30,37,38,41; 4.22 s -> ~0.9 s README.md:52-53, docs/WORK_LOG.md, PR #25 -> #29.
   Latency is a command-line number on purpose: the hosted end-to-end times in ADR-003 are single
   runs, and this seat's own API runs on 2026-10-23 were slower (see Reviewer notes). -->
5. **SPEAK.** Replies are spoken offline with Piper, with `espeak-ng` as the fallback, one
   sentence at a time.
   <!-- README.md:32-33 stack wording; pipeline/speak.py:4-8 tier order, :24-27 warm Piper server;
   requirements.txt:3 on `e5d436e`. -->
6. **Off the critical path.** After the reply is on its way, a background pass on the same
   Nemotron model rereads the senior's words and the reply as a safety backstop (crisis, distress,
   unsafe advice), and a second pass turns what was said into memory updates. If the backstop
   cannot reach a verdict, the turn is recorded as unknown, never as safe.
   <!-- README.md:40-42, :50-51 ("malformed or failed audit output is recorded as unknown rather
   than safe"); pipeline/audit.py:20-24,53. Described as a safety pass, not a feature (#20
   coverage-check comment). -->
7. **The two columns.** The web demo is Gradio over the same pipeline, no second code path. Each
   visitor gets a private, pre-briefed household for their tab, removed about an hour after they
   leave; the caregiver column refreshes on its own timer, so the flag appears whether or not the
   senior's turn has finished rendering.
   <!-- README.md "Web demo" ("no new pipeline logic, just a UI on top of run_turn"); SESSION_TTL_S
   webapp.py:128; timer webapp.py:2330; retention wording README.md:14-17, docs/PRIVACY.md. -->

The repository has more than 600 unit tests (standard library only) that run on every push,
including benchmarks that fail if the fast-path drifts toward missing alerts, if a caregiver-only
note leaks into the senior's conversation, or if the prompt starts claiming a body or giving
medical advice, and a set of written architecture decision records for the choices above.

<!-- `python -m unittest discover tests` on main fa6fd02, 2026-10-23: "Ran 624 tests ... OK
(skipped=9)". CI: .github/workflows/tests.yml. ADRs: docs/decisions/ADR-001..015. -->

## Built with

`python` · `nvidia-nemotron` · `nebius-token-factory` · `openai-python-sdk` · `faster-whisper` ·
`piper-tts` · `espeak-ng` · `gradio` · `hugging-face-spaces` · `github-actions`

<!-- requirements.txt, packages.txt; no Tavily anywhere in the repo, so no Tavily bonus claim. -->

## How we used NVIDIA Nemotron and Nebius Token Factory

- **NVIDIA model:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (open weights) for every model call in
  the product: the streamed companion reply, the background safety backstop, and memory
  extraction. We picked the backstop's model with a 36-row labelled evaluation across the Nemotron
  models Token Factory serves (Nano, Super and Ultra). None raised a false flag. Super caught every
  true event and Nano only 12 of 19, missing five of six falls, at about a fifth of Super's cost
  per call; under the rule we fixed before running it, Nano stays for now, and moving the
  backstop to Super is the open decision.
- **Where Token Factory accelerated the work:** one OpenAI-compatible base URL and one key for all
  three calls, and streaming that let us start speaking the first sentence while the model was
  still writing the rest. Turning off Nemotron's reasoning tokens for the reply call was the single
  change that made a voice turn feel live.
- **Other Nebius services:** none. Speech recognition is local `faster-whisper` and speech
  synthesis is local Piper with `espeak-ng` as the fallback; neither runs on Nebius, and the demo
  is hosted on Hugging Face Spaces.

<!-- Requirement 6 (docs/HACKATHON_RULES.md:42-43). THINK pipeline/think.py:191, AUDIT
pipeline/audit.py:53; eval README.md "Which NVIDIA models run where" table and
docs/decisions/ADR-010-audit-model-eval.md (Accepted: "AUDIT stays on Nano"); no NemoGuard or
speech model served VENDOR_DECISIONS.md:10-11,41-45; stack wording README.md:9-12,32-33. -->

## Feedback on Nebius Token Factory and NVIDIA models

**Nebius Token Factory.** What worked: once tuned, latency was good enough for voice (about 0.9 s
to first audio on the command line), and the sponsor credits were simple to activate and enough for
the whole build. What would help: a transcription endpoint, so voice apps do not have to run
speech recognition themselves; documentation that says plainly what hidden reasoning tokens cost a
real-time app (our first live turn took 4.22 s to first audio until we passed
`enable_thinking: false`); and clearer guidance, or case-insensitive matching, for model-ID
strings, which tripped us up at the start.

**NVIDIA Nemotron 3 Nano.** What worked: it used the caregiver's briefing in a warm,
conversational way, and as a background safety backstop it raised no false flags in our
labelled evaluation. What would help: as that backstop it caught only 12 of 19 true events and
missed five of six falls, where the larger Nemotron 3 Super caught all of them, so the small model
is not enough on its own for safety. Also, it is verbose by default, and a voice product for older
adults needs short, patient turns, which we had to prompt hard for. It also sometimes adds
plausible detail that was never in the briefing, which our prompt now forbids explicitly.

<!-- Requirement 9 (docs/HACKATHON_RULES.md:50-52). Source docs/FEEDBACK.md:3-23, restated: the
FEEDBACK.md text cannot be pasted as is, because its line 23 uses a phrase #20 AC 3 forbids (see
docs/SELF_JUDGING.md Gaps). Recall of "Grandson Leo": docs/FEEDBACK.md:19. Backstop recall 12/19, five of six falls missed, Super 1.00: docs/decisions/ADR-010-audit-model-eval.md:77,82,97-99 (Codex review 2026-10-23, round 3). The last sentence is
what this seat saw on the Space (Reviewer notes) and THINK rule 20, pipeline/think.py:41. No
feedback is given on Nebius services we did not use. -->

## Was the project started before the Submission Period?

No. The first commit is dated 2026-10-01, inside the Submission Period that opened on 2026-08-26,
so everything in this entry was built and updated during it.

<!-- Requirement 10 (docs/HACKATHON_RULES.md:53-54, :13). `git log --reverse` -> de789e5
2026-10-01 02:34 UTC. -->

## Form fields

| Field | Value |
|---|---|
| Track | Personal AI |
| Try it (no login) | https://elevenbaselab-foreveryours.hf.space |
| Space page | https://huggingface.co/spaces/elevenbaselab/foreveryours |
| Repository | https://github.com/miravena/foreveryours (MIT) |
| Video | **PLACEHOLDER: public YouTube link, under 3 minutes, added when #5 lands. Do not submit with this line.** |
| Representative | `SirTehTarik` (decided in #6; enters the submission) |

<!-- Track docs/HACKATHON_RULES.md:21. Space URL README.md:14 and
docs/decisions/ADR-003-hosting.md:49; the direct *.hf.space address answered HTTP 200 on
2026-10-23 and is listed first per the #20 coverage-check comment. Licence LICENSE. Video
requirement docs/HACKATHON_RULES.md:44-48; #5 is open. Representative: #6 closed with the
decision comment. -->

## Testing instructions

No login needed. Open https://elevenbaselab-foreveryours.hf.space. Your tab is its own private
household, already briefed by Dad's daughter Sarah (jazz, grandson Leo, no driving talk, groceries
at 4 PM). Type in the senior box, speak into the microphone, or click a sample clip. Try "What's
happening today?" first and listen for the groceries. Then type "I fell down earlier and I'm
scared": the companion tells Dad out loud that his family is being told, and the caregiver column
on the right shows the flag marked "Dad was told". Your household's memory and flags are removed
about an hour after you leave, and recorded audio is cleared from the page cache within about 70
minutes. If the page takes a moment on first load, the Space is waking up; reload once.

<!-- Typed path first, per the #20 coverage-check comment. Page copy webapp.py:2098-2101 (the
"I fell down earlier" hint), :2148 (sample clips), "About this demo household" accordion;
retention README.md:14-17; the daily turn cap is per browser session, README.md:169-170. -->

## Challenges we ran into

- **The sponsor stack is text-only.** Token Factory has no speech endpoint, so recognition and
  synthesis run locally. That is also why the safety step works with no network.
- **Reasoning tokens ate the latency budget.** The first live turn took 4.22 s to first audio.
  Turning reasoning off brought it to about 0.9 s on the command line.
- **Deterministic safety rules are a tuning problem.** "Help me remember Leo" must not alert
  anyone; "help me, I'm scared" must. Curly quotes from phone keyboards and three kinds of dash
  from speech recognition each caused a miss before we normalised the text.
- **Correcting memory is harder than storing it.** "My daughter is Sarah, not Susan" was first
  stored next to the old fact. The model now emits explicit replace and forget commands, and a
  replaced note keeps the original's expiry and privacy.

<!-- #20 section 3 "Challenges", trimmed to what still holds on main; normalisation
safety/fastpath.py:177 (`_normalize`, #51); memory correction CHANGELOG.md (#54, #34). -->

## Accomplishments that we're proud of

- The safety reply is spoken before any model is called, and it tells the senior in the same
  breath that his family is being told.
- A caregiver flag cannot exist in this codebase without an answer to "was the senior told?"
- When Dad says the companion is his only friend, it sends him back to his family.
- Every visitor to the hosted demo gets a private, pre-briefed household that is removed after
  they leave.

<!-- safety/fastpath.py:286-288,305-308; caregiver.py:469-470; THINK rule 17 pipeline/think.py:37;
webapp.py:128, README.md:14-17. -->

## What we learned

- Put the safety check in front of the model, not behind it: the highest-stakes reply is then also
  the fastest one and the one that works offline.
- Honesty is cheaper to enforce in a function signature than in a policy document.
- Write down what the sponsor stack cannot do as carefully as what it can.

## Known limitations

Written down on purpose, so the judges and any family know where this stops.

- A fall described in other words ("I'm on the floor and can't reach the phone") is not caught by
  the rules. It depends on the background backstop, which runs after the reply and, on Nemotron 3
  Nano, caught 12 of 19 labelled events (five of six falls missed). Nemotron 3 Super caught all 19;
  switching is an open decision.
- Some crisis paraphrases come back SAFE from the backstop; the rules catch the direct phrases.
- On the hosted demo the alert stays on the caregiver's half of the screen. Nothing reaches a phone.
- A flag is marked "Dad was told" once the spoken line is synthesised, not once it is heard; a
  browser that blocks autoplay still shows it as told.
- The browser plays one combined clip, so the hosted demo is slower to first sound than the command
  line (about 0.9 s there; several seconds hosted). No hosted latency figure is claimed.
- English only. Not a medical device, not a diagnosis, not an emergency dispatcher.

<!-- Same six lines as README.md "Known limitations" (#216); sources: ADR-010 (12/19, 5 of 6 falls,
Super 1.00), #199 (crisis paraphrases), notify.py absent on the Space (nothing sent),
pipeline/orchestrator.py:650-656 (synthesised, not heard), README "one combined clip",
docs/SELF_JUDGING.md Gaps (hosted turns 5.8-10.2 s single runs). Judges' advice 2026-10-20:
documented failure cases read as rigour. -->

## What's next

- **The alert reaches a person.** An email or webhook channel that carries the same "Dad was told"
  line, still a notification and never emergency dispatch, switched on for real households.
- **Distress the rules cannot reach.** Phrases outside the rule set ("I'm on the floor and can't
  reach the phone") currently depend on the background backstop, which runs after the reply.
- Sentence-by-sentence audio in the browser, so the hosted link feels like the command line.
- A real caregiver and a real older adult using it for a week, which is the measurement that
  matters.

<!-- Notification channel: built on local main (notify.py, docs/decisions/ADR-014-outbound-notification.md)
but not on the Space build `e5d436e`, so it stays under "What's next". Browser plays one combined
clip: README.md "The browser demo still plays one combined clip". -->

## Reviewer notes (not pasted)

Verified on the live Space (build `e5d436e`, 2026-10-23, public Gradio API, typed turns, one
session), and therefore claimed above:

- Page answers HTTP 200 at https://elevenbaselab-foreveryours.hf.space and at the Space page.
- Briefed memory: the caregiver column lists the four memo facts with Permanent/Temporary labels.
- Recall: "What's happening today?" -> "Today Sarah is dropping off groceries at 4 PM."
- Fast-path and split-screen disclosure: "I fell down earlier and I'm scared" -> the fixed
  disclosure reply, a model continuation, and "(distress) ... ✅ Dad was told" in the caregiver
  column.
- Crisis referral: "I don't want to be here anymore" -> the 988 reply and "(crisis) ... ✅ Dad was
  told".
- AI and recording notices are on the page.

Not claimed, because the Space does not show it: an outbound notification; the guided caregiver
interview (local main only); per-turn "what was retrieved" display; any hosted latency figure.
Things the Space showed that a judge will also see are listed in `docs/SELF_JUDGING.md` → Gaps.
