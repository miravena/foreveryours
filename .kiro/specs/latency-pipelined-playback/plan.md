# plan.md -- Issue #17: pipelined playback (time-to-first-SOUND, not time-to-first-WAV)

> Written per `.agents/skills/plan-feature`. No source code is changed in this
> phase. Implementation follows `.agents/skills/implement-feature` only after
> this plan is approved. Scope and constraints honor `.agents/rules/coding-standards.md`
> and `.agents/rules/testing.md`.

## Intent

Issue #17: `time_to_first_audio_s` currently measures **time to the first WAV
file being written**, not time to the first **sound a judge actually hears**.
`main.py` and `webapp.py` synthesize every reply sentence first, then play
them back sequentially, so a judge's perceived latency is the whole turn, not
the reported number. Chosen direction (confirmed with maintainer): implement the
**real fix** -- pipeline playback with synthesis so sentence 1 starts playing
while sentence 2 is still being synthesized -- and make the reported metric
reflect time-to-first-sound.

## Current behavior (as read from source)

- `pipeline/speak.py` -> `speak_sentences(sentences, out_dir)`: for each
  sentence, synthesizes a WAV to disk (`_synthesize_file`), then `yield
  sentence, out_path`. Synthesis is blocking and per-sentence; no playback here.
- `pipeline/orchestrator.py` -> `_speak_turn`: iterates `speak_sentences`,
  records `first_audio_time` when the FIRST yielded WAV is ready. This is the
  time-to-first-WAV-written value that becomes `TurnResult.time_to_first_audio_s`.
  No audio is played in the orchestrator.
- `main.py`: after `run_turn` returns (all sentences already synthesized),
  loops over `result.audio_paths` calling `_play()` sequentially
  (winsound on Windows, aplay/afplay on *nix) -- blocking playback, one file at a time.
- `webapp.py`: `_combine_audio_chunks` concatenates all chunk WAVs into one
  file AFTER synthesis, handed to Gradio `gr.Audio(autoplay=True)`.

So the real perceived latency on the CLI = synthesize-all-sentences +
start-playing-first. The reported number only covers synthesize-first-sentence.

## Design of the fix

Core idea: overlap playback with synthesis. While sentence N plays, synthesize
sentence N+1. `time_to_first_audio_s` should become time-to-first-sound-started.

### Where the change lives

The cleanest, lowest-coupling option that respects "keep functions focused" and
"don't modify unrelated files":

1. **New opt-in playback helper in `pipeline/speak.py`** (synthesis already lives
   here; playback-of-a-wav is the natural sibling). Add a function that, given the
   `speak_sentences` generator, runs a **producer/consumer** with a single
   background synth thread (or just drives the existing lazy generator) and plays
   each WAV as soon as it is ready, returning the wall-clock moment the first
   `_play` call STARTED.
   - Playback backend: factor `main.py._play` into a reusable
     `speak.play_wav(path)` (moves existing logic; `main.py` calls the new
     function so behavior is unchanged -- no duplication, per coding-standards).
   - A `--no-play` / `play: bool` switch must still be honored.

2. **Orchestrator**: keep `run_turn` returning synthesized `audio_paths` as
   today (webapp relies on them). Add an **optional** `play: bool = False`
   parameter OR, preferred to avoid changing orchestrator responsibilities, keep
   playback OUT of the orchestrator and let `main.py` call the new pipelined
   `speak` helper. Decision: keep orchestrator playback-free (matches current
   architecture where orchestrator never plays); do pipelining in the
   `speak`-layer helper that `main.py` invokes.

3. **Metric semantics**: introduce `time_to_first_sound_s` as the
   playback-start timestamp, measured by the pipelined player. Keep the existing
   `time_to_first_audio_s` (first-WAV-written) but relabel it in output so the
   claim is honest. `main.py`/`chat_loop` print both: "time to first WAV" and
   "time to first sound". This directly resolves the issue's "claim overstates
   what a judge experiences" without deleting the old measurement.

### CLI integration (`main.py`)

