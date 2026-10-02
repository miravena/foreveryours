"""One voice turn, end to end: HEAR -> fast-path check -> RECALL -> THINK
(streamed) -> SPEAK (streamed, sentence-by-sentence) -> async AUDIT +
async memory-extraction.

Latency design: SPEAK starts on the first sentence of THINK's stream, not
the full completion. AUDIT and memory-extraction run in a background
thread after the first sentence is already on its way to audio -- neither
blocks time-to-first-audio. The rule-based fast-path in safety/fastpath.py
runs synchronously but is regex-only (microseconds), so it doesn't cost
anything on the common path, and skips the LLM call for only the immediate
reassurance -- the turn still continues into THINK afterward (see below),
so a distress/confusion trigger doesn't dead-end the conversation.

Disclosure is a hard invariant, not a default: every CaregiverFlags.add()
call here states explicitly whether the senior was actually told, in the
conversation, that the flag was raised. The fast-path's immediate reply IS
that disclosure. The async AUDIT path discloses via a spoken follow-up
line -- if that fails, the flag is recorded as undisclosed, not silently
marked as if it succeeded.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from caregiver import CaregiverFlags  # noqa: E402
from memory.store import MemoryStore  # noqa: E402
from safety import fastpath  # noqa: E402

from . import audit, speak, think  # noqa: E402
from .intent import Intent, detect_intent  # noqa: E402
from .nebius_client import NebiusNotConfigured  # noqa: E402

DISCLOSURE_LINE = "I want to let {caregiver} know about something I just said."

FALLBACK_REPLY_1 = "I'm right here with you, dear. My thoughts drifted for a second—could you say that one more time?"
FALLBACK_REPLY_2 = "I'm having a little trouble with my connection right now, dear, but I'm still right here beside you. Take your time."


def _sanitize_caregiver_update(text: str, caregiver_name: str) -> str:
    """Rewrites first-person caregiver memos to third-person family updates so
    the AI never hallucinates that it is the one physically visiting or delivering."""
    cleaned = re.sub(r"^(i'm|i am)\s+", f"{caregiver_name} is ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(i will|i'll)\s+", f"{caregiver_name} will ", cleaned, flags=re.IGNORECASE)
    return cleaned


@dataclass
class TurnResult:
    transcript: str
    reply_text: str
    audio_paths: list[Path] = field(default_factory=list)
    memories_used: list[str] = field(default_factory=list)
    memory_saved: str | None = None
    caregiver_flag: str | None = None
    time_to_first_audio_s: float | None = None
    audit_verdict: str | None = None  # filled in async, may arrive after return
    background_thread: threading.Thread | None = None  # join() this before reading audit_verdict/memory_saved
    is_fallback: bool = False
    consecutive_errors: int = 0


def _speak_turn(sentences, audio_out_dir: Path) -> tuple[str, list[Path], float | None]:
    """Runs one full SPEAK pass over a sentence stream, returns the joined
    reply text, every audio chunk's path, and the wall-clock time at which
    the FIRST chunk was ready (None if the stream was empty)."""
    t0 = time.monotonic()
    parts: list[str] = []
    paths: list[Path] = []
    first_audio_time: float | None = None
    for sentence, audio_path in speak.speak_sentences(sentences, audio_out_dir):
        parts.append(sentence)
        paths.append(audio_path)
        if first_audio_time is None:
            first_audio_time = time.monotonic() - t0
    return " ".join(parts), paths, first_audio_time


def run_turn(
    transcript: str,
    memory_store: MemoryStore,
    flags: CaregiverFlags,
    audio_out_dir: Path,
    caregiver_name: str = "your family",
    history: list[dict] | None = None,
    consecutive_errors: int = 0,
) -> TurnResult:
    """`history` is session-scoped prior-turn context (see think.build_prompt's
    docstring for why this is kept separate from memory_store) -- pass None
    for a one-shot call like main.py's CLI beats; webapp.py keeps a real list
    across clicks in one browser session and passes it in each turn."""
    t0 = time.monotonic()

    fast = fastpath.check(transcript)
    immediate_audio_paths: list[Path] = []
    continuation_note = None
    if fast.triggered:
        # Fast-path IS the disclosure: the senior hears this before anything
        # else happens, so disclosed_to_senior=True is simply true here.
        flags.add(fast.caregiver_flag, severity=fast.severity, disclosed_to_senior=True)
        _, immediate_audio_paths, first_audio_time = _speak_turn(iter([fast.immediate_reply]), audio_out_dir)
        continuation_note = fast.continuation_note
    else:
        first_audio_time = None

    intent = detect_intent(transcript)
    guardrails = memory_store.caregiver_guardrails()
    raw_schedule = memory_store.caregiver_schedule_updates()
    caregiver_updates = [_sanitize_caregiver_update(u, caregiver_name) for u in raw_schedule]
    profile_facts = memory_store.senior_profile_facts()
    recalled = [m.text for m in memory_store.search(transcript)]

    # History-aware anchor rotation: If an anchor (e.g. jazz) was used in the previous turn,
    # rotate unmentioned anchors to the front to prevent repetitive responses.
    if history and intent != Intent.MEMORY_REQUEST and profile_facts:
        recent_assistant_text = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                recent_assistant_text = msg.get("content", "").lower()
                break
        if recent_assistant_text:
            unmentioned = [
                f for f in profile_facts
                if not any(w in recent_assistant_text for w in re.findall(r"\b[a-zA-Z]{4,}\b", f.lower()) if w not in ("loves", "named", "with", "from"))
            ]
            if unmentioned:
                profile_facts = unmentioned + [f for f in profile_facts if f not in unmentioned]

    # Intent-aware context gating
    if intent == Intent.EMOTIONAL_SUPPORT:
        # Suppress logistical schedule updates completely on emotional disclosures
        filtered_schedule = []
        filtered_profile = profile_facts[:1]  # At most 1 gentle anchor
    elif intent == Intent.LOGISTICAL:
        # Prioritize caregiver schedule updates; suppress unrelated profile facts/hobbies
        filtered_schedule = caregiver_updates
        filtered_profile = []
    elif intent == Intent.MEMORY_REQUEST:
        # Explicit user request for memories: permit multiple
        filtered_schedule = []
        filtered_profile = list(dict.fromkeys(profile_facts + recalled))
    elif intent == Intent.MIXED:
        filtered_schedule = caregiver_updates
        filtered_profile = profile_facts[:1]
    else:  # CASUAL
        filtered_schedule = caregiver_updates[:1]
        filtered_profile = list(dict.fromkeys(profile_facts + recalled))[:1]

    # Deduplicate facts and remove guardrails
    filtered_profile = [f for f in filtered_profile if f not in filtered_schedule and f not in guardrails]

    think_input = transcript if not continuation_note else f"{transcript}\n\n[{continuation_note}]"
    reply_text = ""
    think_audio_paths: list[Path] = []
    think_unavailable = False
    is_fallback = False
    try:
        token_stream = think.stream_reply(
            think_input,
            filtered_profile,
            guardrails=guardrails,
            history=history,
            caregiver_updates=filtered_schedule,
            intent=intent.value,
        )
        sentences = think.sentence_chunks(token_stream)
        reply_text, think_audio_paths, think_first_audio_time = _speak_turn(sentences, audio_out_dir)
        if first_audio_time is None:
            first_audio_time = think_first_audio_time

        # Post-generation deterministic physical embodiment guardrail
        # Prevent any AI physical claims e.g. "I'll bring your groceries" -> "Your family will bring your groceries"
        physical_claim_pattern = re.compile(
            r"\b(i will|i'll|i am going to|i'm going to)\s+(bring|drop off|come over|visit|drive|pick up)\b",
            re.IGNORECASE,
        )
        if physical_claim_pattern.search(reply_text):
            reply_text = physical_claim_pattern.sub(f"{caregiver_name} will \\2", reply_text)
    except NebiusNotConfigured:
        # Fast-path's immediate reply already completed the turn's safety-
        # critical part (spoken + disclosed + flagged). Without a key we
        # can't continue the conversation for real, but that's a degraded
        # continuation, not a reason to crash a turn that already succeeded.
        if not fast.triggered:
            raise
        think_unavailable = True
    except Exception as exc:
        # Unexpected network / provider error during conversation stream
        if not fast.triggered:
            is_fallback = True
            consecutive_errors += 1
            reply_text = FALLBACK_REPLY_2 if consecutive_errors >= 2 else FALLBACK_REPLY_1
            _, fallback_paths, fallback_first_time = _speak_turn(iter([reply_text]), audio_out_dir)
            think_audio_paths.extend(fallback_paths)
            if first_audio_time is None:
                first_audio_time = fallback_first_time

    # Zero-Silence Guarantee: If model returned an empty string or whitespace (token exhaustion)
    if not fast.triggered and not think_unavailable and not reply_text.strip() and not is_fallback:
        is_fallback = True
        consecutive_errors += 1
        reply_text = FALLBACK_REPLY_2 if consecutive_errors >= 2 else FALLBACK_REPLY_1
        _, fallback_paths, fallback_first_time = _speak_turn(iter([reply_text]), audio_out_dir)
        think_audio_paths.extend(fallback_paths)
        if first_audio_time is None:
            first_audio_time = fallback_first_time
    elif not is_fallback:
        consecutive_errors = 0

    result = TurnResult(
        transcript=transcript,
        reply_text=(fast.immediate_reply + " " + reply_text).strip() if fast.triggered else reply_text,
        audio_paths=immediate_audio_paths + think_audio_paths,
        memories_used=filtered_profile + filtered_schedule,
        caregiver_flag=fast.caregiver_flag if fast.triggered else None,
        time_to_first_audio_s=first_audio_time,
        audit_verdict=(
            "skipped (fast-path disclosed directly; continuation needs NEBIUS_API_KEY)"
            if think_unavailable
            else "skipped (fast-path disclosed directly)" if fast.triggered
            else "skipped (fallback turn)" if is_fallback
            else None
        ),
        is_fallback=is_fallback,
        consecutive_errors=consecutive_errors,
    )

    if not fast.triggered and not is_fallback:
        def background() -> None:
            try:
                is_safe, verdict = audit.audit_reply(transcript, reply_text)
                result.audit_verdict = verdict
                if not is_safe:
                    disclosed = False
                    try:
                        caregiver_text = DISCLOSURE_LINE.format(caregiver=caregiver_name)
                        _, extra_paths, _ = _speak_turn(iter([caregiver_text]), audio_out_dir)
                        result.audio_paths.extend(extra_paths)
                        disclosed = True
                    except Exception:  # pragma: no cover - best-effort disclosure
                        disclosed = False
                    flags.add(
                        f"AUDIT flagged a reply as unsafe: {verdict}",
                        severity="audit",
                        disclosed_to_senior=disclosed,
                    )
            except Exception as exc:  # pragma: no cover - best-effort background task
                result.audit_verdict = f"audit error: {exc}"

            try:
                saved = think.extract_new_memory(transcript, reply_text)
                if saved:
                    memory_store.add(saved, source="conversation_extract")
                    result.memory_saved = saved
            except Exception:  # pragma: no cover - best-effort background extraction
                pass

        thread = threading.Thread(target=background, daemon=True)
        thread.start()
        result.background_thread = thread

    return result
