# ADR-007: Attribution — the human is the author, AI help is a trailer

**Status:** Accepted
**Date:** 2026-10-05
**Decided by:** Team (maintainers)
**Affects:** `CONTRIBUTING.md`, `.githooks/commit-msg`, `.githooks/pre-push`, `.github/workflows/attribution.yml`, `.github/commit-template.txt`
**Related issue:** [#42](../../issues/42)

## Question

How do we keep GitHub's Contributors graph crediting the human who did the work
while still recording which AI helped — when commits can come from any tool, on
any machine, in either timezone?

## Context

36 commits carried an unlinked author address — a `noreply@` alias on a personal
domain, matching no GitHub account — so the graph credited `claude` for the
human's work while `Co-Authored-By: Claude … <noreply@anthropic.com>` *did*
resolve to a real account. The assistance was credited and the human was not —
exactly inverted. (The address itself is deliberately not quoted here; it stays
out of tracked files.)

GitHub credits a commit to an account only when the author email matches a
registered address; co-author trailers are credited separately. Both slots are
therefore usable, which is what makes a fix possible without touching history.

Constraints: ADR-006 forbids force-pushing `main`, so the 36 cannot be relabelled;
and with two to three writers across timezones, whatever we choose has to work
without someone remembering to do it at commit time.

Modelled on the AI-native SDLC playbook's "enforce policy where the agent acts,
not in a review cycle nobody runs" principle — the same source as `REVIEW.md`.

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| Rewrite history to correct the 36 emails | Graph correct retroactively | Force-pushes `main` — blocked by ADR-006 and by GitHub's branch protection; real risk of losing a partner's work; invalidates SHAs already cited in Issues and ADRs | No |
| Convention only (write it in `CONTRIBUTING.md`) | Zero machinery | Repeats the first time a tool picks a default email; nobody reads a policy mid-commit | Yes — this is how the 36 happened |
| Convention + advisory guardrails (warn, never block) | Works for every writer, since git hooks and CI run for humans and agents alike; cannot block a deadline push; self-correcting | Only warns on a bad author email — a *missing* trailer still goes unnoticed | No |
| Convention + hard-failing guardrails | Strictest | An attribution failure halts a push that might be the last before a deadline; the cost of failure (a mis-credited commit) is low and reversible | No |

## Decision

**We chose: convention + advisory guardrails, with the hard-fail deferred.**

- **Author = the human**, with a GitHub-linked email. The ID form is the safest
  and is what this repo is configured with:
  `287302999+elevenbaselab@users.noreply.github.com`. **Never an AI identity in
  the author field.**
- **AI help appears only as `Co-Authored-By` trailers**, one per provider/model,
  using that provider's own name and email. Keep the trailer the tool already
  writes rather than stripping it; don't invent an address for a provider that
  publishes none — the trailer still documents the assistance in the text.
- **Old commits keep the email they were written with.** No rewrite, no
  force-push: the convention applies going forward.
- **Guardrails stay warn-only for now:** `commit-msg` warns on an unlinked author
  email (always exits 0), `attribution.yml` warns per commit in CI, and
  `pre-push` blocks only on failing tests and on commit subjects missing
  `Fixes/Refs #N`. Making `attribution.yml` a failure is a separate decision
  after a clean week (an AC on #42, not a change to make casually).

## Rationale

The graph is a nice-to-have; a blocked push before a deadline is not. Every
guardrail here runs for a human exactly as it runs for an agent — a git hook is
not an assistant feature — so a warning raised in CI reaches whoever is working
in the other timezone at 03:00. Once the convention has held for a week without
a warning, promoting it to a failure is one line and costs nothing.

## Consequences

- **Unlocked:** an accurate Contributors graph going forward; one documented rule
  any tool can follow without being told twice; cheap adoption for a fourth writer.
- **Locked in to:** never rewriting history — the 36 old commits stay under
  credited permanently, and that is accepted.
- **Gotchas:** nothing warns when a trailer is *missing*, only when the author
  email is wrong, so a tool that strips trailers under-credits silently.
  `commit.template` is per-clone, so a fresh clone starts without the reminder.

## When to revisit

A commit lands with an AI identity in the author field (the convention failed,
and the warn-only guardrail missed it) — or the attribution workflow has stayed
warning-free for a week, in which case decide whether it becomes a failure.

## Amendment 2026-10-09: `Assisted-by` replaces `Co-Authored-By` for AI

**Decided by:** maintainer (founder), 2026-10-09. **Related issue:** [#42](../../issues/42).

**Change.** AI help is recorded as `Assisted-by: <harness>:<model id> effort=<level>`
trailers, one per harness/model, and **no longer as `Co-Authored-By`**. The human stays
the author and is responsible for the commit. Format and how-to: `CONTRIBUTING.md` ->
"Recording which model did what".

**Why.** The two goals differ. `Co-Authored-By` is a credit mechanism: it names a tool or
vendor as a co-author, carries no model id or effort, and (when the email maps to a
GitHub account) puts that account on the graph. What we need for debugging and for
cross-vendor review (`REVIEW.md`) is which harness, model and effort produced a change.
`Assisted-by` follows the Linux kernel's `Assisted-by: AGENT_NAME:MODEL_VERSION` and
Fedora's AI-contribution policy, neither of which uses an email. `effort=` is our own
extension; neither source defines an effort field.

**Unchanged.** Author = the human with a GitHub-linked email; no rewrite of old commits
(the 36 mis-credited and every existing `Co-Authored-By` stay); guardrails warn, never
block. A warn-only check for a missing `Assisted-by` is a follow-up, not part of this
change.

**Revisit if** a reviewer or the Contributors graph needs the tool credited as a
co-author again, or the kernel/Fedora convention changes.

## Amendment 2026-10-09 (2): cost trail, and a warning that keeps `Co-Authored-By` out

**Decided by:** maintainer (founder), 2026-10-09. **Related issue:** [#118](../../issues/118).

**Change.** (1) Commits, PR `Provenance` blocks and review comments also carry an approximate
cost estimate (`Cost-estimate:` trailer; format and source in `CONTRIBUTING.md` -> "Recording
what it cost"). (2) `.githooks/commit-msg` now also warns, never blocks, on an AI
`Co-Authored-By`, a `Claude-Session:` link, and an `Assisted-by` line with no `Cost-estimate`
line. This is the "warn-only check" the previous amendment deferred.

**Why.** The previous amendment removed `Co-Authored-By` for AI by convention only, and a
harness that adds it by default would put it back unnoticed. The cost line makes the
model/effort trail say what the work took.

**Unchanged.** Advisory only (exit 0); old commits stay as they are; no history rewrite.

## Amendment 2026-10-12: a kernel-shaped three-line format, one shared checker

**Decided by:** founder, 2026-10-12 (decision 912). **Related issues:** [#146](../../issues/146),
[#147](../../issues/147).

**Change.** Every AI-assisted commit, GitHub issue and comment now carries exactly three lines:

```
Assisted-by: <AGENT_NAME>:<MODEL_VERSION> [TOOL1] [TOOL2]
Assisted-meta: provider=<Anthropic|OpenAI|Google|...> effort=<low|medium|high|xhigh|max|unknown>
Cost-estimate: $X.XX (approximate[; in N, out N tokens])
```

- **Line 1** is the Linux kernel's *original* trailer shape
  (`Documentation/process/coding-assistants.rst` at
  [78d979db6c](https://github.com/torvalds/linux/commit/78d979db6c), 2025-12-23):
  `AGENT_NAME` is the harness (`ClaudeCode`, `Codex`, `Kiro`, `Antigravity`, `CopilotApp`),
  `MODEL_VERSION` is the exact model id, and the optional bracketed tools are specialised
  analysis tools used on the change (`codeql`, `openai_review`). Upstream simplified this on
  2026-07-01 ([816d9992d9](https://github.com/torvalds/linux/commit/816d9992d9)) to a bare
  `Assisted-by: LLM`, dropping the model, with the stated rationale of not advertising
  vendors. **We deliberately diverge and keep the model**: this repo needs per-model
  debugging and cross-vendor review (`REVIEW.md`), which a vendor-anonymous trailer cannot
  support, and we accept the tradeoff of naming the vendor in a public history.
- **Line 2** (`Assisted-meta`) is our own addition — the kernel format has no field for
  provider or effort, and we need both (`CONTRIBUTING.md` -> "Which model and effort for
  what", "Recording which model did what").
- **Line 3** (`Cost-estimate`) is unchanged from the previous amendment.
- A **review comment** uses the same three lines, with line 1 written
  `Reviewed-by: <AGENT>:<MODEL> [tools]` in place of `Assisted-by` (`REVIEW.md`).
- A **GitHub issue or comment** written with AI help opens with the same three lines (one
  per line, or `·`-separated on one line).
- **Merge commits made by an agent carry the same three trailers.** A trailer-less merge
  commit bounced review on #14294 — a merge is as much an AI-produced artifact as any other
  commit, so it is not exempt.
- **No `Co-Authored-By` for AI, no `Claude-Session` link, and no `Signed-off-by` from an
  agent** (the kernel reserves `Signed-off-by` for the human submitter) — all unchanged from
  the prior amendments, now stated together in one place.

**Checker consolidation.** The attribution checks (author email, AI `Co-Authored-By`,
session link, missing model, missing `Assisted-meta`, missing `Cost-estimate`) now live in
one script, `scripts/check_attribution.sh <msgfile> [author_email]`, called by both
`.githooks/commit-msg` and `.github/workflows/attribution.yml`, so
`tests/test_attribution_hook.py` exercises exactly what CI runs instead of two
hand-maintained copies drifting apart.

**Unchanged.** Advisory only (exit 0, every check); old commits stay as they are, no history
rewrite (ADR-006); author = the human with a GitHub-linked email.

**Revisit if** the kernel's `Assisted-by: LLM` simplification is adopted upstream widely
enough that naming the model becomes a liability rather than an asset, or the warn-only
checker needs to become a hard failure.
