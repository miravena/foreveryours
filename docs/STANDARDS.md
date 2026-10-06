# Standards

What this codebase already does, written down so both of us — and anyone we hand it to — write it
the same way. Every rule below is copied from code that already follows it; nothing here is
aspirational. **If a rule isn't true of the code, fix the code or this file in the same commit.**

## Naming

- **Modules are `snake_case.py`, one concern each**, named for the pipeline stage they implement:
  `hear`, `think`, `speak`, `audit`, `orchestrator`. `safety/`, `memory/` and `video/` are
  packages for the same reason.
- **Functions are verbs** — `transcribe`, `run_turn`, `build_prompt`, `check`, `supersede`. A
  leading `_` means private to its module and part of no contract (`_normalize`,
  `_sanitize_caregiver_update`).
- **Classes are `PascalCase`.** Anything passed around as data is a `@dataclass`
  (`FastPathResult`, `TurnResult`, `MemoryItem`); an enumerated choice is
  `class X(str, Enum)` (`Intent`, `MemoryScope`, `PrivacyLevel`) so it compares, prints and
  JSON-encodes as the string it stands for.
- **Configuration is `SCREAMING_SNAKE`** (`ASR_BACKEND`, `THINK_MODEL`), read at the point of use
  with a default. Every key is declared in `.env.example`, which must match reality — it has
  drifted once already.
- **Tests** live in `tests/test_<module>.py`, named for the behaviour rather than the method:
  `test_distress_triggers`, not `test_check_line_73`.

## Errors

- **Raise when the caller can't proceed; return when it's just an outcome.** A missing key or
  dependency raises with the fix inside the message — `NebiusNotConfigured` says to set
  `NEBIUS_API_KEY`, the TTS failure says "install espeak-ng or pyttsx3". Use `raise … from exc`
  when wrapping an `ImportError`.
- **Expected results are return values, not exceptions:** `audit_reply -> tuple[bool, str]`,
  `check -> FastPathResult`, `extract_new_memory -> str | None`.
- **Fail loud, never fake.** `beat2` with no key must fail loudly rather than return canned text
  (`AGENTS.md`). There are no bare `except:` clauses anywhere; `except Exception` appears only at
  boundaries that must keep a demo alive (one turn, memory extraction), and those degrade to a
  *visible* fallback (`TurnResult.is_fallback`, `consecutive_errors`) instead of silence.

## API shapes

- **One direction of import.** `pipeline/`, `memory/` and `safety/` never import `webapp.py` or
  `main.py`; those two call into the pipeline. Safety and memory are libraries the pipeline uses,
  never the reverse.
- **A few values come back as a tuple; anything richer is a `@dataclass`.** `_speak_turn` returns
  `tuple[str, list[Path], float | None]`; `run_turn` returns `TurnResult`, which has twelve
  fields. Past three fields, use a dataclass — a positional tuple is unreadable at the call site.
- **Fields that can't be filled in yet are `| None` and say so in the field comment**
  (`audit_verdict` "may arrive after return"; `background_thread` tells you to `join()` before
  reading it). The comment is the contract, not only the docstring.
- **`on_chunk` is the pattern for "act while it streams":** an optional callback fired the moment
  something is ready, defaulting to `None`, so callers that don't care behave exactly as before.

## UI — one page, two audiences

- The demo has two sides and they must stay two sides: **Senior** (left: talk or type) and
  **Caregiver** (right: live panel). Copy speaks to the person on that side.
- **Anything `CAREGIVER_ONLY` is never rendered on the senior's side.** It carries the
  `🔒 [Caregiver Only — Hidden from Dad]` badge for the caregiver and does not exist for the
  senior. This is Benchmark 4 — a leak here is a bug, not a wording change.
- **The fast-path's first reply *is* the disclosure**: it reaches the senior before anything else
  happens, so it must be warm and plain — no model names, no "system", no alarm.
- **Every tab is its own demo household.** No state may cross `FY_SESSIONS_DIR` sessions; one
  judge must never see another judge's conversation.

## Tests

- The suite runs offline with no key. Anything that needs Nebius **skips inside the test** when
  the call fails — never skip up front because a key looks absent.
- Asserting the happy path isn't coverage: the fast-path and memory suites assert *near misses*
  (what must **not** trigger) alongside the triggers.
- Windows: emoji assertions need `PYTHONUTF8=1` (see `AGENTS.md`).
