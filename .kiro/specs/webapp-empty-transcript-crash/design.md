# webapp-empty-transcript-crash Bugfix Design

## Overview

`webapp.py` is the judge-facing Gradio demo. Each senior-side turn is handled by the
inner function `_run_demo_turn`, whose return value is unpacked by the outer wrapper
`run_demo_turn` and then fanned out by Gradio into exactly 7 declared outputs on the
`.click()` / `.submit()` handlers.

Every return path in `_run_demo_turn` yields a 5-tuple
`(transcript_and_reply, reply_audio, new_history, caregiver_panel, biomarkers_str)`
**except one**: the empty/unintelligible-transcript guard

```python
if not transcript.strip():
    return "Couldn't make out any speech or text -- try again.", None, history, panel()
```

which returns a **4-tuple** — it omits the trailing biomarkers panel string. The outer
wrapper then does `(*out, session_id_val, "")`, so a 4-tuple becomes a 6-element result
instead of the expected 7, and Gradio raises an output-count mismatch error. The demo
breaks on a trivially reachable edge case: a judge hitting Send with no speech / blank
text, or submitting audio that transcribes to whitespace.

The fix is minimal and surgical: make the empty-transcript guard return a shape-consistent
5-tuple with an appropriate biomarkers string (reusing the existing
`"### 📊 Acoustic Biomarkers\n_No audio detected_"` convention). No pipeline logic,
layout, or wiring changes — just one return statement gains its missing 5th element.

## Glossary

- **Bug_Condition (C)**: The input condition that triggers the bug — a turn whose resolved
  transcript is empty or whitespace-only after `text_in`/`audio_in` processing, so execution
  reaches the `if not transcript.strip():` guard in `_run_demo_turn`.
- **Property (P)**: The desired behavior for buggy inputs — `_run_demo_turn` returns a
  5-tuple whose first element is the friendly "try again" message and whose 5th element is a
  valid biomarkers panel string, so `run_demo_turn` yields a 7-element result and Gradio
  renders the message without error.
- **Preservation**: The return shape and content of every other `_run_demo_turn` path
  (normal turn, no-input, rate-limited, API-key-paused) must remain exactly as before.
- **`_run_demo_turn`**: The inner turn handler in `webapp.py` that resolves the transcript,
  runs the pipeline, and returns a 5-tuple of UI values.
- **`run_demo_turn`**: The outer wrapper in `webapp.py` that normalizes positional args,
  calls `_run_demo_turn`, and appends `session_id_val` and `""` to form the 7-tuple Gradio expects.
- **biomarkers_str**: The 5th tuple element — a Markdown string under the
  "### 📊 Acoustic Biomarkers" heading describing the acoustic metrics (or why none exist).

## Bug Details

### Bug Condition

The bug manifests when a turn is accepted far enough to compute a transcript, but that
transcript resolves to empty or whitespace-only. Execution reaches the
`if not transcript.strip():` guard, which returns a 4-tuple missing the biomarkers string.
The outer wrapper and Gradio output wiring then see the wrong number of values. The guard
is reachable from two sources: `text_in` that is non-empty but whitespace-only in a way the
earlier `if text_in and text_in.strip()` branch didn't claim, or — the common case — an
`audio_in` clip that `hear.transcribe` returns as empty/whitespace.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type DemoTurnInput   // (audio_in, text_in, history, session_id)
  OUTPUT: boolean

  transcript ← resolveTranscript(input)   // text_in.strip() if set, else hear.transcribe(audio_in)
  RETURN transcript IS NOT NULL
         AND trim(transcript) = ""
         // i.e. control reaches the `if not transcript.strip():` guard
