"""Judge-facing web demo: the pivot beat (issue #21), not just a UI shell.

The point of this file isn't "put the CLI in a browser" -- it's to make the
ONE thing a general-purpose voice assistant can't do visible in a single
screen: when the senior says something worrying, the companion tells HIM
that it's raising a caregiver flag, and in the SAME moment the caregiver side
lights up with that exact flag. Two columns, side by side, on purpose --
that's the demo, not a design choice to revisit later.

Still calls the exact same pipeline.orchestrator.run_turn used by main.py's
CLI beats -- no new pipeline logic, just this layout + session history
(think.build_prompt's docstring explains why history is separate from
memory_store) + a live-polling caregiver panel.

For whoever's newer to this (the "why", not just the "what" -- see
CONTRIBUTING.md's "Working with AI-assisted code" section for the fuller
version): the caregiver panel polls the flags file on a timer instead of
pushing updates over a websocket. A push-based approach would be the "more
correct" engineering answer, but it's also more moving parts to debug under
a deadline, and polling a small JSON file every second is cheap enough that
the extra complexity wouldn't buy us anything a judge would notice. Match
the engineering effort to what the demo actually needs to prove, not to
what's generically "best practice" -- there's no safety or correctness cost
to polling here, only a few seconds of extra latency before the caregiver
side visibly updates, which is still fast enough for the demo.

Run locally:
    python webapp.py
Deploy on Hugging Face Spaces: push this file as `app.py` at the Space root
(Spaces auto-detects Gradio apps named app.py) with requirements.txt alongside it.

MAX_DAILY_REQUESTS caps usage on a public URL so one link can't burn through
the whole Nebius credit balance (see VENDOR_DECISIONS.md).

Public-URL isolation (issues #11, #18): every browser session gets its own
throwaway household under FY_SESSIONS_DIR, pre-briefed with the same demo
caregiver memo as `main.py beat1`. Two judges on the same link never see each
other's flags, memories or voices. A session's directory is deleted roughly
an hour after the tab disconnects (gr.State's delete_callback -> _end_session;
Gradio holds closed-session state for its own fixed STATE_TTL_WHEN_CLOSED,
3600s, confirmed against the installed gradio==6.29.1 source), or after
SESSION_TTL_S of inactivity if no close event ever arrives (the sweeper).
Gradio's own upload/output cache (`delete_cache=GRADIO_CACHE_SWEEP`) is swept
every GRADIO_CACHE_SWEEP[0] seconds and drops files older than
GRADIO_CACHE_SWEEP[1] seconds, so an input clip can live up to roughly
SESSION_TTL_S + GRADIO_CACHE_SWEEP[0] seconds. Neither path promises deletion
the instant the tab closes. Set FY_SHARED_PROFILE=1 to
get the old single shared `data/dad.*` profile back -- useful locally when
recording a video alongside `main.py` beats, never for a public deployment.
"""
from __future__ import annotations

import contextlib
import datetime
import functools
import html
import os

if __name__ == "__main__":
    # Only for `python webapp.py` (local dev). app.py (the hosted/Spaces
    # entrypoint) already loads .env before importing this module; loading it
    # unconditionally at import time made importing webapp for tests pick up
    # a real key depending on process/import order (#81 D2). Must run before
    # the os.environ.get() constants below, or they'd miss .env values
    # (Codex review, PR #90) -- hence the guard sits here, not at EOF.
    from envload import load_repo_env
    load_repo_env()

import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
SENIOR_TIMEZONE = os.environ.get('SENIOR_TIMEZONE', 'Asia/Kuala_Lumpur')
import wave
from pathlib import Path

import gradio as gr

from caregiver import (
    DEFAULT_CAREGIVER_NAME,
    DEFAULT_PROFILE_ID,
    DEMO_MEMO,
    INTERVIEW_QUESTIONS,
    SAMPLE_FAMILY,
    SAMPLE_FAMILY_LABEL,
    CaregiverFlags,
    sample_family_texts,
    interview_answer_memo,
    split_memo_facts,
    validate_sample_profile,
)
from memory.store import CAREGIVER_SOURCES, MemoryScope, MemoryStore, PrivacyLevel
import notify
from pipeline import hear
from pipeline.audit import DEFAULT_AUDIT_MODEL
from pipeline.think import DEFAULT_THINK_MODEL
from pipeline.orchestrator import run_turn
from safety import fastpath
from samples.generate_samples import SAMPLES as SAMPLE_SCRIPTS

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_DIR = Path(__file__).resolve().parent / "out" / "audio"
SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
# Written by scripts/deploy_hf_space.py into the staged Space folder (one line: the
# full git sha the Space was built from). Absent in a checkout, so local runs show no
# build line and the Space shows exactly the commit judges are looking at.
BUILD_INFO_PATH = Path(__file__).resolve().parent / "BUILD_INFO"
SAMPLE_CLIPS = ("senior_schedule.wav", "senior_jazz.wav", "senior_grandson.wav", "senior_distress.wav")
# Each sample chip carries a plain name for the clip (#215); the order matches
# SAMPLE_CLIPS. SAMPLE_SCRIPTS (what each clip says) stays imported so the
# deployed build keeps shipping the script that synthesises the clips; the
# check below fails fast if a clip has no script.
SAMPLE_CLIP_LABELS = (
    "Dad asks what's happening today",
    "Dad talks about jazz",
    "Dad asks his grandson's name",
    "Dad says he fell and is scared",
)
if not all(name in SAMPLE_SCRIPTS for name in SAMPLE_CLIPS):
    raise RuntimeError("a sample clip has no script in samples/generate_samples.py")
MAX_DAILY_REQUESTS = int(os.environ.get("MAX_DAILY_REQUESTS", "50"))
# Audio input bounds, checked before any ASR runs. 25 MB is the ceiling
# OpenAI-compatible transcription endpoints enforce; 120 s is far above any demo
# utterance. MAX_AUDIO_UPLOAD_BYTES is also Gradio's launch(max_file_size=...).
MAX_AUDIO_UPLOAD_BYTES = int(os.environ.get("MAX_AUDIO_UPLOAD_BYTES", str(25 * 1024 * 1024)))
MAX_AUDIO_SECONDS = int(os.environ.get("MAX_AUDIO_SECONDS", "120"))
MAX_HISTORY_TURNS = 4  # (user, assistant) pairs kept -- bounds prompt growth, not a product limit
REMINDER_EVERY_N_TURNS = 6  # session-length-based "this is an AI" reminder (#83 AC)
# Developer-only surface (telemetry, clinical sim, proactive triggers, biomarkers,
# the perseveration flag) stays out of the public page by default (#83, #80 3.C3).
DEV_MODE = os.environ.get("FY_DEV_MODE") == "1"
PRIVACY_NOTICE_URL = "https://github.com/miravena/foreveryours/blob/main/docs/SAFETY_AND_PRIVACY.md"
SESSIONS_DIR = Path(os.environ.get("FY_SESSIONS_DIR", Path(tempfile.gettempdir()) / "foreveryours-sessions"))
SHARED_PROFILE = os.environ.get("FY_SHARED_PROFILE") == "1"
SESSION_TTL_S = int(os.environ.get("SESSION_TTL_S", "3600"))


def _parse_turn_concurrency(raw: str | None) -> int:
    """FY_TURN_CONCURRENCY: how many senior turns (any visitor) may run at
    once across the shared "senior_turn" listeners (ADR-003
    "Concurrency"). Unset means 4. Must be an integer >= 2: 1 is Gradio's
    default, which queued every visitor behind one slow turn, and unbounded
    is refused because the daily cap and audio limits assume a bounded
    number of in-flight turns."""
    if raw is None:
        return 4
    try:
        value = int(raw.strip())
    except ValueError:
        value = 0
    if value < 2:
        raise ValueError(f"FY_TURN_CONCURRENCY must be an integer >= 2 (got {raw!r})")
    return value


TURN_CONCURRENCY = _parse_turn_concurrency(os.environ.get("FY_TURN_CONCURRENCY"))
# Sweeper/_end_session assume CPython's symlink-safe, fd-based rmtree (true on
# Linux); only this process writes SESSIONS_DIR, so another local writer
# swapping an entry mid-delete is out of scope (#150, #151 ASSUMPTIONS).
if not shutil.rmtree.avoids_symlink_attacks:
    print(
        "WARNING: shutil.rmtree on this platform is not symlink-attack-safe "
        "(shutil.rmtree.avoids_symlink_attacks is False); session cleanup "
        "may not be safe against a symlinked session directory."
    )
GRADIO_CACHE_SWEEP = (600, SESSION_TTL_S)  # (check every N s, delete files older than M s)
# Human-readable figures for the notices below (#137, #143). Two different
# delays, from two different sources -- do not conflate them:
#   - Tab-close path: when gr.State's delete_callback (_end_session) actually
#     fires is governed by Gradio's OWN fixed closed-session TTL
#     (StateHolder.STATE_TTL_WHEN_CLOSED in gradio/state_holder.py), which is
#     3600s hardcoded in the installed gradio==6.29.1 regardless of our
#     SESSION_TTL_S -- confirmed by reading that source, not assumed. If
#     SESSION_TTL_S is overridden via env, this number does NOT move with it.
#   - Inactivity-sweep path (close event never arrives): governed by our own
#     SESSION_TTL_S, so this one does track the env override.
#   - Input-audio cache: Gradio's delete_cache=GRADIO_CACHE_SWEEP sweeps every
#     GRADIO_CACHE_SWEEP[0]s and drops files older than GRADIO_CACHE_SWEEP[1]s
#     (== SESSION_TTL_S), so up to GRADIO_CACHE_SWEEP[0] + GRADIO_CACHE_SWEEP[1]
#     seconds -- this part does track SESSION_TTL_S.
_GRADIO_CLOSED_STATE_TTL_S = 3600  # Gradio's own fixed constant, not ours
_CLOSED_TAB_MIN = _GRADIO_CLOSED_STATE_TTL_S // 60
_SESSION_TTL_MIN = SESSION_TTL_S // 60
_CACHE_SWEEP_INTERVAL_MIN = GRADIO_CACHE_SWEEP[0] // 60  # how often the cache sweep runs
_CACHE_MAX_AGE_MIN = GRADIO_CACHE_SWEEP[1] // 60  # how old a file must be before that sweep removes it
_CACHE_MAX_MIN = (GRADIO_CACHE_SWEEP[0] + GRADIO_CACHE_SWEEP[1] + 59) // 60  # worst case: sweep just missed it
HIGH_PRIORITY_SEVERITIES = ("crisis", "distress", "confusion")
# Fixes #140: the caregiver panel's "Briefed memory" list is built from
# MemoryStore.all(), which also holds EMOTIONAL-scope memories extracted from
# the senior's own private words -- that is the surveillance #140 warns
# about. Everything else (disclosed flags, caregiver memos/notes) stays
# visible by design. Senior-derived facts require an independently recorded
# disclosure attestation; extractor labels and scopes are never authorization.
# An unrecognised scope is treated as private and hidden too (fail closed,
# never fail open on a privacy boundary).
_CAREGIVER_PANEL_NON_EMOTIONAL_SCOPES = frozenset(
    s.value for s in MemoryScope if s is not MemoryScope.EMOTIONAL
)


# MemoryStore._decay_emotions() ages a 24h-expired EMOTIONAL item into
# HISTORICAL scope, prefixing its (unchanged, still private) text with
# "[PAST EMOTION - <date>]" instead of deleting it -- scope alone can't
# tell a decayed emotional disclosure apart from an ordinary historical
# fact, so the text prefix has to be checked too, same as "[EMOTIONAL
# STATE]" is for a still-active one.
_EMOTIONAL_TEXT_PREFIXES = ("[EMOTIONAL STATE]", "[PAST EMOTION")


_ALL_KNOWN_SCOPES = frozenset(s.value for s in MemoryScope)


def _caregiver_panel_may_show(item) -> bool:
    """True if `item` (a memory.store.MemoryItem) is safe to render in the
    caregiver panel: caregiver-authored memos/notes always are; senior-derived
    facts require an explicit disclosure attestation in addition to the
    existing scope and text checks."""
    # A pending or asked memory conflict (old|new|reason text) must never
    # render in Briefed memory -- escalate_asked_conflicts() tells the
    # caregiver a content-free flag instead (#165 and duplicates).
    if item.status in ("conflict", "conflict_asked"):
        return False
    # Fallback (RULE): an unrecognised scope is hidden regardless of
    # source. This check used to run only for non-CAREGIVER_SOURCES items
    # (the CAREGIVER_SOURCES branch below short-circuited first), so a
    # caregiver-sourced item with a garbage/future scope value -- e.g. a
    # hand-edited data file, or a later code change that starts writing
    # caregiver items with a new scope this function doesn't know about --
    # would have rendered unconditionally. Checking it first makes the
    # fail-closed guarantee unconditional, matching the RULE's own wording.
    if item.scope not in _ALL_KNOWN_SCOPES:
        return False
    if item.scope == MemoryScope.EMOTIONAL.value or item.text.startswith(_EMOTIONAL_TEXT_PREFIXES):
        return False
    if item.source in CAREGIVER_SOURCES:
        return True
    return (
        bool(getattr(item, "disclosure_attested", False))
        and item.scope in _CAREGIVER_PANEL_NON_EMOTIONAL_SCOPES
    )

