"""SPEAK: text-to-speech, streamed sentence-by-sentence.

Preference order per sentence (all fully offline, no API key, no network):
  0. Piper neural TTS (if the `piper` CLI AND its voice model are both present)
     -- a warm, natural offline neural voice (ADR-008, supersedes ADR-001's
     "accepted robotic-voice tradeoff" once a drop-in neural voice exists).
  1. Windows PowerShell System.Speech.
  2. espeak-ng / espeak CLI on Linux/macOS.
  3. pyttsx3 in-process engine (last resort).

Every tier is a clean subprocess (or the unchanged pyttsx3 last resort) per
sentence, so none re-introduces the long-lived-engine C-buffer silence bug
(#28). Piper is OPTIONAL and auto-detected: when the binary or the model file
is missing the code falls through to exactly the prior behavior, so `main`
stays demo-able with no extra install.

Every tier is bounded by ``TTS_TIMEOUT_S`` (env, default 10 s) per sentence:
a hung Piper falls through to the next tier; a hung espeak, PowerShell or
pyttsx3 raises ``subprocess.TimeoutExpired`` to the caller.

Needs the `espeak-ng` system package on Linux (`apt install espeak-ng`) when
Piper is not used -- pyttsx3.init() raises OSError without it.
"""
from __future__ import annotations

import contextlib
import io
import itertools
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

_turn_counter = itertools.count()
# Guards only the pyttsx3 last-resort tier (shared cached engine); the
# subprocess tiers need no lock. Held by the thread that actually runs
# the engine, not by the waiting caller: a call abandoned at TTS_TIMEOUT_S keeps
# it until the engine really returns, so no second call ever enters the engine
# while a hung one is still inside it.
_pyttsx3_lock = threading.Lock()
# Serializes the stdout redirect around a pyttsx3 call. Always released by
# the caller that took it, unlike _pyttsx3_lock (Codex finding).
_pyttsx3_stdout_lock = threading.Lock()

# Repo root (two levels up from this file: pipeline/speak.py -> repo root).
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Default offline neural voice: small, warm, eldercare-appropriate.
_DEFAULT_PIPER_MODEL = "models/piper/en_US-lessac-medium.onnx"

_DEFAULT_TTS_TIMEOUT_S = 10.0


def _parse_tts_timeout(raw: str | None) -> float:
    """``TTS_TIMEOUT_S`` as a finite, positive float; anything else (unset,
    malformed, zero, negative, inf, nan) falls back to 10 seconds."""
    try:
        value = float(raw) if raw is not None else _DEFAULT_TTS_TIMEOUT_S
    except (TypeError, ValueError):
        return _DEFAULT_TTS_TIMEOUT_S
    if not math.isfinite(value) or value <= 0:
        return _DEFAULT_TTS_TIMEOUT_S
    return value


# Upper bound, in seconds, on each synthesis tier for one sentence.
# A hung Piper/espeak/PowerShell child is killed by subprocess.run and
# raises TimeoutExpired; the in-process pyttsx3 tier is abandoned in a daemon
# thread. Process creation time is not covered (Python's subprocess docs).
TTS_TIMEOUT_S = _parse_tts_timeout(os.environ.get("TTS_TIMEOUT_S"))


def reload_tts_timeout() -> float:
    """Re-read ``TTS_TIMEOUT_S`` from the environment. A caller that loads
    ``.env`` after importing this module (main.py) calls this so the file's
    value takes effect."""
    global TTS_TIMEOUT_S
    TTS_TIMEOUT_S = _parse_tts_timeout(os.environ.get("TTS_TIMEOUT_S"))
    return TTS_TIMEOUT_S


