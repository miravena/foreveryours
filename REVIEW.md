# REVIEW.md -- how we review changes to ForeverYours

Read by a human reviewer and by Claude/Kiro when reviewing a PR. The actual
policy lives in [`AGENTS.md`](AGENTS.md) and [`docs/decisions/`](docs/decisions/);
this file only says which passes to run and how to rank what they find. It does
not restate policy, so it cannot drift from it.

## Passes

Run each pass and tag every finding with the pass it came from.

- **Bugs** -- logic errors, broken edge cases, regressions. The clearest signal:
  does the change keep `main` demo-able? The three-beat demo in
  [`README.md`](README.md) must still work after every change.
- **Safety** -- the heart of this project. Flag as **Important** any change that:
  - narrows or weakens a pattern in `safety/fastpath.py`. This path is
    *deliberately* biased to false positives; narrowing it needs a linked Issue
    and an ADR (see `AGENTS.md` -> "Things people get wrong" and
    `docs/decisions/ADR-005-safety-fastpath.md`). A narrowing PR with no ADR is a
    blocking finding.
  - reduces or removes a caregiver disclosure, or lets a flag be raised without
    stating whether the senior was told. No silent surveillance -- every flag
    discloses, in the conversation, that it was raised.
  - makes a medical, physical-action, or parasocial claim the prompt forbids
    (guarded by `tests/test_mature_benchmarks.py` Benchmark 6).
- **Privacy** -- no new PII in logs or error messages; `.env`, `data/`, `out/`
  are never committed (the pre-commit hook enforces this; flag anything that
  tries to defeat it). Caregiver-only memories must not leak into senior turns
  (Benchmark 4).
- **Compliance-with-plan** -- the diff matches the committed
  `docs/specs/<feature>/plan.md` (or the Issue's acceptance criteria) for the
  change. Call out undocumented scope.

## What "Important" means here

Reserve **Important** for findings that break a README demo beat, weaken a
safety or disclosure invariant, or leak data. Everything else -- style, naming,
micro-refactors -- is a **nit**.

## Cap the nits

At most five nits per review; summarize the rest as a count.

## Do not report

Generated / cache dirs (`__pycache__/`, `.venv/`, `out/`), and anything the
pre-commit hook or CI (`.github/workflows/`) already enforces.

## When and how we review

Reviews are optional and never block a merge ([ADR-006](docs/decisions/ADR-006-working-agreement.md):
merge to `main`, fix forward). They are run by hand; there is no automation. A review is only
worth doing if it leaves a trace, so every review ends in **a comment on the PR**.

| Case | Reviewer | Why |
|---|---|---|
| Our own assistant-written PR (self-review) | OpenAI Codex: `scripts/openai_review.sh` | A different vendor has different blind spots; a second Claude shares the first one's. |
| A partner's PR after it merges | Claude Sonnet 5.5, medium effort, runtime-checked (run the code, don't just read it) | It can run the change and comment; medium has been enough to catch real bugs. |
| Safety-critical files (`safety/fastpath.py`, `memory/store.py`, `caregiver.py`, disclosure logic) | Both: Claude at high effort **and** Codex | A miss here has a real person on the other end. |

Run each review in a **separate subagent** so the reviewer's reading never fills the author's
context. Give it the PR number, this file, and a read-only brief: no edits, no commits, no
pushes, never read `.env` or any key. Opus/Fable are not the default; ask for them only when
Sonnet's review of a safety-critical change looks thin. For model/effort choices beyond
reviewing, see [`CONTRIBUTING.md`](CONTRIBUTING.md)'s "Which model and effort for what".

### The review comment

- One comment per PR (`gh pr comment`, not an approval or change-request).
- Start with who and what ran it, e.g. `Review by Claude Sonnet 5.5 (medium effort), runtime-checked`.
- Findings carry `file:line` and the exact input/output that proves them; say which you reproduced.
- End with a verdict line. Tag the PR's author (`@SirTehTarik`) when a finding concerns their PR.
- No fleet, host or session details: the repo is public.

### Turning findings into Issues without sprawl

1. **Search first.** `gh issue list --search "<keywords>"`. If an open Issue covers it, comment
   there with the evidence instead of opening another.
2. **New Issue = distinct defect.** It needs its own acceptance criteria and a fix that can land
   alone. Group by root cause, not by symptom.
3. **Edit the Issue body** when scope or acceptance criteria change (state lives in the body);
   comments are for evidence and discussion.
4. **Nits never become Issues.** Count them in the review comment (at most five).
5. **At most three new Issues per review.** List the rest, grouped, in the comment.
6. **Regressions reopen.** If something closed has broken again, reopen it with the evidence.
7. **Every Issue** gets a milestone (or Backlog), a link to the review comment, and an `@` mention
   of the PR's author.
