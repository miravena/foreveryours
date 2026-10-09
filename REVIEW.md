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

## Nits

A nit is a finding that breaks no demo beat, weakens no safety or disclosure invariant and
leaks nothing. Nits are still reported and still get a home (see "Where every finding goes");
there is no count limit, because grouping by area keeps them small.

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
| A partner's PR after it merges | Claude Sonnet 5.5, runtime-checked (run the code, don't just read it): **high** effort for safety-critical files and new behaviour that can contact the user, **medium** otherwise | It can run the change and comment; medium has been enough to catch real bugs. One review per PR. |
| Safety-critical files (`safety/fastpath.py`, `memory/store.py`, `caregiver.py`, disclosure logic) | Claude at high effort; add Codex (`scripts/openai_review.sh`, with the model and effort always pinned, never the CLI default) only when that review looks thin | A miss here has a real person on the other end. A second pass is spent on demand, not by default. |

Run each review in a **separate subagent** so the reviewer's reading never fills the author's
context. Give it the PR number, this file, and a read-only brief: no edits, no commits, no
pushes, never read `.env` or any key. Opus/Fable are not the default; ask for them only when
Sonnet's review of a safety-critical change looks thin. For model/effort choices beyond
reviewing, see [`CONTRIBUTING.md`](CONTRIBUTING.md)'s "Which model and effort for what".

### The review comment

- One comment per PR (`gh pr comment`, not an approval or change-request).
- Start with a header in the same shape as the `Assisted-by` commit trailer
  ([CONTRIBUTING.md](CONTRIBUTING.md) -> "Recording which model did what"), e.g.
  `Reviewed-by: ClaudeCode:claude-sonnet-5-5 effort=high, runtime-checked`.
  **runtime-checked** means the reviewer ran the test suite and the README demo beats against the
  PR's merge commit and exercised the specific risk, not only read the diff. If something could not
  be run, say what was skipped, e.g. `runtime-checked (no live key)`.
- Findings carry `file:line` and the exact input/output that proves them, and are tagged
  **reproduced** (ran it, saw it fail) or **read only** (seen in the diff, not run).
- End with a verdict line. Tag the PR's author (`@SirTehTarik`) when a finding concerns their PR.
- No fleet, host or session details: the repo is public.

### Where every finding goes

A finding that only lives in a comment is not actionable, so every finding gets exactly one
home, and the comment lists each finding with the link to it. There are no count limits; the
rules below keep volume down by grouping, not by cutting.

1. **Search first.** `gh issue list --state all --search "<keywords>"`.
2. **An open Issue covers it:** add the evidence there, and if the review shows its acceptance
   criteria are incomplete, edit the Issue body (state lives in the body; comments are for
   evidence). Do not open a second Issue.
3. **A closed Issue has regressed:** reopen it with the evidence.
4. **Findings sharing a root cause:** one Issue, one acceptance-criteria checkbox per symptom.
5. **Nits:** one grouped Issue per file or area, as a checklist that one PR can close
   (e.g. "cleanup: `pipeline/orchestrator.py` from review of #94/#99/#100").
6. **Anything else is a distinct defect:** a new Issue with its own acceptance criteria and a fix
   that can land alone.
7. **Every Issue** gets a milestone, the `review-finding` label (plus `bug` or `enhancement`), a
   link to the review comment, and an `@` mention of the PR's author. Body sections follow the
   work-item template: Why this matters, Acceptance criteria, Current state (with the
   reproduction).

Milestone by finding type: breaks a demo beat or blocks hosting -> M5; safety or disclosure
invariant -> M13 (M5 if it blocks the demo); latency or voice -> M11; submission video or Devpost
text -> M8 / M12; everything else, including grouped nits -> Backlog.

A reviewer posts nothing until the maintainer has read the draft: the review is itself reviewed
before it becomes comments and Issues.