def _replacement_may_show(all_items: list, replacement_text: str) -> bool:
    """A superseded fact's "Replaced by" text is the
    REPLACEMENT item's words, so it may render only when that item would
    itself pass _caregiver_panel_may_show(). A caregiver update ("groceries
    at 6 PM") does; a senior's private correction of a caregiver fact
    (conversation_extract, no disclosure attestation) does not, so the
    caregiver sees the struck-through original and the Superseded badge but
    never the senior's words. Fail-closed: no item with that text, or any
    item with that text that may not be shown, hides it."""
    matches = [i for i in all_items if i.text == replacement_text]
    return bool(matches) and all(_caregiver_panel_may_show(i) for i in matches)


# Briefed memory must list each caregiver-memo fact once. The
# splitters are now shared (caregiver.split_memo_facts), but a store written
# before that, or by any future path that stores a whole memo beside its
# fragments, would still render the fragments AND the whole memo. Facts are
# compared by a key that ignores case, whitespace and sentence punctuation
# but keeps every word (Unicode included) and in-word punctuation, so
# "Dad loves jazz." and "Dad loves jazz" are one fact while "Dose: 1.5 mg"
# and "Dose: 15 mg" are two (a sign stays on its number: "-5 C" is not
# "5 C"). The key includes the item's privacy level: a
# caregiver-only copy and a public copy of the same words mean different
# things to the caregiver and both stay. A caregiver item is dropped only
# when its key repeats a listed fact, or is other shown active caregiver
# items joined end to end (the whole memo). Only CAREGIVER_SOURCES items are
# ever dropped; what _caregiver_panel_may_show hides is unchanged.
# A word may carry apostrophes/hyphens ("o'clock", "well-known") and a number
# may carry .,:/ followed by MORE DIGITS ("1.5", "3:30", "1/2"); "jazz.His"
# (legacy no-space period) is two words, not one (openai_review).
# Comparison operators are tokens of their own: "temperature < 38" and
# "temperature > 38" are opposite instructions, not one fact.
_FACT_TOKEN_RE = re.compile(r"[-+]?\w+(?:['\u2019-]\w+)*(?:[.,:/]\d+)*|[<>=\u2260\u2264\u2265]+")


def _fact_tokens(text: str) -> tuple[str, ...]:
    return tuple(_FACT_TOKEN_RE.findall(text.lower()))


def _fact_key(item) -> tuple:
    return (item.privacy, _fact_tokens(item.text))


def _is_concatenation_of(tokens: tuple[str, ...], parts: set[tuple[str, ...]]) -> bool:
    """True if `tokens` can be spelled by joining two or more of `parts`
    (each usable any number of times) end to end."""
    parts = {p for p in parts if p}
    dead: set[tuple[int, int]] = set()

    def covers(pos: int, used: int) -> bool:
        if pos == len(tokens):
            return used >= 2
        if (pos, min(used, 2)) in dead:
            return False
        for part in parts:
            if tokens[pos:pos + len(part)] == part and covers(pos + len(part), used + 1):
                return True
        dead.add((pos, min(used, 2)))
        return False

    return bool(tokens) and covers(0, 0)


def _longer_lived(a, b):
    """Of two active copies of one fact, the one valid longest (no expiry
    beats any expiry) -- the deadline the panel shows must not be the one
    that lapses first while another copy of the same fact lives on."""
    if a.expires_at is None:
        return a
    if b.expires_at is None or b.expires_at > a.expires_at:
        return b
    return a


def _dedupe_briefed_memory(items: list, now: float) -> list:
    """Render-time dedupe for the Briefed memory list: returns
    `items` in order minus caregiver items that repeat a fact already listed
    -- same key as an active caregiver item, or a key that is the
    concatenation of other active caregiver items' keys. Non-caregiver items
    and items with no words pass through untouched."""
    active: dict[tuple, object] = {}  # key -> the copy to show for that fact
    for item in items:
        if item.source in CAREGIVER_SOURCES and item.is_active(now):
            key = _fact_key(item)
            if key[1]:
                active[key] = _longer_lived(active[key], item) if key in active else item
    kept: list = []
    seen: set[tuple] = set()
    for item in items:
        if item.source not in CAREGIVER_SOURCES:
            kept.append(item)
            continue
        key = _fact_key(item)
        if not key[1]:
            kept.append(item)  # no words to compare on; never guess
            continue
        if key in seen:
            continue  # same fact, different punctuation/case
        if key in active and item is not active[key]:
            if item.is_active(now):
                # Another active copy lives longer; show the fact once, at its
                # place in the list, carrying the longest-lived copy's badge.
                item = active[key]
            else:
                continue  # an active copy of this fact is listed
        others = {k[1] for k in active if k[0] == key[0] and k[1] != key[1]}
        if _is_concatenation_of(key[1], others):
            continue  # the whole memo, already listed fact by fact
        seen.add(key)
        kept.append(item)
    return kept


_lock = threading.Lock()
_request_log: dict[str, int] = {}  # vestigial -- kept only so tests' webapp._request_log.clear() still resolves; _rate_limit_ok keeps its own local dict now

_bg_threads_lock = threading.Lock()
_bg_threads: dict[str, list[threading.Thread]] = {}  # session_id -> every outstanding writer thread for that session, if any (#148: a single slot let a later turn's thread overwrite tracking of a still-running earlier writer)
_session_sweeper_started = False
_session_sweeper_lock = threading.Lock()

# Guards session filesystem state: _active_turns, and every stat/delete the
# sweeper and _end_session perform. Lock order is always _session_fs_lock
# FIRST, then _bg_threads_lock -- never the reverse (#148). The per-profile
# file locks (memory/profile_io.py) come after both:
#   _session_fs_lock -> _bg_threads_lock -> profile lock (store) -> profile lock (flags)
# A profile lock is a LEAF: never take _session_fs_lock or _bg_threads_lock
# while holding one. _touch_session (takes _session_fs_lock) is only ever
# called from webapp handlers, never from inside a store method; keep it so.
_session_fs_lock = threading.RLock()
# session_id -> number of turns AND caregiver memo saves currently in
# progress (#148); see _session_active.
_active_turns: dict[str, int] = {}
# session_id -> lock held for the whole of one streaming turn, so turns for
# ONE session run one after the other while different sessions overlap.
# Created and deleted under _session_fs_lock alongside the
# _active_turns count, so it lives exactly as long as the session's in-flight
# turns. Never block on one of these while holding _session_fs_lock.
_session_turn_locks: dict[str, threading.Lock] = {}
_BG_JOIN_TIMEOUT_S = 10

# The one notice shown when a browser's household is gone and a fresh one
# answers instead (#83). Prefixed to the first output with "\n\n".
_RESET_NOTICE = "_Your demo household was reset after a period of inactivity._"


def _session_really_expired(session_id: str | None, history: list, legacy_form: bool) -> bool:
    """True only when an earlier session was really lost (#215). A missing
    session id on the first turn of a fresh page is not an expiry: nothing was
    reset, so the notice would be false. A real expiry leaves the browser's
    conversation history behind (the history State has no time-to-live); the
    three-argument (audio, history, session) form is the older call shape whose
    caller always held a session, so a missing id there means it went away."""
    if session_id is not None:
        return False
    return bool(history) or legacy_form


class SessionGone(Exception):
    """A session operation that refuses to recreate a deleted household
    (`_session_active(..., refuse_if_deleted=True)`) found its directory
    already gone."""


class _ChunkAck:
    """One chunk's acknowledgement: settled exactly once --
    accepted by the generator right after it yielded the chunk, or refused
    by `_ChunkConsumer.close` / the wait timeout. `wait_accepted()` is what
    `orchestrator._speak_disclosure` resolves an `on_chunk` return value
    with, so only callers that need the answer ever block on it."""

    def __init__(self, consumer: "_ChunkConsumer") -> None:
        self._consumer = consumer
        self._event = threading.Event()
        self.accepted = False

    def is_set(self) -> bool:
        return self._event.is_set()

    def _settle(self, accepted: bool) -> None:
        # Caller holds the consumer's lock. First settlement wins: an ack
        # refused by a timeout or close() is never flipped back to accepted.
        if not self._event.is_set():
            self.accepted = accepted
            self._event.set()

    def wait_accepted(self) -> bool:
        self._event.wait(timeout=_BG_JOIN_TIMEOUT_S)
        with self._consumer._lock:
            self._settle(False)  # no-op if the generator already acked
            return self.accepted


class _ChunkConsumer:
    """The producer/consumer handshake between `run_turn`'s `on_chunk`
    callback (worker + background threads) and the streaming generator.

    A chunk counts as delivered only once the generator has DEQUEUED and
    YIELDED it to the browser and acknowledged it -- the `queue.task_done()`
    contract, never "it was put()". `offer` returns that acknowledgement as
    a bool (blocking up to `_BG_JOIN_TIMEOUT_S`); `submit` enqueues without
    blocking and returns the `_ChunkAck` (or False if already closed), which
    is what the streaming `_on_chunk` hands back so the main reply's
    sentence-by-sentence synthesis never waits on the browser, while
    `orchestrator._speak_disclosure` resolves it before attesting a late
    AUDIT/lifestyle disclosure.

    One lock covers both "check open + put" in `submit` and "mark closed +
    drain" in `close`, so a chunk is either enqueued while open (and later
    accepted by the generator or refused by `close`) or refused outright --
    there is no window where it is enqueued into a queue nobody will read.
    `close` also refuses a chunk already dequeued but still suspended at the
    generator's yield (browser disconnect: `gen.close()` raises GeneratorExit
    there, before the ack)."""

    def __init__(self) -> None:
        import queue as _queue

        self.queue: _queue.Queue = _queue.Queue()
        self._lock = threading.Lock()
        self._open = True
        self._in_flight: _ChunkAck | None = None

    def submit(self, sentence: str, path: Path) -> "_ChunkAck | bool":
        with self._lock:
            if not self._open:
                return False
            ack = _ChunkAck(self)
            self.queue.put(("CHUNK", sentence, path, ack))
            return ack

    def offer(self, sentence: str, path: Path) -> bool:
        ack = self.submit(sentence, path)
        return ack.wait_accepted() if isinstance(ack, _ChunkAck) else False

    def put(self, msg: tuple) -> None:
        """Control messages (DONE / ERROR) -- never acknowledged."""
        self.queue.put(msg)

    def get(self, timeout: float | None = None) -> tuple:
        """Dequeue the next message (raises queue.Empty on timeout). A CHUNK
        becomes the in-flight chunk until `accept` or `close` settles it."""
        msg = self.queue.get(timeout=timeout)
        if msg[0] == "CHUNK":
            with self._lock:
                self._in_flight = msg[3]
        return msg

    def accept(self, ack: _ChunkAck, accepted: bool = True) -> None:
        """Called by the generator right after the chunk's yield returned;
        `accepted=False` when that yield did not actually carry the chunk's
        audio (an unreadable chunk yields `None`, see `_chunk_readable`)."""
        with self._lock:
            ack._settle(accepted)
            if self._in_flight is ack:
                self._in_flight = None

    def close(self) -> None:
        import queue as _queue

        with self._lock:
            self._open = False
            if self._in_flight is not None:
                self._in_flight._settle(False)
                self._in_flight = None
            while True:
                try:
                    msg = self.queue.get_nowait()
                except _queue.Empty:
                    break
                if msg[0] == "CHUNK":
                    msg[3]._settle(False)


def _join_previous_turn(session_id: str) -> None:
    """A turn's background AUDIT + memory-extraction thread is no longer
    joined before returning to the browser (#81 B1 -- that's the whole point
    of running it in the background). But NOT joining it at all let two
    overlapping background threads for the same session race on
    `MemoryStore`: turn B's store can load from disk before turn A's
    background task calls `_flush()`, so B's own later `_flush()` writes a
    stale snapshot that silently drops A's save (Codex review, PR #90). Join
    the PREVIOUS turn's thread(s), bounded, before this turn does anything, so
    writes stay ordered without blocking the turn that's actually in flight.

    Takes a snapshot of every writer currently tracked for this session,
    joins each live one with a bounded timeout, then removes only the ones
    that finished (by identity) -- a writer still alive after the timeout
    stays tracked, so later sweeps/deletes still see it as busy (#148).

    The per-profile lock in `memory/profile_io.py` (every store
    write reloads from disk inside it) closes the "writer still alive after
    the timeout" gap for DATA: a late flush no longer drops anyone's items.
    This join only remains for write ordering and UX."""
    with _bg_threads_lock:
        snapshot = list(_bg_threads.get(session_id, []))
    for t in snapshot:
        if t.is_alive():
            t.join(timeout=_BG_JOIN_TIMEOUT_S)
    with _bg_threads_lock:
        lst = _bg_threads.get(session_id)
        if lst is not None:
            finished = [t for t in snapshot if not t.is_alive()]
            lst[:] = [t for t in lst if not any(t is f for f in finished)]
            if not lst:
                _bg_threads.pop(session_id, None)


def _remember_background_thread(session_id: str, thread: threading.Thread | None) -> None:
    """Appends `thread` to this session's list of live writers, pruning any
    that have already finished. Never replaces a still-live writer (#148: the
    old single-slot dict let a later turn's thread silently overwrite
    tracking of a still-running earlier one). Ignores None and a thread
    already tracked (compared by identity), so registering the same thread
    twice -- e.g. once right after start() and again after it returns -- is a
    no-op."""
    if thread is None:
        return
    with _bg_threads_lock:
        lst = _bg_threads.setdefault(session_id, [])
        lst[:] = [t for t in lst if t.is_alive()]
        if not any(t is thread for t in lst):
            lst.append(thread)


