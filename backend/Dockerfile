FROM python:3.11-slim

WORKDIR /app

# Build deps + libpq para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# Script startup que crea tablas, hace seed y arranca uvicorn
RUN echo '#!/bin/sh' > /start.sh && \
    echo 'set -e' >> /start.sh && \
    echo 'echo "[start] Python: $(python --version)"' >> /start.sh && \
    echo 'echo "[start] DATABASE_URL set: $([ -n \"$DATABASE_URL\" ] && echo yes || echo no)"' >> /start.sh && \
    echo 'echo "[start] PORT: ${PORT:-8000}"' >> /start.sh && \
    echo 'python -c "from app.database import engine, Base; Base.metadata.create_all(bind=engine); print(\"[init] tables OK\")" || echo "[init] FALLO crear tablas (no aborta)"' >> /start.sh && \
    echo 'python seed.py 2>&1 || echo "[seed] FALLO (no aborta)"' >> /start.sh && \
    echo 'echo "[start] uvicorn ON 0.0.0.0:${PORT:-8000}"' >> /start.sh && \
    echo 'exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"' >> /start.sh && \
    chmod +x /start.sh

CMD ["/start.sh"]
