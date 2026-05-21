#!/bin/bash
# push-to-github.sh
# Sube el proyecto al repo de GitHub.
# Uso: bash push-to-github.sh
#
# Requiere:
#   - git instalado
#   - Estar parada en la carpeta raíz del proyecto (conciliacion-bancaria/)

set -e

REPO_URL="https://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@github.com/julietaarrazate/conciliacion-bancaria.git"

echo "🚀 Iniciando push a GitHub..."

# Inicializar git si no existe
if [ ! -d ".git" ]; then
  git init
  git branch -M main
  echo "✅ Repositorio git inicializado"
fi

# Configurar remote
if git remote get-url origin &>/dev/null; then
  git remote set-url origin "$REPO_URL"
else
  git remote add origin "$REPO_URL"
fi

# Staging y commit
git add .
git commit -m "chore: configuración inicial Claude Code + estructura base del proyecto

- CLAUDE.md maestro con memoria viva y reglas anti-delirio
- CLAUDE.md por módulo (backend, frontend, mobile, database)
- .claude/settings.json + comandos /dev /review /migrate /test /sync-memory
- Backend: FastAPI + SQLAlchemy async, modelos, schemas, routers, matching service
- Frontend: React 18 + TypeScript + Vite + Tailwind + React Query
- Mobile: React Native + Expo + React Navigation
- docker-compose.yml, .env.example, setup.sh
- docs/errors-log.md, docs/architecture.md, docs/api-contracts.md" 2>/dev/null || echo "⏭️  Nada nuevo para commitear"

# Push
echo "📤 Haciendo push a main..."
git push -u origin main --force

echo ""
echo "✅ Listo! Código en: https://github.com/julietaarrazate/conciliacion-bancaria"
