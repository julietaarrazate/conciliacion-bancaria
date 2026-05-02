FROM python:3.11-slim

# Dependencias del sistema para psycopg2 y compilacion
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias primero (cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar codigo
COPY . .

# Puerto configurable (Railway y Render lo inyectan como $PORT)
ENV PORT=8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Startup: seed (idempotente) + uvicorn
CMD python seed.py 2>&1 || true; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
