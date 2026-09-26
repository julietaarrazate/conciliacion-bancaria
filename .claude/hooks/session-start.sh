#!/bin/bash
# Instala las dependencias de backend y frontend al iniciar una sesión de
# Claude Code en la web, para poder correr tests/lint/build de entrada.
# Mismos comandos que el CI (.github/workflows/ci.yml). No usa secretos ni toca
# Neon/Render/Vercel. En sesiones locales no hace nada.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"

echo "Instalando dependencias del backend..."
python3 -m pip install -q --ignore-installed -r backend/requirements.txt -r backend/requirements-dev.txt ruff

echo "Instalando dependencias del frontend..."
(cd frontend && npm ci --no-audit --no-fund --loglevel=error)

echo "Dependencias listas."
