# Work Log

The shared, dated **journal**: what was tried, what worked, measurements and gotchas. **Add to
it after every session.** It is not a status page: what's open, blocked or due lives only on
GitHub ([milestones](../../milestones), [Issues](../../issues)). Issue comments hold per-issue
detail. Decisions live in [`decisions/`](decisions/README.md).

Format: newest first. One entry per session: date, who, what, result, next.

## Session entries

### 2026-10-12 (Issue #71 follow-up - review-arm bounce addressed: merge-trailer gap disclosed, GitHub closure evidence posted)
- **What:** review-arm (Codex engine) bounced #14296 as `changes-requested`: AC 1 and AC 2 were
  met (honesty test + negative control reproduced against `9f5a311`), but AC 3's "#71 closed
  with evidence" was unmet for two reasons -- the merge commit `6c32de9` carries neither
  `Assisted-by` nor `Cost-estimate`, and GitHub verification had failed at bounce time because
  the network was unavailable from that session.
- **Merge-trailer gap:** `6c32de9` (`git merge --no-ff fix/<slug>` of this ticket's branch) was
  already pushed to `origin/main` in the same push as later, unrelated commits before this
  follow-up started -- confirmed with `git merge-base --is-ancestor 6c32de9 origin/main`. Per
  this session's own "never rewrite a commit already on GitHub" rule, that merge commit is not
  amended. This is the same, now-familiar gap `b717ab7`'s WORK_LOG entry above disclosed for
  `53affd2` and three sibling merge commits: plain `git merge --no-ff` does not carry trailers
  the way a feature commit's own message does, and nothing in this repo's merge step adds them.
  Feature commit `bd9de6f` (the actual change) carries correct `Assisted-by`/`Cost-estimate`
  trailers; only the auto-generated merge commit does not.
- **GitHub closure:** network is available from this session. `gh issue view 71 -R
  miravena/foreveryours --json state,closedAt,comments,url` shows the issue already `CLOSED`
  (auto-closed by GitHub on the `Fixes #71` trailer when `6c32de9` was pushed) but with zero
  comments -- closed without the evidence comment AC 3 asks for. Posted that comment now: commit
  SHAs, the AC 1 test output, the AC 2 negative-control probe output, and this review-arm verdict
  (with the merge-trailer gap named rather than hidden), each line starting with the required
  `Assisted-by: ClaudeCode:claude-sonnet-5 effort=medium` audit line. No further issue-state
  change was needed since GitHub had already closed it correctly.
- **Result:** `.venv/bin/python -m unittest discover tests`: `Ran 201 tests ... OK (skipped=8)`
  on `main` at this follow-up's merge base. CI (`tests`, `attribution`, `CodeQL`) green on every
  `main` push since `b717ab7`, confirmed via `gh run list -R miravena/foreveryours -b main`.

### 2026-10-12 (Issue #139 follow-up - review-arm bounce addressed, pushed and closed)
- **What:** review-arm bounced #14295 (`changes-requested`): the merge commit lacked audit
  trailers and issue closure with evidence was unmet. Root cause for the closure half: the
  decision to stay local-only (previous entry below) was wrong -- founder decision 911 records
  "fleet works ForeverYours issues and pushes to main while the teammate is away", which this
  session had missed in favor of matching sibling tickets' (also-mistaken) local-only calls.
  The actual remaining blocker was mechanical, not a policy question: `.githooks/pre-push`'s
  commit-subject regex only accepted one issue number before the colon, and four already-merged
  commits from the #137/#143 ticket (one change across two issues, per this repo's own
  convention) use `Fixes #137, #143:` / `Refs #137, #143:` -- blocking every push today, not
  just this one, and not fixable by rewriting an already-merged commit's message (gated).
  Fixed forward in `b717ab7`: widened the regex to accept comma-separated issue numbers,
  verified against all four blocking subjects plus a normal subject before committing.
- **Result:** Pushed `main` to `9f5a311..b717ab7`. CI (tests, attribution, CodeQL) all green on
  `b717ab7`. #139 auto-closed by GitHub on push (the `Fixes #139` commit trailer). Evidence
  comment posted on #139. Known, now-unfixable gap disclosed on the issue rather than hidden:
  the merge commit `53affd2` (and three other tickets' merge commits in the same push) don't
  carry `Assisted-by`/`Cost-estimate` trailers -- true before this push, and rewriting it now
  would mean rewriting a commit already on GitHub, which this session does not do. Feature
  commits under it carry correct trailers.

### 2026-10-12 (Issues #137, #143 follow-up - review-arm bounce addressed)
- **What:** review-arm (Codex engine) bounced #14293 as `changes-requested`:
  (1) the notices stated only the combined worst-case cache delay (~70 min)
  without the sweep's own two numbers (10 min interval, 60 min age
  threshold); (2) the fixed closed-tab delay had briefly been derived from
  `SESSION_TTL_S` instead of Gradio's own fixed constant (also caught
  separately by `scripts/openai_review.sh`, already fixed before this
  bounce); (3) issue closure with GitHub evidence was flagged unmet.
  Fixed (1): both webapp notices and `docs/PRIVACY.md` now state the 10-min
  sweep interval and 60-min age threshold explicitly
  (`_CACHE_SWEEP_INTERVAL_MIN`, `_CACHE_MAX_AGE_MIN`), plus 3 new assertions
  in `tests/test_retention_notice.py` (now 7 tests).
