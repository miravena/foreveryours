"""CLI demo runner for the three-beat demo script (see docs/DEMO_SCRIPT.md).

Thin vertical slice: no dashboard UI yet -- that's tracked as an open
GitHub Issue, deliberately lower priority than the end-to-end pipeline. This
prints the live "memory panel" to the terminal so the pipeline's recall/save
behavior is visibly provable before any UI exists.

Usage:
    cp .env.example .env   # fill in NEBIUS_API_KEY
    python main.py beat1   # caregiver memo
    python main.py beat2 "Hi, how's it going today?"
    python main.py beat2 --audio senior_turn.wav   # real voice in, instead of typed text
    python main.py beat3 "I fell down earlier and I'm scared"
    python main.py beat4 "I forgot, what is my grandson's name?"
    python main.py day2   # run AFTER beat1, in a separate invocation -- proves persistence

Pass --no-play to skip audio playback (e.g. on a headless box with no speaker).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():  # noqa: E731
        pass

from caregiver import DEFAULT_CAREGIVER_NAME, DEFAULT_PROFILE_ID, CaregiverFlags
from memory.store import MemoryStore
from pipeline import hear
from pipeline.orchestrator import run_turn

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_DIR = Path(__file__).resolve().parent / "out" / "audio"


def _play(audio_path: Path) -> None:
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
        except Exception as exc:
            print(f"  (windows playback failed for {audio_path.name}: {exc})")
        return

    player = "afplay" if sys.platform == "darwin" else "aplay"
    try:
        subprocess.run([player, str(audio_path)], check=True, capture_output=True)
    except FileNotFoundError:
        print(f"  (no {player} found -- skipping playback of {audio_path.name})")
    except subprocess.CalledProcessError as exc:
        print(f"  (playback of {audio_path.name} failed: {exc})")


def _print_memory_panel(store: MemoryStore, flags: CaregiverFlags) -> None:
    print("\n--- LIVE MEMORY PANEL ---")
    for item in store.all():
        print(f"  [{item.source}] {item.text}")
    if flags.all():
        print("--- CAREGIVER FLAGS ---")
        for flag in flags.all():
            disclosed = "disclosed to senior" if flag.disclosed_to_senior else "NOT disclosed"
            print(f"  ({flag.severity}, {disclosed}) {flag.text}")
    print("-------------------------\n")


def beat1_caregiver_memo() -> None:
    """Caregiver submits onboarding context -- the 60-second voice memo,
    simplified to text input for the thin slice (ASR applies equally to a
    caregiver memo or a senior turn; wiring the mic widget is UI polish)."""
    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    memo = (
        "Dad loves jazz. His grandson is named Leo. Avoid talking about driving. "
        "I'm dropping off groceries at 4 PM today."
    )
    saved = 0
    for line in memo.split(". "):
        line = line.strip().rstrip(".")
        if line and store.add(line, source="caregiver_memo"):
            saved += 1
    print(f"Caregiver memo saved ({saved} new facts; re-running this beat won't duplicate them).")
    _print_memory_panel(store, CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR))


def beat2_senior_turn(transcript: str | None, audio_in: Path | None = None, play: bool = True) -> None:
    if audio_in is not None:
        transcript = hear.transcribe(audio_in)
        print(f'Heard from "{audio_in.name}": "{transcript}"')

    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR)
    result = run_turn(transcript, store, flags, AUDIO_DIR, caregiver_name=DEFAULT_CAREGIVER_NAME)

    print(f'Senior said: "{transcript}"')
    print(f"Companion replied: \"{result.reply_text}\"")
    if result.time_to_first_audio_s is not None:
        tag = "OK" if result.time_to_first_audio_s < 2.0 else "SLOW"
        print(f"Time to first audio: {result.time_to_first_audio_s:.2f}s [{tag}]")
    print(f"Memories recalled: {result.memories_used}")
    print(f"Audio chunks: {[p.name for p in result.audio_paths]}")
    if play:
        for audio_path in result.audio_paths:
            _play(audio_path)

    if result.background_thread is not None:
        result.background_thread.join(timeout=10)  # the audit/memory-save LLM call can be slower than a fixed sleep
    if result.memory_saved:
        print(f"New memory saved: {result.memory_saved}")
    if result.audit_verdict:
        print(f"Audit verdict: {result.audit_verdict}")
    _print_memory_panel(store, flags)


def beat3_worrying_remark(transcript: str | None, audio_in: Path | None = None, play: bool = True) -> None:
    """Same code path as beat2 -- the fast-path in safety/fastpath.py is what
    makes this beat different (immediate disclosure + caregiver flag, then
    the turn continues naturally instead of ending)."""
    beat2_senior_turn(transcript, audio_in=audio_in, play=play)


def day2_recall_check() -> None:
    """Proves memory persists ACROSS separate process runs, not just within
    one -- run this as its own `python main.py day2` invocation sometime
    after beat1/beat2, ideally in a separate terminal session or even after
    a reboot. MemoryStore reads straight from data/<profile>.json on
    __init__ (see memory/store.py); this process never saw beat1 run, it's
    just reading what beat1's process wrote to disk."""
    import os
    import time

    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    items = store.all()
    if not items:
        print(f"No memory file found at {store.path} -- run `python main.py beat1` first.")
        return

    now = time.time()
    print(f"This process (PID {os.getpid()}) started just now and has no in-memory state from")
    print(f"whatever process originally wrote {store.path}. It only read the file on disk:\n")
    for item in items:
        age_s = now - item.created_at
        print(f"  [{item.source}] \"{item.text}\" -- saved {age_s:.0f}s ago by a different process")
    print(f"\n{len(items)} fact(s) recalled from a prior run. Persistence confirmed.")


def beat4_day2_recall(transcript: str | None, audio_in: Path | None = None, play: bool = True) -> None:
    """Demonstrates persistence by surfacing a memory saved in a previous session
    (e.g., beat1) across process boundaries."""
    import os
    from pipeline.nebius_client import NebiusNotConfigured

    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    items = store.all()
    if not items:
        print(f"No memory file found at {store.path} -- run `python main.py beat1` first.")
        return

    print(f"[Testing Day-2 Recall: PID {os.getpid()} starting fresh with no in-memory state]")
    try:
        beat2_senior_turn(transcript, audio_in=audio_in, play=play)
    except NebiusNotConfigured:
        print(
            "beat4 needs NEBIUS_API_KEY for the conversational reply. "
            "For the no-key persistence proof, run `python main.py day2`."
        )
        sys.exit(2)


if __name__ == "__main__":
    load_dotenv()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    beat = args[0]
    rest = args[1:]
    play = "--no-play" not in rest
    rest = [a for a in rest if a != "--no-play"]

    audio_in: Path | None = None
    if "--audio" in rest:
        idx = rest.index("--audio")
        audio_in = Path(rest[idx + 1])
        rest = rest[:idx] + rest[idx + 2:]
    text_in = rest[0] if rest else None

    if beat == "beat1":
        beat1_caregiver_memo()
    elif beat == "beat2":
        beat2_senior_turn(
            text_in or "Hi, how's it going today? I've been listening to a lot of Miles Davis lately, I love him.",
            audio_in=audio_in,
            play=play,
        )
    elif beat == "beat3":
        beat3_worrying_remark(text_in or "I fell down earlier and I'm scared", audio_in=audio_in, play=play)
    elif beat == "beat4":
        beat4_day2_recall(text_in or "I forgot, what is my grandson's name?", audio_in=audio_in, play=play)
    elif beat == "day2":
        day2_recall_check()
    else:
        print(f"unknown beat: {beat}")
        sys.exit(1)
