# Changelog

All notable changes to ForeverYours are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are tagged
on `main` and published as [GitHub Releases](../../releases).

**How to update:** add a line under `## [Unreleased]` in the PR that makes the
change (group under Added / Changed / Fixed / Docs). When we cut a release,
rename `Unreleased` to the version and date, then tag it.

## [Unreleased]

### Added
- Memory control in conversation: THINK now emits `ADD:` / `SUPERSEDE:` / `DELETE:` commands that the memory store applies. Additions work; **corrections and forget-requests phrased with a family marker are currently stored as new facts instead** — the marker heuristic returns before the model can supersede or delete, so the request to forget gets remembered. Tracked in #54.
- Anti-dependency prompting: rule 17 of the THINK system prompt now actively redirects the senior toward their human family ("Sarah would love to hear your voice — why not give her a call?") rather than only declining to claim exclusivity.
- GitHub Actions workflow running the test suite on every push to `main` and every PR; `SECURITY.md` with private vulnerability reporting (#39).

### Changed
- Benchmark 8 (memory correction end-to-end) is always attempted instead of being skipped outright without an API key; it now skips inside the test only if the API call itself fails (e.g. a dummy key in CI).
- One source of truth: GitHub (milestones, Issues, blocked-by) records all work state; `docs/ROADMAP.md`, `IMPLEMENTATION_PLAN.md` and `WORK_LOG.md` no longer carry status or dates (#38).

### Fixed
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
