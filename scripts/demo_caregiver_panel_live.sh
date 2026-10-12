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
# FY_SHARED_PROFILE=0 is forced (not just left unset): this demo's whole
# premise is a throwaway per-session store under $SESS_DIR, and a real .env
# with FY_SHARED_PROFILE=1 would otherwise leak through, making init_session
# write into the repo's actual shared data/dad.* store instead -- the one
# real thing this script must never touch (Codex review, scripts/openai_review.sh).
PORT="$PORT" FY_SESSIONS_DIR="$SESS_DIR" FY_SHARED_PROFILE=0 "$PYTHON" webapp.py >"$LOG" 2>&1 &
SERVER_PID=$!

base="http://127.0.0.1:$PORT"
up=0
for _ in $(seq 1 30); do
  sleep 0.5
  # A bind failure (port already taken by someone else's server, including
  # a real ForeverYours instance) makes OUR process exit -- but checking
  # "did OUR pid die" and "does /config look like Gradio" are both still
  # inferences from the network side, and an already-running, still-up
  # server on the same port passes both while OUR process is merely slow
  # to start. The only ground truth for "who is actually bound to $PORT"
  # is the kernel's own socket table: `ss -ltnp` names the owning pid of
  # the LISTEN socket directly, and a TCP port has exactly one listener,
  # so once ss confirms $SERVER_PID owns it, no other process -- Gradio
  # or not -- can be the one answering on it (Codex review,
  # scripts/openai_review.sh, two rounds: HTTP-shape checks alone can't
  # close this race, only socket ownership can).
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "FAIL our server process ($SERVER_PID) died before answering -- port $PORT may already be in use; log:"
    cat "$LOG"; exit 1
  fi
  if ! ss -ltnp 2>/dev/null | grep -E ":$PORT[[:space:]]" | grep -q "pid=$SERVER_PID,"; then
    continue  # not yet listening, or (if ever) listening under a different pid -- keep waiting, never trust it
  fi
  if curl -s -o /dev/null -w '' "$base/config" 2>/dev/null; then
    up=1; break
  fi
done
if [[ "$up" -ne 1 ]]; then
  echo "FAIL server never came up (or never proved it owns port $PORT); log:"; cat "$LOG"; exit 1
fi
echo "  ok   port $PORT's LISTEN socket is owned by our pid $SERVER_PID, and it answers $base/config"

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
