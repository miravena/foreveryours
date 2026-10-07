"""Judge-facing web demo: the pivot beat (issue #21), not just a UI shell.

The point of this file isn't "put the CLI in a browser" -- it's to make the
ONE thing a general-purpose voice assistant can't do visible in a single
screen: when the senior says something worrying, the companion tells HIM
that it's notifying the caregiver, and in the SAME moment the caregiver side
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
other's flags, memories or voices. A session's directory is deleted when the
tab closes (gr.State delete_callback) or after SESSION_TTL_S, and Gradio's own
upload/output cache is expired by `delete_cache`. Set FY_SHARED_PROFILE=1 to
get the old single shared `data/dad.*` profile back -- useful locally when
recording a video alongside `main.py` beats, never for a public deployment.
"""
from __future__ import annotations

import datetime
import os

if __name__ == "__main__":
    # Only for `python webapp.py` (local dev). app.py (the hosted/Spaces
    # entrypoint) already loads .env before importing this module; loading it
    # unconditionally at import time made importing webapp for tests pick up
    # a real key depending on process/import order (#81 D2). Must run before
    # the os.environ.get() constants below, or they'd miss .env values
    # (Codex review, PR #90) -- hence the guard sits here, not at EOF.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

import re
import shutil
import tempfile
import threading
import time
import uuid
SENIOR_TIMEZONE = os.environ.get('SENIOR_TIMEZONE', 'Asia/Kuala_Lumpur')
import wave
from pathlib import Path

import gradio as gr

from caregiver import DEFAULT_CAREGIVER_NAME, DEFAULT_PROFILE_ID, DEMO_MEMO, CaregiverFlags
from memory.store import MemoryScope, MemoryStore, PrivacyLevel
from pipeline import hear
from pipeline.orchestrator import run_turn

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_DIR = Path(__file__).resolve().parent / "out" / "audio"
SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLE_CLIPS = ("senior_schedule.wav", "senior_jazz.wav", "senior_grandson.wav", "senior_distress.wav")
MAX_DAILY_REQUESTS = int(os.environ.get("MAX_DAILY_REQUESTS", "50"))
MAX_HISTORY_TURNS = 4  # (user, assistant) pairs kept -- bounds prompt growth, not a product limit
REMINDER_EVERY_N_TURNS = 6  # session-length-based "this is an AI" reminder (#83 AC)
# Developer-only surface (telemetry, clinical sim, proactive triggers, biomarkers,
# the perseveration flag) stays out of the public page by default (#83, #80 3.C3).
DEV_MODE = os.environ.get("FY_DEV_MODE") == "1"
PRIVACY_NOTICE_URL = "https://github.com/miravena/foreveryours/blob/main/docs/SAFETY_AND_PRIVACY.md"
SESSIONS_DIR = Path(os.environ.get("FY_SESSIONS_DIR", Path(tempfile.gettempdir()) / "foreveryours-sessions"))
SHARED_PROFILE = os.environ.get("FY_SHARED_PROFILE") == "1"
SESSION_TTL_S = int(os.environ.get("SESSION_TTL_S", "3600"))
GRADIO_CACHE_SWEEP = (600, SESSION_TTL_S)  # (check every N s, delete files older than M s)

_lock = threading.Lock()
_request_log: dict[str, int] = {}  # vestigial -- kept only so tests' webapp._request_log.clear() still resolves; _rate_limit_ok() keeps its own local dict now


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


def _session_dirs(session_id: str) -> tuple[Path, Path]:
    """(data_dir, audio_dir) for one browser session."""
    if SHARED_PROFILE:
        return DATA_DIR, AUDIO_DIR
    root = SESSIONS_DIR / session_id
    return root / "data", root / "audio"


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


def _sweep_stale_sessions() -> None:
    """Backstop for sessions whose delete_callback never ran (process
    restart, crashed tab): anything untouched for SESSION_TTL_S goes."""
    if SHARED_PROFILE or not SESSIONS_DIR.exists():
        return
    cutoff = time.time() - SESSION_TTL_S
    for child in SESSIONS_DIR.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except FileNotFoundError:
            pass


def _new_session() -> str:
    """Fresh household, pre-briefed with the demo memo so a judge's very
    first remark has caregiver context to recall (beat 2 works on click one)."""
    _sweep_stale_sessions()
    session_id = DEFAULT_PROFILE_ID if SHARED_PROFILE else uuid.uuid4().hex
    data_dir, _ = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    for line in DEMO_MEMO.split(". "):
        line = line.strip().rstrip(".")
        if line:
            store.add(line, source="caregiver_memo")  # no-op on duplicates
    return session_id


def _end_session(session_id: str | None) -> None:
    if session_id and not SHARED_PROFILE:
        shutil.rmtree(SESSIONS_DIR / session_id, ignore_errors=True)


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


