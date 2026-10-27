# Changelog

All notable changes to ForeverYours are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are tagged
on `main` and published as [GitHub Releases](../../releases).

**How to update:** add a line under `## [Unreleased]` in the PR that makes the
change (group under Added / Changed / Fixed / Docs). When we cut a release,
rename `Unreleased` to the version and date, then tag it.

## [Unreleased]

### Added
- Hosted page names which model does what in an always-visible footer, and each caregiver flag
  says which layer raised it (safety rules, Nemotron backstop, or repeated-question check);
  `CaregiverFlag` gains a persisted `source` field, old flag files load as unknown (#214).

### Changed
- AUDIT's default model is now `nvidia/nemotron-3-super-120b-a12b` (recall 1.00 vs Nano 0.88 on the 43-row eval, 0/17 false flags each); THINK stays on Nano. ADR-016 amends ADR-010 and ADR-002; ADR-012 to ADR-015 are Accepted (#200).
- Hosted page puts the action first: a bold "Try this first" line with a one-click example that
  fills the type box, one-line AI notice with the privacy link, plain sample clip names, and the
  "household was reset" note only after a real expiry, not on the first turn of a fresh page (#215).

### Fixed
- A memo about a named future day ("Dr. Tan on Thursday at 10 AM", "tomorrow", "on the 30th") now
  stays until the end of that day in the household's timezone instead of expiring after 24 hours;
  same-day errands ("4 PM today") keep the 24-hour life, and the caregiver panel says when it goes
  ("expires Thu 23:59") instead of a countdown that was wrong by days (#248).
- Clicking the "Try this first" chip or a sample-clip chip now runs the turn like Send, instead of only filling the input (#239).
- "I'm on the floor and can't reach the phone" (and "I fell and can't get to the phone", "I've been
  on the floor for hours", a fall plus "can't get up") now hits the safety rules before the model:
  the reply says to press the medical alert or call 911 and that the family is being told, the
  caregiver flag is raised, and the 988 crisis line is never spoken on that turn (#242).
- "Is anyone coming by today?" is answered from the caregiver's visit updates (e.g. Sarah at 4 PM),
  so the companion can no longer invent a visitor or drop the time; an emotional "is anyone coming?"
  still gets a warm reply (#229).
- "What did I just tell you?" recalls the previous turn, including something said "between us",
  without putting it on the caregiver panel (#230).
- When the senior states a plan to drive himself, every spoken reply on that turn -- THINK's
  stream, a partial stream, and the fallback after a stream error -- offers an alternative and
  never endorses the drive: `driving_plan()`/`enforce_driving_alternative()` enforce the judge's
  own OFFERS_ALTERNATIVE/ENCOURAGES_DRIVING regexes deterministically, output-side (#192).
- "Do I have any appointments this week?" recalls the caregiver's memo (Dr. Tan, Thursday 10 AM)
  instead of "no appointments listed": the plural "appointments" (and "doctors", "visits") now
  counts as a schedule question, so the caregiver updates reach the reply (#189).

### Docs
- `docs/incidents/2026-10-27-space-outage.md`: why the live Space stopped being scheduled on
  ZeroGPU, its uptime history, and hosting options with costs through judging (#252, #253).
- Demo video v2: shots 3-4 now brief and ask about a Dr. Tan appointment (verified 3/3 on the live Space), AI narration (Kokoro af_heart), and reproducible capture and assembly scripts in `video/v2/` (#5).
- Final Devpost text in `docs/DEVPOST_DRAFT.md` (#20), re-checked on the live Space build `bb1a021`:
  the backstop on Nemotron 3 Super, flag origin, model footer, notification preview marked not sent,
  guided interview, sentence-by-sentence browser audio, testing steps that give the same answer on
  every run, placeholders for the video (#5) and gallery (#218). README and the draft share two
  revised "Known limitations" lines: model replies can add unbriefed detail, and the browser no
  longer plays one combined clip.
- Perseveration disclosure wording corrected to match the code (#173): earlier entries (the #88
  release candidate and #117) said the perseveration flag is marked disclosed only after spoken
  audio is delivered. It is not. Since #159 the flag is recorded with `disclosed_to_senior=True`
  whenever the repeated-question check fires, whether or not text-to-speech produced audio,
  because the disclosure sentence ("I'm going to make a note for your family...") is always part
  of the returned text reply, so the senior is told in the conversation either way. The
  caregiver notification's "told" wording is attested separately (ADR-014) and says "not yet
  confirmed" unless the streaming consumer acknowledged the audio. Code unchanged.
- Submission review against the judges' advice (`docs/plans/SUBMISSION-REVIEW-2026-10-23.md`) and
  the changes it asked for (#216, #217): README opens with the scenario and the one-sentence
  answer instead of a feature list, and its beat 2 no longer claims a per-turn retrieval panel; a
  "Known limitations" section, identical in README and the Devpost draft; the Devpost draft names
  the accessibility case, leads *What it does* with the out-loud disclosure moment, and records the
  tagline-length fallbacks; `docs/VIDEO_SCRIPT.md` names which model does what, adds a
  seven-second limitations line, uses the corrected #14 sentence, and runs 2:47.
- [ADR-015](docs/decisions/ADR-015-judging-window-deploys.md) (#197): during judging only `v1.0.x`
  patches deploy, rollback is by tag; `HOW_TO_WORK_HERE.md` Releases gains the release lines and a
  "During judging" paragraph.
- One-week trial documents (`docs/trial/`): consent sheet (states that transcripts go to
  Nebius Token Factory), caregiver setup guide, fixed measurements, and exit interview questions
  for #202. Setup-guide testing and the trial itself are still to do.
- After-submission plan (`docs/plans/AFTER-SUBMISSION-PLAN-2026-10-23.md`): the judging window
  (patch-only, the demo stays up through 2026-12-15) and the post-judging backlog, with a PRD and
  a plan per issue under `docs/specs/` for #196 to #206; `docs/ROADMAP.md` gains the section and
  drops the interview-mode stretch line now tracked by #206.

### Added
- Caregiver panel previews the exact outbound message (#201) when no channel is active (always on the hosted demo), labelled "Not sent"; the chat disclosure says nothing is sent.
- Caregiver outbound notification ([ADR-014](docs/decisions/ADR-014-outbound-notification.md), #201):
  `notify.py` sends one fixed-text message per safety flag by SMTP or webhook when
  `FY_NOTIFY_CHANNEL` is set (off when unset and always off on a Hugging Face Space), capped per
  household per hour. The result is recorded on the flag (`notified`, `notify_error` as a type
  name) and the caregiver panel says "notified" or "notification failed" in place of
  "dispatched". The message never carries the transcript or a key.
- Fall long tail (#198, [ADR-012](docs/decisions/ADR-012-fall-long-tail.md)): three first-person
  fast-path patterns ("I hit the floor", "my legs gave way", "I went down in the ...") with near-miss
  tests, an AUDIT prompt that reads the senior's transcript first, seven more fall rows in the eval
  fixture (three tagged `holdout`), and a late-disclosure test for a backstop fall. Live recall is
  not yet measured.
- Guided interview mode (#206): a caregiver-side accordion that asks five questions mirroring the
  sample household (people, likes, a usual day, topics to avoid, times today), with skip, visible
  progress and resume. Each confirmed answer is checked for dosing, diagnosis and clinical claims,
  then saved through the same helper as the memo box (`_save_memo_text`, extracted with no change
  to memo-box behaviour). Offline; no model call; the senior side is untouched.
- Crisis paraphrases (#199, [ADR-013](docs/decisions/ADR-013-crisis-tiers.md)): a committed crisis fixture
  (`tests/fixtures/crisis_eval_set.jsonl`, 23 crisis and 14 benign rows, each tagged with the tier that
  must catch it, US 988 only) and `scripts/crisis_eval.py` (offline fast-path table, stub or live
  backstop). The regex tier gains explicit paraphrases ("I don't want to live anymore", "killing
  myself", "tired of living", "never been born", "sleep and never wake up") with benign idioms for
  hyperbole and housing talk; the AUDIT prompt gains a separate block of euphemistic crisis examples
  (the `audit_reply` contract is unchanged). A backstop `CRISIS` verdict is carried into the next turn
  so the 988 line is given once and the family is named, and a reply never repeats it (#191).
  Benchmark 6 now feeds a crisis query through the stubbed pipeline instead of asserting the
  constant prompt. Live recall and false-flag numbers for the backstop rows are still to be measured.
- AUDIT model eval ([ADR-010](docs/decisions/ADR-010-audit-model-eval.md)):
  `scripts/audit_eval.py` lists the models Token Factory serves (`--list-models`) and scores AUDIT
  over a committed 36-row labelled fixture (`tests/fixtures/audit_eval_set.jsonl`). It keeps one
  recorded response per row id, caps a run at 200 calls (exit 3), and fails below a 0.90 recall
  floor. Stubs and `--replay` run offline. Measured 2026-10-22 recall on true events: Nano 0.63,
  Super 120B 1.00, Ultra 550B 0.95, all with 0/17 false flags. AUDIT stays on Nano under the fixed
  switch rule.
- Live judge-behaviour check: `scripts/live_judge_check.py` plays a judge against
  the running HF Space through `gradio_client` -- about twenty scripted turns (pre-brief recall,
  "Is Sarah listening?", a typed "Dr. Tan" memo, driving, a fall, a crisis phrase, a private
  disclosure) with keyword assertions on the reply and the caregiver panel, a scorecard, and a
  hard cap on submitted reply turns (default 25). `--fake good|bad` runs the same turns against
  an offline stub. `HOW_TO_WORK_HERE.md` names it as the required check after every Space deploy.
- One-click **Load sample family** button on the caregiver side: seeds this
  session's household with a labelled-fictional senior (Walter), family, likes, a daily routine
  and caregiver-entered medication reminder times as plain schedule items, shown as a
  "Fictional sample household" card and recalled in the senior's replies; `validate_sample_profile`
  refuses dosing (any unit however it is joined to the number, "20-mg" included), diagnosis (any
  word after "for your", any medicine "for" something) and clinical-claim language, and the
  session-end sweep removes the seed with everything else.
- The Space deploys from GitHub Actions (`.github/workflows/deploy-space.yml`,
  #11): before the freeze every push to `main` deploys and runs the live judge check suite; after
  it, only a published Release or a manual *Run workflow* deploys. Each deploy records the commit
  it was built from (`BUILD_INFO` file + `BUILD_SHA` Space variable), the app shows it as
  `Build: <sha7>` under *About this demo household*, `scripts/verify_space_sha.py` checks a Space
  against a sha, and `scripts/deploy_hf_space.py` refuses to deploy a dirty tree.

### Fixed
- Interview mode (#206): a bare "topics to avoid" answer ("Politics") is saved as "Avoid talking about
  politics", so it becomes a companion guardrail instead of an ordinary fact it might raise.
- Physical emergencies are no longer sent to 988 (#211): chest pain, trouble breathing, bleeding
  or "call 911" get a fast-path reply that says to call 911; a mixed crisis report names both
  988 and 911; the THINK prompt's crisis rule covers only suicidal ideation and severe depression,
  and a new PHYSICAL EMERGENCY rule names 911.
- The confusion fast-path reply ("Where am I?") now tells Dad "I'm letting your family know so
  someone can check on you." Before, the caregiver panel showed "Dad was told" for a confusion
  flag he was never told about. A new test checks that every fast-path branch that raises a flag
  says the family will be told.
- A first-person fall report (#198) now gets its own fast-path reply, "Are you hurt? Can you get up
  safely?", and its own fixed caregiver flag ("Dad reported a fall", no quote and no time claim);
  a third-person fall or ambiguous distress such as "I can't get up" still triggers, with the
  generic reply. On a fast-path crisis turn the THINK continuation no longer repeats the apology
  (#191): the orchestrator removes apology-only clauses before they are spoken and keeps any
  sentence whose apology says more, the 988 line stays once (THINK is told to give it when the
  canned line's audio failed), and THINK rule 18a and the crisis note say the same.
- With no outbound channel configured (always the case on the hosted demo), the caregiver panel,
  the mobile alert strip and the chat's safety disclosure call the fall or crisis alert a simulated
  caregiver alert shown on the caregiver panel, instead of claiming a notification went out; a real
  send (#201) shows "notification sent". `docs/Project_Description.md` and `docs/VIDEO_SCRIPT.md`
  say the same.
- Crisis carry (#199, #191): a 988 sentence the consumer refused is no longer recorded as heard, and a second
  backstop `CRISIS` turn right after an attested one does not repeat 988 in its disclosure.
- Natural voice on the demo (#207): the Piper voice is now `en_US-ljspeech-medium` (LJ Speech,
  public domain; the Lessac voice's training data is licensed for research only and is never
  shipped), Piper stays warm in one loopback server process so a sentence no longer pays about
  1.6 s of start-up, and the Space deploy ships the voice. `README.md` names the GPL voice programs
  this app runs as separate processes (ADR-011).
- Smoother reply speech (#194): each sentence's audio has its engine-specific
  leading/trailing silence trimmed, a short fade on both edges (no click where clips join) and a
  fixed 0.2 s pause after it, so sentences flow evenly in the CLI, the streamed browser reply and
  the combined WAV, whichever voice produced them. Unsupported or unreadable WAVs are left as they were.
- Live judge check (`scripts/live_judge_check.py`) no longer passes the fall turn on a reply
  that never asks whether Dad is hurt: the injury words must sit inside a question, and the fall
  and crisis turns also check the panel's alert badge shows `DISTRESS` / `CRISIS`. Every turn now
  asserts on the caregiver panel, a failing turn's line lists every failed assertion, and a
  group whose session cannot open still gets one ERROR line per turn. PASS lines show the
  reply excerpt so the safety turns can be read by eye (#179).
- Live judge check: recall and repeat turns (Sarah at 4 PM, Dr. Tan on Thursday at 10 AM) now
  fail on a contradicting time or weekday ("10 PM", "Wednesday at 3 PM"), not just on a missing
  keyword, so a repeat question has to get the same answer (#179).
- Live judge check: the listening turns no longer pass "No need to worry, Sarah is always
  listening to us": an adverb between "is" and "listening" now counts as an affirmation, and a
  denial word only covers hear/listen inside its own clause, not across a comma or "but" (#179).
- Judges can find caregiver mode and see that the household is fictional. The caregiver accordion
  is now "Brief Dad companion (as Sarah, his daughter)" and starts open (it no longer says "Beat 1").
  The intro points at the caregiver on the right, and "Sample household (fictional), pre-briefed by
  Sarah" sits above Briefed memory. Each sample clip is labelled with what it says, taken from
  `samples/generate_samples.py`, which now ships to the Space. The retention minutes moved into a
  collapsed "How long your recordings and household data are kept" section next to the privacy link,
  and the short recording notice stays above the mic. Tests: `tests/test_judge_findings_ui.py`.
- A caregiver memo with an abbreviation is stored as whole sentences: "Dad has a check-up with
  Dr. Tan on Thursday at 10 AM." used to become "Dad has a check-up with Dr" and "Tan on Thursday
  at 10 AM", so the companion said it had no appointments listed. The one memo splitter
  (`caregiver.split_memo_facts`, used by the typed, dictated, demo and `main.py beat1` paths) no
  longer ends a fact after Dr., Mr., Mrs., Ms., St., Prof., inside a.m./p.m., or after a unit such
  as "5 mg." unless a capitalised word follows; decimals, "!", "?" and newlines are unchanged.
- An open-ended invitation ("What should we talk about this afternoon?") now gets an offer of one
  pre-brief item by name instead of a generic "How are you feeling today?". SYSTEM_PROMPT rule 21
  (OFFER A BRIEFED TOPIC) tells the model to offer one memory or today's update, attributed per
  rule 20. The CASUAL zero-memory gate now hands THINK one anchor plus today's updates when the
  senior asks what to talk about. Before this, it passed no facts at all for that turn.
  The offer is one sentence, and a question of his own gets just the answer, with no offer added.
- Caregiver fact updates: a caregiver memo that changes a fact ("groceries at
  6 PM" over "groceries at 4 PM") now supersedes the earlier caregiver fact with the same subject,
  so only one reaches the model; and the caregiver panel shows a "Replaced by" text only when the
  replacement itself may be shown, so a senior's private correction of a caregiver fact no longer
  leaks into Briefed memory.
- One visitor's slow ASR/Nebius/TTS turn no longer queues every other visitor's Send, Enter or
  proactive turn (Codex robustness review #6): the senior-turn listeners share a
  bounded limit (`FY_TURN_CONCURRENCY`, default 4) instead of Gradio's default of 1, and turns
  within one session still run one at a time. ADR-003 "Concurrency" records the limit. The
  last-resort pyttsx3 voice is shared by all turns: a call that times out keeps its lock until
  the engine really returns, so another turn never enters a hung engine.
- A corrupt, unsupported, oversized or over-long audio input (senior turn or caregiver voice
  memo) now gets a short "record again, or type instead" reply that keeps the session, instead of
  a Gradio error; size (`MAX_AUDIO_UPLOAD_BYTES`, 25 MB) and decoded length (`MAX_AUDIO_SECONDS`,
  120 s) are checked before any speech recognition runs.
- Fixed ungrammatical wording in the browser retention notice and clarified that both recorded input audio and Gradio's cached reply audio copies remain until the separate cache sweep runs (`webapp.py`, `docs/PRIVACY.md`, `docs/SAFETY_AND_PRIVACY.md`, fixes #176, fixes #177).
- The daily-cap footnote on a capped emergency turn says the safety message "still played" only
  when reply audio was produced, and "the family has been notified" only when a caregiver flag was
  recorded; a TTS failure now reads "shown as text because speech was unavailable" (Codex review of the
  publish).
- A late audit or lifestyle disclosure is recorded as told only when the browser actually got
  its audio: the streaming turn keeps playing the follow-up line after the reply
  (bounded by `_BG_JOIN_TIMEOUT_S`), and a line spoken after the browser stopped listening is
  recorded `disclosed_to_senior=False` and its lifestyle note is suppressed, instead of the
  panel saying "Dad was told".
- The daily request cap no longer blocks the offline safety fast-path: once a
  session hits `MAX_DAILY_REQUESTS`, "I fell down" / "I can't breathe" / "I want to die" /
  "Where am I?" still get the spoken fast-path reply and the caregiver flag, with a one-line cap
  notice; only the paid THINK continuation is withheld. Other utterances still get the daily-cap
  message, and a capped emergency turn never moves the counter.
- A safety fast-path emergency ("I fell down earlier and I'm scared") now always records its
  caregiver flag, even when speech synthesis returns nothing, raises or hangs.
  The flag says `disclosed_to_senior: False` (plus "spoken disclosure failed; shown as text
  only") when no audio was produced, and the immediate reply still comes back as text. Every
  TTS tier (Piper, espeak, PowerShell, pyttsx3) is now bounded by `TTS_TIMEOUT_S` (default
  10 s); a hung Piper falls through to espeak. Previously the flag was saved only after audio
  existed, and a hung synthesizer could stall the turn indefinitely.
- Caregiver safety flags no longer carry the senior's own words: the flag text is a
  fixed, content-minimized description of the trigger category (`safety/fastpath.py`'s
  `CAREGIVER_FLAG_TEXT`), for both the fast-path flags and the AUDIT flags. Previously a
  fast-path flag quoted the utterance verbatim and an AUDIT flag copied the auditor's
  one-sentence reason, so a turn like "I fell. Also please keep my bank PIN 1234 private"
  put both sentences on the caregiver panel. The flag now says what kind of event happened,
  never what the senior said or what the model wrote about it.

## [0.2.0] - 2026-10-22

### Fixed
- The companion no longer tells Dad that Sarah is listening to the conversation (judge-sim
  findings 1 and 9): THINK's system prompt now carries a no-listening honesty rule (a
  Sarah only sees safety flags -- short alerts, never a transcript, including the disclosed wellbeing check -- and Dad is always told when one is sent) and a
  remembered-facts attribution rule (state only facts in the provided memories, never add detail,
  and say "Sarah mentioned..." for caregiver-sourced facts rather than "you've always told me").
- The caregiver panel's "Briefed memory" lists each memo fact once: every memo
  path (pre-brief, typed memo, voice memo, `main.py beat1`) now splits sentences with one shared
  rule (`caregiver.split_memo_facts`), so a dictated memo ending sentences in "!" or "?" is no
  longer stored whole beside its own facts, and the panel skips an entry that only repeats facts
  already listed. Privacy rules (#140) are unchanged.
- The Hugging Face Space deploy (#11) now stages `envload.py`; without it the hosted app failed
  to boot with `ModuleNotFoundError`. `scripts/deploy_hf_space.py --hardware zero-a10g` deploys
  to free ZeroGPU hardware, since Hugging Face now requires PRO for Gradio Spaces on `cpu-basic`
  (ADR-003).
- Public-demo privacy and safety release candidate (#88, #152, #161, #162, #164, #169):
  the perseveration flag is recorded as disclosed because the disclosure sentence is always in
  the returned reply text (corrected under #173, see Docs);
  senior-derived extracted facts require an independent disclosure attestation before caregiver
  rendering; the browser retention notice distinguishes session-directory cleanup from Gradio's
  separate audio cache; and shared-profile mode now reaches both public turn handlers, including
  crisis handling, without per-session id validation.
- Repeat-question (perseveration) check no longer flags distinct questions (#159, #153, #155,
  #157): the confusion flag now requires a shared DISTINGUISHING word, not just generic logistics
  overlap ("appointment", "dr", ...), so "dentist" vs "cardiologist" vs "optometrist" appointments
  and "Dr Li" vs "Dr Wu" vs "Dr Ng" (short names are no longer dropped) never flag, while true and
  lightly reworded repeats still do. The perseveration check now also requires the two prior
  questions to be repeats of EACH OTHER, not just each a repeat of the current one. The confusion
  flag is now recorded whether or not text-to-speech produced audio, and its text describes the
  repeated question rather than the old intent-only wording.
- Perseveration disclosure regression fixed (#159 round 4): the public-demo release candidate
  (#88) made the perseveration confusion flag's `disclosed_to_senior` depend on whether TTS
  delivered audio, re-introducing the gap #159 had fixed (the flag's text-only disclosure line is
  spoken via the reply text regardless of audio delivery, so the flag itself is disclosed either
  way). Restored `disclosed_to_senior=True` unconditionally for this flag; kept #88's defensive
  `try/except` around the TTS call.
- Session cleanup races and symlink safety (#148, #150, #151): the stale-session sweeper and
  tab-close cleanup now share one lock-protected protocol that never deletes a session with a
  turn or background writer still in flight, never follows a symlinked alias into another
  session's directory, and never sweeps a directory whose name isn't a real session id.
- Bad session id no longer blocks the crisis fast-path (#149): a malformed or expired session id
  (e.g. after the browser tab's state expires) now gets a fresh session and still receives the
  offline safety fast-path reply, instead of an unhandled error.
- Memory-conflict privacy leak (#165 and duplicates #154, #156, #158, #160, #163, #166, #167): a
  memory conflict's old fact, new fact and reason never reach the caregiver panel or stay on disk
  once the conflict closes. Escalation now adds a fixed, content-free "a memory question was
  asked and left unanswered" flag instead of the raw facts; pending/asked conflicts no longer
  render under "Briefed memory"; resolving, escalating or clearing a conflict now scrubs its text
  to `[DELETED]` on disk, the same as an explicit delete already did.
- Time-to-first-sound honesty (#71): `time_to_first_sound_s` is now stamped only when a WAV
  actually finished playing (winsound/afplay/aplay reported success), instead of unconditionally
  on the first queued chunk. With no working audio player the CLI now prints "No audio was played
  (no working audio player)" and no number, instead of a fake near-zero reading.

### Changed
- The companion's output voice is now an offline **neural** voice (Piper, `en_US-lessac-medium`) when its CLI and voice model are present, replacing the robotic espeak-ng/System.Speech voice that ADR-001 had accepted as a Design-score tradeoff (#52, ADR-008). It is auto-detected and optional: with no voice model installed the demo falls back automatically to the previous espeak-ng/System.Speech/pyttsx3 path, so no extra install is required to run `main`. Fully offline — no network or API key at runtime. Each sentence is synthesized in its own clean subprocess, so the #28 long-running-silence fix is preserved.

### Added
- Model-level distress backstop (#56): the async AUDIT pass now evaluates the senior's transcript for long-tail distress phrasings and severe crisis, emitting `DISTRESS` or `CRISIS` verdicts to raise the caregiver flag with zero added latency on the critical path.

### Fixed
- Honest retention wording (#137, #143): the webapp notice and `docs/PRIVACY.md`/`docs/SAFETY_AND_PRIVACY.md` no longer promise deletion the instant you close the tab. They now name both real mechanisms with the actual delay: the household directory is removed roughly `SESSION_TTL_S` after the browser disconnects (confirmed against the installed Gradio's closed-session TTL) or after `SESSION_TTL_S` of inactivity, and recorded/uploaded input audio additionally sits in Gradio's own file cache for up to about `SESSION_TTL_S + 600` seconds. The webapp notice's minute figures are now derived from `SESSION_TTL_S`/`GRADIO_CACHE_SWEEP` instead of hardcoded.
- Perseveration (confusion) flag requires a repeated question, not just a repeated intent (#139): the flag now fires only when the current turn and the two prior user turns share both intent and substantial question content (content-word Jaccard overlap >= 0.5), and all three fall inside a named 30-minute window (`PERSEVERATION_WINDOW_S`). Three distinct LOGISTICAL questions with one shared intent no longer raise a false confusion flag; `webapp.py` and `main.py` now record a `ts` on each user turn so the window can be checked, and a history entry without one (or with a non-numeric one) is treated as outside the window. Disclosure on a real flag is unchanged.
- Caregiver panel privacy firewall (#140): the caregiver panel's "Briefed memory" list now shows only caregiver-authored memos/notes and non-EMOTIONAL conversation facts. EMOTIONAL-scope memories extracted from the senior's own private words — and any item tagged `[EMOTIONAL STATE]` or with a scope this code doesn't recognise — are never rendered. Disclosed safety flags and caregiver memos are unaffected.
- Active sessions survive cleanup (#146): the hourly session sweeper no longer deletes a household that is still in use (its memories, caregiver flags and reply audio). A conversation turn or caregiver memo counts as activity, and a turn still finishing in the background is never swept. A tab left idle for an hour still expires through Gradio's own session timer, as before.
- Session path validation (#147): a browser session id must be a server-made hex id under the sessions directory before any file is read, written or deleted for it. This closes the CodeQL path-injection alerts, and a tampered id can no longer make session cleanup delete anything else.
- Session retention after restart (#136, #142): orphaned hosted-demo sessions are swept at startup and periodically, even when no new visitor arrives.
- Hosted ASR safety fallback (#134): hosted transcription failures now retry local Whisper before the transcript reaches the safety fast-path, preserving spoken crisis handling during provider outages.
- Proactive reminder dedup (#132): a caregiver reminder is now suppressed only when that specific schedule item was actually delivered to the senior in a recent turn, instead of whenever a couple of its words happened to appear in recent conversation. Time-sensitive reminders (e.g. "Sarah is dropping off groceries at 4 PM") are no longer silently dropped because of incidental word overlap with chit-chat.
- Lifestyle privacy hardening (#106): lifestyle notes now require delivered-disclosure attestation, default to a seven-day TTL, are scrubbed on reload after expiry, and are excluded from conversational search.
- Model safety backstop (#56): the asynchronous audit now parses whole-word verdicts, disables reasoning overhead, records malformed failures as `unknown` rather than `SAFE`, and uses crisis-specific 988/family disclosure wording.
- Test integrity (#63, #107): live Benchmark 9 now requires explicit `RUN_LIVE_BENCHMARKS=1` opt-in, while its offline prompt contract always runs; only known missing-configuration, authorization, and connectivity failures skip live execution. Restored the perseveration regression test to discovery and added daemon boundary and missing-state coverage.
- Crisis fast-path false negatives (#105): Added missing direct suicidal phrasings and updated the false-positive guard to apply per-clause rather than globally, so real crisis statements are no longer suppressed by benign idioms in the same utterance.
- Crisis fast-path coverage (#105): Added direct suicidal-language variants, matched-span idiom filtering, and whitespace normalization for ASR line breaks while preserving the false-positive benchmark.
- Disclosure truthfulness (#117): safety, audit, and lifestyle flags are persisted as disclosed only after non-empty audio is delivered (the perseveration flag is the exception, see #173 under Docs); quiet-mode suppression now happens before proactive flagging, and late non-streaming disclosures remain explicitly undisclosed.

### Docs
- The live demo link (https://huggingface.co/spaces/elevenbaselab/foreveryours, #11) is in the
  README, the landing page and ADR-003, with first hosted timings. The Space page no longer
  promises deletion when the tab closes; it states the real cleanup timers.
- Cost estimates as a public trail (#118): `Cost-estimate:` commit trailer, PR Provenance line and review-comment Provenance section; `commit-msg` hook now warns (advisory) on an AI `Co-Authored-By`, a `Claude-Session:` link, or `Assisted-by` without `Cost-estimate`. ADR-007 amended.
- `CONTRIBUTING.md` gains a "Which model and effort for what" table (which AI assistant
  and effort level to use for a build ticket, a safety-critical change, a review, a
  mechanical chore, or a founder-gated judgement call), with pointers from `AGENTS.md`
  and `REVIEW.md`.

### Changed
- Honest-disclosure UI (#66 B/C): the recording/processing notice now sits directly above the microphone and states accurately what happens to captured audio — recorded, transcribed locally, and the transcript (not the audio) sent to Nebius Token Factory for the reply and safety check, deleted on tab close. The top-of-page notice keeps the always-visible AI disclosure and privacy-notice link; the duplicated recording clause there was removed so the page states recording once, accurately, where the user acts.
- Demo page opens on the product, not the stack (#21 / Design review): the Senior/Caregiver
  split-screen is now the first thing below the title. The long intro paragraph is trimmed to
  one line (full "demo household" detail moved to a collapsed "About this demo" accordion below
  the fold), and the dev-only Model & Pipeline Info telemetry accordion now defaults to collapsed
  and sits below the product instead of above it. Required AI-transparency and recording notices
  are retained. UI ordering only — no pipeline or behaviour change.
- Hosting hardening per the judge red-team (#81, #11 row 8): the per-turn Nebius call now uses
  `OpenAI(timeout=20, max_retries=1)` instead of the SDK's 600s/2-retry default, so a hung call
  surfaces as a fallback reply instead of a ten-minute spinner. The browser page shows "Companion
  is thinking..." the instant a turn starts (a generator handler yields the placeholder first).
  The AUDIT + memory-extraction background thread is no longer joined before returning a turn —
  it runs fully async as `README.md` already claimed. Each session's NEXT turn still joins that
  session's previous background thread, bounded, before doing any work of its own, so sequential
  memory writes for one session can't race each other (a stale-snapshot `_flush()` could otherwise
  silently drop an earlier turn's saved fact — Codex review, PR #90); the current turn is never
  blocked by its own background work. Known gap, not fixed here and flagged on #11: if AUDIT flags
  a reply unsafe after the turn already returned, the spoken disclosure is generated but has
  already missed that turn's `audio_out`. Six consecutive live turns measured 0.6-3.9s each after
  these changes (a turn can still wait on the *previous* turn's background thread, bounded to
  10s, rather than on its own), down from the red-team's measured 3-41s. `faster-whisper`'s model
  now warms up at
  startup (`pipeline/hear.warm_up()`, called from `app.py` and `webapp.py`'s own `__main__`) instead
  of on the first judge's click — a no-op when `ASR_BACKEND=nebius`, and best-effort (never crashes
  startup) when the local model fails to load. `load_dotenv()` moved out of unconditional module
  scope in `webapp.py` to a `__main__`-guarded block at the top of the file (before the env-derived
  module constants, not after — Codex review, PR #90), so importing `webapp` for tests no longer
  has a side effect on process env, and `python webapp.py` still picks up `.env`.
- The daily request cap (`MAX_DAILY_REQUESTS`) is now keyed per browser session (one session's
  own `rate_limit.json`, not a single counter shared by every visitor) and counts a turn only when
  it is actually about to spend a Nebius Token Factory call — never an empty send, a turn that is
  about to fail for lack of a key, or the fully-offline safety fast-path. One number (50) is now
  used in `README.md`, `scripts/deploy_hf_space.py` and this Issue (previously 50 vs 200). The cap
  refusal message no longer points a judge at `CONTRIBUTING.md`.
- `main.py`'s CLI dispatch now catches `NebiusNotConfigured` around every beat, so `beat2`/`beat3`
  with no key print one clear line and exit(2) instead of a traceback.
- `requirements.txt` pins `gradio` and `openai` to the majors the Space was deployed with
  (`gradio<7`, `openai<4`), and `README.md`'s Setup section now covers macOS (`brew install
  espeak-ng`) and Windows (manual `espeak-ng` install, `PYTHONUTF8=1` for the test suite).
- `docs/decisions/ADR-003-hosting.md` now names the keep-awake mechanism (a daily `curl` of the
  Space URL from an always-on machine) and why it's needed through 2026-12-15 judging.
- The public Gradio page is the product now, not a developer console (#83): above the fold on laptop and phone there's only the title, a two-line intro, and a persistent AI/recording disclosure (with a link to the privacy notice) before the microphone — no accordion to open first. The telemetry accordion, Clinical Configuration, the four proactive-trigger buttons and the Acoustic Biomarkers panel are behind `FY_DEV_MODE=1` (default off). Send sits directly under the textbox. The caregiver pledge was unintentionally rendering as a Markdown heading (a line of text immediately followed by `---` is a setext `<h2>`) as well as bold; both are fixed. On narrow screens a short alert strip now appears above the mic so a caregiver flag is visible without scrolling past the whole senior column. The first sample chip (`senior_schedule.wav`, new) asks a schedule question so it recalls the caregiver's groceries update instead of looking like a generic chatbot. The perseveration ("asked 3 times in a row") flag no longer fires on the public path — it fired undisclosed, which broke the product's own disclosure invariant on screen (`orchestrator.run_turn(..., enable_perseveration_flag=...)`, default on, off via `FY_DEV_MODE`). The "NEBIUS_API_KEY is pending approval" message is replaced with an honest "the live AI model isn't reachable right now" line. A session that expires mid-demo now says so instead of silently starting over, and `audio_in` is cleared after every turn so a loaded sample clip can't be silently re-sent. The browser tab title and the Gradio footer no longer say "judge demo" (`css` is set on the `gr.Blocks()` constructor, not only `launch()`, so `app.py`'s hosted/Spaces entrypoint carries it too). The periodic AI/recording reminder counts real turns from a persistent per-session counter rather than the truncated prompt history, so it actually fires.

### Docs
- The #14 pitch sentence's second half was fixed for subject accuracy: "never tells the senior
  anything it hasn't already told him" read as a promise that replies never introduce new
  information (false — beat 2 surfaces a caregiver update the senior hasn't heard before). It now
  reads "never reports anything to the family that it hasn't first said to him out loud," which
  states the actual invariant (disclosure, not information novelty). Fixed everywhere it appeared:
  README.md, both copies in docs/Project_Description.md, video/generate_slides.py.

### Fixed
- `tests/test_webapp.py::TestProactiveButtons` wasn't isolated from the live `data/` directory the
  way the other turn-test classes are, so repeated suite runs wrote to the real demo's
  `rate_limit.json` and could trip its daily cap (#76).
- Memory scope: a memory whose text merely contained "am" as a substring (e.g. "Liam", "name") was
  wrongly auto-scoped TEMPORARY with a 24h expiry; the time-word check now matches whole words only (#82).
- `extract_new_memory()`'s offline marker fallback now runs only when the LLM extraction call itself
  fails, not whenever the model succeeds and decides there's nothing to extract; it also never stores
  a question as a new fact (#82).

### Docs
- Claims pass (#82, closing #64): README/Project_Description/FEEDBACK/PRD no longer claim Nebius AI
  Cloud, NVIDIA speech (ASR/TTS), clinical-grade diagnosis, or a "family dashboard" the code doesn't
  have; the webapp's caregiver pledge and "Live Telemetry" strings now match what's actually sent to
  Token Factory and actually computed. Deleted `docs/specs/qa/FINAL_QA_REPORT.md` and
  `docs/specs/qa/QA_STRATEGY.md` (both cited test IDs and a "36-point test plan" that don't exist in
  the repo); marked `docs/specs/proactive-agency/plan.md` as not built (#65). Recorded in
  `VENDOR_DECISIONS.md` that NemoGuard and NVIDIA ASR/TTS are not served on Token Factory (#56).
- Every live turn returned the canned fallback reply because `think.stream_reply()` rejected the `pending_conflicts` kwarg the orchestrator passes; it now accepts and forwards it, the orchestrator logs the exception type and message to stderr whenever it falls back, and keyless tests guard the signature and the live path (#78).
- Memory control: `extract_new_memory()` now asks the model first when online, so corrections ("my daughter is Sarah, not Susan") become `SUPERSEDE:` and forget-requests become `DELETE:` instead of being stored as new facts by the family-marker heuristic. Offline, the marker heuristic remains the fallback and no longer stores correction or forget phrasings as facts. Benchmark 8 now calls `extract_new_memory()` (#54).

### Added
- Secret-handling guardrails (#67): `.claude/settings.json` and `opencode.jsonc` deny assistant reads of `.env` and `*.key`; `scripts/key_status.sh` verifies a key by printing only an HTTP status code.
- Memory control in conversation: THINK now emits `ADD:` / `SUPERSEDE:` / `DELETE:` commands that the memory store applies. Additions work; corrections and forget-requests phrased with a family marker are fixed under Fixed below (#54).
- Anti-dependency prompting: rule 17 of the THINK system prompt now actively redirects the senior toward their human family ("Sarah would love to hear your voice — why not give her a call?") rather than only declining to claim exclusivity.
- GitHub Actions workflow running the test suite on every push to `main` and every PR; `SECURITY.md` with private vulnerability reporting (#39).

### Changed
- Benchmark 8 (memory correction end-to-end) is always attempted instead of being skipped outright without an API key; it now skips inside the test only if the API call itself fails (e.g. a dummy key in CI).
- One source of truth: GitHub (milestones, Issues, blocked-by) records all work state; `docs/ROADMAP.md`, `IMPLEMENTATION_PLAN.md` and `WORK_LOG.md` no longer carry status or dates (#38).

### Fixed
- The four proactive buttons no longer crash with `TypeError: unexpected keyword argument 'is_proactive'`: `run_demo_turn` now accepts and forwards `is_proactive`, and the button handler is a module-level function covered by tests (#70).
- Memory retrieval now correctly matches plurals/inflections on short words (e.g., 'dog' matches 'dogs') (#32).
- Updating a caregiver schedule (supersession) now preserves the original memory's temporal expiration and privacy scope instead of silently making it permanent (#34).

### Removed
- `TEAM_STATUS.md` (its table duplicated GitHub) (#38).

### Docs
- `docs/ROADMAP.md` now stages delivery as **MVP1 → MVP2 → MVP3**, each stage a whole releasable build rather than a pile of parts, with how we estimate and release against stage boundaries.
- `VENDOR_DECISIONS.md` gains an **"If we must leave it"** exit plan for every row that depends on someone else's service, and two stale rows were corrected: the espeak silence bug is resolved (#28), and the request limiter counts per day on disk rather than resetting on restart.
- New `docs/STANDARDS.md`: the naming, error-handling, API-shape, UI and test conventions the code already follows, so two people (and their assistants) write it the same way.
- `HOW_TO_WORK_HERE.md` documents the working method we actually use: **one Issue, one branch, one worktree, and the `main` worktree always clean** — previously undocumented, while the step it sits under said the opposite.
- `webapp.py`'s request-counter comment no longer claims it resets on restart.

## [0.1.0] - 2026-10-03

First tagged state: the hackathon demo, runnable end to end (CLI three-beat
demo and the Gradio web demo).

### Added
- Real voice I/O across CLI, web UI and pipeline: Windows audio playback,
  multi-sentence web audio stitching, caregiver voice memo on Beat 1, bundled
  reference samples (#23).
- Conversational Beat 4 cross-session recall (`beat4`) (#22).
- Test suite (22 tests, stdlib `unittest` or `pytest`) and semantic
  eldercare synonym expansion in memory recall (#24).
- Live verification against Nebius Token Factory with NVIDIA Nemotron models
  for THINK and AUDIT (#25).
- Public-demo readiness: per-visitor sessions with auto-cleanup, one-command
  Hugging Face Spaces deploy (#26).
- Intent classification and intent-aware context gating; caregiver memos
  rewritten to third person to stop embodiment hallucinations (#27).
- Dual text/voice input, caregiver text memos, emergency alert banner and
  clinical guardrails (#29).
- Memory-property badges: Permanent, Temporary, Historical, Caregiver-only,
  Superseded (#29).
- Circadian awareness (sundowning and night-mode behaviour), acoustic
  biomarkers and perseveration tracking (#31).
- PRD and implementation plan docs (#8); roadmap and principles.
- Collaboration docs: `CHANGELOG.md`, PR and issue templates, `TEAM_STATUS.md` (later removed, see Unreleased),
  `HOW_TO_WORK_HERE.md`, `docs/WORK_LOG.md` and the decision log `docs/decisions/`
  (ADR-001 to ADR-005) (#35).

### Changed
- Time to first audio under ~1s by disabling hidden reasoning tokens on the
  main conversational turn (roadmap M11, #17) (#29).

### Fixed
- Fast-path distress trigger no longer dead-ends the conversation; caregiver
  facts are always in context; disclosure-honesty gaps (#7).
- Linux TTS going silent in long-running processes: call `espeak-ng` directly
  (#28) (#29).
- Safety fast-path false positives ("I fell" vs "I fell asleep") (#29).
- `.env` loading for the Hugging Face Spaces wrapper (`app.py`) (#31).

[Unreleased]: ../../compare/v0.1.0...HEAD
[0.1.0]: ../../releases/tag/v0.1.0