def _run_bounded(fn, label: str, *, wait_s: float | None = None, on_done=None):
    """Run in-process ``fn()`` in a daemon thread, wait at most TTS_TIMEOUT_S
    (or ``wait_s`` when given).

    Returns fn's result; re-raises fn's own exception in the caller (a thread's
    exception would otherwise only reach threading.excepthook and be lost); if
    the thread is still running at the deadline, raises TimeoutExpired and
    abandons it -- it is a daemon, so it never blocks interpreter exit.

    ``on_done`` (if given) is called exactly once, by the worker thread when
    ``fn`` really finishes -- even after the caller has given up on it -- or by
    the caller if the thread never starts. It is how a lock the caller took is
    handed to the call that needs it."""
    outcome: dict = {}
    timeout = TTS_TIMEOUT_S if wait_s is None else wait_s

    def target():
        try:
            outcome["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            outcome["error"] = exc
        finally:
            if on_done is not None:
                on_done()

    worker = threading.Thread(target=target, name=f"tts-{label}", daemon=True)
    try:
        worker.start()
    except BaseException:
        if on_done is not None:
            on_done()
        raise
    worker.join(max(0.0, timeout))
    if worker.is_alive():
        raise subprocess.TimeoutExpired(cmd=label, timeout=TTS_TIMEOUT_S)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def _strip_smart_quotes(sentence: str) -> str:
    """Replace curly/smart quotes LLMs love to emit with plain spaces so they
    don't choke a downstream shell/synthesizer. Mirrors the Windows branch."""
    safe = sentence
    for ch in "\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f":
        safe = safe.replace(ch, " ")
    return safe


def _get_espeak_cli() -> str | None:
    """Finds native espeak-ng or espeak CLI binary if installed."""
    for cmd in ("espeak-ng", "espeak"):
        found = shutil.which(cmd)
        if found:
            return found
    return None


def _get_piper_cli() -> str | None:
    """Finds the offline Piper neural-TTS CLI binary if installed."""
    return shutil.which("piper")


def _get_piper_model() -> Path | None:
    """Resolve the Piper voice model path from env (``TTS_PIPER_MODEL``,
    default ``models/piper/en_US-lessac-medium.onnx``), relative to the repo
    root when not absolute. Return it only if BOTH the ``.onnx`` and its
    sibling ``.onnx.json`` config exist, else ``None`` (so a half-present
    model never half-starts Piper)."""
    raw = os.environ.get("TTS_PIPER_MODEL", _DEFAULT_PIPER_MODEL)
    model = Path(raw)
    if not model.is_absolute():
        model = _REPO_ROOT / model
    config = model.with_suffix(model.suffix + ".json")
    if model.is_file() and config.is_file():
        return model
    return None


def _piper_available() -> bool:
    """Gate honoring ``TTS_BACKEND``: ``espeak`` forces the legacy path off
    Piper (used to keep CI/tests deterministic); otherwise Piper is used only
    when both its CLI and a complete voice model resolve."""
    if os.environ.get("TTS_BACKEND", "auto").strip().lower() == "espeak":
        return False
    return _get_piper_cli() is not None and _get_piper_model() is not None


def _get_tts_engine():
    # If on Windows or native espeak CLI is available, bypass pyttsx3 entirely
    # to avoid C-buffer exhaustion and long-running process silence (Issue #28)
    if sys.platform == "win32" or _get_espeak_cli() is not None:
        return None
    try:
        import pyttsx3

        # pyttsx3.init() loads a native driver and can block; bound it too.
        return _run_bounded(pyttsx3.init, "pyttsx3.init")
    except Exception:
        return None


def _synthesize_file(sentence: str, out_path: Path, engine) -> None:
    # 0. PREFERRED: Piper offline neural voice (ADR-008). Tried first on every
    # platform, but ONLY when both the CLI and a complete voice model resolve;
    # one clean subprocess per sentence (reads text on stdin, writes a WAV to
    # -f), so it inherits the #28 isolation. On any failure, log one line and
    # fall through to the exact existing branches -- never hard-fail.
    if _piper_available():
        piper_cli = _get_piper_cli()
        model = _get_piper_model()
        try:
            subprocess.run(
                [piper_cli, "-m", str(model), "-f", str(out_path)],
                input=_strip_smart_quotes(sentence),
                text=True,
                check=True,
                capture_output=True,
                timeout=TTS_TIMEOUT_S,
            )
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:  # pragma: no cover - env specific
            # A hung Piper is killed by subprocess.run and falls through here
            # exactly like a failed one.
            print(f"  (piper synthesis failed, falling back: {type(exc).__name__})")
            # fall through to the legacy tiers below

    # 1. On Windows: PowerShell System.Speech (avoids pyttsx3 SAPI5 deadlock)
    if sys.platform == "win32":
        safe_sentence = _strip_smart_quotes(sentence).replace("'", "''").replace('"', ' ')
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = -1; "
            f"$s.SetOutputToWaveFile('{out_path.as_posix()}'); "
            f"$s.Speak('{safe_sentence}'); "
            f"$s.Dispose()"
        )
        # TimeoutExpired propagates: the caller bounds the turn.
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            check=True,
            capture_output=True,
            timeout=TTS_TIMEOUT_S,
        )
        return

    # 2. On Linux/macOS: Prefer espeak-ng / espeak CLI (spawns clean isolated process per sentence;
    # avoids the long-lived pyttsx3 C-buffer memory leak and 19-sentence silence bug #28)
    cli = _get_espeak_cli()
    if cli is not None:
        # -s 150: comfortable eldercare speech rate (default is 175 wpm)
        # -p 45: slightly lower pitch for warmer, less metallic timbre
        # -w: output to WAV file
        subprocess.run(
            [cli, "-s", "150", "-p", "45", "-w", str(out_path), sentence],
            check=True,
            capture_output=True,
            timeout=TTS_TIMEOUT_S,  # TimeoutExpired propagates to the caller
        )
        return

    # 3. Fallback to pyttsx3 in-process engine if CLI is not found
    if engine is not None:
        def _pyttsx3_synthesize():
            engine.save_to_file(sentence, str(out_path))
            engine.runAndWait()

        # pyttsx3.init() hands every caller the same cached engine, whose run
        # loop is not reentrant, so concurrent turns take turns here.
        # One deadline, TTS_TIMEOUT_S, covers waiting for the lock plus the
        # synthesis. The lock is handed to the engine thread, which
        # releases it only when the engine returns: after a timeout the
        # abandoned call still owns it, so the next caller times out here
        # instead of entering the engine concurrently with the hung one.
        deadline = time.monotonic() + TTS_TIMEOUT_S
        # redirect_stdout swaps the process-wide sys.stdout, so the whole
        # swap-run-restore section is serialized by _pyttsx3_stdout_lock, which
        # the caller always releases itself (the engine lock is released by the
        # engine thread and can outlive the caller, so it cannot do this job).
        if not _pyttsx3_stdout_lock.acquire(timeout=TTS_TIMEOUT_S):
            raise subprocess.TimeoutExpired(cmd="pyttsx3 (engine busy)", timeout=TTS_TIMEOUT_S)
        try:
            remaining = max(0.0, deadline - time.monotonic())
            if not _pyttsx3_lock.acquire(timeout=remaining):
                raise subprocess.TimeoutExpired(cmd="pyttsx3 (engine busy)", timeout=TTS_TIMEOUT_S)
            # The redirect wraps the bounded call, not the thread body, so
            # stdout is restored even when a hung engine is abandoned.
            try:
                redirect = contextlib.redirect_stdout(io.StringIO())
                redirect.__enter__()
            except BaseException:
                _pyttsx3_lock.release()
                raise
            try:
                _run_bounded(
                    _pyttsx3_synthesize,
                    "pyttsx3",
                    wait_s=deadline - time.monotonic(),
                    on_done=_pyttsx3_lock.release,
                )
            finally:
                redirect.__exit__(None, None, None)
        finally:
            _pyttsx3_stdout_lock.release()
        return

    raise RuntimeError("Speech synthesis unavailable: install espeak-ng or pyttsx3")


