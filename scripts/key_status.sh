#!/usr/bin/env bash
# Verify NEBIUS_API_KEY without ever printing it: prints only "Nebius key: HTTP <code>".
# 200 = key accepted, 401 = rejected, 000 = no network. Exit 0 only on 200, 2 if file/var missing.
# The env file is parsed as DATA (never sourced or eval'd): only the NEBIUS_API_KEY and
# NEBIUS_BASE_URL lines are read, so a malformed line cannot execute or echo anything.
# Usage: scripts/key_status.sh [path/to/.env]   (default: ./.env)
set -u
env_file="${1:-.env}"
[ -r "$env_file" ] || { echo "Nebius key: no readable $env_file" >&2; exit 2; }

NEBIUS_API_KEY=""
NEBIUS_BASE_URL=""
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  line="${line#"${line%%[![:space:]]*}"}"          # leading space
  case "$line" in "export "*) line="${line#export }"; line="${line#"${line%%[![:space:]]*}"}";; esac
  case "$line" in
    NEBIUS_API_KEY=*)  name=NEBIUS_API_KEY;  val="${line#NEBIUS_API_KEY=}";;
    NEBIUS_BASE_URL=*) name=NEBIUS_BASE_URL; val="${line#NEBIUS_BASE_URL=}";;
    *) continue;;
  esac
  val="${val#"${val%%[![:space:]]*}"}"              # leading space after =
  val="${val%"${val##*[![:space:]]}"}"              # trailing space
  case "$val" in
    \"*\") val="${val#\"}"; val="${val%\"}";;
    \'*\') val="${val#\'}"; val="${val%\'}";;
  esac
  printf -v "$name" '%s' "$val"
done < "$env_file"

[ -n "$NEBIUS_API_KEY" ] || { echo "Nebius key: NEBIUS_API_KEY not set in $env_file" >&2; exit 2; }
base="${NEBIUS_BASE_URL:-https://api.tokenfactory.nebius.com/v1}"
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "${base%/}/models" -H "Authorization: Bearer $NEBIUS_API_KEY")
unset NEBIUS_API_KEY
echo "Nebius key: HTTP $code"
[ "$code" = "200" ]
