---
name: Work item
about: A task on the critical path (linked from ROADMAP.md)
title: '[M##] <concise title>'
labels: 'work-item'
---

## Why this matters

One sentence: what breaks if we don't do this? What does it unblock?

Example: "Blocks M5 (go-live); without this, judges will see silent replies after ~5 turns"

## Acceptance criteria

- [ ] **Criterion 1:** Clear, measurable, testable
- [ ] **Criterion 2:** Can be verified without subjective judgment
- [ ] **Criterion 3:** (if needed)
- [ ] **Single source of truth:** this Issue has a milestone and any blockers set as *blocked by*; no status or dates copied into a doc

Example:
- [ ] pyttsx3 produces non-empty audio on turns 1–50 without segfault
- [ ] espeak runs on Linux, macOS, and Windows (or documented why not)
- [ ] All tests still pass

## Current state

What works today? What's broken?

Example: "espeak outputs 44-byte empty WAVs after ~19 sentences in one process (verified 2026-10-02)"

## What to try

Ranked by likelihood of working (try these in order):
1. **Approach A** — Why this first: [link to ADR or WORK_LOG if relevant]
2. **Approach B** — Why second: ...
3. **Approach C** — Fallback if A+B don't work

Example:
1. **Check espeak stderr** — may have a limit flag
2. **Test on macOS** — issue might be Linux-specific (pyttsx3 native there)
3. **Fallback to gTTS** — slower, but online, avoids segfault

## Gotchas (if known)

Things to watch for:
- `--no-play` flag suppresses playback (needed for testing)
- pyttsx3 has different backends per OS (native on Mac, espeak on Linux)
- The `context` gating rules from #27 still apply (don't break them)

## Related

- **Blocked by / blocks:** set under *Relationships* in the sidebar (not only here)
- **Related:** [Issue #9](../../../issues/9) (voice I/O wired), [ADR-001](../../docs/decisions/ADR-001-tts-backend.md) (why espeak)

## How to update this

**As you investigate:**
- Add findings to [WORK_LOG.md](../../docs/WORK_LOG.md) (what you tried, test results)
- Comment here with blockers or pivots
- Link to commits/PRs as you land fixes

**When done:**
- Check all criteria above
- Link the PR or commit that closes this
- Add a final comment: "Verified on [date], see [link]"
- Close the issue

---

**Template notes:**
- Use `[M##]` prefix (e.g., `[M5]`, `[M11]`) to link from ROADMAP milestones
- Link related Issues and ADRs so context is always reachable
- "Gotchas" are things you discovered; future workers can see them immediately
- Either of us can update this — it's just Markdown in GitHub