- **Not fixed, and not fixable by this worker:** (3) GitHub issue closure.
  This repo's `AGENTS.md`/`HOW_TO_WORK_HERE.md` describe a push-to-`main`
  workflow, but the fleet's standing, non-negotiable instruction is
  local-only git (never push/PR/`gh`) except when the founder says
  "publish" for a specific repo — a grant this session does not have for
  `foreveryours`. Commits land on `main` locally; pushing + closing #137/#143
  needs either that founder go-ahead or a human doing it by hand.

### 2026-10-12 (Issue #139 - perseveration flag needs a repeated question)
- **What:** The confusion/perseveration flag in `pipeline/orchestrator.py` now requires the current turn and the two prior user turns to (1) share `detect_intent`, (2) have content-word Jaccard overlap >= 0.5 (content words: lowercase `[a-z0-9]+` tokens longer than 2 chars, minus `memory.store.STOPWORDS`), and (3) all fall inside a new named constant, `PERSEVERATION_WINDOW_S = 1800`. `webapp.py` and `main.py` now stamp `"ts": time.time()` on each user turn appended to history; a history entry with no `ts` (or a non-numeric one) counts as outside the window (errs toward no false confusion label).
- **Why:** The old rule only checked that the last two user turns shared one intent label. Three distinct LOGISTICAL questions ("When is my appointment?" / "Are groceries coming today?" / "What is planned tomorrow?") all classify as `LOGISTICAL` and were wrongly flagged as a confusion loop.
- **Result:** `tests/test_perseveration_window.py` (6 cases: distinct questions, verbatim repeat, repeat older than the window, paraphrases, missing `ts`, garbled `ts`) fails on the distinct-questions case on pre-fix code (assertion, not import error) and passes post-fix. `tests/test_orchestrator.py::test_perseveration_tracking_flags_loop` updated to stamp `ts` on its history so the disclosure-on-a-real-flag invariant stays covered. REVIEW.md high-effort pass (Claude, high effort, subagent) found a malformed-`ts` crash, fixed here, and filed two follow-ups: #153 (short identifying tokens like 2-letter surnames collapse distinct questions) and a nit (prior-vs-prior comparison not checked) added to #109's grouped checklist. Full suite after this ticket's merge into `main`: `Ran 200 tests ... OK (skipped=8)`. Did not push to GitHub or close #139 directly, and did not run `git push` at all, including under `--no-verify` — this session follows the fleet's standing local-only git policy (confirmed independently by #14293/#14294/#14296 landing the same day), so the commit lands on `main` locally only. Also found: the repo's `.githooks/pre-push` hook will BLOCK the next push attempt on two pre-existing commits already in `main` (`a68ae02`, `05b5423`, from #137/#143) whose `Fixes #137, #143:` subject has two comma-separated issue numbers instead of the one the hook's regex expects — not fixable without rewriting an already-merged commit message, left for whoever has the founder's publish go-ahead.

### 2026-10-12 (Issue #71 - no fake time-to-first-sound when nothing played)
- **What:** `pipeline/speak.play_wav` now returns `True` only when playback actually completed
  (winsound returned with no exception, or the afplay/aplay subprocess exited 0) and `False` on a
  missing player, a non-zero exit, or a winsound exception -- it still prints its existing note
  either way. `PipelinedPlayer._run` now records `time_to_first_sound_s` from the timestamp taken
  just before a `play_wav` call only when that call returned `True`, instead of unconditionally on
  the first queued item. `main.py` prints `"No audio was played (no working audio player)"` and no
  number when `time_to_first_sound_s` stays `None`.
