# plan.md -- REVIEW.md + AGENTS.md verification/UTF-8 hardening

> Written per `.agents/skills/plan-feature`. NO source or doc files are changed
> in this phase -- this plan is the only artifact. Implementation follows
> `.agents/skills/implement-feature` only after approval. Scope and constraints
> honor `.agents/rules/coding-standards.md` (prefer simple, no unnecessary deps,
> don't touch unrelated files) and `.agents/rules/testing.md`.
>
> Source: applying the AI-Native SDLC playbook principles to a 2-person
> hackathon repo. Deliberately adopts only the low-cost, high-fit docs/CI
> controls and skips enterprise machinery (intent.md chain, autonomous Maintain
> loops, managed MDM settings).

## Intent

Two documentation/CI changes that harden safety invariants already in AGENTS.md,
without adding architecture:

1. **REVIEW.md** (Deploy-stage play): a repo-root review policy defining the
   passes a PR review (human or Claude/Kiro) should run, with an explicit Safety
   pass that enforces the existing AGENTS.md invariant: `safety/fastpath.py` is
   deliberately biased to false positives and must not be narrowed without an
   Issue + ADR.
2. **AGENTS.md verification hardening** (Test-stage play): make the Windows
   `PYTHONUTF8=1` requirement explicit in the test command, and add it to the
   "Things people get wrong" section (the playbook's "correct a repeated mistake
   in the file" rule). Optionally note the benchmark eval-gate convention.

These are the two highest-value, lowest-cost moves identified: both reinforce
safety invariants the team already cares about, both are documentation (plus at
most a tiny CI touch), neither changes application behavior.

## Current state (read from the repo at main 94c8f30)

- **No REVIEW.md exists** (confirmed via search). Repo root has AGENTS.md,
  CONTRIBUTING.md, HOW_TO_WORK_HERE.md, README.md, CHANGELOG.md, SECURITY.md.
- **AGENTS.md** lists the test command as `python -m unittest discover tests -v`
  under "Commands", with a "Verify before reporting anything done" section and a
  "Things people get wrong" section. It does NOT mention the Windows UTF-8
  requirement. The emoji assertions in tests/test_webapp.py fail under the
  default Windows cp1252 console; they pass with `PYTHONUTF8=1` (observed twice
  this project: 85/85 and 91/91 only green under UTF-8 mode).
- **CI (`.github/workflows/tests.yml`)** runs on `ubuntu-latest`, which is UTF-8
  by default, so CI is UNAFFECTED. The UTF-8 issue is a Windows-local-dev gotcha
  only (relevant to the coworker's machine). The plan must NOT change CI behavior
  for this; any note is informational.
- **`tests.yml` triggers** on push-to-main and all pull_requests, running the
  full `unittest discover`. It does NOT currently special-case config files
  (safety/, AGENTS.md, .agents/skills/).
- **Benchmarks** already exist in `tests/test_mature_benchmarks.py` (false-
  positive safety-escalation rate, caregiver privacy leakage, unnecessary
  personalization, etc.) and run as part of the normal suite.
- **AGENTS.md "Things people get wrong"** already states the fastpath false-
  positive-bias invariant and the "when an assistant makes the same mistake twice,
  put the correction here" rule -- REVIEW.md's Safety pass should point at this,
  not restate policy (AGENTS.md stays the single source for the invariant).

## Design of the changes

### Change 1 -- add REVIEW.md at repo root

A short (under ~1 page) review policy. Structure modeled on the playbook's
REVIEW.md but scaled to this repo:

- **Passes** (tag each finding with its pass):
  - *Bugs*: logic errors, broken edge cases, regressions.
  - *Safety*: ANY change that narrows/weakens a `safety/fastpath.py` pattern, or
    reduces a caregiver disclosure, is Important and must cite a linked Issue +
    ADR (per AGENTS.md and docs/decisions/ADR-005). Also: no silent caregiver
    surveillance -- every flag states whether the senior was told.
  - *Privacy*: no new PII in logs/errors; `.env`, `data/`, `out/` never
    committed (mirrors the pre-commit hook).
  - *Compliance-with-plan*: the diff matches the committed `.kiro/specs/.../plan.md`
    (or the Issue AC) for the change.
- **What "Important" means here**: breaks a beat in the README three-beat demo,
  weakens a safety/disclosure invariant, or leaks data. Style/naming are nits.
- **Cap the nits**: at most ~5 per review.
- **Do not report**: generated/cache dirs (`__pycache__`, `.venv`), anything the
  pre-commit hook or CI already enforces.
- **Keep demo-able**: a change that breaks `main`'s three-beat demo is an
  automatic Important finding (ties to AGENTS.md "keep main demo-able").

REVIEW.md references AGENTS.md and docs/decisions/ for the actual policy; it does
not duplicate it (avoids the drift AGENTS.md warns about).

### Change 2 -- AGENTS.md verification hardening

Minimal, surgical edits to the existing file (keep it under a page):

a. **Commands section**: annotate the test line so the Windows requirement is
   impossible to miss. Example:
   `python -m unittest discover tests -v    # tests (standard library only)`
   add a following line:
   `# Windows: prefix with PYTHONUTF8=1 (set PYTHONUTF8=1) -- emoji test asserts need UTF-8`
   Keep the Linux/macOS command as the canonical one (CI uses it as-is).

b. **"Things people get wrong" section**: add one bullet:
   "On Windows, `unittest` fails on emoji assertions under the default cp1252
   console. Run with `PYTHONUTF8=1` (or `chcp 65001`). Linux/CI is UTF-8 already."
   This is the playbook's "repeated mistake -> write it in the file" rule; it was
   hit twice this project.

c. **(Optional, confirm in review)** Add a one-line pointer in the verify section
   that config changes to `safety/fastpath.py`, `AGENTS.md`, or `.agents/skills/`
   should be checked against `tests/test_mature_benchmarks.py` before merge --
   the lightweight "eval gate" idea, expressed as a convention rather than new CI.
   Flagged optional because it edges toward adding process; include only if the
   maintainer wants it.

### Explicitly NOT in scope

- No change to CI behavior / `tests.yml` (CI is already UTF-8; adding a
  config-file-triggered eval job is deferred -- it's the heavier "eval gate" play
  and not needed to capture the value here).
- No new `intent.md`/`spec.md` artifact chain (GitHub Issues remain the intent
  home, per AGENTS.md "state lives only on GitHub").
- No autonomous Maintain-stage machinery, managed settings, or deploy tiers.
- No application code touched: `pipeline/`, `webapp.py`, `safety/`, `memory/`,
  `caregiver.py`, `main.py` all unchanged.

## Affected files

- `REVIEW.md` (NEW, repo root).
- `AGENTS.md` (edit: Commands annotation + one "Things people get wrong" bullet;
  optional one-line eval-gate convention).
- Plan artifact: `.kiro/specs/review-policy-and-verify-hardening/plan.md` (this file).

Nothing else.

## Dependencies

None. No new third-party packages, no CI runners, no services. Pure docs.

## Risks

- **Doc drift**: REVIEW.md could restate policy that lives in AGENTS.md/ADRs and
  then drift. Mitigation: REVIEW.md *references* those sources for the invariant,
  only adding the review-pass framing.
- **AGENTS.md page-length**: AGENTS.md is intentionally under a page and read in
  full every session. Mitigation: additions are 2-3 lines total; if it pushes
  over a page, trim an already-stale line in the same edit.
- **Over-process**: adding controls to a 2-person repo can cost more than it
  saves. Mitigation: both changes are passive docs an agent reads; neither adds a
  blocking gate or a required human step. The optional eval-gate line is flagged
  separately so the maintainer can decline it.
- **Windows command accuracy**: the `set PYTHONUTF8=1` form must be correct for
  the coworker's shell (cmd vs PowerShell differ). Mitigation: give the portable
  env-var form and both shell spellings in the "Things people get wrong" bullet.

## Tests / verification (per .agents/rules/testing.md)

These are doc-only changes, so "tests" means:
- Run the full suite once after the edits with `PYTHONUTF8=1` and confirm it stays
  green (no behavior changed; this is a regression check that the AGENTS.md
  command as newly written actually works on Windows). Expected: 91 passing.
- Lint/build: none applicable to markdown.
- Manually verify REVIEW.md is under ~1 page and AGENTS.md is still under a page.
- Confirm the three-beat demo instructions in README are untouched (keep main
  demo-able).

## Out of scope / follow-ups (not this change)

- A CI eval-gate job that runs benchmarks when `safety/`, `AGENTS.md`, or
  `.agents/skills/` change (the full Test-stage eval play). Worth a separate Issue
  if the team wants enforcement rather than convention.
- Automated Claude/Kiro PR-review action wired to REVIEW.md (the managed Code
  Review service / claude-code-action). REVIEW.md is useful to humans immediately;
  automation is a later, separate step.

## Decisions (resolved by maintainer)

1. **Eval-gate line: INCLUDE.** `tests/test_mature_benchmarks.py` exists and is
   run by the normal suite, so AGENTS.md gets the convention line pointing at it
   (specifically Benchmark 2 `test_false_positive_safety_escalation_rate` guards
   the fastpath false-positive bias, Benchmark 4 the privacy firewall). The line
   is a convention ("check these before merging changes to safety/, AGENTS.md, or
   .agents/skills/"), not new CI.
2. **One `docs:` commit** for both REVIEW.md and the AGENTS.md edit.
