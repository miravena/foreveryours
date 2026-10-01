"""Application entrypoint for ForeverYours web interface.
Auto-detected by Hugging Face Spaces (as app.py) and cloud hosts.
"""
import os

if __name__ == "__main__":
    try:
        from webapp import build_demo

        app = build_demo()
        app.launch(
            server_name="0.0.0.0",
            server_port=int(os.environ.get("PORT", "7860")),
        )
    except ModuleNotFoundError as exc:
        print(f"Error: {exc}. Run 'pip install -r requirements.txt' to install web dependencies.")