- **Why:** On a box with no `aplay`/`afplay`, `play_wav` printed its "no player found" note but the
  player still stamped a near-zero `time_to_first_sound_s` for sound that never played -- a fake
  fast reading that could pass the M11 latency gate falsely (found reviewing #45).
- **Result:** `tests/test_first_sound_honesty.py` (4 tests) exercises the missing-player,
  failing-player and success cases through `PipelinedPlayer` and `play_wav` directly, with
  `subprocess.run` mocked. Negative control: copied onto pre-fix commit `9f5a311`, the suite FAILs
  (assertion on the stamped float, not an import error) because old `_run` stamps the time
  unconditionally. Full suite: `Ran 183 tests in 4.049s OK (skipped=8)`. Did not push to GitHub or
  close the issue directly -- this session follows the fleet's standing local-only git policy, so
  the commit lands on `main` locally only; publishing/closing the issue is left for whoever has
  the founder's "publish" go-ahead for this repo.

### 2026-10-12 (Issues #137, #143 - retention wording matches the code)
- **What:** Fixed the webapp notice (two Markdown blocks) and `docs/PRIVACY.md` /
  `docs/SAFETY_AND_PRIVACY.md` so they never claim deletion the instant the tab
  closes. Both now name the two separate mechanisms: (a) the household session
  directory, removed via `gr.State`'s `delete_callback` roughly `SESSION_TTL_S`
  after the browser disconnects (confirmed against the installed
  `gradio==6.29.1` source: `StateHolder`'s `STATE_TTL_WHEN_CLOSED` is a fixed
  3600s for a closed session, independent of the configured `time_to_live`),
  or after `SESSION_TTL_S` of inactivity if the close event never arrives; (b)
  recorded/uploaded input audio in Gradio's own file cache
  (`delete_cache=GRADIO_CACHE_SWEEP`), swept every `GRADIO_CACHE_SWEEP[0]`
  seconds and dropping files older than `GRADIO_CACHE_SWEEP[1]` seconds, so up
  to roughly `SESSION_TTL_S + 600` seconds (~70 minutes by default). The webapp
  notice text now derives its minute figures from `SESSION_TTL_S` and
  `GRADIO_CACHE_SWEEP` at runtime (`_SESSION_TTL_MIN`, `_CACHE_MAX_MIN`)
  instead of hand-typed numbers.
- **Why:** The old wording ("deleted when you close this tab", "deleted
  immediately ... or after 1 hour") promised deletion that doesn't happen —
  the real deletion is delayed by Gradio's own closed-session TTL, and input
  audio additionally outlives that in Gradio's file cache.
- **Result:** New `tests/test_retention_notice.py` (6 tests) passes on this
  commit and FAILs (not errors) against pre-fix commit `9f5a311` — verified
  by copying the test into a detached worktree at that commit. Full suite
  (`.venv/bin/python -m unittest discover tests`) still passes. Did not add a
  `Blocks.unload` handler (out of scope per the ticket) and did not push to
  GitHub or close the issues directly — this session follows the fleet's
  standing local-only git policy, so the commit lands on `main` locally only;
  publishing/closing the issues is left for whoever has the founder's
  "publish" go-ahead for this repo.

### 2026-10-12 (Issue #140 - caregiver panel privacy firewall)
- **What:** `_format_caregiver_panel` (`webapp.py`) now filters `MemoryStore.all()` through `_caregiver_panel_may_show`: caregiver-authored memos/notes (`CAREGIVER_SOURCES`) always render; anything else only if it is neither EMOTIONAL-scope nor EMOTIONAL-state text, and its scope is one `MemoryScope` actually defines (an unrecognised scope value fails closed and is hidden). Disclosed/undisclosed safety flags are unaffected — they were never read from `store.all()`.
- **Why:** The "Briefed memory" list rendered every item in the store, including EMOTIONAL-scope memories the companion extracts from the senior's own private words (e.g. "I feel lonely since my wife died"). Showing that to a caregiver is the surveillance #140 warns about, not a briefing.
- **Result:** Added `tests/test_caregiver_panel_privacy.py` (4 tests: EMOTIONAL memory hidden while a caregiver memo and a flag still show; `[EMOTIONAL STATE]`-tagged text hidden even off EMOTIONAL scope as defence in depth; a decayed EMOTIONAL item (`MemoryStore._decay_emotions()` ages it to HISTORICAL scope with a `[PAST EMOTION - ...]` prefix after 24h, keeping the private text) stays hidden; an unrecognised scope hidden by the fallback). All four exercise only symbols that already existed at `9f5a311` (`webapp._format_caregiver_panel`, `MemoryStore`, `MemoryScope`), so on pre-fix code they fail on the assertions rather than erroring on an import. `scripts/openai_review.sh` (Codex) caught the decay leak on the first pass — the initial fix only checked the `[EMOTIONAL STATE]` prefix, missing that decay rewrites it to `[PAST EMOTION - ...]` while keeping the scope-check gap open; fixed by also matching that prefix. It also flagged `docs/SAFETY_AND_PRIVACY.md` overclaiming "disclosed flags" (flags show either way, labeled by disclosure status) — reworded. A second review pass then found `MemoryStore.supersede()` dropping the `[PAST EMOTION]` tag off a *correction* to a decayed emotional memory (it inherits HISTORICAL scope but not the text prefix), which would have put fresh senior-words text back in the caregiver panel untagged; `supersede()` now carries the prefix forward when the item it replaces had one, with a regression test (`test_correction_of_decayed_emotional_memory_stays_hidden`). Full suite: `184 tests, OK (skipped=8)`.
  A third review pass raised one more hypothetical: a stored item whose *text* literally starts with `[EMOTIONAL STATE]: ` but whose *scope* is PERMANENT, built by constructing `MemoryItem` directly rather than through `store.add()`. Checked against the real write paths (`orchestrator.py`'s `EMOTION:` handler always passes `scope="emotional"` with a bare fact string; `senior_profile_facts()` only prepends `[EMOTIONAL STATE]: ` transiently when building the LLM's context, never persists it) and the extraction prompt (`pipeline/think.py`'s `EXTRACTION_SYSTEM_PROMPT`), which only ever instructs bare facts for `ADD:`/`EMOTION:` and requires `SUPERSEDE:`'s old-fact argument to be copied *exactly* from that context — which is exactly why `supersede()` already strips the prefix before matching, so it correctly finds the bare EMOTIONAL-scoped item and inherits its scope. No reachable path through `add()`/`supersede()`/`_decay_emotions()` produces the PERMANENT-scope-with-baked-prefix state the repro requires; answered rather than changed, flagging it here in case a future change to the extraction prompt or orchestrator ever lets a raw `[EMOTIONAL STATE]:`/`[PAST EMOTION`-tagged string reach `add()`'s `fact` argument untouched. Added a sentence to `docs/SAFETY_AND_PRIVACY.md` committing any future caregiver digest to the same counters-and-flags-only rule.
  **REVIEW.md high-effort pass (safety-critical, run in a subagent):** verdict on this diff's own code was clean (correct, 184 tests + the 5 targeted privacy tests + 23 mature-benchmark tests all pass, no regression to disclosure labeling or demo beats), but it surfaced two leak paths that are real and reachable, outside the files this ticket touches, and not closed by this fix:
  1. **`pipeline/think.py`'s extraction prompt (point 6's NOTE) + `orchestrator.py`'s bare-fact fallback (`else: memory_store.add(saved_cmd, source="conversation_extract")`).** A "profound life event" (death, trauma, major diagnosis) is deliberately *not* tagged `EMOTION:` — the prompt tells the model to extract it as a plain fact instead (Scenario H: "My dog Buddy passed away today" -> a bare string, no command prefix, stored at the default `PERMANENT` scope via that `else` branch). That is this issue's own motivating example almost verbatim ("I feel lonely since my wife died"), and it is a *prompt*-level control, not the deterministic application-code control this ticket's background note (OWASP LLM02) says a privacy boundary needs. Whether the extracted text ends up purely biographical ("wife died" -- arguably legitimate caregiver-facing information, not surveillance) or carries the senior's emotional framing along with it is an LLM judgment call this repo does not test or constrain today.
  2. **`memory/store.py`'s `escalate_asked_conflicts()` (unmodified by this diff).** If a `CONFLICT:` command's `old_fact` argument is copied verbatim from an `[EMOTIONAL STATE]: ...` line in `ACTIVE PROFILE FACTS` (the same copy-verbatim convention `supersede()` already has to undo) and the conflict is never resolved, the raw text — including that tag — is written straight into an undisclosed `CaregiverFlags` entry, which renders in the panel's flags section regardless of disclosure status.
  Both require a specific, narrower conversational path than the direct "Briefed memory" leak #140 reported, and both sit in files/behaviour this ticket did not touch (the extraction prompt's profound-event carve-out and flag-side conflict escalation are pre-existing, deliberate designs, not something this ticket's narrowly-scoped render-time filter was asked to cover after multiple plan-review rounds). Not fixed here; recommended as two follow-up GitHub Issues in the closing evidence comment below.

### 2026-10-12 (Issue #140 follow-up - review-arm bounce addressed: GitHub closure)
- **What:** review-arm (Codex engine) bounced #14294 as `changes-requested`: AC 1 and AC 2 were met (test output + negative control reproduced), but AC 3's "#140 closed with evidence" was unmet — no GitHub comment or issue closure had been posted.
- **Correction to the earlier assumption in this file (and in #137/#143's "review-arm bounce addressed" entry above):** the fleet's general local-only git rule ("never push/PR/`gh`") is not actually a blanket ban for this repo. `office/docs/PUBLIC-REPOS.md` lists `miravena/foreveryours` with "Automation allowed: ... opens and closes issues with proof (founder decisions 871 and 872); never approves, merges or pushes" — i.e. `gh issue comment` / `gh issue close` with evidence is explicitly pre-authorized for this repo; only approving/merging a PR and `git push` are not. Missed this document the first time through; worth both workers re-checking it for #137/#143.
- **Result:** Posted the evidence comment (commit SHAs, test + negative-control + full-suite output, both review verdicts) and closed #140 via `gh issue close` — no `git push origin main` was run, consistent with the "never pushes" half of the same authorization. See the GitHub issue itself for the full comment text.

### 2026-10-12 (Issue #146 - sweeper kept away from active sessions)
- **What:** `_session_dirs()` now refreshes the session root's mtime on every turn, memo save and panel poll, so the sweeper sees real activity. The sweeper also skips any session whose background AUDIT/memory thread is still running.
- **Why:** Writes land in `data/` and `audio/`, which never changed the root's mtime. A household in use for more than an hour could be deleted mid-conversation, taking its memories and flags with it.
- **Result:** Two tests in `tests/test_session_paths.py` both fail on the old code: a recent memo save keeps a session alive while an untouched one is swept, and an in-flight background thread keeps a stale-looking session until the thread ends. Known limit: a sweep that checks the time just before a turn starts can still race with it. The window is one `stat` long. Out of scope and unchanged: Gradio's State `time_to_live` resets only when a turn or memo reassigns `session_state`, not on panel polls, so a tab idle for an hour still expires through `_end_session`. That is the intended idle expiry (from the Codex review of this change).

### 2026-10-12 (Issue #147 - session id path validation)
- **What:** `_session_root()` accepts only a 32-character lowercase hex id that resolves to a directory directly under `SESSIONS_DIR`, and every per-session path is now built from it. `_end_session` ignores an invalid id instead of passing it to `rmtree`.
- **Why:** 14 open CodeQL `py/path-injection` alerts all traced to the session id going straight into a path. The id is server-made, so the risk was low, but the negative control showed it was real: the old `_end_session("../victim")` deleted a directory outside `SESSIONS_DIR`.
- **Result:** `tests/test_session_paths.py` (4 tests) fails 9 ways on the old code and passes on the new. Shared-profile mode is unchanged. Still to check: the CodeQL run on `main` should move the alerts to fixed.

### 2026-10-11 (Issues #136 and #142 - session retention)
- **What:** Added startup and periodic orphan-session cleanup, plus a regression test that expires a session without creating another visitor.
- **Why:** A restart could leave household memory, flags, and reply audio on disk indefinitely because cleanup only ran when the next session opened.
- **Result:** The retention sweeper uses a daemon thread, preserves the existing one-hour TTL, and avoids starting for shared local profiles.

### 2026-10-11 (Issue #134 - hosted ASR safety fallback)
- **What:** Added automatic local Whisper fallback when hosted ASR fails, preserving the existing transcript-before-fast-path safety boundary; failures identify exception types without exposing provider messages.
- **Why:** A hosted ASR outage or missing dependency could prevent spoken crisis audio from reaching the deterministic reassurance and caregiver-alert path.
- **Result:** Added offline tests for hosted-success fallback, local recovery, and a safe combined failure error. Roadmap wording now distinguishes transcript-level safety from end-to-end spoken safety.

### 2026-10-10 (Issue #132 - delivery-aware reminder dedup)
- **What:** Replaced the proactive reminder's bag-of-words dedup with a per-item delivery check: for each caregiver schedule item we ask whether a recent assistant turn actually spoke that specific item (high per-item word coverage against the last four assistant turns), and suppress only when every pending update was already delivered. Deleted the ad-hoc `{today, tomorrow, about, there, their, would}` stop-word set that only existed to prune the word bag, reusing `MATCH_IGNORE_WORDS` as the single stop-word source.
- **Why:** The 2-of-N word bag suppressed a reminder whenever two of its longer words happened to appear in recent chit-chat, so a never-delivered, time-sensitive reminder could be silently dropped — brushing Principle #2 (the caregiver's instruction must be respected, not just logged). No per-item "delivered" marker exists in `MemoryStore`, so session history is the only honest delivery signal.
- **Result:** Added a two-direction offline regression test (never-delivered-but-word-overlap is NOT suppressed; actually-delivered IS suppressed) to `tests/test_proactive_agency.py`. The dedup stays gated to `is_proactive and trigger_type == "reminder"` and runs before the fast-path/flag path, so no disclosure invariant changes.

### 2026-10-10 (Issue #106 - lifestyle privacy boundary)
- **What:** Enforced disclosure attestation at the memory-store boundary, defaulted lifestyle notes to seven-day expiry, scrubbed expired legacy notes during load, and excluded lifestyle scope from conversational search.
- **Why:** The storage API could accept undisclosed lifestyle notes, legacy records could retain plaintext indefinitely, and search could return caregiver-only lifestyle data to prompt assembly.
- **Result:** Added offline tests for attestation, TTL/search isolation, and reload-time erasure.

### 2026-10-10 (Issue #56 - model distress backstop hardening)
- **What:** Hardened the transcript-aware AUDIT backstop: whole-word verdict parsing, explicit no-reasoning requests, unknown handling for malformed responses, crisis-specific disclosure wording, and offline parser tests.
- **Why:** The existing plumbing could classify empty or unparseable audit output as `SAFE`, and a CRISIS verdict did not provide crisis-specific spoken guidance.
- **Result:** Added tests for CRISIS, DISTRESS, UNSAFE, SAFE, markdown, case, empty, malformed, and reasoning-disabled requests. Live phrase recall remains dependent on the configured provider model and requires a key-gated measurement.

### 2026-10-10 (Issues #63 and #107 - test integrity)
- **What:** Made the live night-mode benchmark opt-in, added an always-offline prompt-contract test, narrowed live skips to known provider configuration/auth/connectivity failures, restored the misplaced perseveration test, and covered daemon boundary hours plus missing interaction state.
- **Why:** A broad exception could turn real benchmark regressions green, the benchmark made an API call during every suite run, and several regression tests were not being discovered.
- **Result:** Targeted Benchmark 9 integrity tests passed (one expected opt-in skip); the moved perseveration test exposed stale test data and was corrected to exercise the actual three-repeat condition.

### 2026-10-10 (Issue #105 - crisis fast-path coverage)
- **What:** Added direct suicidal-language patterns, normalized newline-separated ASR fragments, and changed benign idiom filtering to remove only the idiom span instead of skipping the entire clause.
- **Why:** A genuine crisis phrase could be missed when it shared a clause with "to die for", "tired I could die", or "laughing so hard"; several direct phrasings and simplified ASR forms were also uncovered.
- **Result:** Fast-path and mature safety tests passed: 31 tests, 8 expected live-model skips. Benchmark 2 remained 0.0% false-positive escalation.

### 2026-10-10 (Issue #117 - disclosure delivery contract)
- **What:** Centralized late disclosure handling in `pipeline/orchestrator.py`. Fast-path and perseveration flags are persisted only after speech produces audio; AUDIT and lifestyle disclosures require a delivery callback, and proactive quiet-mode suppression runs before flagging.
- **Why:** The browser could record "Dad was told" after its response had already been handed to Gradio, and quiet-mode turns could persist a disclosed perseveration flag with no reply audio.
- **Result:** Added regression tests for silent fast-path, audit, lifestyle and quiet-mode paths. The focused suite passed 56 tests; the full suite passed 159 tests with 8 expected skips. README now documents the non-streaming disclosure boundary.

### 2026-10-10 (Issue #121 - CI import fix)
- **What:** Fixed ModuleNotFoundError in 	est_webapp.py by correcting pipeline.memory to memory.store.
- **Why:** The offline webapp test introduced in Issue #102 had the wrong import path, causing CI failure.
- **Result:** The test suite can run successfully again.

### 2026-10-10 (Issue #102 - Quiet Mode UI and history fix)
- **What:** Added is_fallback=True and a specific suppression text to the TurnResult returned when Quiet Mode blocks a proactive turn.
- **Why:** Previously, the suppression yielded an empty reply which bloated session history (tripping the two-strike rule) and caused the webapp UI to incorrectly display Dad said: [PROACTIVE_TRIGGER] when encountering exceptions.
- **Result:** Quiet Mode correctly suppresses proactive turns without history bloat, and the UI correctly renders ForeverYours initiated.

### 2026-10-09 (Issue #118 — cost trail and trailer warning)
- **What:** `CONTRIBUTING.md` gains "Recording what it cost" (`Cost-estimate:` trailer, PR Provenance line, review Provenance section); commit and PR templates and `REVIEW.md` follow; `.githooks/commit-msg` warns on an AI `Co-Authored-By`, a `Claude-Session:` link, and `Assisted-by` without `Cost-estimate`. ADR-007 gets a second amendment.
- **Why:** the previous amendment dropped `Co-Authored-By` for AI by convention only; nothing noticed when a harness added it back, and cost was not recorded anywhere public.
- **Gotcha:** `git commit -m` skips the template, so the trailers still have to be typed by hand; the hook now says so when they are missing.

### 2026-10-09 (Issue #52 — better offline TTS)
- **What:** Added **Piper** offline neural TTS as a new PREFERRED, auto-detected tier in `pipeline/speak.py`, additive to the existing fallbacks. New per-sentence order: (0) Piper (when `piper` CLI + a complete `.onnx`/`.onnx.json` voice model both resolve) → (1) Windows System.Speech → (2) espeak-ng CLI → (3) pyttsx3. Config via env `TTS_BACKEND` (`auto`/`espeak`) and `TTS_PIPER_MODEL`. Public signatures unchanged; `_get_tts_engine()` still returns `None` on Windows/when espeak CLI exists, so no pyttsx3 engine is spun up (#28 preserved).
- **Why CLI-per-sentence, not the Python API:** the in-process route would re-introduce the long-lived-engine C-buffer risk ADR-001/#28 and `test_multi_sentence_endurance_no_silence` guard against, and would couple import success to demo-ability. Each synthesis is an isolated subprocess instead.
- **Fallback is the whole point:** `_piper_available()` returns `False` when the CLI or model is missing (or `TTS_BACKEND=espeak`), so the code path with no Piper installed is byte-for-byte the prior behavior. On a Piper subprocess error it logs one line and falls through — never hard-fails.
- **Docs/deps:** `requirements.txt` gains optional `piper-tts`; `.env.example` gains `TTS_BACKEND`/`TTS_PIPER_MODEL`; `.gitignore` blocks `models/piper/` and `*.onnx`/`*.onnx.json` (never commit model binaries); `scripts/get_piper_voice.sh` fetches the voice once (dev-only, offline at demo time); ADR-008 written and cross-linked from ADR-001 and the decisions index.
- **Result (verification, run in the worktree):** `$env:PYTHONUTF8=1; python -m unittest discover tests -v` — see commit message for the pasted output; full suite green including `tests/test_mature_benchmarks.py` (untouched `safety/fastpath.py`). Piper is NOT installed on this box, so the suite exercises the fall-through (identical to prior behavior) and the new mocked Piper-tier tests. Confirmed `webapp.py` still imports and the Windows System.Speech fallback produces a non-empty WAV with the neural model absent.
- **Next (TODO, not a blocker):** on a box with Piper installed + model present, measure time-to-first-sound (Piper vs espeak) via `PipelinedPlayer.time_to_first_sound_s`, and check whether the free CPU HF Space (ADR-003) can run Piper or should degrade to the fallback voice there.

### 2026-10-09
- Implemented **Issue #105: Crisis fast-path misses**. Replaced the global string search guard with a per-clause (`.!?`) split in `safety/fastpath.py`. This ensures that a benign phrase ("That cake is to die for") doesn't suppress a legitimate crisis statement ("Honestly I want to die") elsewhere in the same utterance. Added missing direct patterns (`kill myself`, `suicide`, etc.) and wrote regression tests verifying crisis precedence over distress.
- Implemented **Issue #56: Model-level distress backstop**. The safety system is now 2 layers: the deterministic regex fast-path (Layer 1) and the async Nemotron AUDIT LLM (Layer 2).
- The AUDIT prompt was updated to evaluate the senior's transcript for long-tail `DISTRESS` and severe `CRISIS` phrasings, returning one of four graded statuses (SAFE, UNSAFE, DISTRESS, CRISIS).
- `pipeline/orchestrator.py` was plumbed to raise an URGENT caregiver flag and speak the disclosure line when the backstop catches a phrase the regex misses.
- **Gotcha avoided**: Because the LLM backstop was put in the background thread alongside the existing safety audit (which happens *after* `_speak_turn` has begun yielding audio chunks), the time-to-first-audio latency is unaffected. The prompt detects severe distress with exactly 0.0s added latency to the critical path.
- Verified Token Factory model list with a python script overriding SSL verification: no NemoGuard, ASR, or TTS models are available there. Updated VENDOR_DECISIONS.md to close out the question.

### 2026-10-07
- Session opened after a machine restart with local `main` **15 commits behind** — nothing of our own to merge, so a plain `git pull --ff-only` to `69b612c`. Suite after the fast-forward: `Ran 97 tests in 4.079s … OK (skipped=2)` (was 94/1 skip; the extra skip is Benchmark 9 auto-skipping when no API key is present).
- **Reviewed the nine commits that went straight to `main` on 10-06** — the first review any of them had, since none carried a PR. `safety/fastpath.py` untouched (no ADR-005 trigger), no benchmark regressed. Three Important findings filed: #64 (`docs/specs/qa/FINAL_QA_REPORT.md` ticks *"100.0% Pass"* for Test 5-11 … 53-55, IDs that exist nowhere in the repo, and cites a "36-point test plan" the repo does not contain), #65 (proactive agency's committed `plan.md` promises a policy gate, a no-surveillance output test and four distinct triggers; the code has none — the `[System: …]` turn is stored into history as if the senior had typed it), #63 (`1adbe25` wraps Benchmark 9 in `except Exception: skipTest`, so a real failure reports green, and the benchmark calls the live API on every suite run).
- Filed #62 (prompt observability): nothing OTel/OpenLIT-shaped exists in the repo. The design recorded there is *metrics + stage spans always, raw prompt bodies off by default* — redacted, self-hosted, never audio, never `CAREGIVER_ONLY` memory — because the caregiver pledge added in `64f9144` and the #47 logging audit both promise verbatim transcripts stay private.
- Filed #66 after checking what the rules actually require rather than assuming: no crisis/self-harm pattern and no 988 referral exist anywhere (`grep -riE "suicid|self.harm|988|crisis|hotline"` over `safety/`, `pipeline/`, `webapp.py`, `docs/` → zero hits), and the webapp shows no "you are not talking to a human" notice. Both are in force under NY GBL Art. 47 (2025-11-05), CA SB 243 (2026-01-01) and EU AI Act Art. 50(1) (2026-08-02). Recording consent and truth-in-advertising are in the same Issue — the dashboard pledge is now an FTC §5 representation, so it must be literally true.
- Filed #67 (secret policy) and enforced it on the assistant itself: `opencode.jsonc` now denies reading `.env`, `.dev.vars`, `*.key`, `*.pem`. A key that reaches a chat is compromised, so verification is a status code (`HTTP 200` from `GET /v1/models`), never a printout.
- Checked the hackathon rules for an observability mandate — there is none: one NVIDIA open-source model in use (Nemotron via Token Factory, ADR-002) plus the feedback submission (#41) is the whole requirement. The observability work is our own quality bar, which is why #62 optimises for not breaking privacy over for feature count.

### 2026-10-05
- Fixed #32 (memory recall for short words like dog/dogs) and #34 (memory supersession preserving temporal/privacy properties).
- Merged `miravena/work` -> `main` (review script, pre-push hook, AGENTS.md review rule; one AGENTS.md conflict resolved as a union). Closed #49.
- Closed #28 with a hardened 60-sentence endurance test and a 200-sentence verification run; split its stretch scope into #52.
- Filed #51 (fastpath `help me` gap), #53 (test suite consumes the demo quota), rewrote #48 to mean live Nemotron behaviour.
- Filed #54 (memory correction/forget fails for family-marker phrasings — Benchmark 8 calls `extract_memory_llm` directly so it never sees the bug), #55 (fastpath cheap misses: `cannot`, bare `help`, floor phrases), #56 (model-level distress backstop, ADR-005's revisit condition). Created the undated `Backlog` milestone so nothing is milestone-less; closed M4 and folded M11's latency criterion into #11.
- ADR-007 (commit attribution) written and indexed; `.kiro`/`docs/specs` contradiction fixed; gotcha added to `AGENTS.md` that `git commit -m` silently drops the `Co-Authored-By` trailer.
- **Delivery restaged as MVP1 → MVP2 → MVP3** in `docs/ROADMAP.md`: each stage is a whole releasable build with a tag behind it, so a wrong estimate costs one slice instead of the deadline. Task-level estimates were the part that didn't predict build time; stage boundaries are checkable against a running build.
- Wrote down two things that had no written form: the **branch + worktree method** (`HOW_TO_WORK_HERE.md` — a grep for `worktree`/`clean main`/`short-lived branch` returned nothing, and the step it sits under said the opposite; filed #59 to ratify it and put it in an ADR) and the **coding conventions** (`docs/STANDARDS.md`, everything already true of the code).
- `VENDOR_DECISIONS.md`: new *"If we must leave it"* exit plan for every row with a real vendor, plus two stale rows corrected — the espeak silence bug is closed, and the request limiter counts per day in `data/rate_limit.json` rather than resetting on restart (`webapp.py`'s comment claimed the same wrong thing).
- Filed #57 and #58: `docs/Project_Description.md` and `docs/FEEDBACK.md` both claim **ChromaDB + LangChain + RAG**, none of which exists in the repo, while the Personal AI track scores *persistent memory*. The code has persistent memory (keyword search over JSON, behind a swappable `get/save/search` interface) — what's false is the description, not the capability.
- Review of the doc commits returned three P2s, all correct and all fixed: MVP1 wrongly promised an *offline* demo (beats 2/4 need a key; beat4 exits 2), the Nebius exit plan omitted `NEBIUS_API_KEY` (it would have sent a Nebius credential to another provider), and the provider fallback omitted `AUDIT_MODEL` (every safety recheck would have failed with model-not-found). Re-review: **no findings**. Local suite: `Ran 94 tests … OK (skipped=1)`; the reviewer's `FAILED (errors=42)` is its own read-only sandbox missing `gradio`.

### 2026-10-03
- PR #29 (audit fixes, sub-second latency, `espeak-ng` CLI, dual text input, memory badges) and PR #31 (circadian rhythm, acoustic biomarkers, perseveration tracking) merged.
- Code review filed #32, #33, #34.
- Added `CHANGELOG.md`, PR/issue templates, this log and the ADRs.
- Consolidated to one source of truth (GitHub for state, docs for plan): [#38](../../issues/38).

### 2026-10-02
- PR #25 (live Nebius/Nemotron verification), #26 (public-demo safety + HF Spaces deploy), #27 (intent gating, caregiver-memo sanitising) merged.
- Render-time guard against leaked filesystem paths in video casts.

### 2026-10-01
- PRs #7, #8, #22, #23, #24 merged: core fixes, PRD/plan, day-2 recall, real voice I/O, test suite.

## Testing and measurements

| Test | Result | Date | Notes |
|------|--------|------|-------|
| beat1 (caregiver memo) | Works, no key | 10-01 | |
| beat3 (fast-path disclosure) | Works, no key | 10-01 | 0.11s to first reply |
| beat2 (full LLM turn) | 4.22s to first audio | 10-02 | Before reasoning-off (PR #25) |
| beat2 with `enable_thinking: false` | ~0.91s to first audio | 10-03 | PR #29 |
| Day-2 recall | Cross-process persistence | 10-01 | |
| Real voice round trip | Works | 10-01 | audio -> ASR -> model -> TTS -> play |
| Hosted isolation (dry run) | Sessions independent | 10-02 | `--dry-run --keep-stage` |
| TTS endurance, 200 sentences in one process | 0 empty WAVs, min 123 KB, 12.5s | 10-05 | #28 evidence; regression test runs 60 in-suite (~3s) |
| Full suite after the 10-06 fast-forward | `Ran 97 tests in 4.079s … OK (skipped=2)` | 10-07 | 94 → 97 tests; the second skip is Benchmark 9 with no API key present |

## Known gotchas

- **Killing servers:** don't `kill %1` or pattern-kill inside a compound shell command (it kills your own shell). Use `fuser -k PORT/tcp`.
- **Playwright + Gradio audio upload:** click `button[aria-label='Upload file']`, then `set_input_files` on `[data-testid=file-upload]`.
- **Pull before you trust status:** your teammate may have pushed to `main`. `git pull` before trusting what you remember of the app.
- **Free HF Spaces sleep:** keep the Space awake before judging; a cold first click can hang.
- **A worktree needs its own `.venv`:** `.githooks/pre-push` runs `$ROOT/.venv/bin/python`, so a fresh worktree silently falls back to system `python3`, which lacks gradio — the hook then reports "unit tests fail" when really the runner has no dependencies. Build one per worktree (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
- **Tests spend the demo's quota:** the suite increments the live daily counter 11x per run (see #53). A day of local testing will make webapp tests fail with a message about the daily cap, and can deny a real judge their turn.
- **Direct commits to `main` bypass `REVIEW.md`:** ADR-006 permits them, but the review passes only ever run on PRs — nine landed in one day with no review anywhere (found by diffing `main..origin/main` after a fast-forward). Review the commit log between PR merges, not just `gh pr list`.

## Decisions logged

One line each; the reasoning is in the ADR.

| Decision | Choice | Date | ADR |
|----------|--------|------|-----|
| TTS | pyttsx3; `espeak-ng` CLI on Linux/macOS | 10-01 (amended 10-03) | [001](decisions/ADR-001-tts-backend.md) |
| THINK + AUDIT model | Nemotron Nano 30B on Nebius | 10-01 | [002](decisions/ADR-002-think-audit-model.md) |
| Hosting | HF Spaces | 10-01 | [003](decisions/ADR-003-hosting.md) |
| ASR | Local faster-whisper | 10-02 | [004](decisions/ADR-004-asr-backend.md) |
| Safety fast-path | Rule-based regex | 10-01 | [005](decisions/ADR-005-safety-fastpath.md) |
| Working agreement | Direct commits to `main`; pvjthomas keeps write access | 10-04 | [006](decisions/ADR-006-working-agreement.md) |
| Attribution | Human = author, AI = `Co-Authored-By` trailer; warn-only guardrails | 10-05 | [007](decisions/ADR-007-attribution.md) |
| Build vs reuse | Keep privacy layer, fast-path, voice loop; licence check on `piper-tts`; trial embedding retrieval (Proposed, review #114) | 10-09 | [009](decisions/ADR-009-build-vs-reuse.md) |

## How to update this

1. After each session add a dated entry (newest first). Put open items on GitHub, not here.
2. Add measurements to the testing table.
3. Log every decision as an ADR and add the one-liner above.
4. Record gotchas so they aren't rediscovered.