END FUNCTION
```

### Examples

- A judge presses **Send** with no mic recording and empty text, uploads a silent/empty
  WAV → `hear.transcribe` returns `""` → guard returns 4-tuple → **Gradio output-count
  mismatch error** (expected: friendly "try again" message).
- A judge uploads an unintelligible clip that transcribes to whitespace `"   "` → guard
  returns 4-tuple → **crash** (expected: "try again" message).
- A judge submits text that is only whitespace reaching the guard → 4-tuple → **crash**
  (expected: "try again" message).
- Edge case — a judge presses Send with neither audio nor text at all → the *earlier*
  no-input branch (line 317) returns a correct 5-tuple → **no bug** (this path is already correct).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- A normal conversational turn with a valid transcript must still return its existing
  5-tuple (transcript+reply, reply audio, updated history, caregiver panel, biomarkers string).
- The no-input path ("Record audio or type what Dad says first.") must still return its
  existing 5-tuple with the "_No audio detected_" biomarkers string.
- The rate-limited path must still return its existing 5-tuple with the "_Rate limited_"
  biomarkers string.
- The distress/fall offline fast-path must still produce the caregiver flag, disclosure
  banner, and reply audio exactly as before.
- Gradio output wiring (7 outputs) and the outer `run_demo_turn` signature must remain unchanged.

**Scope:**
All inputs that do NOT reach the empty-transcript guard (i.e. where the resolved transcript
is non-empty, or where an earlier guard already returned) must be completely unaffected by
this fix. This includes:
- Valid conversational transcripts (text or audio)
- The no-input case (neither audio nor text)
- Rate-limited requests
- Requests that raise the NEBIUS_API_KEY-pending exception

## Hypothesized Root Cause

Investigation of every return statement in `_run_demo_turn` confirms the root cause precisely:

1. **Single inconsistent return path (confirmed)**: The `if not transcript.strip():` guard
   at line 320 returns a 4-tuple `(message, None, history, panel())`, omitting the 5th
   biomarkers element that every sibling path includes. This is the sole defect.

2. **No second defective path (verified, not just assumed)**: The requirements phase noted a
   *possible* second wrong-arity path. Enumerating all returns in `_run_demo_turn`:
   - rate-limit path (line 303) → 5-tuple ✓
   - no-input path (line 317) → 5-tuple ✓
   - empty-transcript guard (line 320) → **4-tuple ✗ (the bug)**
   - NEBIUS_API_KEY exception path (line 330) → 5-tuple ✓
   - normal success path (line 366) → 5-tuple ✓

   Only one path is wrong. The fix touches exactly that one return statement.

3. **Why it propagates to a crash**: `run_demo_turn` blindly spreads `(*out, ...)`, trusting
   `_run_demo_turn` to always return 5 elements. Python does not enforce the declared return
   arity, so the shape error surfaces only downstream at Gradio's output binding (7 declared
   outputs vs 6 produced), far from the real cause.

## Correctness Properties

Property 1: Bug Condition - Empty/unintelligible transcript returns a consistent 5-tuple

_For any_ input where the bug condition holds (isBugCondition returns true — the resolved
transcript is empty or whitespace-only), the fixed `_run_demo_turn` SHALL return a 5-tuple
whose first element contains the "try again" message and whose 5th element is a valid
biomarkers panel string, such that the outer `run_demo_turn` yields exactly 7 elements and
Gradio renders the message without an output-count mismatch error.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - All non-buggy input paths unchanged

_For any_ input where the bug condition does NOT hold (isBugCondition returns false), the
fixed `_run_demo_turn` SHALL produce exactly the same result as the original function,
preserving the return shape and content of the normal-turn, no-input, rate-limited, and
API-key-paused paths.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct (and it is, per the full enumeration above):

**File**: `webapp.py`

**Function**: `_run_demo_turn`

**Specific Changes**:

1. **Add the missing 5th element to the empty-transcript guard**: Change the single return
   statement so it returns a 5-tuple consistent with the sibling no-audio path.

   Before:
   ```python
   if not transcript.strip():
       return "Couldn't make out any speech or text -- try again.", None, history, panel()
   ```

   After:
   ```python
   if not transcript.strip():
       return (
           "Couldn't make out any speech or text -- try again.",
           None,
           history,
           panel(),
           "### 📊 Acoustic Biomarkers\n_No audio detected_",
       )
   ```

2. **Biomarkers string choice**: Reuse the existing `"### 📊 Acoustic Biomarkers\n_No audio
   detected_"` string already used by the no-input path. An empty/unintelligible transcript
   yielded no usable acoustic signal, so "_No audio detected_" is the honest, consistent label.

3. **No other code changes**: `run_demo_turn`, the Gradio wiring (7 outputs), the function
   signatures, and all other return paths remain untouched. The fix is one return statement.

4. **Keep the demo runnable**: Per AGENTS.md, `python webapp.py` must still launch cleanly;
   the change is isolated to one return and does not alter imports, globals, or layout.

## Testing Strategy

### Validation Approach

The strategy is two-phase: first surface a counterexample that demonstrates the arity bug on
the unfixed guard, then verify the fix returns a consistent 5-tuple (and 7-element end-to-end
result) while leaving every other path's shape and content unchanged. Tests use the project's
standard-library `unittest` and live in `tests/test_webapp.py`, following the existing patterns
there (`init_session`, `patch.object(webapp.hear, "transcribe", ...)`, `NEBIUS_API_KEY=""`).

