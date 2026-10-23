#!/usr/bin/env bash
# Download the offline Piper neural voice (en_US-ljspeech-medium) ONCE, into
# models/piper/. Developer convenience and the deploy workflow's pre-step: the demo
# NEVER downloads at runtime (offline guarantee -- see ADR-008). Idempotent: skips
# if present. This voice is trained on the public-domain LJ Speech dataset; the
# earlier en_US-lessac-medium voice is trained on research-only data (ADR-011).
#
# Windows (PowerShell) one-liner equivalent, run from the repo root:
#   New-Item -ItemType Directory -Force models\piper | Out-Null
#   $base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ljspeech/medium"
#   Invoke-WebRequest "$base/en_US-ljspeech-medium.onnx"      -OutFile models\piper\en_US-ljspeech-medium.onnx
#   Invoke-WebRequest "$base/en_US-ljspeech-medium.onnx.json" -OutFile models\piper\en_US-ljspeech-medium.onnx.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/models/piper"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ljspeech/medium"
MODEL="en_US-ljspeech-medium.onnx"

mkdir -p "$DEST"

if [ -f "$DEST/$MODEL" ] && [ -f "$DEST/$MODEL.json" ]; then
  echo "Piper voice already present at $DEST/$MODEL -- nothing to do."
  exit 0
fi

echo "Downloading Piper voice en_US-ljspeech-medium into $DEST ..."
curl -fL "$BASE/$MODEL"      -o "$DEST/$MODEL"
curl -fL "$BASE/$MODEL.json" -o "$DEST/$MODEL.json"
echo "Done. The demo will now use the neural voice; remove the files to fall back to espeak-ng."
