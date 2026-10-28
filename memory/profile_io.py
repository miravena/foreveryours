"""One lock per profile file, and a unique-temp-file atomic JSON write.

`MemoryStore` (`<data_dir>/<profile>.json`) and `CaregiverFlags`
(`<data_dir>/<profile>.flags.json`) used to load a snapshot, mutate it and
flush it whole. Two instances on the same household -- a turn's background
AUDIT/extraction thread still alive past `webapp._BG_JOIN_TIMEOUT_S`, the
next turn, a caregiver memo save -- each flushed their own snapshot, so the
last writer silently dropped the other's items. Both flushes also shared ONE
fixed `.tmp` name, so two simultaneous flushes interleaved on it and one
`os.replace` could fail with FileNotFoundError.

The fix is a plain read-modify-write transaction: every write takes
`profile_lock(path)`, reloads the file from disk inside the lock, applies
its mutation and flushes through `atomic_write_json` before releasing.

Scope: the lock is PROCESS-LOCAL. The hosted Space runs one Gradio process
(`app.py`), so that is the whole race surface. Two separate processes on one
profile (e.g. `main.py` beside `webapp.py` with FY_SHARED_PROFILE=1) are
still last-writer-wins; `mkstemp` + `os.replace` still guarantees neither
ever sees a torn or partial file.

Lock order (also documented above `webapp._session_fs_lock`):
`webapp._session_fs_lock` -> `webapp._bg_threads_lock` -> profile lock
(store) -> profile lock (flags). A profile lock is a LEAF: never acquire
`_session_fs_lock` or `_bg_threads_lock` while holding one. The only nesting
of two profile locks is store -> flags (`MemoryStore.escalate_asked_conflicts`
calling `CaregiverFlags.add`).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

_registry_lock = threading.Lock()
_locks: dict[str, threading.RLock] = {}


def profile_lock(path: Path) -> threading.RLock:
    """The one lock for this profile file, keyed by its realpath so two
    spellings of the same file share it. Created on first use and never
    evicted (a few hundred sessions x 2 files is nothing). Re-entrant, so a
    write transaction may call another write method on the same store."""
    key = os.path.realpath(path)
    with _registry_lock:
        lock = _locks.get(key)
        if lock is None:
            lock = _locks[key] = threading.RLock()
        return lock


def atomic_write_json(path: Path, payload) -> None:
    """Write `payload` as indented JSON to a UNIQUE temp file in the same
    directory (`tempfile.mkstemp`, O_EXCL), then `os.replace` it over `path`,
    so a crash mid-write never leaves invalid JSON and two writers never
    share a temp file. On any failure the temp file is removed best-effort
    and the exception propagates; there is no retry."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(payload, indent=2))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
