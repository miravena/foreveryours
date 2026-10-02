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
import shutil
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

import gradio as gr

from caregiver import DEFAULT_CAREGIVER_NAME, DEFAULT_PROFILE_ID, DEMO_MEMO, CaregiverFlags
from memory.store import MemoryStore
from pipeline import hear
from pipeline.orchestrator import run_turn

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_DIR = Path(__file__).resolve().parent / "out" / "audio"
SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLE_CLIPS = ("senior_jazz.wav", "senior_grandson.wav", "senior_distress.wav")
MAX_DAILY_REQUESTS = int(os.environ.get("MAX_DAILY_REQUESTS", "50"))
MAX_HISTORY_TURNS = 4  # (user, assistant) pairs kept -- bounds prompt growth, not a product limit
SESSIONS_DIR = Path(os.environ.get("FY_SESSIONS_DIR", Path(tempfile.gettempdir()) / "foreveryours-sessions"))
SHARED_PROFILE = os.environ.get("FY_SHARED_PROFILE") == "1"
SESSION_TTL_S = int(os.environ.get("SESSION_TTL_S", "3600"))
GRADIO_CACHE_SWEEP = (600, SESSION_TTL_S)  # (check every N s, delete files older than M s)

_lock = threading.Lock()
_request_log: dict[str, int] = {}  # date string -> count, in-memory, resets on restart


def _rate_limit_ok() -> bool:
    today = datetime.date.today().isoformat()
    with _lock:
        count = _request_log.get(today, 0)
        if count >= MAX_DAILY_REQUESTS:
            return False
        _request_log[today] = count + 1
        return True


def _session_dirs(session_id: str) -> tuple[Path, Path]:
    """(data_dir, audio_dir) for one browser session."""
    if SHARED_PROFILE:
        return DATA_DIR, AUDIO_DIR
    root = SESSIONS_DIR / session_id
    return root / "data", root / "audio"


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
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
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
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)

    lines = ["### What ForeverYours has told you"]
    flag_items = flags.all()
    if not flag_items:
        lines.append("_No flags yet. You'll see something here the moment Dad says something worth knowing about._")
    for flag in reversed(flag_items):  # newest first -- this is the thing a caregiver glances at
        disclosed = "✅ Dad was told" if flag.disclosed_to_senior else "⚠️ NOT yet disclosed to Dad"
        lines.append(f"- **({flag.severity})** {flag.text}\n  {disclosed}")

    lines.append("\n### Briefed memory")
    items = store.all()
    if not items:
        lines.append("_(nothing briefed yet)_")
    for item in items:
        lines.append(f"- [{item.source}] {item.text}")
    return "\n".join(lines)


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
    audio_in: str | None, history: list[dict], session_id: str | None
) -> tuple[str, str | None, list[dict], str, str]:
    session_id = session_id or _new_session()
    out = _run_demo_turn(audio_in, history, session_id)
    return (*out, session_id)


def _run_demo_turn(
    audio_in: str | None, history: list[dict], session_id: str
) -> tuple[str, str | None, list[dict], str]:
    data_dir, audio_dir = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
    panel = lambda: _format_caregiver_panel(session_id)  # noqa: E731

    if not _rate_limit_ok():
        return (
            "This demo has hit its daily request cap -- please try again tomorrow "
            "(protects the shared Nebius API credits). See CONTRIBUTING.md.",
            None,
            history,
            panel(),
        )

    if not audio_in:
        return "Record or upload something first.", None, history, panel()

    transcript = hear.transcribe(Path(audio_in))
    if not transcript.strip():
        return "Couldn't make out any speech in that clip -- try again.", None, history, panel()

    _clear_session_audio(audio_dir)
    try:
        result = run_turn(
            transcript, store, flags, audio_dir, caregiver_name=DEFAULT_CAREGIVER_NAME, history=history
        )
    except Exception as exc:
        err = str(exc)
        if "NEBIUS_API_KEY" in err or "NebiusNotConfigured" in type(exc).__name__:
            return (
                f'**Dad said:** "{transcript}"\n\n'
                f"⚠️ *Companion reply paused: NEBIUS_API_KEY is pending approval.*\n\n"
                f"👉 **Try an emergency phrase:** Say *\"I fell down earlier and I'm scared\"* — the safety fast-path runs completely offline with real spoken voice!",
                None,
                history,
                panel(),
            )
        raise

    if result.background_thread is not None:
        result.background_thread.join(timeout=10)

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
    return transcript_and_reply, reply_audio, new_history, panel()



