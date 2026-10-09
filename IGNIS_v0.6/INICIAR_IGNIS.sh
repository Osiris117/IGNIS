#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 start_ignis.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python start_ignis.py "$@"
else
  echo "[IGNIS] ERROR: Python 3.10+ was not found. Install Python or use Docker." >&2
  exit 1
fi
