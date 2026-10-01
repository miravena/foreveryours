"""CLI demo runner for the AC3 three-beat script.

Thin vertical slice: no dashboard UI yet (that's caregiver-dashboard polish,
explicitly lower priority than the end-to-end pipeline per the ticket). This
prints the live "memory panel" to the terminal so the pipeline's recall/save
behavior is visibly provable before any UI exists.

Usage:
    cd competitions/nebius-foreveryours/app
    cp .env.example .env   # fill in NEBIUS_API_KEY
    python -m main beat1   # caregiver memo
    python -m main beat2 "Hi, how's it going today?"
    python -m main beat3 "I fell down earlier and I'm scared"
    python -m main beat4 "I forgot, what is my grandson's name?"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from caregiver import DEFAULT_CAREGIVER_NAME, DEFAULT_PROFILE_ID, CaregiverFlags
from memory.store import MemoryStore
from pipeline.orchestrator import run_turn

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_DIR = Path(__file__).resolve().parent / "out" / "audio"


def _print_memory_panel(store: MemoryStore, flags: CaregiverFlags) -> None:
    print("\n--- LIVE MEMORY PANEL ---")
    for item in store.all():
        print(f"  [{item.source}] {item.text}")
    if flags.all():
        print("--- CAREGIVER FLAGS ---")
        for flag in flags.all():
            print(f"  ({flag.severity}) {flag.text}")
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
    for line in memo.split(". "):
        line = line.strip().rstrip(".")
        if line:
            store.add(line, source="caregiver_memo")
    print(f"Caregiver memo saved ({len(memo.split('. '))} facts).")
    _print_memory_panel(store, CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR))


def beat2_senior_turn(transcript: str) -> None:
    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR)
    result = run_turn(DEFAULT_PROFILE_ID, transcript, store, flags, AUDIO_DIR)

    print(f'Senior said: "{transcript}"')
    print(f"Companion replied: \"{result.reply_text}\"")
    if result.time_to_first_audio_s is not None:
        tag = "OK" if result.time_to_first_audio_s < 2.0 else "SLOW"
        print(f"Time to first audio: {result.time_to_first_audio_s:.2f}s [{tag}]")
    print(f"Memories recalled: {result.memories_used}")
    print(f"Audio chunks: {[str(p) for p in result.audio_paths]}")

    time.sleep(0.5)  # let the background audit/extraction thread finish for the demo print
    if result.memory_saved:
        print(f"New memory saved: {result.memory_saved}")
    if result.audit_verdict:
        print(f"Audit verdict: {result.audit_verdict}")
    _print_memory_panel(store, flags)


def beat3_worrying_remark(transcript: str) -> None:
    """Same code path as beat2 -- the fast-path in safety/fastpath.py is what
    makes this beat different (caregiver flag + honest in-conversation line)."""
    print(f"[{DEFAULT_CAREGIVER_NAME} will be told honestly, in-conversation, if this trips the fast-path]")
    beat2_senior_turn(transcript)


def beat4_day2_recall(transcript: str) -> None:
    """Demonstrates persistence by surfacing a memory saved in a previous session
    (e.g., beat2) across process boundaries."""
    print("[Testing Day-2 Recall: Simulating a new session on a different day]")
    beat2_senior_turn(transcript)


if __name__ == "__main__":
    load_dotenv()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    beat = args[0]
    if beat == "beat1":
        beat1_caregiver_memo()
    elif beat == "beat2":
        beat2_senior_turn(args[1] if len(args) > 1 else "Hi, how's it going today?")
    elif beat == "beat3":
        beat3_worrying_remark(args[1] if len(args) > 1 else "I fell down earlier and I'm scared")
    elif beat == "beat4":
        beat4_day2_recall(args[1] if len(args) > 1 else "I forgot, what is my grandson's name?")
    else:
        print(f"unknown beat: {beat}")
        sys.exit(1)
