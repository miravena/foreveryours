#!/usr/bin/env bash
# Runtime/deployment evidence for issue #140 (caregiver panel privacy gate).
#
# Launches the REAL webapp.py Gradio server as its own OS process, drives it
# over its actual HTTP API (not an in-process function call or a unit test)
# to create a real session, injects an EMOTIONAL-scope memory and a disclosed
# caregiver flag directly into that session's on-disk store -- the same
# files the running process reads on every panel poll -- then calls the live
# _format_caregiver_panel render over the same HTTP API and checks the
# response. This is the deployed production code path executing end-to-end
# over its real network API, not a mock.
#
# Safe to re-run: uses a throwaway FY_SESSIONS_DIR and PORT, kills the server
# and removes the temp dir on exit regardless of outcome.
#
#   scripts/demo_caregiver_panel_live.sh
#   PYTHON=/path/to/python PORT=7913 scripts/demo_caregiver_panel_live.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON=python3; fi
fi
PORT="${PORT:-7913}"
SESS_DIR="$(mktemp -d)"
LOG="$(mktemp)"
SERVER_PID=""

cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$SESS_DIR" "$LOG"
}
trap cleanup EXIT

cd "$ROOT"
echo "== launching webapp.py on 127.0.0.1:$PORT (FY_SESSIONS_DIR=$SESS_DIR)"
PORT="$PORT" FY_SESSIONS_DIR="$SESS_DIR" "$PYTHON" webapp.py >"$LOG" 2>&1 &
SERVER_PID=$!

base="http://127.0.0.1:$PORT"
up=0
for _ in $(seq 1 30); do
  if curl -s -o /dev/null -w '' "$base/config" 2>/dev/null; then up=1; break; fi
  sleep 0.5
done
if [[ "$up" -ne 1 ]]; then
  echo "FAIL server never came up; log:"; cat "$LOG"; exit 1
fi
echo "  ok   server answering on $base"

SESSION_HASH="demo$$-$RANDOM"  # Gradio State (session_id) is bound to session_hash, not
                                # the explicit data payload -- every call in this script
                                # must reuse the SAME hash as init_session's, or the server
                                # falls back to a stateless "no session yet" render.

call() {  # call <api_name> <json-data-array> -> prints the "data: [...]" line
  local api="$1" data="$2" hash="$SESSION_HASH"
  local event
  event="$(curl -s -X POST "$base/gradio_api/call/$api" \
    -H 'Content-Type: application/json' \
    -d "{\"data\": $data, \"session_hash\": \"$hash\"}" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["event_id"])')"
  curl -s -N "$base/gradio_api/call/$api/$event" | grep '^data: '
}

echo "== creating a real session via POST /gradio_api/call/init_session"
init_line="$(call init_session '[]')"
echo "$init_line" | fold -w 160
session_id="$(find "$SESS_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | head -1)"
if [[ -z "$session_id" ]]; then
  echo "FAIL no session directory created under $SESS_DIR"; exit 1
fi
echo "  ok   session $session_id created on disk"

echo "== injecting an EMOTIONAL-scope memory + a disclosed flag straight into that session's live store"
"$PYTHON" - "$SESS_DIR/$session_id/data" <<'PY'
import sys
from pathlib import Path
from memory.store import MemoryStore, MemoryScope
from caregiver import CaregiverFlags, DEFAULT_PROFILE_ID

data_dir = Path(sys.argv[1])
store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
store.add("I feel lonely since my wife died", source="conversation_extract", scope=MemoryScope.EMOTIONAL.value)

flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
flags.add("Dad mentioned feeling dizzy this morning", severity="info", disclosed_to_senior=True)
print("  wrote: EMOTIONAL memory 'I feel lonely since my wife died' + flag 'Dad mentioned feeling dizzy this morning'")
PY

echo "== calling the LIVE _format_caregiver_panel render over the HTTP API"
panel_line="$(call _format_caregiver_panel "[\"$session_id\"]")"
echo "$panel_line" | fold -w 160

fail=0
if grep -qF 'lonely since my wife died' <<<"$panel_line"; then
  echo "FAIL the EMOTIONAL memory text appears in the live-rendered panel"; fail=1
else
  echo "  ok   EMOTIONAL memory text is absent from the live-rendered panel"
fi
if grep -qF 'Dad mentioned feeling dizzy this morning' <<<"$panel_line"; then
  echo "  ok   the disclosed flag is shown"
else
  echo "FAIL the disclosed flag is missing from the live-rendered panel"; fail=1
fi
if grep -qF 'Dad loves jazz' <<<"$panel_line"; then
  echo "  ok   a caregiver memo is shown"
else
  echo "FAIL a caregiver memo is missing from the live-rendered panel"; fail=1
fi

exit "$fail"
