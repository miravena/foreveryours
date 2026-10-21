"""Deploy the judge-facing web demo to a Hugging Face Space (issue #11).

    pip install huggingface_hub
    HF_TOKEN=hf_... NEBIUS_API_KEY=... python scripts/deploy_hf_space.py <user-or-org>/<space-name>

    python scripts/deploy_hf_space.py <user>/<space> --dry-run   # stage only, no upload
    python scripts/deploy_hf_space.py <user>/<space> --hardware zero-a10g   # free-account path

What it does, in order:
1. Stages only what the Space needs (app code, samples, requirements.txt,
   packages.txt, LICENSE) into a temp folder -- never .env, data/, out/,
   tests/, video/ or docs/.
2. Writes a Space README.md with the YAML config header Spaces reads
   (sdk: gradio, app_file: app.py). The GitHub README stays header-free.
3. Creates the Space if it doesn't exist, uploads the folder, and sets
   NEBIUS_API_KEY as a Space *secret* (never a committed file) plus the
   non-secret variables below.

Why a script instead of "push app.py to a Space": the Space needs a config
header our GitHub README shouldn't carry, and the key must go in as a
secret. Doing either by hand at deadline time is where mistakes happen.

Hardware: since mid-2026 Hugging Face only lets PRO accounts (or Team/Enterprise
orgs) run a Gradio Space on cpu-basic. A free account older than 30 days with a
verified email can still host up to 2 ZeroGPU Spaces, so --hardware zero-a10g
deploys there. The app is CPU-only; ZeroGPU just needs one @spaces.GPU function
to boot, which app.py provides. Hardware is set when the Space is created, and
requested again if an existing Space is on something else.

Free CPU Spaces sleep after ~48h without traffic; the first click after that
waits on a cold start (faster-whisper model download + espeak). A daily
keep-awake request from an always-on machine covers this through the end of
judging -- see ADR-003 for the command and its schedule.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STAGE_FILES = [
    "app.py", "webapp.py", "caregiver.py", "envload.py", "__init__.py",
    "requirements.txt", "packages.txt", "LICENSE",
]
STAGE_DIRS = ["memory", "pipeline", "safety"]
SAMPLE_GLOB = "samples/*.wav"

HARDWARE_CHOICES = ["cpu-basic", "zero-a10g", "cpu-upgrade"]
ZEROGPU_REQUIREMENT = "spaces  # ZeroGPU runtime; app.py registers its @spaces.GPU marker with it\n"

SPACE_VARIABLES = {
    "ASR_BACKEND": "whisper_local",  # Token Factory has no transcription endpoint (PR #25)
    "ASR_MODEL": "base.en",
    "MAX_DAILY_REQUESTS": "50",  # one number everywhere: README, this script, #11 (#81 A1)
    "SESSION_TTL_S": "3600",
}

SPACE_README = """---
title: ForeverYours
emoji: 🎙️
colorFrom: indigo
colorTo: yellow
sdk: gradio
sdk_version: {gradio_version}
python_version: "3.10.13"
app_file: app.py
pinned: false
license: mit
short_description: A voice companion the family briefs, with honest flags
---

# ForeverYours: live demo

Talk as the senior on the left (or click a sample clip); watch the caregiver side on the right.
Each visitor gets a private demo household, removed about an hour after the tab closes; recorded
clips can stay in Gradio's file cache for up to about 70 minutes
([privacy details](https://github.com/miravena/foreveryours/blob/main/docs/PRIVACY.md)).

Source, setup and docs: https://github.com/miravena/foreveryours
"""


def stage(dest: Path, gradio_version: str, hardware: str = "cpu-basic") -> list[str]:
    for name in STAGE_FILES:
        shutil.copy2(ROOT / name, dest / name)
    if hardware.startswith("zero-"):
        # Only the Space gets `spaces`; local installs and CI don't need it.
        with open(dest / "requirements.txt", "a", encoding="utf-8") as req:
            req.write(ZEROGPU_REQUIREMENT)
    for name in STAGE_DIRS:
        shutil.copytree(
            ROOT / name, dest / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    (dest / "samples").mkdir()
    for wav in sorted(ROOT.glob(SAMPLE_GLOB)):
        shutil.copy2(wav, dest / "samples" / wav.name)
    (dest / "README.md").write_text(
        SPACE_README.format(gradio_version=gradio_version), encoding="utf-8"
    )
    return sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("space_id", help="<user-or-org>/<space-name>")
    parser.add_argument("--dry-run", action="store_true", help="stage and list files, upload nothing")
    parser.add_argument("--hardware", choices=HARDWARE_CHOICES, default="cpu-basic",
                        help="Space hardware (default cpu-basic, which needs PRO; "
                             "zero-a10g works on an eligible free account)")
    parser.add_argument("--private", action="store_true", help="create the Space private (judges can't reach it)")
    parser.add_argument("--gradio-version", default=None, help="sdk_version for the Space (default: installed gradio)")
    parser.add_argument("--keep-stage", type=Path, default=None, help="also copy the staged folder here")
    args = parser.parse_args()

    gradio_version = args.gradio_version
    if gradio_version is None:
        try:
            import gradio
            gradio_version = gradio.__version__
        except ImportError:
            print("gradio not installed; pass --gradio-version", file=sys.stderr)
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        stage_dir = Path(tmp)
        files = stage(stage_dir, gradio_version, args.hardware)
        print(f"Staged {len(files)} files for {args.space_id} "
              f"(gradio {gradio_version}, hardware {args.hardware}):")
        for f in files:
            print(f"  {f}")
        if args.keep_stage:
            shutil.copytree(stage_dir, args.keep_stage, dirs_exist_ok=True)
            print(f"Copied staging folder to {args.keep_stage}")
        if args.dry_run:
            print("Dry run: nothing uploaded.")
            return 0

        token = os.environ.get("HF_TOKEN")
        nebius_key = os.environ.get("NEBIUS_API_KEY")
        if not token:
            print("HF_TOKEN is not set (needs a write token from huggingface.co/settings/tokens).", file=sys.stderr)
            return 2
        if not nebius_key:
            print("NEBIUS_API_KEY is not set; without it the Space only runs the offline fast-path. "
                  "Set it, or re-run with NEBIUS_API_KEY= explicitly empty to deploy anyway.", file=sys.stderr)
            if "NEBIUS_API_KEY" not in os.environ:
                return 2

        from huggingface_hub import HfApi

        api = HfApi(token=token)
        api.create_repo(args.space_id, repo_type="space", space_sdk="gradio",
                        space_hardware=args.hardware, private=args.private, exist_ok=True)
        runtime = api.get_space_runtime(args.space_id)
        # exist_ok=True leaves an existing Space's hardware alone. A pending request
        # wins over the current hardware, so compare against that first.
        if (runtime.requested_hardware or runtime.hardware) != args.hardware:
            api.request_space_hardware(args.space_id, args.hardware)
        if nebius_key:
            api.add_space_secret(args.space_id, "NEBIUS_API_KEY", nebius_key)
        for key, value in SPACE_VARIABLES.items():
            api.add_space_variable(args.space_id, key, value)
        api.upload_folder(folder_path=str(stage_dir), repo_id=args.space_id, repo_type="space",
                          commit_message="Deploy ForeverYours demo")

    print(f"Deployed. Space: https://huggingface.co/spaces/{args.space_id} "
          "(first build takes a few minutes; watch its Logs tab).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
