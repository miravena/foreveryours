# Changelog

All notable changes to ForeverYours are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are tagged
on `main` and published as [GitHub Releases](../../releases).

**How to update:** add a line under `## [Unreleased]` in the PR that makes the
change (group under Added / Changed / Fixed / Docs). When we cut a release,
rename `Unreleased` to the version and date, then tag it.

## [Unreleased]

### Changed
- The companion's output voice is now an offline **neural** voice (Piper, `en_US-lessac-medium`) when its CLI and voice model are present, replacing the robotic espeak-ng/System.Speech voice that ADR-001 had accepted as a Design-score tradeoff (#52, ADR-008). It is auto-detected and optional: with no voice model installed the demo falls back automatically to the previous espeak-ng/System.Speech/pyttsx3 path, so no extra install is required to run `main`. Fully offline — no network or API key at runtime. Each sentence is synthesized in its own clean subprocess, so the #28 long-running-silence fix is preserved.

### Added
- Model-level distress backstop (#56): the async AUDIT pass now evaluates the senior's transcript for long-tail distress phrasings and severe crisis, emitting `DISTRESS` or `CRISIS` verdicts to raise the caregiver flag with zero added latency on the critical path.

### Fixed
- Model safety backstop (#56): the asynchronous audit now parses whole-word verdicts, disables reasoning overhead, records malformed failures as `unknown` rather than `SAFE`, and uses crisis-specific 988/family disclosure wording.
- Test integrity (#63, #107): live Benchmark 9 now requires explicit `RUN_LIVE_BENCHMARKS=1` opt-in, while its offline prompt contract always runs; only known missing-configuration, authorization, and connectivity failures skip live execution. Restored the perseveration regression test to discovery and added daemon boundary and missing-state coverage.
- Crisis fast-path false negatives (#105): Added missing direct suicidal phrasings and updated the false-positive guard to apply per-clause rather than globally, so real crisis statements are no longer suppressed by benign idioms in the same utterance.
- Crisis fast-path coverage (#105): Added direct suicidal-language variants, matched-span idiom filtering, and whitespace normalization for ASR line breaks while preserving the false-positive benchmark.
- Disclosure truthfulness (#117): safety, perseveration, audit, and lifestyle flags are persisted as disclosed only after non-empty audio is delivered; quiet-mode suppression now happens before proactive flagging, and late non-streaming disclosures remain explicitly undisclosed.

### Docs
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
