#!/usr/bin/env bash
# Download the offline Piper neural voice (en_US-lessac-medium) ONCE, into
# models/piper/. This is a developer convenience: the demo NEVER downloads at
# runtime (offline guarantee -- see ADR-008). Idempotent: skips if present.
#
# Windows (PowerShell) one-liner equivalent, run from the repo root:
#   New-Item -ItemType Directory -Force models\piper | Out-Null
#   $base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
#   Invoke-WebRequest "$base/en_US-lessac-medium.onnx"      -OutFile models\piper\en_US-lessac-medium.onnx
#   Invoke-WebRequest "$base/en_US-lessac-medium.onnx.json" -OutFile models\piper\en_US-lessac-medium.onnx.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/models/piper"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
MODEL="en_US-lessac-medium.onnx"

mkdir -p "$DEST"

if [ -f "$DEST/$MODEL" ] && [ -f "$DEST/$MODEL.json" ]; then
  echo "Piper voice already present at $DEST/$MODEL -- nothing to do."
  exit 0
fi

echo "Downloading Piper voice en_US-lessac-medium into $DEST ..."
curl -fL "$BASE/$MODEL"      -o "$DEST/$MODEL"
curl -fL "$BASE/$MODEL.json" -o "$DEST/$MODEL.json"
echo "Done. The demo will now use the neural voice; remove the files to fall back to espeak-ng."