def save_caregiver_voice_memo(memo_audio: str | None, session_id: str | None) -> tuple[str, str]:
    """Caregiver submits onboarding context via voice memo (Beat 1)."""
    session_id = session_id or _new_session()
    if not memo_audio:
        return _format_caregiver_panel(session_id), session_id
    transcript = hear.transcribe(Path(memo_audio))
    data_dir, _ = _session_dirs(session_id)
    store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
    for line in transcript.split(". "):
        line = line.strip().rstrip(".")
        if line:
            store.add(line, source="caregiver_memo")
    return _format_caregiver_panel(session_id), session_id


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="ForeverYours — judge demo", delete_cache=GRADIO_CACHE_SWEEP) as demo:
        gr.Markdown(
            "# ForeverYours\n"
            "Watch both sides at once: talk as the senior on the left, watch the caregiver side "
            "on the right update live. Try an ordinary remark first, then try something like "
            "\"I fell down earlier\" -- the right side updates within a couple seconds, "
            "and the reply on the left tells Dad, out loud, that it's doing that.\n\n"
            "Your tab is its own private demo household, already briefed by Dad's daughter "
            "Sarah (jazz, grandson Leo, no driving talk, groceries at 4 PM). Nobody else on "
            "this link sees it, and its memory, flags and audio are deleted when you close "
            "the tab or after an hour."
        )
        with gr.Accordion("Live Telemetry (Powered by Nebius AI)", open=True):
            gr.Markdown("**Thinking & Safety Engine:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (Nebius Token Factory)\n\n"
                        "**Audio Perception (HEAR):** `faster-whisper` (Local CPU offline fallback)\n\n"
                        "*Background memory extraction & safety audit run asynchronously via Nebius API.*")
        history_state = gr.State([])
        session_state = gr.State(None, time_to_live=SESSION_TTL_S, delete_callback=_end_session)

        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🧑 Senior side")
                audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak (as the senior)")
                # Judges without a mic (or who'd rather not record their own voice)
                # can still drive every beat with one click.
                gr.Examples(
                    examples=[[str(SAMPLES_DIR / name)] for name in SAMPLE_CLIPS],
                    inputs=[audio_in],
                    label="No mic? Try a sample clip",
                    cache_examples=False,
                )
                run_btn = gr.Button("Send", variant="primary")
                transcript_out = gr.Markdown(label="Conversation")
                audio_out = gr.Audio(label="Companion's reply", autoplay=True)
            with gr.Column():
                gr.Markdown("## 👩 Caregiver side (live)")
                caregiver_panel = gr.Markdown(_format_caregiver_panel(None))
                with gr.Accordion("🎙️ Submit Caregiver Voice Memo (Beat 1)", open=False):
                    memo_audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Record context memo")
                    save_memo_btn = gr.Button("Save Voice Memo", variant="secondary")

        run_btn.click(
            fn=run_demo_turn,
            inputs=[audio_in, history_state, session_state],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel, session_state],
        )

        save_memo_btn.click(
            fn=save_caregiver_voice_memo,
            inputs=[memo_audio_in, session_state],
            outputs=[caregiver_panel, session_state],
        )

        # Independent of the click above -- this is what makes the caregiver
        # side feel "live" rather than only updating when the senior side
        # does. See the module docstring for why polling, not push.
        timer = gr.Timer(2)
        timer.tick(fn=_format_caregiver_panel, inputs=[session_state], outputs=[caregiver_panel])
        demo.load(fn=init_session, outputs=[session_state, caregiver_panel])
    return demo


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    build_demo().launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")))
