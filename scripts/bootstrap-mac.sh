#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m venv "$ROOT/.venv"

if [[ ! -x "$ROOT/.venv/bin/pip" ]]; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$ROOT/get-pip.py"
  "$ROOT/.venv/bin/python" "$ROOT/get-pip.py"
fi

"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install numpy opencv-python

if [[ ! -f "$ROOT/config/server.local.json" ]]; then
  cp "$ROOT/config/server.example.json" "$ROOT/config/server.local.json"
fi

echo "Mac bootstrap complete."
echo "Activate with: source $ROOT/.venv/bin/activate"