def _format_caregiver_panel(session_id: str | None) -> str:
    """Reads straight from disk every call -- this is what makes it a live
    panel rather than a snapshot: whatever this session's turns (or, with
    FY_SHARED_PROFILE=1, main.py) wrote is reflected here within one poll
    interval (see the Timer below)."""
    if not session_id:
        return "_Setting up your demo household..._"
    data_dir, _ = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)

    lines = [
        # A blank line before "---" matters: text immediately followed by "---"
        # is a Markdown setext heading (renders <h2>), which is how the pledge
        # became the largest text on the page (#83, #80 2.B2) even un-bolded.
        "🛡️ Peace of mind without surveillance. ForeverYours summarizes important updates and medical/safety flags. Turn transcripts (not audio) go to Nebius Token Factory to generate replies and run the safety check; see [Safety & privacy design](https://github.com/miravena/foreveryours/blob/main/docs/SAFETY_AND_PRIVACY.md).",
        "",
        "---",
    ]
    flag_items = flags.all()
    distress_flags = [f for f in flag_items if f.severity in ("distress", "confusion")]
    if distress_flags:
        latest = distress_flags[-1]
        disclosed = "✅ **Disclosed to Senior in conversation**" if latest.disclosed_to_senior else "⚠️ **NOT yet disclosed**"
        lines.append(
            "> 🚨 **HIGH PRIORITY SAFETY ALERT DISPATCHED**\n"
            f"> **Event:** {latest.text}\n"
            f"> **Severity:** `{latest.severity.upper()}` | **Status:** Caregiver notified\n"
            f"> **Disclosure:** {disclosed}\n"
        )

    lines.append("### What ForeverYours has told you")
    if not flag_items:
        lines.append("_No flags yet. You'll see something here the moment Dad says something worth knowing about._")
    for flag in reversed(flag_items):  # newest first -- this is the thing a caregiver glances at
        disclosed = "✅ Dad was told" if flag.disclosed_to_senior else "⚠️ NOT yet disclosed to Dad"
        lines.append(f"- **({flag.severity})** {flag.text}\n  {disclosed}")

    lines.append("\n### Briefed memory")
    items = store.all()
    if not items:
        lines.append("_(nothing briefed yet)_")
    now = time.time()
    for item in items:
        # Privacy badge
        is_private = (item.privacy == PrivacyLevel.CAREGIVER_ONLY.value)
        priv_badge = "🔒 **[Caregiver Only — Hidden from Dad]** " if is_private else ""

        # Scope & Status badge
        if item.status == "superseded":
            badge = "🔄 _[Superseded]_ "
            desc = f"~~{item.text}~~"
            if item.superseded_by:
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
    return "\n".join(lines)


def _format_mobile_alert_strip(session_id: str | None) -> str:
    """Short version of the caregiver panel's top alert, shown above the mic
    only on narrow screens (CSS below) -- on a phone the caregiver column is
    stacked below the whole senior column, so without this a flag is invisible
    until the judge scrolls past everything (#83, #80 2.B2)."""
    if not session_id:
        return ""
    data_dir, _ = _session_dirs(session_id)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
    distress_flags = [f for f in flags.all() if f.severity in ("distress", "confusion")]
    if not distress_flags:
        return ""
    latest = distress_flags[-1]
    disclosed = "told Dad already" if latest.disclosed_to_senior else "not yet disclosed to Dad"
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


def run_demo_turn(
    audio_in: str | None = None,
    text_in_or_history: str | list[dict] | None = None,
    history_or_session: list[dict] | str | None = None,
    session_id: str | None = None,
    simulated_time_in: str | None = None,
    is_proactive: bool = False,
) -> tuple[str, str | None, list[dict], str, str, str, str, None]:
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
    session_expired = session_id_val is None
    session_id_val = session_id_val or _new_session()

    simulated_hour = 10
    if "Sundowning" in simulated_time_str:
        simulated_hour = 18
    elif "Night" in simulated_time_str:
        simulated_hour = 23

    out = _run_demo_turn(audio_in, actual_text, history, session_id_val, simulated_hour, is_proactive=is_proactive)
    if session_expired:
        out = (
            "_Your demo household was reset after a period of inactivity._\n\n" + out[0],
            *out[1:],
        )
    # Clear audio_in on every turn: otherwise a loaded sample clip stays in the
    # recorder and a later Send with an empty textbox silently re-transcribes
    # the old clip (#83, #80 2.B3).
    return (*out, session_id_val, "", None)


def run_proactive_turn(history, session, sim_time):
    """Handler for the four proactive buttons: same 8 outputs as run_demo_turn."""
    return run_demo_turn(None, None, history, session, sim_time, is_proactive=True)


