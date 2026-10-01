"""CLI demo runner for the three-beat demo script (see docs/DEMO_SCRIPT.md).

Thin vertical slice: no dashboard UI yet -- that's tracked as an open
GitHub Issue, deliberately lower priority than the end-to-end pipeline. This
prints the live "memory panel" to the terminal so the pipeline's recall/save
behavior is visibly provable before any UI exists.

Usage:
    cp .env.example .env   # fill in NEBIUS_API_KEY
    python main.py beat1   # caregiver memo
    python main.py beat2 "Hi, how's it going today?"
    python main.py beat3 "I fell down earlier and I'm scared"
"""
from __future__ import annotations

import sys
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


def beat2_senior_turn(transcript: str) -> None:
    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR)
    result = run_turn(transcript, store, flags, AUDIO_DIR, caregiver_name=DEFAULT_CAREGIVER_NAME)

    print(f'Senior said: "{transcript}"')
    print(f"Companion replied: \"{result.reply_text}\"")
    if result.time_to_first_audio_s is not None:
        tag = "OK" if result.time_to_first_audio_s < 2.0 else "SLOW"
        print(f"Time to first audio: {result.time_to_first_audio_s:.2f}s [{tag}]")
    print(f"Memories recalled: {result.memories_used}")
    print(f"Audio chunks: {[str(p) for p in result.audio_paths]}")

    if result.background_thread is not None:
        result.background_thread.join(timeout=10)  # the audit/memory-save LLM call can be slower than a fixed sleep
    if result.memory_saved:
        print(f"New memory saved: {result.memory_saved}")
    if result.audit_verdict:
        print(f"Audit verdict: {result.audit_verdict}")
    _print_memory_panel(store, flags)


def beat3_worrying_remark(transcript: str) -> None:
    """Same code path as beat2 -- the fast-path in safety/fastpath.py is what
    makes this beat different (immediate disclosure + caregiver flag, then
    the turn continues naturally instead of ending)."""
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
        beat2_senior_turn(args[1] if len(args) > 1 else "Hi, how's it going today? I've been listening to a lot of Miles Davis lately, I love him.")
    elif beat == "beat3":
        beat3_worrying_remark(args[1] if len(args) > 1 else "I fell down earlier and I'm scared")
    else:
        print(f"unknown beat: {beat}")
        sys.exit(1)
