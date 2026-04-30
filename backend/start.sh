#!/usr/bin/env bash
# Startup script para Render con logs verbosos
echo "================================"
echo "[start.sh] python: $(python --version)"
echo "[start.sh] pwd: $(pwd)"
echo "[start.sh] DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo yes || echo no)"
echo "[start.sh] PORT: ${PORT:-8000}"
echo "================================"

echo "[start.sh] Importing app to verify..."
python -c "from app.main import app; print('[start.sh] app import OK')" 2>&1 || {
    echo "[start.sh] FATAL: no se puede importar app.main"
    exit 1
}

echo "[start.sh] Running seed (no aborta si falla)..."
python seed.py 2>&1 || echo "[start.sh] seed fallo (continuando)"

echo "[start.sh] Starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