def _stream_with_thinking_indicator(real_result_fn):
    """Wrap a turn handler as a generator so the browser shows "thinking..."
    the instant a turn starts, instead of a blank spinner for however long
    Token Factory takes to answer (#81 B1, #11 row 8 decision). `gr.skip()`
    leaves every other output untouched on the first yield."""
    def gen(*args, **kwargs):
        yield (
            "_Companion is thinking..._",
            gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
        )
        yield real_result_fn(*args, **kwargs)
    return gen


run_demo_turn_streaming = _stream_with_thinking_indicator(run_demo_turn)
run_proactive_turn_streaming = _stream_with_thinking_indicator(run_proactive_turn)


def _run_demo_turn(
    audio_in: str | None,
    text_in: str | None,
    history: list[dict],
    session_id: str,
    simulated_hour: int = 10,
    is_proactive: bool = False,
) -> tuple[str, str | None, list[dict], str, str]:
    data_dir, audio_dir = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
    panel = lambda: _format_caregiver_panel(session_id)  # noqa: E731

    biomarkers = {"wpm": 0.0, "avg_pause_s": 0.0}

    if is_proactive:
        transcript = "[System: The senior is currently quiet. Please initiate a conversation based on the context above. BE BRIEF AND WARM.]"
    elif text_in and text_in.strip():
        transcript = text_in.strip()
    elif audio_in:
        transcript, biomarkers = hear.transcribe(Path(audio_in), return_metrics=True)
    else:
        return "Record audio or type what Dad says first.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_"

    if not transcript.strip() and not is_proactive:
        return "Couldn't make out any speech or text -- try again.", None, history, panel(), "### 📊 Acoustic Biomarkers\n_No audio detected_"

    # Cap only what's actually about to spend a Nebius call -- not the empty
    # sends and no-key misses handled above, and not the offline safety
    # fast-path (#81 A1).
    if _will_call_nebius() and not _rate_limit_ok(data_dir):
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
            transcript, store, flags, audio_dir, caregiver_name=DEFAULT_CAREGIVER_NAME, history=history, simulated_hour=simulated_hour, is_proactive=is_proactive,
            enable_perseveration_flag=DEV_MODE,
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
        return (
            f'**Dad said:** "{transcript}"\n\n⚠️ *I\'m sorry, I ran into an unexpected error processing that.*',
            None,
            history,
            panel(),
            "### 📊 Acoustic Biomarkers\n_Error_",
        )

    # AUDIT + memory extraction now run fully off the critical path (#81 B1):
    # no join here on any turn. #11 row 8's decision was to keep a bounded
    # join "only on turns where the crisis tier fired" -- but `background_thread`
    # is only ever set on NON-fast-path turns (`orchestrator.run_turn`: the
    # background task is created iff `not fast.triggered`), so that condition
    # can never be true alongside a real thread to join; implementing it
    # literally was dead code (Codex review, PR #90). Flagged back on #11:
    # if AUDIT flags a reply unsafe after this returns, its spoken disclosure
    # is generated but has already missed this turn's `audio_out` -- same
    # gap as before this PR, not introduced by it, but now a known one
    # instead of a silently-skipped "fix".

    if not result.is_fallback:
        new_history = history + [
            {"role": "user", "content": transcript},
            {"role": "assistant", "content": result.reply_text},
        ]
        new_history = new_history[-(MAX_HISTORY_TURNS * 2) :]
    else:
        new_history = history

    combined_audio = _combine_audio_chunks(result.audio_paths, audio_dir)
    reply_audio = str(combined_audio) if combined_audio else None
    transcript_and_reply = f'**Dad said:** "{transcript}"\n\n**Companion replied:** "{result.reply_text}"'
    if result.caregiver_flag:
        transcript_and_reply += "\n\n*(📢 Honest Safety Disclosure: Caregiver notified with Dad's knowledge)*"
    turn_count = _next_turn_count(data_dir)
    if turn_count % REMINDER_EVERY_N_TURNS == 0:
        transcript_and_reply += "\n\n*(🤖 Reminder: this is an AI companion, and this conversation is recorded and transcribed.)*"

    wpm = biomarkers.get("wpm", 0.0)
    pause = biomarkers.get("avg_pause_s", 0.0)
    if wpm > 0:
        biomarker_str = f"### 📊 Acoustic Biomarkers\n- **Speaking Rate:** {wpm} wpm\n- **Avg Pause:** {pause}s\n\n_Computed from this clip only; nothing is tracked across sessions._"
    else:
        biomarker_str = "### 📊 Acoustic Biomarkers\n_Calculated from live voice input only_"

    return transcript_and_reply, reply_audio, new_history, panel(), biomarker_str


def save_caregiver_text_memo(memo_text: str | None, session_id: str | None) -> tuple[str, str, str]:
    """Caregiver submits context via text note (e.g. from work / phone)."""
    session_id = session_id or _new_session()
    if not memo_text or not memo_text.strip():
        return _format_caregiver_panel(session_id), session_id, ""
    data_dir, _ = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    for raw_part in re.split(r"[.!?\n]+", memo_text):
        line = raw_part.strip()
        if line:
            store.add(line, source="caregiver_memo")
    return _format_caregiver_panel(session_id), session_id, ""


