# ADR-011: Public-domain Piper voice, kept warm in its own process; GPL engines stay separate programs

**Status:** Accepted
**Date:** 2026-10-23
**Decided by:** Founder (which voice, and shipping it now); measurements by the assistant
**Affects:** `pipeline/speak.py`, `scripts/get_piper_voice.sh`, `scripts/deploy_hf_space.py`,
`.github/workflows/deploy-space.yml`, `requirements.txt`, README licence notice
**Related issue:** [#207](../../issues/207); amends [ADR-008](ADR-008-neural-tts.md)

## Question

ADR-008 adopted Piper with the `en_US-lessac-medium` voice. Three facts surfaced on 2026-10-23:
that voice's dataset licence, the cost of one `piper` process per sentence, and that the hosted
Space never had the voice at all (judges hear espeak-ng). Which voice do we ship, how do we run it
so speech is not choppy, and what does GPL ask of an MIT repo?

## Context

- **Lessac voice.** Its model card points at the Blizzard 2013 licence (University of Edinburgh,
  CSTR): a "Research Purposes only" licence granted to a named registrant, non-transferable, no
  sub-licence, and it expressly excludes "the development, marketing, commercialisation, sale or
  licencing of voice synthesis ... products or services". Nobody on this project registered.
- **CLI cost, measured** (4-core ARM, Piper 1.8.0, medium voice): one `piper` call takes 2.0 s for
  a 1.4 s sentence; three sentences through one process take 2.9 s. So about 1.6 s is fixed
  start-up (Python, onnxruntime, model load) and about 0.4 s is synthesis. Pipelined playback would
  stall before every sentence, which is the choppiness #194 set out to remove.
- **Licences.** espeak-ng is GPL-3.0; piper-tts 1.8 is GPL-3.0-or-later and bundles espeak-ng.
  This repo is MIT. Both engines are started as separate programs that receive a sentence and
  return a WAV; no engine code is imported into this process.
- **ADR-008** rejected Piper's Python API in-process to keep the #28 isolation (a long-lived
  in-process engine that leaked and fell silent).

## Options considered

| Option | Pros | Cons | Tried? |
|--------|------|------|--------|
| Keep `en_US-lessac-medium` | Known voice | Licence excludes our use; cannot ship | No |
| **`en_US-ljspeech-medium`** (LJ Speech, public domain) | Clean licence, largest single-speaker dataset, same size and speed | A different voice | Yes |
| Other permissive voices: `kristin`, `bryce` (public domain), `joe` (CC0), `libritts_r` (CC BY 4.0) | Clean | Not auditioned; any can be set via `TTS_PIPER_MODEL` | No |
| `ryan`, `hfc_female`, `hfc_male` (CC BY-NC-SA 4.0) | Good quality | Non-commercial share-alike terms; avoid | No |
| Per-sentence `piper` CLI only (ADR-008 shape) | Simplest | About 1.6 s of silence before every sentence | Yes, measured |
| Piper Python API in our process | Fastest | GPL code imported into the MIT process; ADR-008's long-lived-engine risk | No |
| **Warm `python -m piper.http_server` on loopback, a separate process** | Model loaded once; still a separate program; each request bounded; falls through to the CLI, then espeak-ng | One more process; flask (BSD) as an optional dependency | Yes |

## Decision

1. **The default voice is `en_US-ljspeech-medium`.** The Lessac voice is never staged to the
   Space: `scripts/deploy_hf_space.py` copies only the default pair, or nothing.
2. **Piper runs as one warm loopback server per app process**, started at boot
   (`speak.warm_up()` from `webapp.py` and `main.py`) or on first use. Each sentence is one HTTP
   request bounded by `TTS_TIMEOUT_S`. Any failure falls through to the `piper` CLI and then
   espeak-ng, exactly as before; a server that fails is retried after a 60 s back-off, not per
   sentence. `TTS_PIPER_SERVER=0` turns the server off.
3. **The Space ships the voice.** The deploy workflow runs `scripts/get_piper_voice.sh` before
   staging, so the Space's build contains the voice and the demo still never downloads at runtime
   (ADR-008's offline guarantee).
4. **GPL stance.** espeak-ng and Piper are used as separate programs; nothing from them is
   imported (`_piper_server_importable` locates the module on disk without importing it).
   `README.md` names both, their licences and their source, which also covers a Space image
   someone downloads from Hugging Face. This is the maintainers' reading, not legal advice; have it
   checked before any commercial use.

## Consequences

- **Unlocked:** the natural voice on the hosted demo; after the first sentence of a process,
  synthesis is well under a second per sentence, so playback stays ahead.
- **Locked in to:** `flask` as an optional dependency, one extra process per app, and a 64 MB
  voice upload on every deploy.
- **Gotchas:** the `piper` CLI fallback needs the venv's `bin` on `PATH`; a changed
  `TTS_PIPER_MODEL` restarts the server; while a server is in back-off, sentences come from the
  CLI (same voice, slower).

## When to revisit

- Time-to-first-sound measured on the Space misses the ADR-003 budget.
- A small, permissively licensed voice that clearly sounds better appears (Pocket TTS by Kyutai
  was noted as a candidate; its chain avoids espeak-ng).
- The project goes commercial: get the licence position checked.
