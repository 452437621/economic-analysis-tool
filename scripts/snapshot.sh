#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${EPIC_PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || command -v python)"
fi
exec "$PY" "$ROOT/scripts/epic.py" snapshot "$@"
