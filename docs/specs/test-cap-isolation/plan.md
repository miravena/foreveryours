# plan.md -- #53: test suite drains the demo's daily request cap

> Written per `.agents/skills/plan-feature`. NO source files changed in this
> phase -- this plan is the only artifact. Implementation follows
> `.agents/skills/implement-feature` after approval. Honors
> `.agents/rules/coding-standards.md` (prefer simple, don't touch unrelated
> files) and `.agents/rules/testing.md`.

## Intent (GitHub #53)

`tests/test_webapp.py` turn tests call `webapp.run_demo_turn` -> `_rate_limit_ok()`,
which reads/writes the LIVE `data/rate_limit.json` counter shared with the running
demo. Each suite run consumes ~11 units; default cap `MAX_DAILY_REQUESTS=50`, so the
5th run of a day fails -- with misleading failure names (`'Record audio ...' not
found in 'This demo has hit its daily request cap...'`). Running tests can also deny
a real judge their turn, which touches the hackathon "no restriction" rule.

## Current state (verified on current `main`, NOT the issue's `f47e99f`)

Several of the issue's defects are ALREADY FIXED on main; the plan must not redo them:

- **Defect 2 (false comment) -- ALREADY FIXED.** `webapp.py:81` now reads
  `# date string -> count; re-read from rate_limit.json on each call`. Accurate. No change.
- **VENDOR_DECISIONS.md -- ALREADY ACCURATE.** Line 17 says the counter is in
  `data/rate_limit.json` "so it survives a restart" and "resets daily rather than on
  restart". The stale "resets on process restart" wording the issue quotes is gone. No change.
- **Criterion 4 test ALREADY EXISTS.** `tests/test_webapp.py::TestEmptyTranscriptArity::
  test_rate_limited_path_preserved` (line ~386) patches `_rate_limit_ok` -> False and
  asserts the cap message. It covers the cap path AND does not drain quota. Keep as-is.

The ONE real remaining defect:

- **Defect 1 (tests spend real quota) -- NOT FIXED.** `_rate_limit_ok()` reads
  `DATA_DIR / "rate_limit.json"` where `DATA_DIR` is a module global
  (`webapp.py` top). `TestWebappSessions.setUp` patches `SESSIONS_DIR` and
  `SHARED_PROFILE` but NOT `DATA_DIR`, and does not patch `_rate_limit_ok`. So every
  `run_demo_turn` in that class hits the real `data/rate_limit.json`.
  `TestEmptyTranscriptArity.setUp` has the same gap for its turn-based tests
  (only `test_rate_limited_path_preserved` is isolated, via its own patch).

## Design of the fix

Smallest change that fixes defect 1 for both test classes, per the issue's ranked
option 1 ("point DATA_DIR at a temp dir ... in setUp"):

1. In BOTH `TestWebappSessions.setUp` and `TestEmptyTranscriptArity.setUp`, add
   `patch.object(webapp, "DATA_DIR", <temp>/ "data")` to the existing `self.patches`
   list. `_rate_limit_ok` reads `DATA_DIR` at call time, so the counter file lands in
   the per-test temp dir and the live `data/rate_limit.json` is never touched.
   - Both setUps already create a `TemporaryDirectory`; reuse it (e.g.
     `Path(self.temp_dir.name) / "data"`). Do NOT pre-create the file; absent file =
     count 0, which is the clean start the issue's Criterion 1 wants.
   - Keep the existing `webapp._request_log.clear()` so the in-memory global can't
     carry a count between tests either.

2. No change to `webapp.py` logic. Persisting to disk is deliberate (`25a0f0d`); the
   issue explicitly says do NOT "fix" this by raising the cap, and the counter
   persistence is correct. The bug is purely that tests weren't isolated from it.

### Why not patch `_rate_limit_ok` instead?

Patching `DATA_DIR` is strictly better here: it keeps the real `_rate_limit_ok`
logic under test (so a future regression in the counter is still caught) while
isolating only the FILE it writes. Patching the function out would reduce coverage of
the cap logic. The one place patching the function IS right -- forcing the cap-hit
branch deterministically -- is already done in `test_rate_limited_path_preserved`.

## Affected files

- `tests/test_webapp.py` -- add `patch.object(webapp, "DATA_DIR", ...)` to the two
  setUps. Test-only change.
- Plan artifact: `.kiro/specs/test-cap-isolation/plan.md` (+ mirrored to
  `docs/specs/test-cap-isolation/plan.md`).

Explicitly NOT changed: `webapp.py` (comment already correct), `VENDOR_DECISIONS.md`
(already accurate), application code, CI.

## Dependencies

None. Uses `unittest.mock.patch.object` already imported in the test file.

## Risks

- **Missing a turn-based test in a third class/path.** Mitigation: after the fix, the
  acceptance check (run the suite 10x and diff `data/rate_limit.json`) proves NO path
  still writes it, regardless of which test triggered it.
- **A test that genuinely asserts cap behaviour.** Only
  `test_rate_limited_path_preserved` does; it patches `_rate_limit_ok` directly and is
  unaffected by the `DATA_DIR` patch. Verify it still passes.
- **Windows UTF-8**: unrelated but remember `PYTHONUTF8=1` for the local run.

## Tests / verification (per .agents/rules/testing.md and #53 ACs)

- **Criterion 1 (measured):** `rm -f data/rate_limit.json`; run
  `python -m unittest discover tests` 10 times; assert `data/rate_limit.json` is still
  absent (or unchanged) afterward. Paste the before/after.
- **Criterion 4:** confirm `test_rate_limited_path_preserved` still passes.
- Full suite green (PYTHONUTF8=1 on Windows); run the benchmark set too since the
  suite touches webapp turns, though no safety file changes here.

## Decisions / out of scope

- **Criterion 5 (the cap VALUE: is 50/day a "restriction" for judging?)** is a
  founder/policy call, NOT a code fix. The deploy script already sets
  `MAX_DAILY_REQUESTS=200` for the hosted Space. This plan does NOT change the value;
  flag it to the maintainer and, if they decide, record it on #11 / an ADR separately.
- Defects 2, 3 (comment, VENDOR_DECISIONS, misleading failure names) are already
  resolved on main or are a downstream symptom of defect 1 that disappears once the
  counter is isolated.

## Open decision for implement phase

Confirm the spec folder name: proposed `test-cap-isolation` (describes the fix, not
just the issue number). Alternative: `issue-53-rate-limit-test-isolation`.