- Replace the post-hoc `for audio_path in result.audio_paths: _play(...)` loop
  with a call to the new pipelined player when `play` is True AND we have a live
  sentence stream. Because `run_turn` currently fully synthesizes before
  returning, achieving TRUE overlap requires the player to drive synthesis. Two
  implementation shapes (pick in implement phase, note tradeoff here):
  - (A) Minimal: keep `run_turn` as-is (synthesizes all), then play sequentially
    but start the clock at first `_play` -- this fixes the METRIC but not real
    overlap. Rejected: issue explicitly wants real pipelining.
  - (B) Real overlap: have `run_turn` expose the sentence generator (or a
    callback) so playback can begin on sentence 1 while synthesis of sentence 2
    continues. This needs `_speak_turn` to optionally accept a per-chunk
    callback invoked as each WAV is produced, which plays it immediately.
    **Chosen: (B)** via an optional `on_chunk` callback on `_speak_turn` /
    `run_turn` (default None = today's behavior, so webapp is untouched).

### webapp.py

Out of scope for the real-overlap change: the browser plays a single combined
WAV via Gradio autoplay and cannot easily stream sentence-by-sentence without new
pipeline/streaming machinery (the issue itself lists browser streaming as a
separate, larger fallback). Leave `webapp.py` behavior unchanged. Note this
explicitly in the PR so reviewers know the CLI got pipelined playback and the
browser path is tracked separately.

## Affected files

- `pipeline/speak.py` -- add `play_wav(path)` (moved from main) and a
  `play_sentences_pipelined(...)` helper; return first-sound timestamp.
- `pipeline/orchestrator.py` -- add optional `on_chunk` callback to
  `_speak_turn` and thread it through `run_turn`; add
  `time_to_first_sound_s` to `TurnResult` (default None).
- `main.py` -- use the pipelined player; print both WAV-written and
  sound-started timings; keep `--no-play`.
- `README.md` / `docs/ROADMAP.md` -- correct the "<2s to first audio" wording
  to say what is measured (first sound vs first WAV), per the issue.
- Tests: `tests/test_speak.py` and/or `tests/test_orchestrator.py`.

Explicitly NOT changed: `webapp.py`, `safety/`, `memory/`, `caregiver.py`.

## Dependencies

- No new third-party dependencies (coding-standards: "do not introduce
  unnecessary dependencies"). Use stdlib `threading`/`queue` and the existing
  subprocess playback backends.

## Risks

- **Audio device contention / headless CI**: playback must stay fully optional and
  no-op cleanly when no player exists (already handled by `_play`'s FileNotFound
  guards; preserve that). Tests must NOT depend on real audio hardware -- mock the
  player.
- **Thread safety**: a single synth thread + main-thread playback avoids ordering
  bugs; sentences must play in order. Keep it a bounded `queue.Queue` so
  synthesis can run at most one sentence ahead.
- **Windows `winsound` is blocking and main-thread**; keep playback on the main
  thread and synthesis on the worker to get overlap.
- **Metric regression**: existing tests asserting `time_to_first_audio_s`
  semantics must keep passing; add new assertions for `time_to_first_sound_s`
  rather than redefining the old field.

## Tests (per .agents/rules/testing.md)

- Pipelined player plays chunks in order and starts the first chunk before the
  last chunk is synthesized (simulate slow synth via a mock that sleeps; assert
  first play-start happens before final synth completes).
- `play_wav` no-ops gracefully when the backend is missing (mock
  `shutil.which` / FileNotFound).
- `on_chunk` callback fires once per sentence, in order; default None preserves
  current behavior (regression).
- `time_to_first_sound_s` is populated and <= full-turn time; old
  `time_to_first_audio_s` still present.
- Full suite stays green: `python -m unittest discover tests` (on Windows run
  with `PYTHONUTF8=1`). No audio hardware required.

## Out of scope

- Browser (webapp) sentence-level streaming -- larger, tracked separately.
- Any change to synthesis quality, TTS backend, or safety/memory logic.

## Open decision for implement phase

Confirm callback shape (`on_chunk(sentence, path)`) vs returning a generator
from `run_turn`. Plan picks the callback to avoid changing `run_turn`'s return
contract that `webapp.py` depends on.