def speak_sentences(sentences: Iterator[str], out_dir: Path) -> Iterator[tuple[str, Path]]:
    """Consume the WHOLE sentence stream for one turn in a single call --
    each call gets its own turn id, so calling this once per sentence (as
    opposed to once per turn) would silently make every file collide on the
    same name. One call per turn is the contract."""
    out_dir.mkdir(parents=True, exist_ok=True)
    turn_id = f"{int(time.time())}-{next(_turn_counter)}"
    engine = _get_tts_engine()

    for i, sentence in enumerate(sentences):
        out_path = out_dir / f"reply_{turn_id}_{i:03d}.wav"
        _synthesize_file(sentence, out_path, engine)
        yield sentence, out_path


def play_wav(audio_path: "Path") -> bool:
    """Play a single WAV file through the OS audio backend, blocking until it
    finishes. Factored out of main.py so both the CLI and the pipelined player
    share one implementation (no duplication). No-ops with a printed note if the
    backend is missing, so headless boxes never crash a turn.

    Returns True only when playback actually completed (winsound returned with
    no exception, or the afplay/aplay subprocess exited 0). Returns False on a
    missing player, a non-zero exit, or a winsound exception -- the note is
    still printed either way. Callers (PipelinedPlayer) rely on this to avoid
    reporting a time-to-first-sound for sound that never played (#71)."""
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
        except Exception as exc:  # pragma: no cover - platform/audio specific
            print(f"  (windows playback failed for {audio_path.name}: {exc})")
            return False
        return True

    player = "afplay" if sys.platform == "darwin" else "aplay"
    try:
        subprocess.run([player, str(audio_path)], check=True, capture_output=True)
    except FileNotFoundError:
        print(f"  (no {player} found -- skipping playback of {audio_path.name})")
        return False
    except subprocess.CalledProcessError as exc:  # pragma: no cover - audio specific
        print(f"  (playback of {audio_path.name} failed: {exc})")
        return False
    return True


