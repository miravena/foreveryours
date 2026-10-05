# Bugfix Requirements Document

## Introduction

In `webapp.py`, the inner turn handler `_run_demo_turn` returns a 5-tuple on every
path except one: when the transcript is empty or unintelligible, it returns a
4-tuple (missing the trailing biomarkers panel string). The caller `run_demo_turn`
unpacks that result with `(*out, session_id_val, "")` expecting 5 elements, and the
Gradio `.click()` / `.submit()` handlers are wired to exactly 7 outputs
`[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in]`.

So when a judge submits blank or unintelligible audio/text, the short path yields the
wrong number of outputs and Gradio raises an output-count mismatch error. This is a
demo-breaker on a predictable, easy-to-hit edge case. The fix makes the
empty/unintelligible path return a consistent 5-tuple so the outputs line up and the
user sees the friendly "try again" message instead of a crash.

## Bug Analysis

### Current Behavior (Defect)

When the senior-side input produces no usable transcript, the early-return path emits
too few values for the caller and the Gradio output wiring.

1.1 WHEN the transcript is empty or whitespace-only after `audio_in`/`text_in` is processed THEN `_run_demo_turn` returns a 4-tuple `("Couldn't make out any speech or text -- try again.", None, history, panel())` instead of a 5-tuple
1.2 WHEN `run_demo_turn` unpacks that 4-tuple via `(*out, session_id_val, "")` THEN the final result has 6 elements instead of the expected 7
1.3 WHEN the Gradio `.click()`/`.submit()` handler receives the 6-element result against its 7 declared outputs THEN the demo raises a runtime output-count mismatch error, breaking the turn

### Expected Behavior (Correct)

The empty/unintelligible path should be shape-consistent with every other return path.

2.1 WHEN the transcript is empty or whitespace-only after `audio_in`/`text_in` is processed THEN `_run_demo_turn` SHALL return a 5-tuple that includes an appropriate biomarkers panel string as its 5th element, consistent with the other no-audio / rate-limited paths (e.g. a string like "### 📊 Acoustic Biomarkers\n_No audio detected_")
2.2 WHEN `run_demo_turn` unpacks the 5-tuple via `(*out, session_id_val, "")` THEN the final result SHALL have exactly 7 elements
2.3 WHEN the Gradio `.click()`/`.submit()` handler receives the 7-element result against its 7 declared outputs THEN the demo SHALL display the friendly "Couldn't make out any speech or text -- try again." message without raising an error

### Unchanged Behavior (Regression Prevention)

Every other input path already returns the correct shape and must stay unchanged.

3.1 WHEN a valid transcript is provided (normal conversational turn) THEN `_run_demo_turn` SHALL CONTINUE TO return its existing 5-tuple with transcript+reply, reply audio, updated history, caregiver panel, and biomarkers string
3.2 WHEN neither audio nor text is provided THEN `_run_demo_turn` SHALL CONTINUE TO return its existing 5-tuple with the "Record audio or type what Dad says first." message and the "_No audio detected_" biomarkers string
3.3 WHEN the daily rate limit is exceeded THEN `_run_demo_turn` SHALL CONTINUE TO return its existing 5-tuple with the rate-limit message and the "_Rate limited_" biomarkers string
3.4 WHEN a distress/fall phrase triggers the offline safety fast-path THEN the system SHALL CONTINUE TO produce the caregiver flag, disclosure banner, and reply audio exactly as before

## Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type DemoTurnInput   // (audio_in, text_in, history, session_id)
  OUTPUT: boolean

  // The bug fires only when input was accepted far enough to compute a
  // transcript, but that transcript is empty or whitespace-only.
  transcript ← resolveTranscript(X)        // from text_in, else audio_in
  RETURN transcript IS NOT NULL AND trim(transcript) = ""
END FUNCTION
```

```pascal
// Property: Fix Checking - empty/unintelligible transcript returns a 5-tuple
FOR ALL X WHERE isBugCondition(X) DO
  result ← _run_demo_turn'(X)
  ASSERT length(result) = 5
  ASSERT result[0] CONTAINS "try again"
  ASSERT isBiomarkerPanelString(result[4])
  // and end-to-end:
  outer ← run_demo_turn'(X)
  ASSERT length(outer) = 7 AND no_output_count_error(outer)
END FOR
```

```pascal
// Property: Preservation Checking - all non-buggy inputs unchanged
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT _run_demo_turn(X) = _run_demo_turn'(X)
END FOR
```