def save_caregiver_voice_memo(memo_audio: str | None, session_id: str | None) -> tuple[str, str]:
    """Caregiver submits onboarding context via voice memo (Beat 1)."""
    session_id = session_id or _new_session()
    if not memo_audio:
        return _format_caregiver_panel(session_id), session_id
    transcript = hear.transcribe(Path(memo_audio))
    data_dir, _ = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir, timezone_str=SENIOR_TIMEZONE)
    for line in transcript.split(". "):
        line = line.strip().rstrip(".")
        if line:
            store.add(line, source="caregiver_memo")
    return _format_caregiver_panel(session_id), session_id


PAGE_CSS = """
.mobile-alert-strip { display: none; }
@media (max-width: 768px) {
    .mobile-alert-strip:not(:empty) { display: block !important; margin-bottom: 0.75em; }
}
footer { display: none !important; }
"""


def build_demo() -> gr.Blocks:
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
            "Watch both sides at once: talk or type as the senior on the left, and watch the "
            "caregiver side on the right update live, the moment something worth knowing happens."
        )
        gr.Markdown(
            "🤖 **This is an AI companion, not a person.** Everything you say here is recorded and "
            f"transcribed to generate a reply. Read the [privacy notice]({PRIVACY_NOTICE_URL}) before you speak."
        )
        history_state = gr.State([])
        session_state = gr.State(None, time_to_live=SESSION_TTL_S, delete_callback=_end_session)

        if DEV_MODE:
            with gr.Accordion("Model & Pipeline Info", open=True):
                gr.Markdown("**Thinking & Safety Engine:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (Nebius Token Factory)\n\n"
                            "**Audio Perception (HEAR):** `faster-whisper` (local CPU)\n\n"
                            "*Background memory extraction & safety audit run asynchronously via Nebius Token Factory.*")

        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🧑 Senior side")
                mobile_alert = gr.Markdown("", elem_classes=["mobile-alert-strip"])
                audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak (as the senior)")
                text_in = gr.Textbox(
                    placeholder="Or type what Dad says (e.g. 'I fell down earlier' or 'Who is Sarah?')...",
                    label="Type (as the senior)",
                    lines=1,
                )
                run_btn = gr.Button("Send", variant="primary")
                # Judges without a mic (or who'd rather not record their own voice)
                # can still drive every beat with one click. First chip asks a
                # schedule question so the reply recalls a caregiver fact,
                # rather than looking like a generic chatbot (#83, #80 3.C4).
                gr.Examples(
                    examples=[[str(SAMPLES_DIR / name)] for name in SAMPLE_CLIPS],
                    inputs=[audio_in],
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
                audio_out = gr.Audio(label="Companion's reply", autoplay=True)
            with gr.Column():
                gr.Markdown("## 👩 Caregiver side (live)")
                caregiver_panel = gr.Markdown(_format_caregiver_panel(None))
                biomarkers_panel = gr.Markdown("### 📊 Acoustic Biomarkers\n_Awaiting voice input..._", visible=DEV_MODE)
                with gr.Accordion("📝 Submit Caregiver Memo (Beat 1 Onboarding)", open=False):
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

        run_btn.click(
            fn=run_demo_turn_streaming,
            inputs=[audio_in, text_in, history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
        )

        for btn in [proactive_btn_morning, proactive_btn_grocery, proactive_btn_hobby, proactive_btn_silence]:
            btn.click(
                fn=run_proactive_turn_streaming,
                inputs=[history_state, session_state, simulated_time_in],
                outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
            )

        text_in.submit(
            fn=run_demo_turn_streaming,
            inputs=[audio_in, text_in, history_state, session_state, simulated_time_in],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, biomarkers_panel, session_state, text_in, audio_in],
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

        # Independent of the click above -- this is what makes the caregiver
        # side feel "live" rather than only updating when the senior side
        # does. See the module docstring for why polling, not push. The mobile
        # alert strip rides the same poll so a phone sees it within one tick too.
        timer = gr.Timer(2)
        timer.tick(fn=_format_caregiver_panel, inputs=[session_state], outputs=[caregiver_panel])
        timer.tick(fn=_format_mobile_alert_strip, inputs=[session_state], outputs=[mobile_alert])
        demo.load(fn=init_session, outputs=[session_state, caregiver_panel])
        demo.load(fn=_format_mobile_alert_strip, inputs=[session_state], outputs=[mobile_alert])
    return demo


if __name__ == "__main__":
    hear._get_whisper_model()  # warm up now, not on the first judge's click (#81 B4)
    build_demo().launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")))
