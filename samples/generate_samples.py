"""Utility script to generate offline demo .wav audio samples for the ForeverYours 4-beat demo.

Generates:
  - samples/caregiver_memo.wav (Beat 1 onboarding memo)
  - samples/senior_jazz.wav (Beat 2 conversation turn with durable fact)
  - samples/senior_distress.wav (Beat 3 worrying remark tripping safety fast-path)
  - samples/senior_grandson.wav (Beat 4 day-2 recall check for Leo)
"""
from pathlib import Path

SAMPLES = {
    "caregiver_memo.wav": (
        "Dad loves jazz. His grandson is named Leo. Avoid talking about driving. "
        "I'm dropping off groceries at 4 PM today."
    ),
    "senior_jazz.wav": (
        "Hi, how's it going today? I've been listening to a lot of Miles Davis lately, I love him."
    ),
    "senior_distress.wav": (
        "I fell down earlier and I'm scared."
    ),
    "senior_grandson.wav": (
        "I forgot, what is my grandson's name?"
    ),
}

def generate_all() -> None:
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        for filename, text in SAMPLES.items():
            dest = out_dir / filename
            print(f"Generating {dest.name} with pyttsx3...")
            engine.save_to_file(text, str(dest))
            engine.runAndWait()
            print(f"  Saved {dest.name} ({dest.stat().st_size} bytes)")
    except ImportError:
        import subprocess
        import sys

        if sys.platform == "win32":
            ps_script = out_dir / "generate_samples.ps1"
            print(f"pyttsx3 not installed; using Windows Speech synthesizer via {ps_script.name}...")
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)], check=True)
        else:
            raise RuntimeError("pyttsx3 is required on non-Windows platforms: pip install pyttsx3")

    print("\nAll sample audio files generated successfully in samples/ directory.")

if __name__ == "__main__":
    generate_all()
