#!/usr/bin/env bash
# Startup script para Render. Corre seed pero no aborta si falla,
# despues levanta uvicorn.
set -e

echo "[start.sh] Running seed..."
python seed.py || echo "[start.sh] seed fallo, continuando con uvicorn"

echo "[start.sh] Starting uvicorn on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
