"""Check that a Hugging Face Space runs the commit you expect (issue #11).

    python scripts/verify_space_sha.py elevenbaselab/foreveryours              # expect local HEAD
    python scripts/verify_space_sha.py elevenbaselab/foreveryours --sha <sha>  # expect this sha
    python scripts/verify_space_sha.py elevenbaselab/foreveryours --wait 900   # first wait for RUNNING
    python scripts/verify_space_sha.py elevenbaselab/foreveryours --smoke      # running app + view_api()

Reads the BUILD_INFO file that scripts/deploy_hf_space.py stages into the Space and
exits 0 only when it equals the expected sha. With --wait it first polls the Space
runtime until its stage is RUNNING (bounded by the given seconds), which is how the
deploy workflow (.github/workflows/deploy-space.yml) knows the new build is up before
it runs any live check. With --smoke it also connects to the running app through
gradio_client and requires that the app itself shows "Build: <sha7>" for the expected
sha (retrying until --wait runs out) and answers view_api(). BUILD_INFO alone only
proves the upload landed: right after an upload the previous build can still report
RUNNING, so --smoke is what proves the new build is the one serving.

HF_TOKEN is read from the environment only when present (the Space is public) and is
never printed. Everything that talks to the network is injectable (`api_factory`,
`downloader`, `client_factory`) so tests run offline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
BUILD_INFO = "BUILD_INFO"
RUNNING = "RUNNING"
BUILD_LINE = re.compile(r"Build: `([0-9a-f]{7,40})`")  # webapp._build_line()
FAILED_STAGES = {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE", "DELETING"}


def local_head_sha(root: Path = ROOT) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _token() -> str | None:
    return os.environ.get("HF_TOKEN") or None


def default_api_factory():
    from huggingface_hub import HfApi
    return HfApi(token=_token())


def default_downloader(space_id: str) -> str:
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(repo_id=space_id, filename=BUILD_INFO, repo_type="space",
                           token=_token(), force_download=True)
    return Path(path).read_text(encoding="utf-8")


def default_client_factory(space_id: str):
    from gradio_client import Client
    return Client(space_id, token=_token(), verbose=False)


def wait_until_running(space_id: str, timeout_s: float, api_factory: Callable = default_api_factory,
                       poll_s: float = 15.0, sleep: Callable[[float], None] = time.sleep,
                       clock: Callable[[], float] = time.monotonic, log: Callable[[str], None] = print) -> str:
    """Poll the Space runtime until stage == RUNNING. Returns the final stage; raises on
    a failed build or when `timeout_s` elapses."""
    api = api_factory()
    deadline = clock() + timeout_s
    last = None
    while True:
        stage = str(getattr(api.get_space_runtime(space_id), "stage", "")).upper()
        stage = stage.rsplit(".", 1)[-1]  # SpaceStage.RUNNING -> RUNNING
        if stage != last:
            log(f"{space_id}: runtime stage {stage}")
            last = stage
        if stage == RUNNING:
            return stage
        if stage in FAILED_STAGES:
            raise RuntimeError(f"{space_id} is in stage {stage}; check its Logs tab")
        if clock() >= deadline:
            raise TimeoutError(f"{space_id} not RUNNING after {int(timeout_s)}s (last stage {stage})")
        sleep(poll_s)


def space_build_sha(space_id: str, downloader: Callable[[str], str] = default_downloader) -> str:
    return downloader(space_id).strip()


def running_build_sha7(client) -> str | None:
    """The sha7 the running app renders as "Build: <sha7>", read from its Gradio config."""
    match = BUILD_LINE.search(json.dumps(getattr(client, "config", None) or {}))
    return match.group(1)[:7] if match else None


def smoke(space_id: str, expected_sha: str, client_factory: Callable = default_client_factory,
          *, wait_s: float = 0, poll_s: float = 15.0, sleep: Callable[[float], None] = time.sleep,
          clock: Callable[[], float] = time.monotonic, log: Callable[[str], None] = print) -> None:
    """Require the RUNNING app (not just the Space repo) to show the expected build, then
    check its API answers. Retries until `wait_s` runs out: right after an upload the old
    build keeps serving while the new one builds, and connecting can fail mid-restart."""
    want = expected_sha[:7]
    deadline = clock() + wait_s
    while True:
        try:
            client = client_factory(space_id)
            shown = running_build_sha7(client)
            problem = None if shown == want else f"running app shows build {shown or 'none'}"
        except Exception as exc:  # connection refused / 503 while the Space restarts
            client, problem = None, f"cannot connect to the running app ({type(exc).__name__})"
        if problem is None:
            break
        if clock() >= deadline:
            raise RuntimeError(f"{space_id}: {problem}, expected {want}")
        log(f"{space_id}: {problem}, waiting for {want}")
        sleep(poll_s)
    log(f"{space_id}: running app shows build {want}")
    info = client.view_api(return_format="dict", print_info=False)
    endpoints = info.get("named_endpoints", {}) if isinstance(info, dict) else {}
    if not endpoints:
        raise RuntimeError(f"{space_id}: view_api returned no named endpoints")
    log(f"{space_id}: {len(endpoints)} API endpoints reachable")


def verify(space_id: str, expected_sha: str, *, wait_s: float = 0, do_smoke: bool = False,
           api_factory: Callable = default_api_factory,
           downloader: Callable[[str], str] = default_downloader,
           client_factory: Callable = default_client_factory,
           sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
           log: Callable[[str], None] = print) -> int:
    if wait_s > 0:
        wait_until_running(space_id, wait_s, api_factory, sleep=sleep, clock=clock, log=log)
    try:
        deployed = space_build_sha(space_id, downloader)
    except Exception as exc:  # EntryNotFoundError etc.: the Space predates BUILD_INFO
        log(f"{space_id}: no readable {BUILD_INFO} ({type(exc).__name__}); "
            "the Space was deployed before build shas were recorded, redeploy to fix")
        return 1
    if deployed != expected_sha:
        log(f"{space_id}: MISMATCH deployed {deployed[:7]} expected {expected_sha[:7]}")
        return 1
    log(f"{space_id}: OK build {deployed[:7]} matches expected sha")
    if do_smoke:
        smoke(space_id, expected_sha, client_factory, wait_s=wait_s, sleep=sleep, clock=clock, log=log)
    return 0


def main(argv: list[str] | None = None, **hooks) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("space_id", help="<user-or-org>/<space-name>")
    parser.add_argument("--sha", default=None, help="expected full sha (default: local git HEAD)")
    parser.add_argument("--wait", type=float, default=0, metavar="SECONDS",
                        help="first poll the runtime until RUNNING, giving up after SECONDS")
    parser.add_argument("--smoke", action="store_true", help="also require the running app to show the expected build and answer view_api()")
    args = parser.parse_args(argv)
    expected = args.sha or local_head_sha()
    try:
        return verify(args.space_id, expected, wait_s=args.wait, do_smoke=args.smoke, **hooks)
    except (RuntimeError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
