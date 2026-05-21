#!/bin/bash
# setup.sh — Configuración inicial del proyecto
# Correr UNA vez después de clonar el repo

set -e

echo "🏦 Configurando Sistema de Conciliación Bancaria..."
echo ""

# 1. Variables de entorno
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ .env creado desde .env.example — EDITAR con valores reales antes de continuar"
else
  echo "⏭️  .env ya existe"
fi

# 2. Backend
echo ""
echo "📦 Instalando dependencias del backend..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt --quiet
echo "✅ Backend listo"
cd ..

# 3. Frontend
echo ""
echo "📦 Instalando dependencias del frontend..."
cd frontend
npm install --silent
echo "✅ Frontend listo"
cd ..

# 4. Mobile (opcional)
if command -v expo &> /dev/null; then
  echo ""
  echo "📦 Instalando dependencias mobile..."
  cd mobile
  npm install --silent
  echo "✅ Mobile listo"
  cd ..
fi

# 5. Base de datos
echo ""
echo "🐳 Levantando PostgreSQL..."
docker-compose up -d postgres
echo "Esperando que PostgreSQL esté listo..."
sleep 5

# 6. Migraciones
echo ""
echo "🗄️ Aplicando migraciones..."
cd backend
source .venv/bin/activate
alembic upgrade head
echo "✅ Migraciones aplicadas"
cd ..

echo ""
echo "🎉 Setup completo. Para iniciar:"
echo "   docker-compose up -d         # todo en Docker"
echo "   o"
echo "   cd backend && uvicorn app.main:app --reload"
echo "   cd frontend && npm run dev"
