FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Script de arranque (evita problemas de shell con ; y ||)
RUN printf '#!/bin/bash\nset -e\necho "=== Conciliacion Bancaria ==="\necho "PORT: ${PORT:-8000}"\necho "DB: ${DATABASE_URL:0:30}..."\npython seed.py 2>&1 || echo "seed omitido"\nexec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}\n' > /start.sh && chmod +x /start.sh

EXPOSE 8000
CMD ["/bin/bash", "/start.sh"]