def _is_session_busy(session_id: str) -> bool:
    """A session is BUSY when a turn is in progress on it or any tracked
    background writer for it is still alive (#148)."""
    if _active_turns.get(session_id, 0) > 0:
        return True
    with _bg_threads_lock:
        threads = list(_bg_threads.get(session_id, []))
    return any(t.is_alive() for t in threads)


def _rate_limit_ok(data_dir: Path) -> bool:
    """Cap is keyed per session (`data_dir` is this session's own directory,
    see `_session_dirs`), so one judge filling theirs up never blocks another
    judge's link (#81 A1). Reads/writes that session's own `rate_limit.json`
    directly -- NOT the `_request_log` module global, which would otherwise
    leak one session's count into the next session's first check whenever
    the next session's file doesn't exist yet (Codex review, PR #90)."""
    today = datetime.date.today().isoformat()
    rate_file = data_dir / "rate_limit.json"
    with _lock:
        log: dict[str, int] = {}
        if rate_file.exists():
            try:
                import json
                log = json.loads(rate_file.read_text("utf-8"))
            except Exception:
                log = {}

        count = log.get(today, 0)
        if count >= MAX_DAILY_REQUESTS:
            return False

        log = {today: count + 1}  # keep it small, only need today

        try:
            import json
            data_dir.mkdir(parents=True, exist_ok=True)
            rate_file.write_text(json.dumps(log), "utf-8")
        except Exception:
            pass
        return True


def _will_call_nebius() -> bool:
    """Whether this turn is actually about to spend a Nebius Token Factory
    call -- the cap should count only that, never an empty send or a turn
    that's about to fail for lack of a key. With a key configured, THINK is
    called for every turn, fast-path or not (the fast-path's immediate reply
    is free, but its continuation isn't) -- so this is a key-presence check,
    not a fast-path check (#81 A1, Codex review PR #90)."""
    return bool(os.environ.get("NEBIUS_API_KEY", "").strip())


def _cap_notice(spoke: bool, flagged: bool) -> str:
    """The daily-cap footnote on a capped fast-path turn. It claims only what
    happened: "still played" only when reply audio was produced (a TTS failure
    or timeout leaves the reply as text), and "the family has been
    notified" only when this turn recorded a caregiver flag (Codex review of
    the publish, P2)."""
    said = ("the safety message above still played" if spoke
            else "the safety message above is shown as text because speech was unavailable")
    family = " and the family has been notified" if flagged else ""
    return ("\n\n_This demo has hit its daily request cap, so the companion can't continue "
            f"the conversation until tomorrow -- {said}{family}._")


CAP_NOTICE = _cap_notice(spoke=True, flagged=True)
CAP_BIOMARKERS = "### 📊 Acoustic Biomarkers\n_Rate limited_"


def _audio_upload_path(audio_in: str) -> Path | None:
    """`audio_in` resolved, if it lies under a directory audio legitimately
    comes from: the temp dir (Gradio's upload cache sits there unless
    GRADIO_TEMP_DIR moves it) or the bundled samples. None otherwise. The path
    reaches us from the browser, so realpath + startswith is the containment
    check CodeQL py/path-injection recognises."""
    real = os.path.realpath(audio_in)
    bases = [tempfile.gettempdir(), str(SAMPLES_DIR)]
    if os.environ.get("GRADIO_TEMP_DIR"):
        bases.append(os.environ["GRADIO_TEMP_DIR"])
    for base in bases:
        base = os.path.realpath(base)
        if real.startswith(base + os.sep):
            return Path(real)
    return None


def _guarded_transcribe(audio_in: str, return_metrics: bool) -> tuple[str | None, dict, str | None]:
    """Transcribe `audio_in`, or refuse it with a short retry-or-type-instead
    reply. Returns (transcript, biomarkers, refusal); exactly one of
    transcript/refusal is None. Checks run size -> duration -> transcribe, so
    no ASR CPU is spent on a refused file, and nothing here writes state.
    A missing or zero-byte path skips the probes: transcribe() already returns
    "" for it, which reaches the caller's "Couldn't make out any speech" branch."""
    biomarkers = {"wpm": 0.0, "avg_pause_s": 0.0}
    path = _audio_upload_path(audio_in)
    if path is None:
        print("[hear] refused an audio path outside the upload and sample dirs", file=sys.stderr)
        return None, biomarkers, _transcription_failed(ValueError("audio path"))
    if path.exists() and path.stat().st_size > 0:
        size = path.stat().st_size
        if size > MAX_AUDIO_UPLOAD_BYTES:
            return None, biomarkers, (
                f"That recording is too large ({size / (1024 * 1024):.1f} MB; the limit is "
                f"{MAX_AUDIO_UPLOAD_BYTES / (1024 * 1024):g} MB). Please record a shorter clip, "
                "or type what Dad says instead."
            )
        try:
            seconds = hear.probe_duration(path)
        except hear.AudioInputError as exc:
            return None, biomarkers, _transcription_failed(exc)
        if seconds > MAX_AUDIO_SECONDS:
            return None, biomarkers, (
                f"That recording is {seconds:.0f} seconds long; the limit is {MAX_AUDIO_SECONDS} "
                "seconds. Please record a shorter clip, or type what Dad says instead."
            )
    try:
        if return_metrics:
            transcript, biomarkers = hear.transcribe(path, return_metrics=True)
        else:
            transcript = hear.transcribe(path)
    except Exception as exc:
        return None, biomarkers, _transcription_failed(exc)
    return transcript, biomarkers, None


def _transcription_failed(exc: Exception) -> str:
    # Type name only, never the message: it can carry a file path.
    print(f"[hear] transcription failed: {type(exc).__name__}", file=sys.stderr)
    return "I couldn't make out that recording -- please try recording again, or type what Dad says instead."


def _cap_decision(data_dir: Path, transcript: str) -> tuple[bool, bool]:
    """Returns `(block_turn, allow_hosted_call)` for this turn.

    Invariant: the offline safety fast-path runs before every hosted-call cap;
    a cap only withholds the paid continuation; call `_rate_limit_ok` here and
    nowhere else in a turn. So a capped "I fell down" / "I can't breathe" still
    gets its spoken reply and caregiver flag (`block_turn` False,
    `allow_hosted_call` False), while a capped ordinary utterance keeps the
    daily-cap message (`block_turn` True). `_rate_limit_ok` only counts a turn
    when it is under the cap, so a capped emergency turn never moves the
    counter, and the fast-path check is pure. Any later cap (the process-wide
    one) folds into `capped` here -- never a new early return in a
    handler."""
    fast_triggered = fastpath.check(transcript).triggered
    capped = _will_call_nebius() and not _rate_limit_ok(data_dir)
    return capped and not fast_triggered, not capped


_SESSION_ID_RE = re.compile(r"[0-9a-f]{32}")


def _session_root(session_id: str) -> Path:
    """This session's directory, directly under SESSIONS_DIR. The id is always
    a server-made uuid4 hex, but it reaches us through Gradio State, so it is
    checked before it becomes a path or an rmtree target (#147, CodeQL
    py/path-injection). Raises ValueError for anything else."""
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("invalid session id")
    base = os.path.realpath(SESSIONS_DIR)
    root = os.path.realpath(os.path.join(base, session_id))
    # realpath + startswith is the containment check CodeQL recognises; the
    # dirname check then pins it to exactly one level below SESSIONS_DIR.
    if not root.startswith(base + os.sep):
        raise ValueError("invalid session id")
    if os.path.dirname(root) != base:
        raise ValueError("invalid session id")
    return Path(root)


def _normalize_or_new_session(session_id: str) -> str:
    """A non-empty but malformed/foreign id (e.g. "../x") must not raise its
    way past the crisis fast-path (#149): the public entry points call this
    right after the `session_id_val or _new_session()` line (which only
    catches the falsy/None case) so a bad id is replaced by a fresh session
    before any pipeline work runs, and the turn proceeds normally on it."""
    try:
        _session_root(session_id)
    except ValueError:
        return _new_session()
    return session_id


def _session_dirs(session_id: str) -> tuple[Path, Path]:
    """(data_dir, audio_dir) for one browser session."""
    if SHARED_PROFILE:
        return DATA_DIR, AUDIO_DIR
    root = _session_root(session_id)
    _touch_session(root)
    return root / "data", root / "audio"


def _touch_session(root: Path) -> None:
    """Every turn, memo save and panel poll goes through _session_dirs, so
    this is the activity timestamp the sweeper reads (#146). Writes land in
    data/ and audio/, which never change the root's own mtime.

    Takes `_session_fs_lock` (#148) so a touch landing while the sweeper is
    mid-decision on this same entry waits for the sweeper, rather than racing
    a stat the sweeper already took."""
    with _session_fs_lock:
        try:
            os.utime(root)
        except FileNotFoundError:
            pass  # brand-new session; MemoryStore creates it


def _next_turn_count(data_dir: Path) -> int:
    """Total turns this session, uncapped -- `history` is truncated to
    MAX_HISTORY_TURNS for prompt size, so its length can't drive the
    session-length AI/recording reminder (Codex review, #83 PR #85)."""
    counter_file = data_dir / "turn_count.txt"
    try:
        count = int(counter_file.read_text("utf-8").strip()) + 1
    except (OSError, ValueError):
        count = 1
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        counter_file.write_text(str(count), "utf-8")
    except OSError:
        pass
    return count


def _get_turn_count(data_dir: Path) -> int:
    """Gets the current turn count without incrementing it."""
    counter_file = data_dir / "turn_count.txt"
    try:
        return int(counter_file.read_text("utf-8").strip())
    except (OSError, ValueError):
        return 0


def _log_rmtree_error(func, path, exc_info) -> None:
    """onerror handler for the sweeper's rmtree (#150, #151): log and move on
    to the next entry instead of silently swallowing every failure
    (ignore_errors=True) or letting one bad entry abort the whole sweep."""
    print(f"Session sweeper: failed to remove {path!r} via {func}: {exc_info}")


@contextlib.contextmanager
def _session_active(session_id: str, *, refuse_if_deleted: bool):
    """Registers one in-flight operation on `session_id` (a turn, or a
    caregiver memo save) for the whole `with` body: `_active_turns` is
    incremented and the session touched under `_session_fs_lock`, so
    `_end_session` and the sweeper see it as BUSY and leave its directory
    alone until the body exits (#148). Yields the session root, or
    None under SHARED_PROFILE (no per-session directory, nothing to
    register). `session_id` must already be a valid id.

    `refuse_if_deleted=True` (memo saves): if the literal directory entry
    `SESSIONS_DIR/<id>` is no longer a directory -- the tab closed or the
    sweeper removed it after the id was handed to the browser -- raise
    `SessionGone` BEFORE registering, instead of letting a store recreate
    the household with only the caregiver's private memo in it. Turns pass
    False and keep today's behaviour on a swept session."""
    if SHARED_PROFILE:
        yield None
        return
    root = _session_root(session_id)
    with _session_fs_lock:
        # root is SESSIONS_DIR/<id> after the containment check; isdir follows
        # a symlinked entry the same way, so this is the check _end_session's
        # removal is seen by.
        if refuse_if_deleted and not os.path.isdir(root):
            raise SessionGone(session_id)
        _active_turns[session_id] = _active_turns.get(session_id, 0) + 1
        _touch_session(root)
    try:
        yield root
    finally:
        with _session_fs_lock:
            n = _active_turns.get(session_id, 0) - 1
            if n <= 0:
                _active_turns.pop(session_id, None)
                # No operation is in flight, so no turn holds this lock.
                _session_turn_locks.pop(session_id, None)
            else:
                _active_turns[session_id] = n


def _sweep_stale_sessions() -> None:
    """Backstop for sessions whose delete_callback never ran (process
    restart, crashed tab): anything untouched for SESSION_TTL_S goes.

    Each entry is examined and deleted under `_session_fs_lock` (#148, #150,
    #151): a symlinked alias into another session (even with a valid hex
    name) is skipped before anything resolves it, a stray non-hex-named
    directory is left alone, and a session that is BUSY (a turn in progress
    or a live tracked writer) is skipped regardless of mtime. Only a real,
    non-symlink, correctly-named, idle directory gets stat'd and, if stale,
    removed -- by its own entry path, never a resolved target. Holding the
    lock across the stat+delete is intentional: a touch or turn registration
    for that same entry waits for the sweeper to finish deciding."""
    if SHARED_PROFILE or not SESSIONS_DIR.exists():
        return
    cutoff = time.time() - SESSION_TTL_S
    try:
        entries = list(SESSIONS_DIR.iterdir())
    except FileNotFoundError:
        return
    for child in entries:
        with _session_fs_lock:
            if os.path.islink(child):
                continue
            if not _SESSION_ID_RE.fullmatch(child.name):
                continue
            try:
                if not child.is_dir():
                    continue
                if _is_session_busy(child.name):
                    continue
                if child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, onerror=_log_rmtree_error)
            except FileNotFoundError:
                pass


def _start_session_sweeper(
    interval_s: float | None = None,
    stop_event: threading.Event | None = None,
) -> threading.Thread | None:
    """Sweep orphaned sessions at startup and without requiring a visitor."""
    global _session_sweeper_started
    if SHARED_PROFILE:
        return None
    with _session_sweeper_lock:
        if _session_sweeper_started and stop_event is None:
            return None
        if stop_event is None:
            _session_sweeper_started = True

    interval = interval_s if interval_s is not None else GRADIO_CACHE_SWEEP[0]
    event = stop_event or threading.Event()

    def sweep() -> None:
        _sweep_stale_sessions()
        while not event.wait(interval):
            _sweep_stale_sessions()

    thread = threading.Thread(target=sweep, name="session-retention-sweeper", daemon=True)
    thread.start()
    return thread


