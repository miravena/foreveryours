# Final Timezone Fix Plan

## Objective
Address the final two loopholes:
1. Missing Orchestrator Injection: `webapp.py` and `main.py` instantiate `MemoryStore` without a `timezone_str`, defaulting to UTC.
2. Invalid Timezone Strings: `MemoryStore` silently swallows bad timezones during emotional decay.

## Changes Required

### 1. `memory/store.py` (Validation)
- In `__init__`, actively validate `timezone_str` using `zoneinfo.ZoneInfo(timezone_str)`.
- If it's invalid (raises `zoneinfo.ZoneInfoNotFoundError`), log a prominent warning using the `logging` module and explicitly fallback to `"UTC"`. This prevents silent obscurement of bad configuration while keeping the app alive.

### 2. `webapp.py` & `main.py` (Injection)
- Read `SENIOR_TIMEZONE` from `os.environ.get("SENIOR_TIMEZONE", "Asia/Kuala_Lumpur")` globally.
- Inject it into all `MemoryStore(..., timezone_str=SENIOR_TIMEZONE)` instantiations.

### 3. Verification
- Run local unit tests (existing benchmarks) to ensure validation doesn't crash on mocked environments.

### 4. Review
- Write `docs/specs/timezone-final/review.md` evaluating the final patch.
