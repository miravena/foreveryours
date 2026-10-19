#!/usr/bin/env bash
# Runtime/deployment evidence for issues #148 (PRIMARY), #149, #150, #151
# (session sweeper + _end_session race-free & symlink-safe; bad session id
# never blocks the crisis fast path).
#
# Launches the REAL webapp.py Gradio server as its own OS process and
# drives it over its actual HTTP API (not an in-process function call or a
# unit test with mocked internals):
#
#   1. Creates a real session via init_session, then creates a same-
#      directory symlink alias (a valid-hex-name entry under
#      FY_SESSIONS_DIR whose target is that same real session directory)
#      and a stray non-hex directory, both backdated past SESSION_TTL_S.
#      Calling init_session again forces a REAL _sweep_stale_sessions() run
#      inside the live server process (init_session -> _new_session() ->
#      _sweep_stale_sessions()). Checks the symlink entry and the stray
#      directory both survive that real sweep, and the symlink's target
#      directory (the original session) still has its files intact --
#      i.e. the sweep never rmtree's through the alias.
#   2. Imports the real webapp.py module fresh (no unittest, no mocking)
#      against the SAME FY_SESSIONS_DIR the live server is using, and calls
#      run_demo_turn_streaming / save_caregiver_text_memo directly with a
#      malformed/foreign session id ("../x") -- the crisis fast-path still
#      fires, a fresh valid session id comes back, and the memo saver
#      returns its normal placeholder text, no raise, nothing written
#      outside FY_SESSIONS_DIR. This is NOT done over the HTTP API: Gradio
#      tracks session_state as a server-side gr.State value keyed by
#      session_hash and does not accept a client-supplied value for it
#      (confirmed empirically -- see the comment at that step), so an
#      external HTTP caller cannot inject an arbitrary session id at all.
#      That is exactly why the unit tests call these functions
#      directly in Python rather than over HTTP, and why this step does
#      the same against the live server's real on-disk state instead.
#
# _end_session itself and the background periodic sweeper thread have no
# HTTP-exposed trigger (one is a gr.State delete_callback fired by Gradio
# internally on tab-close/TTL, the other a daemon thread on a timer) --
# step 1 proves the SAME _sweep_stale_sessions() code path _end_session
# shares (skip-if-symlink, skip-if-invalid-name) live over HTTP, which is
# the shared mechanism issues #148/#150/#151 depend on.
#
# Safe to re-run: uses a throwaway FY_SESSIONS_DIR and PORT, kills the
# server and removes the temp dir on exit regardless of outcome.
#
#   scripts/demo_session_safety_live.sh
#   PYTHON=/path/to/python PORT=7917 scripts/demo_session_safety_live.sh
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
PORT="${PORT:-7917}"
SESS_DIR="$(mktemp -d)"
VICTIM_ROOT="$(mktemp -d)"
LOG="$(mktemp)"
SERVER_PID=""

cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$SESS_DIR" "$LOG" "$VICTIM_ROOT"
}
trap cleanup EXIT

cd "$ROOT"
echo "== launching webapp.py on 127.0.0.1:$PORT (FY_SESSIONS_DIR=$SESS_DIR, SESSION_TTL_S=30)"
# NEBIUS_API_KEY is set empty so neither the server (which loads .env) nor the
# in-process step below makes a live, billed THINK call; load_dotenv never
# overrides a variable that is already set.
NEBIUS_API_KEY= PORT="$PORT" FY_SESSIONS_DIR="$SESS_DIR" FY_SHARED_PROFILE=0 SESSION_TTL_S=30 \
  "$PYTHON" webapp.py >"$LOG" 2>&1 &
SERVER_PID=$!

base="http://127.0.0.1:$PORT"
up=0
for _ in $(seq 1 30); do
  sleep 0.5
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "FAIL our server process ($SERVER_PID) died before answering; log:"; cat "$LOG"; exit 1
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

fail=0

echo "== creating a real session via POST /gradio_api/call/init_session"
init_line="$(call init_session '[]')"
session_id="$(find "$SESS_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | head -1)"
if [[ -z "$session_id" ]]; then
  echo "FAIL no session directory created under $SESS_DIR"; exit 1
fi
echo "  ok   session $session_id created on disk"

echo "== creating an in-directory symlink alias + a stray non-hex directory, both backdated past the 30s TTL (session_id itself stays fresh)"
alias_id="$("$PYTHON" -c 'import uuid; print(uuid.uuid4().hex)')"
ln -s "$SESS_DIR/$session_id" "$SESS_DIR/$alias_id"
mkdir -p "$SESS_DIR/not-a-session-id"
echo marker > "$SESS_DIR/$session_id/MARKER"
touch -d '1 hour ago' "$SESS_DIR/not-a-session-id"
touch -h -d '1 hour ago' "$SESS_DIR/$alias_id" 2>/dev/null || true  # best effort on the link's own mtime; sweeper skips it by islink(), not by age
echo "  wrote: alias $alias_id -> $session_id (fresh), stray dir 'not-a-session-id' (backdated), marker file in $session_id"

