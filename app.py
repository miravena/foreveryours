"""Application entrypoint for ForeverYours web interface.
Auto-detected by Hugging Face Spaces (as app.py) and cloud hosts.
"""
import os

from envload import load_repo_env

try:
    import spaces  # present on Hugging Face Spaces; absent locally, which is fine
except ImportError:
    spaces = None

if spaces is not None:
    @spaces.GPU(duration=1)
    def _zerogpu_marker():
        """Never called. The app runs on CPU; ZeroGPU hardware refuses to boot
        a Space with no @spaces.GPU function (#11). Off ZeroGPU it does nothing."""

load_repo_env()

try:
    from pipeline import hear
    from webapp import build_demo, MAX_AUDIO_UPLOAD_BYTES
    hear.warm_up()  # (#81 B4)
    app = build_demo()
except ModuleNotFoundError as exc:
    print(f"Error: {exc}. Run 'pip install -r requirements.txt' to install web dependencies.")
    app = None

if __name__ == "__main__" and app:
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        max_file_size=f"{MAX_AUDIO_UPLOAD_BYTES}b",  # Gradio refuses oversize uploads too
        enable_monitoring=False,  # no /monitoring dashboard: it lists usage and request details to anyone
    )
