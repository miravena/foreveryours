#!/usr/bin/env bash
# Independent OpenAI review of this branch's diff, via the Codex CLI.
#
#   scripts/openai_review.sh              # reviews main...HEAD
#   scripts/openai_review.sh origin/main  # reviews against another base
#
# Safe for assistants to run: it only prints the review. Login lives in ~/.codex
# (run `codex login` yourself, once); no key is read from or written to this repo.
# Codex runs read-only inside a throwaway `git archive` export of HEAD, so it never
# sees .env, data/, out/ or .venv. Only committed files are reviewed: commit first.
set -euo pipefail

BASE="${1:-main}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

command -v codex >/dev/null || { echo "codex CLI not found. Install it and run 'codex login' yourself." >&2; exit 1; }
git rev-parse --verify --quiet "$BASE" >/dev/null || { echo "unknown base: $BASE" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git archive HEAD | tar -C "$WORK" -xf -
git diff "$BASE"...HEAD > "$WORK/REVIEW.diff"
[[ -s "$WORK/REVIEW.diff" ]] || { echo "no diff between $BASE and HEAD, nothing to review" >&2; exit 0; }

cd "$WORK"
codex exec --sandbox read-only --skip-git-repo-check - <<'EOF'
Review the change in REVIEW.diff against the rest of this repo (read AGENTS.md first).
Report only real problems, most severe first, each with file:line and a concrete
failure scenario: bugs, broken demo beats, secrets or private data about to be
committed, docs that now disagree with the code, tests that don't test the change.
Respect the "Things people get wrong" section of AGENTS.md. Do not suggest style
rewrites. If nothing is wrong, say "no findings". Do not modify any files.
EOF