# Two controls, so the checks below fail if the sweep never runs or follows a link:
# - an expired real session directory, which a working sweep MUST delete;
# - a second alias whose target is itself stale (outside FY_SESSIONS_DIR). A sweeper
#   that resolved the link before checking age would see a stale session and delete
#   through it; a correct one skips the link before looking at the target.
expired_id="$("$PYTHON" -c 'import uuid; print(uuid.uuid4().hex)')"
mkdir "$SESS_DIR/$expired_id"
touch -d '1 hour ago' "$SESS_DIR/$expired_id"
stale_alias_id="$("$PYTHON" -c 'import uuid; print(uuid.uuid4().hex)')"
# The target gets a valid session-id name too, so a sweeper that resolved the link
# would pass every name check on the target and really delete it.
VICTIM="$VICTIM_ROOT/$("$PYTHON" -c 'import uuid; print(uuid.uuid4().hex)')"
mkdir "$VICTIM"
echo marker > "$VICTIM/MARKER"
touch -d '1 hour ago' "$VICTIM/MARKER" "$VICTIM"
ln -s "$VICTIM" "$SESS_DIR/$stale_alias_id"
echo "  wrote: expired session $expired_id (backdated), alias $stale_alias_id -> stale dir outside FY_SESSIONS_DIR"

echo "== forcing a REAL sweep in the live server process (init_session -> _new_session -> _sweep_stale_sessions)"
call init_session '[]' >/dev/null

if [[ -L "$SESS_DIR/$alias_id" ]]; then
  echo "  ok   the symlink alias entry itself survived the live sweep"
else
  echo "FAIL the symlink alias entry was removed by the live sweep"; fail=1
fi
if [[ -f "$SESS_DIR/$session_id/MARKER" ]]; then
  echo "  ok   the alias's TARGET directory and its file are intact -- the sweep never rmtree'd through the symlink"
else
  echo "FAIL the alias's target directory/file is gone -- the live sweep deleted through the symlink"; fail=1
fi
if [[ -d "$SESS_DIR/not-a-session-id" ]]; then
  echo "  ok   the stray non-hex directory survived the live sweep"
else
  echo "FAIL the stray non-hex directory was removed by the live sweep"; fail=1
fi
if [[ ! -e "$SESS_DIR/$expired_id" ]]; then
  echo "  ok   the expired session directory was deleted -- the sweep really ran"
else
  echo "FAIL the expired session directory is still there -- the sweep did not run"; fail=1
fi
if [[ -L "$SESS_DIR/$stale_alias_id" && -f "$VICTIM/MARKER" ]]; then
  echo "  ok   the alias to a stale target survived, and its target was not deleted through it"
else
  echo "FAIL the sweep followed the alias to a stale target and deleted through it"; fail=1
fi

# NOTE on what HTTP can and can't prove here: an earlier version of this
# script tried to send session_id="../x" as the client-supplied "data" value
# for the session_state slot over HTTP. That does NOT exercise #149: Gradio
# treats session_state as a server-tracked gr.State value keyed by
# session_hash, and ignores/overrides whatever the client sends for a State
# input -- confirmed empirically (a never-before-used session_hash still got
# session_id=None, Gradio's own default, not the "../x" the client sent).
# So the bad-id path is reachable only the way the issue describes it
# ("a stale/expired Gradio State"), never by an external HTTP caller
# supplying an arbitrary string -- which is exactly why the unit tests call
# run_demo_turn_streaming/save_caregiver_text_memo directly in Python against
# the real, unmocked webapp module instead of over HTTP. This script proves
# the SAME real module, imported fresh (not through unittest), behaves the
# same way against the LIVE server's own FY_SESSIONS_DIR, as an outside-the-
# test-framework runtime check alongside the unit tests.
echo "== real-module (not unittest, not mocked) crisis-fastpath + memo-saver check against the live server's SESSIONS_DIR"
NEBIUS_API_KEY= "$PYTHON" - "$SESS_DIR" <<'PY'
import sys
sys.path.insert(0, ".")
import os
os.environ["FY_SESSIONS_DIR"] = sys.argv[1]
os.environ["FY_SHARED_PROFILE"] = "0"
os.environ["NEBIUS_API_KEY"] = ""
import webapp

fail = False

outputs = list(webapp.run_demo_turn_streaming(None, "I want to die", [], "../x", "Morning (Default)"))
final = outputs[-1]
if "988" in final[0]:
    print("  ok   run_demo_turn_streaming('../x', 'I want to die') hit the crisis fast-path (contains '988')")
else:
    print("FAIL run_demo_turn_streaming did not hit the crisis fast-path:", final[0][:200]); fail = True
new_sid = final[5]
import re
if isinstance(new_sid, str) and re.fullmatch(r"[0-9a-f]{32}", new_sid) and os.path.isdir(os.path.join(sys.argv[1], new_sid)):
    print(f"  ok   returned a fresh valid session id ({new_sid}) with a real directory on disk")
else:
    print("FAIL did not return a fresh valid session id:", new_sid); fail = True

outside = os.path.join(sys.argv[1], "..", "x")
text_result = webapp.save_caregiver_text_memo("Dad has physio Tuesday.", "../x")
if "Dad has physio Tuesday" in text_result[0]:
    print("FAIL save_caregiver_text_memo attributed the memo to a bad id instead of returning the placeholder"); fail = True
elif not (isinstance(text_result, tuple) and len(text_result) == 3 and isinstance(text_result[0], str) and text_result[0].strip()):
    print("FAIL save_caregiver_text_memo('../x') did not return its normal panel text:", repr(text_result)[:200]); fail = True
else:
    print("  ok   save_caregiver_text_memo('../x') returned its normal placeholder text, no raise")
# Checked after BOTH calls, so a write by either one outside FY_SESSIONS_DIR is caught.
if os.path.exists(outside):
    print("FAIL something was written outside FY_SESSIONS_DIR at '../x'"); fail = True
else:
    print("  ok   nothing was written outside FY_SESSIONS_DIR by either call")

sys.exit(1 if fail else 0)
PY
if [[ $? -ne 0 ]]; then fail=1; fi

exit "$fail"
