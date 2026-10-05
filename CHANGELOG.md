# Changelog

All notable changes to ForeverYours are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are tagged
on `main` and published as [GitHub Releases](../../releases).

**How to update:** add a line under `## [Unreleased]` in the PR that makes the
change (group under Added / Changed / Fixed / Docs). When we cut a release,
rename `Unreleased` to the version and date, then tag it.

## [Unreleased]

### Added
- GitHub Actions workflow running the test suite on every push to `main` and every PR; `SECURITY.md` with private vulnerability reporting (#39).

### Changed
- One source of truth: GitHub (milestones, Issues, blocked-by) records all work state; `docs/ROADMAP.md`, `IMPLEMENTATION_PLAN.md` and `WORK_LOG.md` no longer carry status or dates (#38).

### Fixed
- Memory retrieval now correctly matches plurals/inflections on short words (e.g., 'dog' matches 'dogs') (#32).
- Updating a caregiver schedule (supersession) now preserves the original memory's temporal expiration and privacy scope instead of silently making it permanent (#34).

### Removed
- `TEAM_STATUS.md` (its table duplicated GitHub) (#38).

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