class PipelinedPlayer:
    """Plays reply audio on a background thread, overlapping with synthesis (issue #17).

    Used as the ``on_chunk`` callback passed to ``orchestrator.run_turn``: the
    synthesis loop calls ``feed(sentence, path)`` the instant each WAV is written,
    and this player drains a FIFO queue on its own thread -- so sentence 2 is being
    synthesized while sentence 1 is already playing. Playback order is preserved
    (single consumer thread, FIFO queue).

    ``time_to_first_sound_s`` is the wall-clock delay from construction to the
    first ``play_wav`` call that actually completed playback -- i.e. time to
    first SOUND HEARD, the number issue #17 says we should report instead of
    time-to-first-WAV-written. It stays ``None`` when no ``play_wav`` call ever
    returns ``True`` (no working audio player, every attempt failed, or
    nothing was fed), so a missing audio backend is never reported as a fast
    turn (#71). It measures from player construction to the start of the first
    successful playback, and excludes speech-to-text (ASR happens before the
    player is constructed).

    Usage:
        player = PipelinedPlayer(play=play)
        result = run_turn(..., on_chunk=player.feed)
        player.close()                      # wait for all queued audio to finish
        t = player.time_to_first_sound_s    # None if nothing played

    When ``play`` is False the player is inert: ``feed`` is a no-op, nothing is
    queued or played, and ``time_to_first_sound_s`` stays None.
    """

    def __init__(self, play: bool = True) -> None:
        import queue
        import threading

        self.play = play
        self.time_to_first_sound_s: float | None = None
        self._t0 = time.monotonic()
        self._q: "queue.Queue[Path | None]" = queue.Queue()
        self._thread: "threading.Thread | None" = None
        if play:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            path = self._q.get()
            if path is None:  # sentinel from close()
                return
            t = time.monotonic() - self._t0
            played = play_wav(path)
            if played and self.time_to_first_sound_s is None:
                self.time_to_first_sound_s = t

    def feed(self, sentence: str, audio_path: "Path") -> None:
        """on_chunk callback: queue a freshly synthesized WAV for playback."""
        if self.play:
            self._q.put(audio_path)

    def close(self) -> None:
        """Signal end-of-stream and block until all queued audio has played."""
        if self._thread is not None:
            self._q.put(None)
            self._thread.join()
