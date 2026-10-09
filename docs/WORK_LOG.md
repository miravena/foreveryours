# Work Log

The shared, dated **journal**: what was tried, what worked, measurements and gotchas. **Add to
it after every session.** It is not a status page: what's open, blocked or due lives only on
GitHub ([milestones](../../milestones), [Issues](../../issues)). Issue comments hold per-issue
detail. Decisions live in [`decisions/`](decisions/README.md).

Format: newest first. One entry per session: date, who, what, result, next.

## Session entries

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
