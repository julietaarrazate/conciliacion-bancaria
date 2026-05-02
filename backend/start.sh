#!/usr/bin/env bash
# Script de arranque para Render (y cualquier entorno Linux).
# No usa '&&' para que un fallo en seed no impida que uvicorn arranque.
set -e

PORT="${PORT:-10000}"

echo "==================================="
echo " Conciliacion Bancaria - Backend"
echo " Python: $(python --version)"
echo " PORT: $PORT"
echo " DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'SI' || echo 'NO (usando SQLite)')"
echo "==================================="

echo "[startup] Verificando importacion de app..."
python -c "from app.main import app; print('[startup] app OK')"

echo "[startup] Ejecutando seed (no aborta si falla)..."
python seed.py 2>&1 || echo "[startup] seed saltado (puede ser que los usuarios ya existan)"

echo "[startup] Iniciando uvicorn en 0.0.0.0:$PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
