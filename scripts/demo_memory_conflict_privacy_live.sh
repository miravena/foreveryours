#!/usr/bin/env bash
# Runtime/deployment evidence for issue #165 and duplicates #154, #156, #158,
# #160, #163, #166, #167 (memory-conflict text never reaches the caregiver).
#
# Launches the REAL webapp.py Gradio server as its own OS process, drives it
# over its actual HTTP API (not an in-process function call or a unit test)
# to create a real session, calls the LIVE add_conflict/mark_conflicts_asked/
# escalate_asked_conflicts methods against that session's on-disk store --
# the same files the running process reads on every panel poll -- then calls
# the live _format_caregiver_panel render over the same HTTP API at each step
# and checks the response, and finally reads the raw on-disk store file to
# confirm the conflict text was scrubbed. This is the deployed production
# code path executing end-to-end over its real network API, not a mock.
#
# Safe to re-run: uses a throwaway FY_SESSIONS_DIR and PORT, kills the server
# and removes the temp dir on exit regardless of outcome.
#
#   scripts/demo_memory_conflict_privacy_live.sh
#   PYTHON=/path/to/python PORT=7914 scripts/demo_memory_conflict_privacy_live.sh
set -euo pipefail

if ! command -v ss >/dev/null 2>&1; then
  echo "FAIL this script requires 'ss' (Debian/Ubuntu package: iproute2) to verify" >&2
  echo "     which process actually owns \$PORT before trusting it -- not installed." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON=python3; fi
fi
PORT="${PORT:-7914}"
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
PORT="$PORT" FY_SESSIONS_DIR="$SESS_DIR" FY_SHARED_PROFILE=0 "$PYTHON" webapp.py >"$LOG" 2>&1 &
SERVER_PID=$!

base="http://127.0.0.1:$PORT"
up=0
for _ in $(seq 1 30); do
  sleep 0.5
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "FAIL our server process ($SERVER_PID) died before answering -- port $PORT may already be in use; log:"
    cat "$LOG"; exit 1
  fi
  if ! ss -ltnp 2>/dev/null | grep -E ":$PORT[[:space:]]" | grep -q "pid=$SERVER_PID,"; then
    continue
  fi
  if curl -s -o /dev/null -w '' "$base/config" 2>/dev/null; then
    up=1; break
  fi
done
if [[ "$up" -ne 1 ]]; then
  echo "FAIL server never came up (or never proved it owns port $PORT); log:"; cat "$LOG"; exit 1
fi
echo "  ok   port $PORT's LISTEN socket is owned by our pid $SERVER_PID, and it answers $base/config"

SESSION_HASH="demo$$-$RANDOM"

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

PRIVATE_OLD="I feel lonely since my wife died"
PRIVATE_NEW="I feel fine"
PRIVATE_REASON="senior said they are lonely"
STORE_FILE="$SESS_DIR/$session_id/data/$($PYTHON -c "
import webapp
print(webapp.DEFAULT_PROFILE_ID)
").json"

fail=0

# Checks all three conflict fields independently (old fact, new fact, reason
# -- not just two hardcoded words from the old fact), so a leak confined to
# the new fact or the reason can't slip past this script (Codex review,
# scripts/openai_review.sh).
check_private_absent() {
  local haystack="$1" label="$2" ok=0
  # Guard against a Gradio error or empty response being mistaken for a
  # clean render: "data: null" (or any response missing the panel's own
  # fixed heading) contains none of the private words either, which would
  # make every check below pass without ever looking at a real panel
  # (Codex review, scripts/openai_review.sh). The on-disk-file check passes
  # a raw JSON blob here instead of an SSE line, so it skips this guard.
  if [[ "$label" != on\ disk* ]] && ! grep -qF '### Briefed memory' <<<"$haystack"; then
    echo "FAIL response $label does not look like a real panel render (missing '### Briefed memory'): $haystack"
    return 1
  fi
  if grep -qF "$PRIVATE_OLD" <<<"$haystack"; then
    echo "FAIL old fact ('$PRIVATE_OLD') appears $label"; ok=1
  fi
  if grep -qF "$PRIVATE_NEW" <<<"$haystack"; then
    echo "FAIL new fact ('$PRIVATE_NEW') appears $label"; ok=1
  fi
  if grep -qF "$PRIVATE_REASON" <<<"$haystack"; then
    echo "FAIL reason ('$PRIVATE_REASON') appears $label"; ok=1
  fi
  if [[ "$ok" -eq 0 ]]; then
    echo "  ok   old fact, new fact and reason are all absent $label"
  fi
  return "$ok"
}

echo "== add_conflict() straight into that session's live store"
"$PYTHON" - "$SESS_DIR/$session_id/data" "$PRIVATE_OLD" "$PRIVATE_NEW" "$PRIVATE_REASON" <<'PY'
import sys
from pathlib import Path
from memory.store import MemoryStore
from caregiver import DEFAULT_PROFILE_ID

data_dir = Path(sys.argv[1])
store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
store.add_conflict(sys.argv[2], sys.argv[3], sys.argv[4])
print("  wrote: pending conflict", sys.argv[2], "|", sys.argv[3], "|", sys.argv[4])
PY

echo "== calling the LIVE _format_caregiver_panel render right after add_conflict()"
panel_line="$(call _format_caregiver_panel "[\"$session_id\"]")"
echo "$panel_line" | fold -w 160
check_private_absent "$panel_line" "in the live-rendered panel after add_conflict()" || fail=1

echo "== mark_conflicts_asked(), then re-checking the live panel"
"$PYTHON" - "$SESS_DIR/$session_id/data" <<'PY'
import sys
from pathlib import Path
from memory.store import MemoryStore
from caregiver import DEFAULT_PROFILE_ID
MemoryStore(DEFAULT_PROFILE_ID, Path(sys.argv[1])).mark_conflicts_asked()
PY
panel_line="$(call _format_caregiver_panel "[\"$session_id\"]")"
check_private_absent "$panel_line" "in the live-rendered panel after mark_conflicts_asked()" || fail=1

echo "== escalate_asked_conflicts(), then re-checking the live panel"
"$PYTHON" - "$SESS_DIR/$session_id/data" <<'PY'
import sys
from pathlib import Path
from memory.store import MemoryStore
from caregiver import CaregiverFlags, DEFAULT_PROFILE_ID
data_dir = Path(sys.argv[1])
store = MemoryStore(DEFAULT_PROFILE_ID, data_dir)
flags = CaregiverFlags(DEFAULT_PROFILE_ID, data_dir)
store.escalate_asked_conflicts(flags)
PY
panel_line="$(call _format_caregiver_panel "[\"$session_id\"]")"
echo "$panel_line" | fold -w 160
check_private_absent "$panel_line" "in the live-rendered panel after escalate_asked_conflicts()" || fail=1
if grep -qF 'Unresolved Memory Ambiguity: a memory question was asked and left unanswered.' <<<"$panel_line"; then
  echo "  ok   the fixed, content-free escalation flag is shown"
else
  echo "FAIL the fixed, content-free escalation flag is missing from the live-rendered panel"; fail=1
fi

echo "== reading the raw on-disk store file for this session"
raw="$(cat "$STORE_FILE")"
check_private_absent "$raw" "on disk at $STORE_FILE" || fail=1

exit "$fail"
