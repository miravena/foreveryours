# Memory Lifecycle Plan (Emotional & Uncertain)

## Objective
Implement Point 2 of the product critique: Expanding memory from a simple `[Permanent]` / `[Temporary]` binary into a robust lifecycle that handles fleeting emotions (`[EMOTIONAL]`) and speculative facts (`[UNCERTAIN]`).

## Changes Required

### 1. `memory/store.py` (Schema)
- Update `MemoryScope` Enum to include `EMOTIONAL` and `UNCERTAIN`.

### 2. `pipeline/think.py` (Extractor Prompt & Few-Shot)
- Add two new commands to `EXTRACTION_SYSTEM_PROMPT`:
  - `6. To record a fleeting emotion or mood (e.g. feeling lonely, angry at someone): EMOTION: <fact>`
  - `7. To record something the senior says they are unsure about or speculating on: UNCERTAIN: <fact>`
- Add Few-Shot examples:
  - `[SCENARIO F]` (Emotion): "I'm so angry with Sarah today." -> `EMOTION: Angry with Sarah today`
  - `[SCENARIO G]` (Uncertainty): "I think my grandson might be moving to Penang next year, but I'm not sure." -> `UNCERTAIN: Grandson might be moving to Penang next year`

### 3. `pipeline/orchestrator.py` (Routing & TTL)
- Intercept `EMOTION:` -> Call `memory_store.add(...)` with `scope="emotional"` and `expires_at = time.time() + (24 * 3600)`.
- Intercept `UNCERTAIN:` -> Call `memory_store.add(...)` with `scope="uncertain"`.
- When gathering `profile_facts` from the `MemoryStore` to feed into the conversational LLM (in `run_turn`), format uncertain items:
  ```python
  fact_strings = []
  for f in profile_facts:
      if f.scope == "uncertain":
          fact_strings.append(f"[UNVERIFIED/UNCERTAIN]: {f.text}")
      elif f.scope == "emotional":
          fact_strings.append(f"[EMOTIONAL STATE]: {f.text}")
      else:
          fact_strings.append(f.text)
  ```

### 4. Verification (`tests/test_mature_benchmarks.py`)
- **Benchmark 14**: Test `EMOTION:` extraction, verify 24h expiration.
- **Benchmark 15**: Test `UNCERTAIN:` extraction, verify prompt prefix formatting.

### 5. Review
- Write `docs/specs/memory-lifecycle/review.md` evaluating the robustness of the lifecycles.
