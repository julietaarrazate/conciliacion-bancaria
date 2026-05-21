# /test — Correr tests del proyecto

Correr tests según el módulo:

**Backend:**
```bash
cd backend && pytest tests/ -v --tb=short
```

**Frontend:**
```bash
cd frontend && npm test -- --watchAll=false
```

**Integración:**
```bash
docker-compose up -d && cd backend && pytest tests/integration/ -v
```

Reportar resultados. Si hay fallos, analizar causa raíz antes de intentar fix.
No parchear tests para que pasen — arreglar el código.