def _new_session() -> str:
    """Fresh household, pre-briefed with the demo memo so a judge's very
    first remark has caregiver context to recall (beat 2 works on click one)."""
    _sweep_stale_sessions()
    session_id = DEFAULT_PROFILE_ID if SHARED_PROFILE else uuid.uuid4().hex
    data_dir, _ = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    facts = split_memo_facts(DEMO_MEMO)  # one shared splitter
    # A seed never re-adds a line already in the store, superseded included:
    # with FY_SHARED_PROFILE=1 a new tab re-runs this over a household whose
    # caregiver already changed 4 PM to 6 PM, and re-adding 4 PM would
    # supersede the update (Codex review).
    seen = {i.text for i in store.all() if i.source == "caregiver_memo"}
    for line in facts:
        if line not in seen:
            store.add(line, source="caregiver_memo", supersede=False)  # a seed never replaces a caregiver fact
    return session_id


def _end_session(session_id: str | None) -> None:
    """Gradio's delete_callback on tab close. Validates the id BEFORE
    touching `_bg_threads` (#148: the old code popped the tracking entry even
    for an id that then failed validation). Under `_session_fs_lock`: a
    symlinked alias (even with a valid hex name) is left untouched -- never
    resolved, never deleted -- and a BUSY session (a turn in progress, or any
    live tracked writer) is left fully alone, `_bg_threads` included, so the
    sweeper can still see it as busy and clean up the tracking once the TTL
    and the writer both clear (#148, #150, #151).

    `_session_root()` returns a REALPATH -- for a symlinked entry, that's
    already the resolved target, not the entry itself, so checking
    `os.path.islink()` on it is checking the wrong path (it is never a link).
    The entry under `SESSIONS_DIR` has to be inspected and deleted by its own
    (unresolved) path, exactly like the sweeper does, or a same-directory
    alias (a symlink whose target is itself another real session under
    `SESSIONS_DIR`) sails through the realpath+containment check in
    `_session_root()` and gets its *target* deleted."""
    if not session_id or SHARED_PROFILE:
        return
    try:
        _session_root(session_id)  # validates id shape and resolved containment only
    except ValueError:
        return  # a Gradio delete callback: never raise, never delete outside SESSIONS_DIR
    entry = SESSIONS_DIR / session_id  # the literal, unresolved directory entry
    with _session_fs_lock:
        if os.path.islink(entry):
            return
        if _is_session_busy(session_id):
            return
        with _bg_threads_lock:
            _bg_threads.pop(session_id, None)
        shutil.rmtree(entry, ignore_errors=True)


def _clear_session_audio(audio_dir: Path) -> None:
    """Previous turns' reply audio has already been handed to Gradio (which
    copies outputs into its own cache), so nothing on our side needs it."""
    if SHARED_PROFILE or not audio_dir.exists():
        return
    for wav in audio_dir.glob("*.wav"):
        wav.unlink(missing_ok=True)


def init_session() -> tuple[str, str]:
    session_id = _new_session()
    return session_id, _format_caregiver_panel(session_id)


_SAMPLE_CARD_GROUPS = (
    ("persona", "Who Dad is"),
    ("family", "Family and visitors"),
    ("likes", "Likes"),
    ("routine", "Daily routine"),
    ("reminder", "Medication reminders"),
    ("avoid", "Topics to avoid"),
    ("health", "Caregiver notes (never spoken to Dad)"),
)


def _sample_family_loaded(store: MemoryStore, now: float) -> bool:
    """True once the one-click seed (caregiver.SAMPLE_FAMILY) is in this
    session's store: its persona line is an active caregiver_memo item.
    Checked against the store, never a flag file, so the sweep/_end_session
    delete path needs nothing extra."""
    anchor = sample_family_texts()[0]
    return any(
        item.text == anchor and item.source == "caregiver_memo" and item.is_active(now)
        for item in store.all()
    )


def _format_sample_family_card(store: MemoryStore, now: float) -> list[str]:
    """The caregiver-side profile card for the seeded household, grouped by
    the seed's own groups, labelled fictional, with every reminder shown as a
    plain schedule line attributed to the caregiver by name -- never dosing
    advice (docs/PRD.md non-goal; caregiver.validate_sample_profile is the
    guard at load time). Only items actually active in the store are listed,
    so the card never claims more than Briefed memory holds."""
    active = {
        item.text for item in store.all()
        if item.source == "caregiver_memo" and item.is_active(now)
    }
    caregiver = SAMPLE_FAMILY["caregiver_name"]
    lines = [
        f"### 🏠 {SAMPLE_FAMILY_LABEL}",
        f"_**Fictional sample data** -- loaded with one click so you can see a caregiver-configured "
        f"household before anyone speaks. Entered as {caregiver}'s notes; reminders are schedule items only, "
        f"not medical advice._",
    ]
    for group, heading in _SAMPLE_CARD_GROUPS:
        texts = [text for g, text, _p in SAMPLE_FAMILY["items"] if g == group and text in active]
        if not texts:
            continue
        lines.append(f"**{heading}**")
        for text in texts:
            if group == "reminder":
                lines.append(f"- 🔔 {text} _(reminder set by {caregiver})_")
            elif group == "health":
                lines.append(f"- 🔒 {text}")
            else:
                lines.append(f"- {text}")
    lines.append("")
    return lines


# Shown directly above "### Briefed memory" in every render of the caregiver
# panel (the placeholder before the session exists too), so a judge never
# mistakes the pre-briefed household for a real family.
SAMPLE_HOUSEHOLD_LINE = "_Sample household (fictional), pre-briefed by Sarah_"
_PANEL_PLACEHOLDER = (
    "_Setting up your demo household..._\n\n"
    f"{SAMPLE_HOUSEHOLD_LINE}\n\n### Briefed memory\n_(loading...)_"
)



# With no outbound channel configured (the default, and always on the hosted
# Space) a flag is only written to the local flags file this panel polls: no
# caregiver is contacted. Every judge-visible label then says "simulated
# caregiver alert" and where it appears, and never claims a send (#201's
# senders are the only thing that contacts anyone).
SIMULATED_ALERT_STATUS = (
    "Simulated caregiver alert -- in this demo it appears on this panel only; "
    "no caregiver is contacted"
)
SIMULATED_ALERT_CARD = "> 🚨 **HIGH PRIORITY SAFETY ALERT (simulated caregiver alert, shown on this demo panel)**"
SIMULATED_ALERT_SUMMARY = "⚠️ **Simulated caregiver alert raised**"
SIMULATED_DISCLOSURE_NOTE = (
    "\n\n*(📢 Honest Safety Disclosure: simulated caregiver alert raised on the "
    "caregiver panel, with Dad's knowledge; demo: nothing is sent, "
    f"{DEFAULT_CAREGIVER_NAME} would be notified)*"
)
LIVE_DISCLOSURE_NOTE = (
    "\n\n*(📢 Honest Safety Disclosure: caregiver alert raised on the caregiver "
    "panel, with Dad's knowledge; its outbound notification status shows there)*"
)


def _channel_off() -> bool:
    """True when no outbound notification channel is configured (#201)."""
    return isinstance(notify.get_notifier(), notify.NullNotifier)


def _alert_is_simulated(flag) -> bool:
    """A flag nobody was sent: no channel, and no send attempted for it."""
    return getattr(flag, "notified", None) is None and _channel_off()


def _disclosure_note() -> str:
    """The note under a flagged turn: simulated unless a channel is on."""
    return SIMULATED_DISCLOSURE_NOTE if _channel_off() else LIVE_DISCLOSURE_NOTE


def _notification_preview(flag) -> str:
    """What the caregiver would be sent, for a flag nobody was sent (#201): the
    exact `notify.build_message` body (same redaction, no transcript text),
    plus an honest line that nothing went out. "" when a channel is active."""
    if not _alert_is_simulated(flag):
        return ""
    why = ("notifications are off in this demo" if os.environ.get("SPACE_ID")
           else "no notification channel is set up")
    msg = notify.build_message(
        flag, os.environ.get("FY_NOTIFY_HOUSEHOLD_LABEL") or notify.DEFAULT_HOUSEHOLD_LABEL)
    body = "\n".join(f"> {line}".rstrip() for line in msg.body.split("\n"))
    return (f"> **Preview — the message {DEFAULT_CAREGIVER_NAME} would receive:**\n"
            f"> *Not sent: {why}*\n>\n> **{msg.subject}**\n>\n{body}\n")


def _notification_status(flag) -> str:
    """Outbound-notification state of one flag (#201): sent, failed, or ""
    when no send was attempted -- never a claim the code did not make."""
    notified = getattr(flag, "notified", None)
    if notified is True:
        return "📨 Notification sent to caregiver"
    if notified is False:
        return "⚠️ Notification failed"
    return ""