### Exploratory Bug Condition Checking

**Goal**: Surface a counterexample demonstrating the wrong arity BEFORE the fix, confirming the
root cause (one guard returns a 4-tuple).

**Test Plan**: Call `_run_demo_turn` with a session and inputs that resolve to an empty/whitespace
transcript (mock `hear.transcribe` to return `("", {...})`, or pass whitespace text), then assert
on the length of the returned tuple. Run against the UNFIXED code to observe `len == 4` (and the
end-to-end `run_demo_turn` yielding `len == 6`).

**Test Cases**:
1. **Empty audio transcript**: Mock `transcribe` → `("", metrics)`, call `_run_demo_turn`; expect
   `len(result) == 4` on unfixed code (will fail the length-5 assertion that the fix makes pass).
2. **Whitespace audio transcript**: Mock `transcribe` → `("   ", metrics)`; same expectation.
3. **End-to-end mismatch**: Call `run_demo_turn` with the same empty-transcript mock; expect
   `len == 6` on unfixed code instead of 7 (reproduces the Gradio output-count mismatch).

**Expected Counterexamples**:
- `_run_demo_turn(...)` returns a 4-tuple for empty transcript input.
- `run_demo_turn(...)` returns a 6-tuple end-to-end, which Gradio cannot bind to 7 outputs.
- Confirmed cause: the `if not transcript.strip():` guard omits the biomarkers string.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function returns a
5-tuple with the "try again" message and a biomarkers string, and the end-to-end result is 7 elements.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := _run_demo_turn_fixed(input)
  ASSERT length(result) = 5
  ASSERT result[0] CONTAINS "try again"
  ASSERT isBiomarkerPanelString(result[4])   // starts with "### 📊 Acoustic Biomarkers"
  outer := run_demo_turn_fixed(input)
  ASSERT length(outer) = 7
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function
produces the same result (shape and content) as the original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT _run_demo_turn_original(input) = _run_demo_turn_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is a good fit for preservation because it exercises
many points across the input domain and catches edge cases manual tests miss. However, this
codebase uses standard-library `unittest` only (no Hypothesis dependency), so preservation is
covered by representative example tests over each distinct non-buggy path, mirroring the existing
`tests/test_webapp.py` style. Each test observes behavior and asserts the 5-tuple shape plus the
path-specific content is unchanged.

**Test Plan**: Observe each non-buggy path on the current code, then assert its return shape
(length 5) and its characteristic content remain correct after the fix.

**Test Cases**:
1. **Valid transcript preservation**: A normal turn (e.g. the distress phrase via the offline
   fast-path) returns a 5-tuple with transcript+reply, reply audio, and a biomarkers string —
   unchanged.
2. **No-input preservation**: Neither audio nor text → 5-tuple with "Record audio or type what
   Dad says first." and "_No audio detected_" — unchanged.
3. **Rate-limited preservation**: With the daily cap exceeded → 5-tuple with the rate-limit
   message and "_Rate limited_" — unchanged.
4. **Distress fast-path preservation**: The fall phrase still produces the caregiver flag,
   disclosure banner, and reply audio (already asserted by existing tests, which must stay green).

### Unit Tests

- Empty-transcript guard returns a 5-tuple whose 5th element is the "_No audio detected_"
  biomarkers string and whose message contains "try again".
- No-input path still returns its 5-tuple with the correct message and biomarkers string.
- Rate-limited path still returns its 5-tuple with the "_Rate limited_" biomarkers string.

### Property-Based Tests

- Not adopted as a new dependency for this fix (project uses `unittest` only). The preservation
  guarantee is instead approximated by one representative example test per non-buggy path, as
  above. If Hypothesis were introduced later, the natural property is: for any transcript the
  resolver yields, `len(_run_demo_turn(...)) == 5` and `len(run_demo_turn(...)) == 7`.

### Integration Tests

- End-to-end `run_demo_turn` with an empty-transcript mock returns exactly 7 elements and the
  trailing `("", session_id)` normalization is intact — reproducing the real Gradio binding and
  confirming no output-count mismatch.
- Existing end-to-end tests (`test_senior_text_input_turn_without_mic`,
  `test_high_priority_alert_banner_renders_on_distress`, `test_dual_input_prioritizes_text`)
  continue to pass, confirming the 7-output contract and distress fast-path are preserved.
