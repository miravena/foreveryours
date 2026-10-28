# Public-demo release candidate plan

## Scope and acceptance criteria

This plan implements Step 1 of the agreed ForeverYours project plan without
changing deployment or submission artifacts. The local repository has no
`intent.md` or `spec.md`; the authoritative requirements are GitHub issues
#88, #161, #162, #164, #152, and #169, plus the existing issue-specific plans
and regression tests.

### 1. No-silent-surveillance perseveration disclosure (#88)

> **Superseded by the code (#173).** The plan below was not implemented as written. The shipped
> behavior: the perseveration flag is persisted with `disclosed_to_senior=True` whenever the
> check fires, whether or not text-to-speech produced audio, because the disclosure sentence is
> always part of the returned text reply (#159). The "persist `False` on failed delivery" bullet
> applies to fast-path, audit and lifestyle flags, not this one. Kept as the original plan.

- Keep the existing repeated-question safeguards: matching intent, content
  overlap, distinguishing words, timestamps, and exclusion of proactive turns.
- Make the confusion flag's disclosure state reflect actual delivery, not
  merely construction of a response or a synthesized path.
- Ensure the disclosure is present in the senior-facing returned text/audio
  for normal and quiet-mode behavior. If delivery fails, persist
  `disclosed_to_senior=False` and leave the caregiver-visible flag honest.
- Do not count ordinary repeated “yes” messages or unrelated casual turns.
- Add runnable regression tests that cover true repeats, false positives,
  proactive history exclusion, quiet mode, and failed disclosure delivery.

### 2. Caregiver-panel authorization firewall (#161, #162, #164)

- Treat every `conversation_extract` item as senior-derived and private by
  default, regardless of whether the extractor labels it `ADD`, bare text,
  `UNCERTAIN`, permanent, historical, or emotional.
- Permit caregiver-panel rendering only for caregiver-authored sources or
  senior-derived records carrying an independently recorded authorization
  that the senior was told and agreed to the disclosure.
- Preserve the existing fail-closed checks for conflicts, unknown scopes,
  emotional prefixes, and caregiver-only records.
- Add focused tests for private permanent facts, uncertain facts, `ADD:` output,
  bare-fact/model-misclassified output, and explicitly authorized records.
- Ensure the extraction path records authorization only after the relevant
  disclosure is successfully delivered; a model classification alone must
  never authorize caregiver visibility.

### 3. Honest browser audio-retention disclosure (#152)

- Update the browser “About this demo household” text to distinguish:
  session-directory cleanup after Gradio closed-session handling or the
  application inactivity sweep, from Gradio's separate input/output cache.
- Derive and state the configured cache sweep interval, age threshold, and
  worst-case retention from `GRADIO_CACHE_SWEEP`; state that
  `SESSION_TTL_S` controls application cleanup/inactivity and cache age as
  configured, without claiming the tab-close event itself deletes audio.
- Keep `docs/PRIVACY.md`, `docs/SAFETY_AND_PRIVACY.md`, and retention tests
  consistent with the browser disclosure.

### 4. Shared-profile public turn handlers (#169)

- When `FY_SHARED_PROFILE=1`, both `run_demo_turn` and
  `run_demo_turn_streaming` must use shared `DATA_DIR`/`AUDIO_DIR` without
  validating the profile id (`dad`) as a per-session hex directory name.
- Preserve strict per-session validation and normalization when shared mode is
  disabled, including malformed-id crisis handling and path containment.
- Add tests for both public entry points in shared mode with ordinary text and
  a crisis message, asserting execution reaches the offline pipeline/fast
  path rather than failing at session validation.

## Affected files

- `pipeline/orchestrator.py`: delivery-aware perseveration disclosure and
  extraction authorization handoff.
- `memory/store.py`: persist any explicit disclosure authorization metadata
  needed by the caregiver firewall, with backwards-compatible loading.
- `webapp.py`: fail-closed caregiver visibility, shared-profile turn routing,
  and browser retention wording.
- `tests/test_orchestrator.py`, `tests/test_perseveration_window.py`,
  `tests/test_caregiver_panel_privacy.py`, `tests/test_session_paths.py`,
  `tests/test_webapp.py`, and/or focused new test methods.
- `docs/PRIVACY.md`, `docs/SAFETY_AND_PRIVACY.md`, `CHANGELOG.md`, and
  `docs/WORK_LOG.md` for directly related user-facing and engineering notes.

## Risks and compatibility

- Disclosure status must not be set before audio/text delivery succeeds;
  quiet mode must not create a silent authorization.
- Existing caregiver memos, safety flags, lifestyle disclosure attestation,
  memory conflict scrubbing, and senior-facing recall must remain unchanged.
- Existing JSON memory files lack new metadata, so loading must default
  safely to unauthorized rather than expose old senior-derived facts.
- Shared-profile mode is intentionally a local/demo compatibility mode; it
  must not weaken the normal public per-tab isolation path.
- No API key, `.env`, deployment configuration, or submission artifact will
  be read or changed.

## Verification

1. Run the focused regression tests for orchestrator/perseveration privacy,
   caregiver-panel privacy, retention wording, and session paths.
2. Run `PYTHONUTF8=1 python -m unittest discover tests -v` (PowerShell
   equivalent environment assignment) and fix failures in code, not tests.
3. Run `tests/test_mature_benchmarks.py` explicitly as required by the
   repository workflow.
4. Run the offline demo smoke path if dependencies permit, then inspect the
   final diff for scope, secrets, and documentation consistency.
5. Commit the single logical release-candidate change with the repository's
   required issue trailer/attribution format; do not push or create deployment
   artifacts.
