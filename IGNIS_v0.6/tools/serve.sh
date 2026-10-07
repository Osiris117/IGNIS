#!/usr/bin/env bash
# IGNIS — arranque con instalación automática de dependencias (idempotente).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${IGNIS_PORT:-8010}"
if ! python3 -c "import fastapi, uvicorn, duckdb, multipart, dotenv" 2>/dev/null; then
  echo "[IGNIS] Instalando dependencias…"
  python3 -m pip install --quiet -r requirements.txt
fi
echo "[IGNIS] Servidor en http://0.0.0.0:${PORT}  (preview: mismo puerto)"
exec python3 -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT}" --log-level warning
