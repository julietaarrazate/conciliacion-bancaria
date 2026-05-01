FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# Crear tablas + seed (no aborta si falla) + arrancar uvicorn
CMD python -c "from app.database import engine, Base; Base.metadata.create_all(bind=engine); print('[init] tables OK')" && \
    python seed.py 2>&1 || true ; \
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
