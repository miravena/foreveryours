#!/usr/bin/env bash
# Verify NEBIUS_API_KEY without ever printing it: prints only "Nebius key: HTTP <code>".
# 200 = key accepted, 401 = rejected, 000 = no network. Exit 0 only on 200.
# Usage: scripts/key_status.sh [path/to/.env]   (default: ./.env)
set -u
env_file="${1:-.env}"
[ -r "$env_file" ] || { echo "Nebius key: no readable $env_file" >&2; exit 2; }
set -a; . "$env_file"; set +a
[ -n "${NEBIUS_API_KEY:-}" ] || { echo "Nebius key: NEBIUS_API_KEY not set in $env_file" >&2; exit 2; }
base="${NEBIUS_BASE_URL:-https://api.tokenfactory.nebius.com/v1}"
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "${base%/}/models" -H "Authorization: Bearer $NEBIUS_API_KEY")
unset NEBIUS_API_KEY
echo "Nebius key: HTTP $code"
[ "$code" = "200" ]
