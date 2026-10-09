"""Load this repo's own .env, and never a parent directory's.

python-dotenv's bare load_dotenv() searches upward from the calling file, so a checkout or
worktree with no .env of its own silently picked up a key from a parent directory (found in
the 2026-10-09 review runs). Live calls go through scripts/with_key.sh; see AGENTS.md.
"""
from pathlib import Path


def load_repo_env(root=None) -> bool:
    """Load <root>/.env (default: this repo's root) without overriding the environment.
    Returns True if a file was loaded. No upward search."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    path = Path(root).resolve() / ".env" if root else Path(__file__).resolve().parent / ".env"
    return bool(load_dotenv(path)) if path.is_file() else False
