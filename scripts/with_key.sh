#!/usr/bin/env bash
# Run ONE command with the Nebius key in that command's environment only, and redact the
# key from everything the command prints. This is the sanctioned way for an assistant or a
# reviewer to make a live call: the key never enters a chat, a shell profile or a log, and
# the output says that a live key was used, so a review can state it truthfully.
#
# Usage: scripts/with_key.sh <command> [args...]
#        KEY_ENV_FILE=/path/to/.env scripts/with_key.sh python -m unittest tests.test_x
#
# The env file (default ./.env) is parsed as DATA, like scripts/key_status.sh: only the
# NEBIUS_API_KEY and NEBIUS_BASE_URL lines are read; nothing is sourced or eval'd.
# The command's exit code is returned unchanged. Exit 2 = no readable env file or no key.
set -u
env_file="${KEY_ENV_FILE:-.env}"
[ "$#" -ge 1 ] || { echo "usage: with_key.sh <command> [args...]" >&2; exit 2; }
[ -r "$env_file" ] || { echo "with_key: no readable $env_file" >&2; exit 2; }

NEBIUS_API_KEY=""
NEBIUS_BASE_URL=""
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  line="${line#"${line%%[![:space:]]*}"}"
  case "$line" in "export "*) line="${line#export }"; line="${line#"${line%%[![:space:]]*}"}";; esac
  case "$line" in
    NEBIUS_API_KEY=*)  name=NEBIUS_API_KEY;  val="${line#NEBIUS_API_KEY=}";;
    NEBIUS_BASE_URL=*) name=NEBIUS_BASE_URL; val="${line#NEBIUS_BASE_URL=}";;
    *) continue;;
  esac
  val="${val#"${val%%[![:space:]]*}"}"
  val="${val%"${val##*[![:space:]]}"}"
  case "$val" in
    \"*\") val="${val#\"}"; val="${val%\"}";;
    \'*\') val="${val#\'}"; val="${val%\'}";;
  esac
  printf -v "$name" '%s' "$val"
done < "$env_file"

[ -n "$NEBIUS_API_KEY" ] || { echo "with_key: NEBIUS_API_KEY not set in $env_file" >&2; exit 2; }
export NEBIUS_API_KEY
[ -n "$NEBIUS_BASE_URL" ] && export NEBIUS_BASE_URL

echo "with_key: LIVE Nebius key in use for: $*" >&2

set -o pipefail
"$@" 2>&1 | python3 -I -c '
import os, sys
k = os.environ["NEBIUS_API_KEY"]
for line in sys.stdin:
    sys.stdout.write(line.replace(k, "[REDACTED]"))
    sys.stdout.flush()
'
exit "${PIPESTATUS[0]}"