def _format_caregiver_panel(session_id: str | None) -> str:
    """Reads straight from disk every call -- this is what makes it a live
    panel rather than a snapshot: whatever this session's turns (or, with
    FY_SHARED_PROFILE=1, main.py) wrote is reflected here within one poll
    interval (see the Timer below)."""
    if not session_id:
        return _PANEL_PLACEHOLDER
    try:
        data_dir, _ = _session_dirs(session_id)
    except ValueError:
        # Malformed/foreign id (#149) -- same placeholder as "no session yet",
        # never an exception out of a polled panel.
        return _PANEL_PLACEHOLDER
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)

    flag_items = flags.all()
    distress_flags = [f for f in flag_items if f.severity in HIGH_PRIORITY_SEVERITIES]
    turn_count = _get_turn_count(data_dir)
    
    simulated = bool(distress_flags) and _alert_is_simulated(distress_flags[-1])
    if not distress_flags:
        wellbeing_status = "🟢 **Calm · No safety concerns**"
    elif simulated:
        wellbeing_status = SIMULATED_ALERT_SUMMARY
    else:
        wellbeing_status = "⚠️ **Safety alert raised**"
    wellbeing_summary = f"> **Today:** {turn_count} conversation{'s' if turn_count != 1 else ''} · {wellbeing_status}\n"

    lines = [
        # A blank line before "---" matters: text immediately followed by "---"
        # is a Markdown setext heading (renders <h2>), which is how the pledge
        # became the largest text on the page (#83, #80 2.B2) even un-bolded.
        "🛡️ Peace of mind without surveillance. ForeverYours summarizes important updates and medical/safety flags. Turn transcripts (not audio) go to Nebius Token Factory to generate replies and run the safety check; see [Safety & privacy design](https://github.com/miravena/foreveryours/blob/main/docs/SAFETY_AND_PRIVACY.md).",
        "",
        "---",
        wellbeing_summary,
    ]
    
    if distress_flags:
        latest = distress_flags[-1]
        disclosed = "✅ **Disclosed to Senior in conversation**" if latest.disclosed_to_senior else "⚠️ **NOT yet disclosed**"
        status = SIMULATED_ALERT_STATUS if simulated else _notification_status(latest)
        title = SIMULATED_ALERT_CARD if simulated else "> 🚨 **HIGH PRIORITY SAFETY ALERT**"
        lines.append(
            f"{title}\n"
            f"> **Event:** {latest.text}\n"
            f"> **Severity:** `{latest.severity.upper()}`" + (f" | **Status:** {status}" if status else "") + "\n"
            f"> **Disclosure:** {disclosed}\n"
        )
        preview = _notification_preview(latest)
        if preview:
            lines.append(preview)

    lines.append("### What ForeverYours has told you")
    if not flag_items:
        lines.append("_No flags yet. You'll see something here the moment Dad says something worth knowing about._")
    for flag in reversed(flag_items):  # newest first -- this is the thing a caregiver glances at
        disclosed = "✅ Dad was told" if flag.disclosed_to_senior else "⚠️ NOT yet disclosed to Dad"
        status = _notification_status(flag)
        origin = _flag_origin(flag)
        lines.append(
            f"- **({flag.severity})** {flag.text}\n  {disclosed}"
            + (f" · {status}" if status else "")
            + (f" · {origin}" if origin else "")
        )

    now = time.time()
    sample_loaded = _sample_family_loaded(store, now)
    if sample_loaded:
        lines.append("")
        lines.extend(_format_sample_family_card(store, now))

    lines.append("")
    lines.append(SAMPLE_HOUSEHOLD_LINE)
    lines.append("\n### Briefed memory")
    all_items = store.all()
    items = _dedupe_briefed_memory(
        [item for item in all_items if _caregiver_panel_may_show(item)], now
    )
    if sample_loaded:
        # The seed is listed once, on the card above, grouped and labelled
        # fictional (same one-listing rule).
        seed_texts = set(sample_family_texts())
        items = [item for item in items if not (item.source == "caregiver_memo" and item.text in seed_texts)]
        lines.append(f"_(plus the {SAMPLE_FAMILY_LABEL.lower()} above)_")
    if not items:
        lines.append("_(nothing briefed yet)_")
    for item in items:
        # Privacy badge
        is_private = (item.privacy == PrivacyLevel.CAREGIVER_ONLY.value)
        priv_badge = "🔒 **[Caregiver Only — Hidden from Dad]** " if is_private else ""

        # Scope & Status badge
        if item.status == "superseded":
            badge = "🔄 _[Superseded]_ "
            desc = f"~~{item.text}~~"
            if item.superseded_by and _replacement_may_show(all_items, item.superseded_by):
                desc += f" → *Replaced by: {item.superseded_by}*"
        elif item.expires_at is not None:
            remaining = item.expires_at - now
            if remaining <= 0:
                badge = "⌛ _[Expired]_ "
                desc = f"~~{item.text}~~"
            else:
                mins = max(1, int(remaining // 60))
                time_str = f"{mins}m" if mins < 60 else f"{mins // 60}h {mins % 60}m"
                badge = f"🕒 **[Temporary — expires in {time_str}]** "
                desc = item.text
        elif item.scope == MemoryScope.HISTORICAL.value:
            badge = "📜 _[Historical]_ "
            desc = item.text
        else:
            badge = "🟢 **[Permanent]** "
            desc = item.text

        lines.append(f"- {badge}{priv_badge}{desc} `({item.source})`")
        
    lines.append("\n---\n_ForeverYours shows safety-relevant events, never surveillance. Private conversations stay private._")
    return "\n".join(lines)


def _format_mobile_alert_strip(session_id: str | None) -> str:
    """Short version of the caregiver panel's top alert, shown above the mic
    only on narrow screens (CSS below) -- on a phone the caregiver column is
    stacked below the whole senior column, so without this a flag is invisible
    until the judge scrolls past everything (#83, #80 2.B2)."""
    if not session_id:
        return ""
    try:
        data_dir, _ = _session_dirs(session_id)
    except ValueError:
        return ""  # malformed/foreign id (#149) -- never raise out of a polled strip
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
    distress_flags = [f for f in flags.all() if f.severity in HIGH_PRIORITY_SEVERITIES]
    if not distress_flags:
        return ""
    latest = distress_flags[-1]
    disclosed = "told Dad already" if latest.disclosed_to_senior else "not yet disclosed to Dad"
    if _alert_is_simulated(latest):
        return f"🚨 **Simulated caregiver alert:** {latest.text} ({disclosed}; shown on the caregiver panel only)"
    return f"🚨 **Caregiver alert:** {latest.text} ({disclosed})"


def _combine_audio_chunks(audio_paths: list[Path], out_dir: Path) -> Path | None:
    """Concatenate sentence-level audio WAV chunks into one unified audio file
    so the user hears the entire companion response."""
    if not audio_paths:
        return None
    if len(audio_paths) == 1:
        return audio_paths[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    combined_path = out_dir / f"combined_{int(time.time() * 1000)}.wav"
    try:
        with wave.open(str(audio_paths[0]), "rb") as first_wav:
            params = first_wav.getparams()
        with wave.open(str(combined_path), "wb") as out_wav:
            out_wav.setparams(params)
            for p in audio_paths:
                with wave.open(str(p), "rb") as w:
                    out_wav.writeframes(w.readframes(w.getnframes()))
        return combined_path
    except Exception as exc:
        print(f"Failed to combine audio chunks ({exc}); returning first chunk as fallback.")
        return audio_paths[0]


def _chunk_readable(path: Path) -> bool:
    """Whether a TTS chunk can actually be opened and is non-empty -- a guarded
    read, not an existence check: a missing file, an empty one, a directory or
    anything else that raises `OSError` on open/read returns False.
    The streaming generator yields a chunk's path to the browser only when
    this holds, so Gradio's `stream_output` is never handed a path it cannot
    open, and a disclosure whose chunk could not be delivered is refused
    (recorded undisclosed) instead of attested."""
    try:
        with open(path, "rb") as f:
            return len(f.read(12)) > 0
    except OSError:
        return False


def run_demo_turn(
    audio_in: str | None = None,
    text_in_or_history: str | list[dict] | None = None,
    history_or_session: list[dict] | str | None = None,
    session_id: str | None = None,
    simulated_time_in: str | None = None,
    is_proactive: bool = False,
    trigger_type: str = "silence",
) -> tuple[str, str | None, list[dict], str, str, str, str, None]:
    legacy_form = isinstance(text_in_or_history, list)
    if isinstance(text_in_or_history, list):
        history = text_in_or_history
        session_id_val = history_or_session if isinstance(history_or_session, str) else session_id
        actual_text = None # audio mode fallback
        simulated_time_str = "Morning (Default)"
    else:
        actual_text = text_in_or_history
        history = history_or_session if isinstance(history_or_session, list) else []
        session_id_val = session_id
        simulated_time_str = simulated_time_in or "Morning (Default)"

    # A missing session_id here means the Gradio State expired mid-demo (#83,
    # #80 3.C7): a fresh, unbriefed household is about to answer, so say so
    # rather than silently looking like a reset conversation.
    session_expired = _session_really_expired(session_id_val, history, legacy_form)
    session_id_val = session_id_val or _new_session()
    if not SHARED_PROFILE:
        session_id_val = _normalize_or_new_session(session_id_val)

    simulated_hour = 10
    if "Sundowning" in simulated_time_str:
        simulated_hour = 18
    elif "Night" in simulated_time_str:
        simulated_hour = 23

    out = _run_demo_turn(audio_in, actual_text, history, session_id_val, simulated_hour, is_proactive=is_proactive, trigger_type=trigger_type)
    if session_expired:
        out = (
            _RESET_NOTICE + "\n\n" + out[0],
            *out[1:],
        )
    # Clear audio_in on every turn: otherwise a loaded sample clip stays in the
    # recorder and a later Send with an empty textbox silently re-transcribes
    # the old clip (#83, #80 2.B3).
    return (*out, session_id_val, "", None)


def run_proactive_turn(history, session, sim_time, trigger_type):
    """Handler for the four proactive buttons: same 8 outputs as run_demo_turn."""
    return run_demo_turn(None, None, history, session, sim_time, is_proactive=True, trigger_type=trigger_type)



def run_demo_turn_streaming(
    audio_in: str | None = None,
    text_in_or_history: str | list[dict] | None = None,
    history_or_session: list[dict] | str | None = None,
    session_id: str | None = None,
    simulated_time_in: str | None = None,
    is_proactive: bool = False,
    trigger_type: str = "silence",
):
    """Public Gradio entry point. Normalizes the session id and registers the
    turn as in-progress (#148, #149) BEFORE any other work, including the
    "thinking" yield -- then delegates to `_run_demo_turn_streaming_impl` for
    the actual turn. The `finally` here runs even if the browser disconnects
    and Gradio closes this generator mid-turn (`gen.close()` throws
    GeneratorExit at the suspended yield, which unwinds through this
    `finally` on its way out), so `_active_turns` is always cleaned up."""
    legacy_form = isinstance(text_in_or_history, list)
    if isinstance(text_in_or_history, list):
        history = text_in_or_history
        session_id_val = history_or_session if isinstance(history_or_session, str) else session_id
        actual_text = None
        simulated_time_str = "Morning (Default)"
    else:
        actual_text = text_in_or_history
        history = history_or_session if isinstance(history_or_session, list) else []
        session_id_val = session_id
        simulated_time_str = simulated_time_in or "Morning (Default)"

    session_expired = _session_really_expired(session_id_val, history, legacy_form)
    session_id_val = session_id_val or _new_session()
    if not SHARED_PROFILE:
        session_id_val = _normalize_or_new_session(session_id_val)

    simulated_hour = 10
    if "Sundowning" in simulated_time_str:
        simulated_hour = 18
    elif "Night" in simulated_time_str:
        simulated_hour = 23

    # SHARED_PROFILE=True keeps the old behaviour: root is None, so there is
    # no per-session lock -- there is only one shared profile to begin with.
    with _session_active(session_id_val, refuse_if_deleted=False) as root:
        turn_lock = None
        if root is not None:
            with _session_fs_lock:
                # Registered above, so the count is > 0 and nobody pops it.
                turn_lock = _session_turn_locks.setdefault(session_id_val, threading.Lock())
        # One consumer per call. Closing it in this `finally` (which a
        # browser disconnect's GeneratorExit also unwinds through) refuses every
        # chunk still pending, so nothing is attested to a closed stream.
        consumer = _ChunkConsumer()
        acquired = False
        try:
            # Different sessions overlap (Gradio's "senior_turn" limit
            # bounds them); a second turn for THIS session waits here until the
            # first finishes. Acquired outside _session_fs_lock (#148 lock order).
            if turn_lock is not None:
                turn_lock.acquire()
                acquired = True
            yield from _run_demo_turn_streaming_impl(
                audio_in, actual_text, history, session_id_val, simulated_hour,
                session_expired, is_proactive, trigger_type, consumer=consumer,
            )
        finally:
            if acquired:
                turn_lock.release()
            consumer.close()


def _run_demo_turn_streaming_impl(
    audio_in: str | None,
    actual_text: str | None,
    history: list[dict],
    session_id_val: str,
    simulated_hour: int,
    session_expired: bool,
    is_proactive: bool,
    trigger_type: str,
    consumer: "_ChunkConsumer | None" = None,
):
    import queue
    import threading
    from pathlib import Path

    if consumer is None:
        consumer = _ChunkConsumer()

    yield (
        "_Companion is thinking..._",
        gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
    )

    data_dir, audio_dir = _session_dirs(session_id_val)
    _join_previous_turn(session_id_val)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
    panel = lambda: _format_caregiver_panel(session_id_val)  # noqa: E731
    biomarkers = {"wpm": 0.0, "avg_pause_s": 0.0}

    if is_proactive:
        transcript = "[PROACTIVE_TRIGGER]"
    elif actual_text and actual_text.strip():
        transcript = actual_text.strip()
    elif audio_in:
        transcript, biomarkers, refusal = _guarded_transcribe(audio_in, True)
        if refusal is not None:  # refused/failed audio writes nothing
            out = (refusal, None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_")
            if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
            yield (*out, session_id_val, "", None)
            return
    else:
        out = ("Record audio or type what Dad says first.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_")
        if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
        yield (*out, session_id_val, "", None)
        return

    if not transcript.strip() and not is_proactive:
        out = ("Couldn't make out any speech or text -- try again.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_")
        if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
        yield (*out, session_id_val, "", None)
        return

    block_turn, allow_hosted_call = _cap_decision(data_dir, transcript)
    if block_turn:
        out = ("This demo has hit its daily request cap -- please try again tomorrow.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_Rate limited_")
        if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
        yield (*out, session_id_val, "", None)
        return

    # Deletes the PREVIOUS turn's *.wav only: every file this turn yields
    # still exists when Gradio's stream_output reads it.
    _clear_session_audio(audio_dir)

    def _on_chunk(sentence: str, chunk_path: Path):
        # Returns the chunk's ack without blocking (False if the
        # stream already closed). It resolves True only after the generator
        # below dequeued AND yielded the chunk; `_speak_disclosure` waits on
        # it before attesting, the main reply's synthesis never does.
        return consumer.submit(sentence, chunk_path)

    def _worker():
        try:
            res = run_turn(
                transcript, store, flags, audio_dir, caregiver_name=DEFAULT_CAREGIVER_NAME, history=history, simulated_hour=simulated_hour, is_proactive=is_proactive, trigger_type=trigger_type,
                enable_perseveration_flag=DEV_MODE,
                on_chunk=_on_chunk,
                allow_hosted_call=allow_hosted_call,
            )
            # Hand off to the background AUDIT/memory-extraction thread BEFORE
            # consumer.put(("DONE", ...)) (#148): if the generator was already closed
            # (browser disconnected) and nothing ever reads "DONE", that
            # writer must still be tracked. _remember_background_thread
            # ignores a thread already tracked (identity), so the later
            # registration below (after DONE) is a no-op.
            _remember_background_thread(session_id_val, res.background_thread)
            consumer.put(("DONE", res))
        except Exception as exc:
            consumer.put(("ERROR", exc))

    t = threading.Thread(target=_worker)
    t.start()
    _remember_background_thread(session_id_val, t)

    current_reply_text = ""
    spoke = False  # did any reply chunk actually reach the browser
    while True:
        msg = consumer.get()
        if msg[0] == "DONE":
            result = msg[1]
            break
        elif msg[0] == "ERROR":
            exc = msg[1]
            err = str(exc)
            if "NEBIUS_API_KEY" in err or "NebiusNotConfigured" in type(exc).__name__:
                out = (
                    f'**Dad said:** "{transcript}"\n\n'
                    f"⚠️ *The live AI model isn't reachable right now -- the offline safety fast-path still works.*\n\n"
                    f"💡 **Try an emergency phrase:** Say or type *\"I fell down earlier and I'm scared\"* - the safety fast-path runs completely offline with real spoken voice!",
                    None,
                    history,
                    panel(),
                    "### 📊 Acoustic Biomarkers\n_Awaiting API Key_",
                )
                if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
                yield (*out, session_id_val, "", None)
                return
            
            print(f"Pipeline error processing turn: {type(exc).__name__}")
            import traceback
            traceback.print_exc()
            out = (
                f'**Dad said:** "{transcript}"\n\n⚠️ *I\'m sorry, I ran into an unexpected error processing that.*',
                None,
                history,
                panel(),
                "### 📊 Acoustic Biomarkers\n_Error_",
            )
            if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
            yield (*out, session_id_val, "", None)
            return
        elif msg[0] == "CHUNK":
            _, sentence, chunk_path, ack = msg
            current_reply_text += sentence + " "
            # This chunk's own audio, once. The reply player streams,
            # so it appends each yielded chunk; re-sending the accumulated
            # recording made it restart from the first sentence.
            reply_audio = str(chunk_path) if _chunk_readable(chunk_path) else None
            spoke = spoke or reply_audio is not None
            
            if is_proactive:
                transcript_and_reply = f'**ForeverYours initiated:**\n\n"{current_reply_text.strip()}"'
            else:
                transcript_and_reply = f'**Dad said:** "{transcript}"\n\n**Companion replied:** "{current_reply_text.strip()}"'
                
            biomarkers_panel = f"### 📊 Acoustic Biomarkers\n- Words per minute: {biomarkers.get('wpm', 0):.0f}\n- Avg pause: {biomarkers.get('avg_pause_s', 0.0):.1f}s"
            
            out = (transcript_and_reply, reply_audio, history, panel(), biomarkers_panel)
            if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
            yield (*out, session_id_val, "", None)
            consumer.accept(ack, reply_audio is not None)

    _remember_background_thread(session_id_val, result.background_thread)

    if not result.is_fallback:
        if is_proactive:
            new_history = history + [{"role": "assistant", "content": result.reply_text}]
        else:
            new_history = history + [
                {"role": "user", "content": transcript, "ts": time.time()},
                {"role": "assistant", "content": result.reply_text},
            ]
        new_history = new_history[-(MAX_HISTORY_TURNS * 2) :]
    else:
        new_history = history

    # Every sentence already went out on its own CHUNK yield; the
    # DONE-final yield carries no audio (re-sending it is the replay bug), and
    # the cap notice's "still played" rests on `spoke` (a chunk delivered).

    if is_proactive:
        transcript_and_reply = f'**ForeverYours initiated:**\n\n"{result.reply_text}"'
    else:
        transcript_and_reply = f'**Dad said:** "{transcript}"\n\n**Companion replied:** "{result.reply_text}"'
    
    if result.caregiver_flag:
        transcript_and_reply += _disclosure_note()
    
    turn_count = _next_turn_count(data_dir)
    if turn_count % REMINDER_EVERY_N_TURNS == 0:
        transcript_and_reply += "\n\n*(🤖 Reminder: this is an AI companion, and this conversation is recorded and transcribed.)*"

    wpm = biomarkers.get("wpm", 0.0)
    pause = biomarkers.get("avg_pause_s", 0.0)
    if not allow_hosted_call:
        transcript_and_reply += _cap_notice(spoke, bool(result.caregiver_flag))
        biomarker_str = CAP_BIOMARKERS
    elif wpm > 0:
        biomarker_str = f"### 📊 Acoustic Biomarkers\n- **Speaking Rate:** {wpm} wpm\n- **Avg Pause:** {pause}s\n\n_Computed from this clip only; nothing is tracked across sessions._"
    else:
        biomarker_str = "### 📊 Acoustic Biomarkers\n_Calculated from live voice input only_"

    out = (transcript_and_reply, None, new_history, panel(), biomarker_str)
    if session_expired: out = (_RESET_NOTICE + "\n\n" + out[0], *out[1:])
    # The DONE-final yield: exactly once, immediately.
    yield (*out, session_id_val, "", None)

    # Drain. The background AUDIT/extraction thread may speak a
    # disclosure line seconds after DONE; keep consuming until it finishes or
    # _BG_JOIN_TIMEOUT_S elapses, so that audio reaches the browser and only
    # a chunk the browser actually got is attested. Each late yield is
    # additive: same final history and text, fresher caregiver panel, and
    # that disclosure chunk's own audio, once.
    bg = result.background_thread
    deadline = time.monotonic() + _BG_JOIN_TIMEOUT_S
    late_yields = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if (bg is None or not bg.is_alive()) and consumer.queue.empty():
            break
        try:
            msg = consumer.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        if msg[0] != "CHUNK":
            continue
        _, _sentence, chunk_path, ack = msg
        # An unreadable chunk yields no audio and is refused (recorded
        # undisclosed) -- the browser never heard that line.
        late_audio = str(chunk_path) if _chunk_readable(chunk_path) else None
        late = (out[0], late_audio, new_history, panel(), biomarker_str)
        yield (*late, session_id_val, "", None)
        consumer.accept(ack, late_audio is not None)
        late_yields += 1
        out = late
    consumer.close()
    # The flag/lifestyle note is persisted only after its ack, i.e. after the
    # yield that carried its audio rendered the panel: one panel-only refresh
    # (same history, no audio -- every chunk already went out) once the
    # background thread has finished.
    if late_yields and (bg is None or not bg.is_alive()):
        yield (out[0], None, new_history, panel(), biomarker_str, session_id_val, "", None)

def run_proactive_turn_streaming(history, session, sim_time, trigger_type):
    yield from run_demo_turn_streaming(None, None, history, session, sim_time, is_proactive=True, trigger_type=trigger_type)




def _run_demo_turn(
    audio_in: str | None,
    text_in: str | None,
    history: list[dict],
    session_id: str,
    simulated_hour: int = 10,
    is_proactive: bool = False,
    trigger_type: str = "silence",
) -> tuple[str, str | None, list[dict], str, str]:
    """Registers the turn as in-progress (#148) before any other work, and
    always deregisters it in `finally` -- every branch below returns a
    value, so `finally` covers every one of them, including the early
    "no speech detected" returns. `session_id` must already be a validated
    id by this point (the public wrappers normalize before calling in)."""
    with _session_active(session_id, refuse_if_deleted=False):
        return _run_demo_turn_impl(audio_in, text_in, history, session_id, simulated_hour, is_proactive=is_proactive, trigger_type=trigger_type)


def _run_demo_turn_impl(
    audio_in: str | None,
    text_in: str | None,
    history: list[dict],
    session_id: str,
    simulated_hour: int = 10,
    is_proactive: bool = False,
    trigger_type: str = "silence",
) -> tuple[str, str | None, list[dict], str, str]:
    data_dir, audio_dir = _session_dirs(session_id)
    _join_previous_turn(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
    panel = lambda: _format_caregiver_panel(session_id)  # noqa: E731

    biomarkers = {"wpm": 0.0, "avg_pause_s": 0.0}

    if is_proactive:
        transcript = "[PROACTIVE_TRIGGER]"
    elif text_in and text_in.strip():
        transcript = text_in.strip()
    elif audio_in:
        transcript, biomarkers, refusal = _guarded_transcribe(audio_in, True)
        if refusal is not None:  # refused/failed audio writes nothing
            return refusal, None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_"
    else:
        return "Record audio or type what Dad says first.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_"

    if not transcript.strip() and not is_proactive:
        return "Couldn't make out any speech or text -- try again.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_"

    # Cap only what's actually about to spend a Nebius call -- not the empty
    # sends and no-key misses handled above. A fast-path utterance at the cap
    # still runs, with only its THINK continuation withheld (#81 A1).
    block_turn, allow_hosted_call = _cap_decision(data_dir, transcript)
    if block_turn:
        return (
            "This demo has hit its daily request cap -- please try again tomorrow.",
            None,
            history,
            panel(),
            "### 📊 Acoustic Biomarkers\n_Rate limited_",
        )

    _clear_session_audio(audio_dir)
    try:
        result = run_turn(
            transcript, store, flags, audio_dir, caregiver_name=DEFAULT_CAREGIVER_NAME, history=history, simulated_hour=simulated_hour, is_proactive=is_proactive, trigger_type=trigger_type,
            enable_perseveration_flag=DEV_MODE,
            allow_hosted_call=allow_hosted_call,
        )
    except Exception as exc:
        err = str(exc)
        if "NEBIUS_API_KEY" in err or "NebiusNotConfigured" in type(exc).__name__:
            return (
                f'**Dad said:** "{transcript}"\n\n'
                f"⚠️ *The live AI model isn't reachable right now -- the offline safety fast-path still works.*\n\n"
                f"👉 **Try an emergency phrase:** Say or type *\"I fell down earlier and I'm scared\"* — the safety fast-path runs completely offline with real spoken voice!",
                None,
                history,
                panel(),
                "### 📊 Acoustic Biomarkers\n_Awaiting API Key_",
            )
        
        print(f"Pipeline error processing turn: {type(exc).__name__}")
        import traceback
        traceback.print_exc()
        return (
            f'**Dad said:** "{transcript}"\n\n⚠️ *I\'m sorry, I ran into an unexpected error processing that.*',
            None,
            history,
            panel(),
            "### 📊 Acoustic Biomarkers\n_Error_",
        )

    # AUDIT + memory extraction now run fully off the critical path (#81 B1):
    # no join here before returning. #11 row 8's decision was to keep a
    # bounded join "only on turns where the crisis tier fired" -- but
    # `background_thread` is only ever set on NON-fast-path turns
    # (`orchestrator.run_turn`: the background task is created iff
    # `not fast.triggered`; the outbound-notification senders (#201) live in
    # `result.notify_threads` and are never joined, so a slow mail server
    # cannot stall this or the next turn), so that condition can never be true alongside a
    # real thread to join; implementing it literally was dead code (Codex
    # review, PR #90). Flagged back on #11: if AUDIT flags a reply unsafe
    # after this returns, its spoken disclosure is generated but has already
    # missed this turn's `audio_out`. The STREAMING path closes that gap
    # (It keeps consuming after DONE and attests only chunks the
    # browser received); this non-streaming path passes no `on_chunk`, so
    # such a disclosure is still recorded undisclosed, honestly.
    # `_join_previous_turn` (called at the top of this function, on
    # the NEXT turn) still bounds how long a stale thread can run before the
    # next turn's MemoryStore write would otherwise race it.
    _remember_background_thread(session_id, result.background_thread)

    if not result.is_fallback:
        if is_proactive:
            new_history = history + [{"role": "assistant", "content": result.reply_text}]
        else:
            new_history = history + [
                {"role": "user", "content": transcript, "ts": time.time()},
                {"role": "assistant", "content": result.reply_text},
            ]
        new_history = new_history[-(MAX_HISTORY_TURNS * 2) :]
    else:
        new_history = history

    combined_audio = _combine_audio_chunks(result.audio_paths, audio_dir)
    reply_audio = str(combined_audio) if combined_audio else None
    # A proactive turn has no senior utterance, so the panel must NOT print a
    # `Dad said:` line attributing the internal trigger token to the senior
    # (#65). Render it as an assistant/system-initiated message instead; a
    # normal turn keeps the senior-then-companion transcript as before.
    if is_proactive:
        transcript_and_reply = f'**ForeverYours initiated:**\n\n"{result.reply_text}"'
    else:
        transcript_and_reply = f'**Dad said:** "{transcript}"\n\n**Companion replied:** "{result.reply_text}"'
    if result.caregiver_flag:
        transcript_and_reply += _disclosure_note()
    turn_count = _next_turn_count(data_dir)
    if turn_count % REMINDER_EVERY_N_TURNS == 0:
        transcript_and_reply += "\n\n*(🤖 Reminder: this is an AI companion, and this conversation is recorded and transcribed.)*"

    wpm = biomarkers.get("wpm", 0.0)
    pause = biomarkers.get("avg_pause_s", 0.0)
    if not allow_hosted_call:
        transcript_and_reply += _cap_notice(bool(reply_audio), bool(result.caregiver_flag))
        biomarker_str = CAP_BIOMARKERS
    elif wpm > 0:
        biomarker_str = f"### 📊 Acoustic Biomarkers\n- **Speaking Rate:** {wpm} wpm\n- **Avg Pause:** {pause}s\n\n_Computed from this clip only; nothing is tracked across sessions._"
    else:
        biomarker_str = "### 📊 Acoustic Biomarkers\n_Calculated from live voice input only_"

    return transcript_and_reply, reply_audio, new_history, panel(), biomarker_str


def _session_id_invalid(session_id: str) -> bool:
    """True for a malformed/foreign id (#149); never under SHARED_PROFILE."""
    if SHARED_PROFILE:
        return False
    try:
        _session_root(session_id)
    except ValueError:
        return True
    return False


def _save_memo_text(session_id: str, memo_text: str, scope: str | None = None) -> None:
    """The one place caregiver memo text is written to a session's store:
    the memo box and the interview (#206) both come through here, so fact
    splitting and fact supersede apply identically. The caller holds
    `_session_active(session_id, refuse_if_deleted=True)` and has checked the
    text is not blank. It does NOT validate medical content (the memo box
    never did); the interview calls caregiver.validate_sample_profile first.
    `scope` is None for the memo box (the store infers it); the interview passes
    the question's declared scope so "Sarah visits at 15:00" is TEMPORARY too."""
    extra = {"scope": scope} if scope else {}
    data_dir, _ = _session_dirs(session_id)
    # A conversation turn's background extraction can still be writing
    # this session's MemoryStore; join it so writes stay ordered. The
    # per-profile lock (memory/profile_io.py) is what keeps a
    # writer still alive after the bounded join from dropping this save.
    _join_previous_turn(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    facts = split_memo_facts(memo_text)  # one shared splitter
    for line in facts:  # facts of one memo never supersede each other
        store.add(line, source="caregiver_memo", keep_texts=facts, **extra)


def save_caregiver_text_memo(memo_text: str | None, session_id: str | None) -> tuple[str, str, str]:
    """Caregiver submits context via text note (e.g. from work / phone).

    The whole session-dependent body -- empty-input branch, join, writes and
    the returned panel -- runs inside `_session_active(...,
    refuse_if_deleted=True)`, so the session counts as BUSY for
    `_end_session` and the sweeper until the panel is rendered, and a save
    for a household already deleted is REFUSED rather than recreating it:
    the memo is written nowhere, a fresh household answers with
    the reset notice, and the typed text stays in the box to resubmit."""
    session_id = session_id or _new_session()
    if _session_id_invalid(session_id):
        # Malformed/foreign id (#149): nothing to write to, so return the
        # same placeholder panel text rather than raise.
        return _format_caregiver_panel(session_id), session_id, ""
    try:
        with _session_active(session_id, refuse_if_deleted=True):
            if not memo_text or not memo_text.strip():
                return _format_caregiver_panel(session_id), session_id, ""
            _save_memo_text(session_id, memo_text)
            return _format_caregiver_panel(session_id), session_id, ""
    except SessionGone:
        # Never _format_caregiver_panel(old id): it builds a store and would
        # recreate the deleted directory.
        new_sid = _new_session()
        return _RESET_NOTICE + "\n\n" + _format_caregiver_panel(new_sid), new_sid, memo_text or ""


def save_caregiver_voice_memo(memo_audio: str | None, session_id: str | None) -> tuple[str, str]:
    """Caregiver submits onboarding context via voice memo (Beat 1). Same
    session lifecycle as save_caregiver_text_memo; transcription
    runs before registering, since it reads Gradio's upload, not the session."""
    session_id = session_id or _new_session()
    if _session_id_invalid(session_id):
        return _format_caregiver_panel(session_id), session_id  # malformed/foreign id (#149)
    transcript = refusal = None
    if memo_audio:
        transcript, _m, refusal = _guarded_transcribe(memo_audio, False)
    try:
        with _session_active(session_id, refuse_if_deleted=True):
            if not memo_audio:
                return _format_caregiver_panel(session_id), session_id
            if refusal is not None:  # nothing reaches the store
                return "⚠️ " + refusal.replace("what Dad says", "the memo") + "\n\n" + _format_caregiver_panel(session_id), session_id
            data_dir, _ = _session_dirs(session_id)
            _join_previous_turn(session_id)  # see save_caregiver_text_memo
            store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
            facts = split_memo_facts(transcript)  # one shared splitter
            for line in facts:  # facts of one memo never supersede each other
                store.add(line, source="caregiver_memo", keep_texts=facts)
            return _format_caregiver_panel(session_id), session_id
    except SessionGone:
        # The household is gone: the transcript is dropped (the voice memo has
        # no textbox to hand it back in) and nothing is written anywhere.
        new_sid = _new_session()
        return _RESET_NOTICE + "\n\n" + _format_caregiver_panel(new_sid), new_sid


# Guided interview (#206). The state lives in a per-tab gr.State (it dies with
# the tab; the memos it saved live in the session directory and are deleted by
# _end_session and the sweeper): {"answered": [keys], "skipped": [keys]}.
# "index" is derived, never stored, so a resume cannot re-ask an answered question.
def _interview_binding(session_id: str | None) -> str | None:
    """Identifies one household, not just one id: the session id plus a nonce
    file inside its directory. A swept household that is recreated under the
    same id (the sample loader does that) has no nonce file, so state built for
    the old one no longer matches. Never creates a directory."""
    if not session_id:
        return None
    if SHARED_PROFILE:
        return session_id
    try:
        root = _session_root(session_id)
    except ValueError:
        return f"{session_id}:invalid"
    marker = root / "interview_nonce"
    try:
        return f"{session_id}:{marker.read_text(encoding='utf-8').strip()}"
    except OSError:
        pass
    if not root.is_dir():
        return f"{session_id}:none"
    nonce = uuid.uuid4().hex
    try:
        with open(marker, "x", encoding="utf-8") as fh:
            fh.write(nonce)
    except FileExistsError:
        return _interview_binding(session_id)
    except OSError:
        return f"{session_id}:none"
    return f"{session_id}:{nonce}"


def _interview_new_state(session_id: str | None = None) -> dict:
    return {"answered": [], "skipped": [], "sid": session_id}


def _interview_state(state, session_id: str | None) -> dict:
    """A well-formed copy of whatever the browser handed back. The state is
    bound to the household it was built for: a different session id (the old
    one was swept and a new one issued) means a fresh interview, because the
    answers it remembers are gone with that household."""
    known = {q["key"] for q in INTERVIEW_QUESTIONS}
    if not isinstance(state, dict) or state.get("sid") != session_id:
        return _interview_new_state(session_id)
    clean: dict = {"sid": session_id}
    for name in ("answered", "skipped"):
        raw = state.get(name)
        keys = [k for k in raw if isinstance(k, str) and k in known] if isinstance(raw, list) else []
        clean[name] = list(dict.fromkeys(keys))
    return clean


def _interview_index(state: dict) -> int:
    """First question neither answered nor skipped; len(questions) when done."""
    seen = set(state["answered"]) | set(state["skipped"])
    for i, q in enumerate(INTERVIEW_QUESTIONS):
        if q["key"] not in seen:
            return i
    return len(INTERVIEW_QUESTIONS)


def _render_interview(state: dict, notice: str = "") -> str:
    total = len(INTERVIEW_QUESTIONS)
    lines = []
    if notice:
        lines.append(notice)
    lines.append(f"**{len(state['answered'])} of {total} answered, {len(state['skipped'])} skipped**")
    i = _interview_index(state)
    if i >= total:
        lines.append("All done. Dad's companion now has this in Briefed memory.")
    else:
        q = INTERVIEW_QUESTIONS[i]
        lines.append(f"**Question {i + 1} of {total}:** {q['prompt']}")
        lines.append(f"_For example: {q['example']}_")
        if not q["skippable"]:
            lines.append("_This one can't be skipped._")
    return "\n\n".join(lines)


def interview_refresh(state, session_id: str | None):
    """Timer tick: if the state belongs to a household that no longer exists,
    reset it and its text; otherwise change nothing (a refusal notice stays)."""
    binding = _interview_binding(session_id)
    if isinstance(state, dict) and state.get("sid") == binding:
        return gr.skip(), gr.skip()
    fresh = _interview_new_state(binding)
    return fresh, _render_interview(fresh)


def interview_next(state, session_id: str | None = None) -> tuple[dict, str]:
    """Start or resume: show the first question not yet answered or skipped."""
    state = _interview_state(state, _interview_binding(session_id))
    return state, _render_interview(state)


def interview_skip(state, session_id: str | None = None) -> tuple[dict, str]:
    """Skip the current question if it may be skipped. Saves nothing."""
    state = _interview_state(state, _interview_binding(session_id))
    i = _interview_index(state)
    if i >= len(INTERVIEW_QUESTIONS):
        return state, _render_interview(state)
    q = INTERVIEW_QUESTIONS[i]
    if not q["skippable"]:
        return state, _render_interview(state, "⚠️ This question can't be skipped.")
    state["skipped"].append(q["key"])
    return state, _render_interview(state)


def interview_confirm(answer: str | None, state, session_id: str | None) -> tuple[str, str, dict, str, str]:
    """Confirm the typed answer to the current question. It is first checked
    with caregiver.validate_sample_profile (dosing, diagnosis, clinical claims;
    the memo path itself does not do that): a refused answer is shown with its
    reason, nothing is saved and the question stays open. Otherwise it is saved
    through _save_memo_text, exactly as a typed memo, and the interview moves
    on. No model call is made and the senior side is not involved.
    Returns (caregiver panel, session id, state, interview text, answer box)."""
    session_id = session_id or _new_session()
    state = _interview_state(state, _interview_binding(session_id))
    if _session_id_invalid(session_id):
        return _format_caregiver_panel(session_id), session_id, state, _render_interview(state), ""
    answer = answer or ""
    try:
        # Everything that renders the panel runs inside the registration, so a
        # swept household is never recreated by a refused or blank answer.
        with _session_active(session_id, refuse_if_deleted=True):
            i = _interview_index(state)
            panel = lambda notice="", box="": (
                _format_caregiver_panel(session_id), session_id, state, _render_interview(state, notice), box)
            if i >= len(INTERVIEW_QUESTIONS):
                return panel()
            if not answer.strip():
                return panel("⚠️ Type an answer, or skip this question.", answer)
            try:
                validate_sample_profile(answer)
            except ValueError as exc:
                m = re.match(r"sample profile refused: (.+?) language \((.*?)\) in ", str(exc))
                what = f"{m.group(1)} language ({m.group(2)})" if m else "medical wording"
                # The matched text is the caregiver's own: escape before it reaches Markdown.
                return panel(
                    html.escape(f"⚠️ Not saved: the answer contains {what}. "
                                "Describe people, routines and preferences only, or skip this question."),
                    answer)
            q = INTERVIEW_QUESTIONS[i]
            _save_memo_text(session_id, interview_answer_memo(q["key"], answer), scope=q["scope"])
            state["answered"].append(q["key"])
            return panel()
    except SessionGone:
        # The household is gone: nothing was saved, the interview restarts
        # with the new one, and the typed answer stays in the box.
        new_sid = _new_session()
        fresh = _interview_new_state(_interview_binding(new_sid))
        return (_RESET_NOTICE + "\n\n" + _format_caregiver_panel(new_sid), new_sid, fresh,
                _render_interview(fresh), answer)


def load_sample_family(session_id: str | None) -> tuple[str, str]:
    """One click, before anyone speaks: seed this session's own MemoryStore
    with caregiver.SAMPLE_FAMILY (a labelled-fictional senior, family, likes,
    daily routine and caregiver-entered medication REMINDER times) and return
    the caregiver panel showing it. Structured items are written
    directly with their scope/privacy, never through the memo splitter.
    Validates the whole seed BEFORE the first write, so an invalid seed
    writes nothing. store.add no-ops on duplicates, so a second click adds
    nothing. Lives only under the session's data dir, so _end_session and
    _sweep_stale_sessions delete it with everything else."""
    session_id = session_id or _new_session()
    try:
        data_dir, _ = _session_dirs(session_id)
    except ValueError:
        return _format_caregiver_panel(session_id), session_id  # malformed/foreign id (#149)
    validate_sample_profile(SAMPLE_FAMILY["items"])  # refuse dosing/diagnosis/clinical text up front
    _join_previous_turn(session_id)  # see save_caregiver_text_memo
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    seen = {i.text for i in store.all() if i.source == "caregiver_memo"}  # never revert an update
    for _group, text, privacy in SAMPLE_FAMILY["items"]:
        if text in seen:
            continue
        store.add(
            text,
            source="caregiver_memo",
            supersede=False,  # a seed never replaces a caregiver fact, nor another seed line
            scope=MemoryScope.PERMANENT.value,  # clock-time items auto-scope TEMPORARY in add()
            privacy=PrivacyLevel.CAREGIVER_ONLY.value if privacy == "caregiver_only" else PrivacyLevel.PUBLIC_TO_SENIOR.value,
        )
    return _format_caregiver_panel(session_id), session_id


PAGE_CSS = """
.mobile-alert-strip { display: none; }
@media (max-width: 768px) {
    .mobile-alert-strip:not(:empty) { display: block !important; margin-bottom: 0.75em; }
}
footer { display: none !important; }
"""


def _build_line(path: Path = BUILD_INFO_PATH) -> str:
    """"Build: <sha7>" when a deploy wrote BUILD_INFO next to this file, else ""."""
    try:
        sha = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not sha:
        return ""
    return f"Build: `{sha[:7]}`"


_FLAG_ORIGINS = {
    "fastpath": "raised by: safety rules, before the model",
    "perseveration": "raised by: repeated-question check",
}

_NEMOTRON_ID = re.compile(r"^NVIDIA-(Nemotron-.+?)(?:-A\d+B)?$")


def _model_label(model_id: str) -> str:
    """Readable name for a Token Factory model id: "NVIDIA Nemotron 3 Nano
    30B" for the Nemotron ids, the bare id after the vendor prefix otherwise."""
    name = model_id.rsplit("/", 1)[-1]
    m = _NEMOTRON_ID.match(name)
    return f"NVIDIA {m.group(1).replace('-', ' ')}" if m else name


def _think_model() -> str:
    return os.environ.get("THINK_MODEL", DEFAULT_THINK_MODEL)


def _audit_model() -> str:
    return os.environ.get("AUDIT_MODEL", DEFAULT_AUDIT_MODEL)


def _flag_origin(flag) -> str:
    """Which layer raised `flag` (#214); empty when unknown. Display only.
    The backstop is named from AUDIT_MODEL, the same lookup pipeline/audit.py
    makes, so an override never shows up as "Nemotron"."""
    source = getattr(flag, "source", None) or ""
    if source == "audit":
        label = _model_label(_audit_model())
        short = "Nemotron" if label.startswith("NVIDIA Nemotron") else label
        return f"raised by: {short} backstop, after the reply"
    return _FLAG_ORIGINS.get(source, "")


def _model_footer(platform: str | None = None) -> str:
    """One always-visible line saying which model does what (#214). Every part
    reads the same setting the pipeline reads at call time (THINK_MODEL,
    AUDIT_MODEL, ASR_BACKEND, TTS_BACKEND), so the footer names what runs."""
    from pipeline import speak

    think_label, audit_label = _model_label(_think_model()), _model_label(_audit_model())
    if think_label == audit_label:
        models = f"Reply and safety backstop: {think_label} on Nebius Token Factory"
    else:
        models = (
            f"Reply: {think_label} on Nebius Token Factory · "
            f"Safety backstop: {audit_label} on Nebius Token Factory"
        )
    if os.environ.get("ASR_BACKEND", "whisper_local") == "nebius":
        asr = os.environ.get("ASR_NEBIUS_MODEL", "nvidia/parakeet-tdt-1.1b")
        hearing = f"{_model_label(asr)} on Nebius Token Factory"
    else:
        hearing = "faster-whisper, on this app's server"
    # Same order as pipeline/speak.py: Piper, Windows System.Speech, espeak, pyttsx3.
    if speak._piper_available():
        voice = "Piper"
    elif (platform or sys.platform) == "win32":
        voice = "Windows System.Speech"
    elif speak._get_espeak_cli() is not None:
        voice = "eSpeak NG"
    else:
        voice = "pyttsx3"
    return f"{models} · Hearing: {hearing} · Voice: {voice}, on this app's server"


def build_demo() -> gr.Blocks:
    _start_session_sweeper()
    with gr.Blocks(
        title="ForeverYours — talk, and the family that isn't there finds out",
        delete_cache=GRADIO_CACHE_SWEEP,
        # Set here, not in launch(): app.py (the Hugging Face / hosted entrypoint)
        # calls build_demo() and never calls launch() with our kwargs, so css
        # passed only to launch() never reaches the hosted page (Codex review,
        # #83 PR #85).
        css=PAGE_CSS,
    ) as demo:
        gr.Markdown(
            "# ForeverYours\n"
            "**Try this first: *I fell down earlier and I'm scared***\n\n"
            "Talk or type as the senior on the left; the caregiver on the right (Sarah, Dad's daughter) "
            "updates live. No mic? Use a sample clip below.\n\n"
            "**⚠️ TRANSPARENCY NOTICE: You are interacting with an Artificial Intelligence (AI) companion, not a human.** "
            f"[Privacy notice]({PRIVACY_NOTICE_URL})"
        )
        # The retention minutes sit collapsed here, beside the privacy-notice
        # link, so the short recording notice above the mic stays one glance
        # long. The text is still in the page (tests/test_retention_notice.py).
        with gr.Accordion("How long your recordings and household data are kept", open=False):
            gr.Markdown(
                f"Your household's memory, flags and audio are removed about {_CLOSED_TAB_MIN} "
                f"minutes after you close this tab, or after {_SESSION_TTL_MIN} minutes of "
                f"inactivity if the close never registers. Your recorded/uploaded input audio "
                f"separately sits in Gradio's own cache, swept every {_CACHE_SWEEP_INTERVAL_MIN} "
                f"minutes and removing files older than {_CACHE_MAX_AGE_MIN} minutes, so up to "
                f"about {_CACHE_MAX_MIN} minutes. Nothing is removed the instant the tab closes."
            )
        history_state = gr.State([])
        session_state = gr.State(None, time_to_live=SESSION_TTL_S, delete_callback=_end_session)

        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🧑 Senior side")
                mobile_alert = gr.Markdown("", elem_classes=["mobile-alert-strip"])
                # Recording/processing notice sits next to the input the user
                # acts on and states only what the pipeline actually does: the
                # transcript (not the audio) leaves the device by default
                # (ASR is local faster-whisper), mirroring the caregiver panel's
                # already-vetted wording so both sides agree (#66 B/C).
                gr.Markdown(
                    "🎙️ *When you speak or type here, it is recorded and turned into text. "
                    "That text (not your voice recording) is sent to Nebius Token Factory to write a "
                    "reply and run a safety check. How long it is kept: open "
                    "\"How long your recordings and household data are kept\" above.*"
                )
                audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak (as the senior)")
                text_in = gr.Textbox(
                    placeholder="Or type what Dad says (e.g. 'I fell down earlier' or 'Who is Sarah?')...",
                    label="Type (as the senior)",
                    lines=1,
                )
                run_btn = gr.Button("Send", variant="primary")
                # One click fills the type box with the line the page asks the
                # judge to try first (#215); the typed path needs no mic.
                gr.Examples(
                    examples=[["I fell down earlier and I'm scared"]],
                    inputs=[text_in],
                    label="Try this first",
                    cache_examples=False,
                )
                # Judges without a mic (or who'd rather not record their own voice)
                # can still drive every beat with one click. First chip asks a
                # schedule question so the reply recalls a caregiver fact,
                # rather than looking like a generic chatbot (#83, #80 3.C4).
                gr.Examples(
                    examples=[[str(SAMPLES_DIR / name)] for name in SAMPLE_CLIPS],
                    inputs=[audio_in],
                    example_labels=list(SAMPLE_CLIP_LABELS),
                    label="No mic? Try a sample clip",
                    cache_examples=False,
                )

                with gr.Accordion("Clinical Configuration", open=False, visible=DEV_MODE):
                    simulated_time_in = gr.Dropdown(
                        choices=["Morning (Default)", "Evening (Sundowning)", "Night"],
                        value="Morning (Default)",
                        label="Simulated Time of Day"
                    )

                with gr.Accordion("🛠️ Simulate Proactive Triggers", open=False, visible=DEV_MODE):
                    gr.Markdown("Clicking these simulates the background agent initiating conversation without a microphone prompt.")
                    with gr.Row():
                        proactive_btn_morning = gr.Button("Morning Greeting")
                        proactive_btn_grocery = gr.Button("Caregiver Reminder")
                        proactive_btn_hobby = gr.Button("Hobby Engagement")
                        proactive_btn_silence = gr.Button("Silence Check-in")

                transcript_out = gr.Markdown(label="Conversation")
                # Streaming, so each yielded sentence chunk is appended and heard once (a plain player restarted on every yield); every handler writing it must be a generator function, or Gradio does not stream it.
                audio_out = gr.Audio(label="Companion's reply", streaming=True, autoplay=True)
            with gr.Column():
                gr.Markdown("## 👩 Caregiver side (live)")
                caregiver_panel = gr.Markdown(_format_caregiver_panel(None))
                biomarkers_panel = gr.Markdown("### 📊 Acoustic Biomarkers\n_Awaiting voice input..._", visible=DEV_MODE)
                # One click seeds a labelled-fictional household into this
                # session only. Sits inside the caregiver column, next
                # to the memo accordion, so the Senior/Caregiver split-screen
                # the video script uses is unchanged.
                load_sample_btn = gr.Button("Load sample family", variant="secondary")
                with gr.Accordion("Brief Dad companion (as Sarah, his daughter)", open=True):
                    with gr.Tabs():
                        with gr.TabItem("Type Note"):
                            memo_text_in = gr.Textbox(
                                placeholder="e.g. Dad loves chicken soup. Sarah is dropping off groceries at 4 PM.",
                                label="Write context memo",
                                lines=2,
                            )
                            save_text_memo_btn = gr.Button("Save Text Memo", variant="secondary")
                        with gr.TabItem("Record Voice Memo"):
                            memo_audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Record context memo")
                            save_audio_memo_btn = gr.Button("Save Voice Memo", variant="secondary")
                # Guided interview (#206): one question at a time, saved through
                # the same helper as the memo box; the senior never hears it.
                with gr.Accordion("Guided interview: brief the companion in five questions", open=False):
                    interview_state = gr.State(_interview_new_state())
                    interview_md = gr.Markdown(_render_interview(_interview_new_state()))
                    interview_answer_in = gr.Textbox(label="Your answer", lines=2)
                    with gr.Row():
                        interview_start_btn = gr.Button("Start / resume", variant="secondary")
                        interview_confirm_btn = gr.Button("Confirm answer", variant="primary")
                        interview_skip_btn = gr.Button("Skip", variant="secondary")

        # Below the product on purpose (#21 / Design review): the split-screen
        # above is the hero, so the longer context and the dev telemetry sit
        # under it, collapsed, rather than pushing the demo below the fold.
        with gr.Accordion("About this demo household", open=False):
            gr.Markdown(
                "Your tab is its own private demo household, already briefed by Dad's daughter "
                "Sarah (jazz, grandson Leo, no driving talk, groceries at 4 PM). Nobody else on "
                "this link sees it. Its memory and flags are removed when "
                f"the session cleanup timer runs (about {_CLOSED_TAB_MIN} minutes after "
                f"the tab closes), or after {_SESSION_TTL_MIN} minutes of inactivity if "
                f"the close never registers. This removes the household session directory, "
                f"not Gradio's separate audio cache. Both recorded or uploaded input audio "
                f"and Gradio's cached copies of reply audio separately remain in that cache until its sweep runs every "
                f"{_CACHE_SWEEP_INTERVAL_MIN} minutes and removes files older than "
                f"{_CACHE_MAX_AGE_MIN} minutes, so they can remain for up to about "
                f"{_CACHE_MAX_MIN} minutes. We never promise deletion the instant the "
                f"tab closes."
            )

            build_line = _build_line()
            if build_line:
                gr.Markdown(build_line)

        if DEV_MODE:
            with gr.Accordion("Model & Pipeline Info", open=False):
                gr.Markdown("**Thinking & Safety Engine:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (Nebius Token Factory)\n\n"
                            "**Audio Perception (HEAR):** `faster-whisper` (local CPU)\n\n"
                            "*Background memory extraction & safety audit run asynchronously via Nebius Token Factory.*")

        gr.Markdown(_model_footer())

        # Every senior-turn producer (Send, Enter, the four proactive
        # buttons) shares concurrency_id "senior_turn" with a bounded limit
        # (FY_TURN_CONCURRENCY, default 4) instead of Gradio's default of 1, so
        # one visitor's slow ASR/Nebius/TTS turn no longer queues everyone
        # else's. Same id = one shared bound. Caregiver memo handlers keep
        # Gradio's default (out of scope). ADR-003 "Concurrency".
        run_btn.click(
            fn=run_demo_turn_streaming,
            inputs=[audio_in, text_in, history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            concurrency_limit=TURN_CONCURRENCY,
            concurrency_id="senior_turn",
        )

        proactive_btn_morning.click(
            fn=functools.partial(run_proactive_turn_streaming, trigger_type="morning"),
            inputs=[history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            concurrency_limit=TURN_CONCURRENCY,
            concurrency_id="senior_turn",
        )
        proactive_btn_grocery.click(
            fn=functools.partial(run_proactive_turn_streaming, trigger_type="reminder"),
            inputs=[history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            concurrency_limit=TURN_CONCURRENCY,
            concurrency_id="senior_turn",
        )
        proactive_btn_hobby.click(
            fn=functools.partial(run_proactive_turn_streaming, trigger_type="hobby"),
            inputs=[history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            concurrency_limit=TURN_CONCURRENCY,
            concurrency_id="senior_turn",
        )
        proactive_btn_silence.click(
            fn=functools.partial(run_proactive_turn_streaming, trigger_type="silence"),
            inputs=[history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            concurrency_limit=TURN_CONCURRENCY,
            concurrency_id="senior_turn",
        )

        text_in.submit(
            fn=run_demo_turn_streaming,
            inputs=[audio_in, text_in, history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            concurrency_limit=TURN_CONCURRENCY,
            concurrency_id="senior_turn",
        )

        save_text_memo_btn.click(
            fn=save_caregiver_text_memo,
            inputs=[memo_text_in, session_state],
            outputs=[caregiver_panel, session_state, memo_text_in],
        )

        memo_text_in.submit(
            fn=save_caregiver_text_memo,
            inputs=[memo_text_in, session_state],
            outputs=[caregiver_panel, session_state, memo_text_in],
        )

        save_audio_memo_btn.click(
            fn=save_caregiver_voice_memo,
            inputs=[memo_audio_in, session_state],
            outputs=[caregiver_panel, session_state],
        )

        interview_start_btn.click(
            fn=interview_next,
            inputs=[interview_state, session_state],
            outputs=[interview_state, interview_md],
        )
        interview_skip_btn.click(
            fn=interview_skip,
            inputs=[interview_state, session_state],
            outputs=[interview_state, interview_md],
        )
        interview_confirm_btn.click(
            fn=interview_confirm,
            inputs=[interview_answer_in, interview_state, session_state],
            outputs=[caregiver_panel, session_state, interview_state, interview_md, interview_answer_in],
        )

        load_sample_btn.click(
            fn=load_sample_family,
            inputs=[session_state],
            outputs=[caregiver_panel, session_state],
        )

        # Independent of the click above -- this is what makes the caregiver
        # side feel "live" rather than only updating when the senior side
        # does. See the module docstring for why polling, not push. The mobile
        # alert strip rides the same poll so a phone sees it within one tick too.
        timer = gr.Timer(2)
        timer.tick(fn=_format_caregiver_panel, inputs=[session_state], outputs=[caregiver_panel])
        timer.tick(fn=interview_refresh, inputs=[interview_state, session_state], outputs=[interview_state, interview_md])
        timer.tick(fn=_format_mobile_alert_strip, inputs=[session_state], outputs=[mobile_alert])
        demo.load(fn=init_session, outputs=[session_state, caregiver_panel])
        demo.load(fn=_format_mobile_alert_strip, inputs=[session_state], outputs=[mobile_alert])
    return demo


if __name__ == "__main__":
    hear.warm_up()  # (#81 B4)
    from pipeline import speak as _speak
    # Load the Piper voice while the UI builds, so the first reply does not wait on it (#207).
    threading.Thread(target=_speak.warm_up, name="piper-warm-up", daemon=True).start()
    build_demo().launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        max_file_size=f"{MAX_AUDIO_UPLOAD_BYTES}b",  # Gradio refuses oversize uploads too
    )
