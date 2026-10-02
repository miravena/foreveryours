#!/usr/bin/env bash
# No-key smoke test (issue #19): ~30s, behavior-based, safe to run anytime.
# Runs the unit tests, then the three key-free CLI beats against a throwaway
# copy of the repo (so your own data/ and out/ are untouched) and greps for
# the lines that prove each beat worked.
#
#   scripts/smoke.sh                 # uses .venv/bin/python if present, else python3
#   PYTHON=/path/to/python scripts/smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON=python3; fi
fi
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Copy only source, never data/, out/, .env or .venv.
tar -C "$ROOT" --exclude=./data --exclude=./out --exclude=./.env --exclude=./.venv \
    --exclude=./video --exclude=.git -cf - . | tar -C "$WORK" -xf -
cd "$WORK"
export NEBIUS_API_KEY=""

fail=0
check() {  # check <label> <expected-substring> <output>
  if grep -qF -- "$2" <<<"$3"; then echo "  ok   $1"; else echo "  FAIL $1 (missing: $2)"; fail=1; fi
}

echo "== unit tests"
"$PYTHON" -m pytest -q 2>&1 | tail -1
"$PYTHON" -m pytest -q >/dev/null 2>&1 || fail=1

echo "== beat1 (caregiver memo)"
out="$("$PYTHON" main.py beat1 2>&1)"
check "memo saved" "Caregiver memo saved" "$out"
check "grandson fact stored" "His grandson is named Leo" "$out"

echo "== beat3 (distress fast-path, no key)"
out="$("$PYTHON" main.py beat3 --no-play 2>/dev/null)"
check "senior told out loud" "letting your family know" "$out"
check "flag disclosed" "disclosed to senior" "$out"

echo "== day2 (persistence across processes)"
out="$("$PYTHON" main.py day2 2>&1)"
check "facts recalled" "Persistence confirmed" "$out"

if [[ $fail -ne 0 ]]; then echo "SMOKE FAILED"; exit 1; fi
echo "SMOKE PASSED"
