#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT/config/pi-agent.local.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "$CONFIG" ]]; then
  CONFIG="$ROOT/config/pi-agent.example.json"
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON_BIN" -m livingroomcam.agent "$CONFIG"
