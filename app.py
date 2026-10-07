"""Application entrypoint for ForeverYours web interface.
Auto-detected by Hugging Face Spaces (as app.py) and cloud hosts.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from pipeline import hear
    from webapp import build_demo
    hear._get_whisper_model()  # warm up at import, not on the first judge's click (#81 B4)
    app = build_demo()
except ModuleNotFoundError as exc:
    print(f"Error: {exc}. Run 'pip install -r requirements.txt' to install web dependencies.")
    app = None

if __name__ == "__main__" and app:
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
    )
