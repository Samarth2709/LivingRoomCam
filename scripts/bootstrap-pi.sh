#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m venv "$ROOT/.venv"

if [[ ! -x "$ROOT/.venv/bin/pip" ]]; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$ROOT/get-pip.py"
  "$ROOT/.venv/bin/python" "$ROOT/get-pip.py"
fi

"$ROOT/.venv/bin/pip" install numpy opencv-python-headless

if [[ ! -f "$ROOT/config/pi-agent.local.json" ]]; then
  cp "$ROOT/config/pi-agent.example.json" "$ROOT/config/pi-agent.local.json"
fi

echo "Pi bootstrap complete."
echo "Edit $ROOT/config/pi-agent.local.json if the server URL changes."
