# Timezone Blindness Fix Plan

## Objective
Fix the timezone blindness loophole when decaying emotions. The Unix timestamp must be formatted in the senior's local timezone (e.g., UTC+8 for Penang) instead of blindly relying on the host server's timezone.

## Changes Required

### 1. `memory/store.py`
- Modify the `MemoryStore.__init__` signature to accept a `timezone_str: str = "UTC"`.
- Update `self.timezone_str = timezone_str`.
- Update `_decay_emotions()`:
  - Add `from zoneinfo import ZoneInfo`.
  - Format the datetime explicitly using the `timezone_str`:
    ```python
    dt = datetime.datetime.fromtimestamp(i.created_at, tz=datetime.timezone.utc)
    try:
        local_dt = dt.astimezone(ZoneInfo(self.timezone_str))
    except Exception:
        local_dt = dt # fallback
    date_str = local_dt.strftime('%b %d, %Y')
    ```

### 2. `pipeline/orchestrator.py` & callers
- We don't strictly need to modify callers if they rely on the default, but we can update test cases to pass a specific timezone to prove it works.

### 3. Verification (`tests/test_mature_benchmarks.py`)
- **Benchmark 20**: Test that providing `timezone_str="Asia/Kuala_Lumpur"` shifts an emotion created at UTC 22:00 (which is the previous day in UTC, but the next day in Malaysia) to the correct local date string when it decays.

### 4. Review
- Write `docs/specs/timezone-blindness/review.md` evaluating the success and identifying any remaining gaps.
