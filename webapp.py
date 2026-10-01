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
"""
from __future__ import annotations

import datetime
import os
import threading
from pathlib import Path

import gradio as gr

from caregiver import DEFAULT_CAREGIVER_NAME, DEFAULT_PROFILE_ID, CaregiverFlags
from memory.store import MemoryStore
from pipeline import hear
from pipeline.orchestrator import run_turn

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_DIR = Path(__file__).resolve().parent / "out" / "audio"
MAX_DAILY_REQUESTS = int(os.environ.get("MAX_DAILY_REQUESTS", "50"))
MAX_HISTORY_TURNS = 6  # (user, assistant) pairs kept -- bounds prompt growth, not a product limit

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


def _format_caregiver_panel() -> str:
    """Reads straight from disk every call -- this is what makes it a live
    panel rather than a snapshot: whatever main.py or another browser tab
    wrote is reflected here within one poll interval (see the Timer below)."""
    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR)

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


def run_demo_turn(
    audio_in: str | None, history: list[dict]
) -> tuple[str, str | None, list[dict], str]:
    store = MemoryStore(DEFAULT_PROFILE_ID, DATA_DIR)
    flags = CaregiverFlags(DEFAULT_PROFILE_ID, DATA_DIR)

    if not _rate_limit_ok():
        return (
            "This demo has hit its daily request cap -- please try again tomorrow "
            "(protects the shared Nebius API credits). See CONTRIBUTING.md.",
            None,
            history,
            _format_caregiver_panel(),
        )

    if not audio_in:
        return "Record or upload something first.", None, history, _format_caregiver_panel()

    transcript = hear.transcribe(Path(audio_in))
    if not transcript.strip():
        return "Couldn't make out any speech in that clip -- try again.", None, history, _format_caregiver_panel()

    result = run_turn(
        transcript, store, flags, AUDIO_DIR, caregiver_name=DEFAULT_CAREGIVER_NAME, history=history
    )

    if result.background_thread is not None:
        result.background_thread.join(timeout=10)

    new_history = history + [
        {"role": "user", "content": transcript},
        {"role": "assistant", "content": result.reply_text},
    ]
    new_history = new_history[-(MAX_HISTORY_TURNS * 2) :]

    reply_audio = str(result.audio_paths[0]) if result.audio_paths else None
    transcript_and_reply = f'**Dad said:** "{transcript}"\n\n**Companion replied:** "{result.reply_text}"'
    return transcript_and_reply, reply_audio, new_history, _format_caregiver_panel()


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="ForeverYours — judge demo") as demo:
        gr.Markdown(
            "# ForeverYours\n"
            "Watch both sides at once: talk as the senior on the left, watch the caregiver side "
            "on the right update live. Try an ordinary remark first, then try something like "
            "\"I fell down earlier\" -- the right side updates within a couple seconds, "
            "and the reply on the left tells Dad, out loud, that it's doing that. "
            "No conversation history persists after you close this tab (issue #16)."
        )
        history_state = gr.State([])

        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🧑 Senior side")
                audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak (as the senior)")
                run_btn = gr.Button("Send", variant="primary")
                transcript_out = gr.Markdown(label="Conversation")
                audio_out = gr.Audio(label="Companion's reply", autoplay=True)
            with gr.Column():
                gr.Markdown("## 👩 Caregiver side (live)")
                caregiver_panel = gr.Markdown(_format_caregiver_panel())

        run_btn.click(
            fn=run_demo_turn,
            inputs=[audio_in, history_state],
            outputs=[transcript_out, audio_out, history_state, caregiver_panel],
        )

        # Independent of the click above -- this is what makes the caregiver
        # side feel "live" rather than only updating when the senior side
        # does. See the module docstring for why polling, not push.
        timer = gr.Timer(2)
        timer.tick(fn=_format_caregiver_panel, outputs=[caregiver_panel])
    return demo


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    build_demo().launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")))
