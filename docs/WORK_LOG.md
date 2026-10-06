# Work Log

The shared, dated **journal**: what was tried, what worked, measurements and gotchas. **Add to
it after every session.** It is not a status page: what's open, blocked or due lives only on
GitHub ([milestones](../../milestones), [Issues](../../issues)). Issue comments hold per-issue
detail. Decisions live in [`decisions/`](decisions/README.md).

Format: newest first. One entry per session: date, who, what, result, next.

## Session entries

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

## Known gotchas

- **Killing servers:** don't `kill %1` or pattern-kill inside a compound shell command (it kills your own shell). Use `fuser -k PORT/tcp`.
- **Playwright + Gradio audio upload:** click `button[aria-label='Upload file']`, then `set_input_files` on `[data-testid=file-upload]`.
- **Pull before you trust status:** your teammate may have pushed to `main`. `git pull` before trusting what you remember of the app.
- **Free HF Spaces sleep:** keep the Space awake before judging; a cold first click can hang.
- **A worktree needs its own `.venv`:** `.githooks/pre-push` runs `$ROOT/.venv/bin/python`, so a fresh worktree silently falls back to system `python3`, which lacks gradio — the hook then reports "unit tests fail" when really the runner has no dependencies. Build one per worktree (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
- **Tests spend the demo's quota:** the suite increments the live daily counter 11x per run (see #53). A day of local testing will make webapp tests fail with a message about the daily cap, and can deny a real judge their turn.

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

## How to update this

1. After each session add a dated entry (newest first). Put open items on GitHub, not here.
2. Add measurements to the testing table.
3. Log every decision as an ADR and add the one-liner above.
4. Record gotchas so they aren't rediscovered.
