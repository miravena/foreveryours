"""Record the REAL ForeverYours CLI as asciinema v2 casts.

Unlike the Claims Copilot pipeline this is ported from, none of these three
beats need a Nebius key -- beat1 (caregiver memo), beat3 (fast-path safety,
no-key graceful degradation), and day2 (cross-process recall proof) all work
with zero API dependency. No proxy, no routed model, nothing hidden.

Nothing here is staged. asciinema records the real terminal (stdout+stderr)
of the real `python main.py <beat>` process; render_terminal.py later
replays these exact casts. If a live run fails, this script exits non-zero
and writes no cast -- we do NOT fall back to a hand-made terminal.

Runs against an isolated copy of app/ (not the live one serving webapp.py)
so recording doesn't reset the data/ a human might be testing against
concurrently -- see video/README.md.
"""
import fcntl
import os
import pty
import shlex
import struct
import sys
import termios

HERE = os.path.dirname(os.path.abspath(__file__))
# APP is an ISOLATED COPY of app/ (no .venv, no data/) -- see video/README.md
# for why: recording resets data/ and out/, which would clobber a human's
# live webapp.py session if we ran against the real app/ directory.
APP = os.environ.get("FOREVERYOURS_RECORD_APP", os.path.join(HERE, "..", "app"))
# The interpreter is the REAL app/'s venv (has the deps installed) -- only
# the data/ isolation needs to be a separate directory, not the venv itself.
PY = os.environ.get(
    "FOREVERYOURS_RECORD_PY", os.path.join(HERE, "..", "app", ".venv", "bin", "python")
)
CASTS = os.path.join(HERE, "casts")


def _run_in_pty(argv, env, rows, cols, cwd):
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.chdir(cwd)
        os.execvpe(argv[0], argv, env)
        os._exit(127)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    try:
        while True:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
    finally:
        os.close(fd)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def _wrapper(prompt_cmd, real_cmd):
    # prompt_cmd is passed as a printf ARGUMENT (shlex-quoted), never spliced
    # into the single-quoted format string -- a literal apostrophe in
    # prompt_cmd (e.g. "I'm scared") would otherwise close that quote early
    # and corrupt the script (caught when live_beat3's cast came back empty).
    quoted_prompt = shlex.quote(prompt_cmd)
    return (
        "#!/bin/bash\n"
        "clear\n"
        "PS1_SHOWN='foreveryours$ '\n"
        f'printf \'%s%s\\n\' "$PS1_SHOWN" {quoted_prompt}\n'
        "sleep 1.2\n"
        f"{real_cmd}\n"
        "echo\n"
        "printf '%s\\n' \"$PS1_SHOWN\"\n"
        "sleep 1.5\n"
    )


def _record(name, prompt_cmd, real_cmd, rows=30, cols=100):
    os.makedirs(CASTS, exist_ok=True)
    wrapper = os.path.join(CASTS, f"_{name}.sh")
    with open(wrapper, "w") as fh:
        fh.write(_wrapper(prompt_cmd, real_cmd))
    os.chmod(wrapper, 0o755)
    cast = os.path.join(CASTS, f"{name}.cast")

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = "xterm-256color"
    print(f"Recording {name}.cast ...")

    argv = ["asciinema", "rec", "--overwrite", "-c", f"bash {wrapper}", cast]
    rc = _run_in_pty(argv, env, rows, cols, cwd=APP)
    os.remove(wrapper)
    if rc != 0 or not os.path.exists(cast) or os.path.getsize(cast) < 200:
        sys.exit(f"FAILED to record {name}: rc={rc}. Refusing to fake a cast.")
    print(f"  wrote {cast} ({os.path.getsize(cast)} bytes)")
    return cast


def main():
    data_dir = os.path.join(APP, "data")
    out_dir = os.path.join(APP, "out")
    import shutil
    shutil.rmtree(data_dir, ignore_errors=True)
    shutil.rmtree(out_dir, ignore_errors=True)

    _record("live_beat1", "python main.py beat1", f'"{PY}" main.py beat1 --no-play')
    # beat3 is the only beat that touches pyttsx3 (speech synthesis runs even
    # with --no-play, which only skips playback). Its espeak driver has a
    # harmless ctypes-callback cleanup quirk that prints a traceback -- and
    # that traceback includes the full site-packages path (an internal
    # /home/<user>/... filesystem path), which the secret/PII gate correctly
    # refuses to publish. It's library noise, not demo content, so it's
    # suppressed here rather than scrubbed after the fact.
    _record("live_beat3", 'python main.py beat3 "I fell down earlier and I\'m scared"',
            f'"{PY}" main.py beat3 "I fell down earlier and I\'m scared" --no-play 2>/dev/null')
    _record("live_day2", "python main.py day2", f'"{PY}" main.py day2 --no-play')
    print("All three casts recorded.")


if __name__ == "__main__":
    main()
