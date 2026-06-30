# Cómo contribuir a Cuadra

Guía para mantener el repo sano a lo largo de los años. Es complementaria a
[`CLAUDE.md`](CLAUDE.md) (orientación rápida) y a [`/docs`](docs/README.md) (referencia profunda).

## Setup

```bash
# Backend
cd backend && pip install -r requirements.txt
export SUPERADMIN_PASSWORD="..."        # ver README
python seed.py && uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Flujo de trabajo

1. **Rama**: desarrollá en una rama (`claude/...` o `feature/...`), nunca directo a `main` sin PR.
2. **Commits**: autoría obligatoria
   `git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>"` (Vercel bloquea otros
   autores). Mensajes claros y atómicos.
3. **PR**: usá la [plantilla de PR](.github/PULL_REQUEST_TEMPLATE.md). Squash a `main`.
4. **CI**: el [workflow de CI](.github/workflows/ci.yml) corre `pytest`, `tsc --noEmit` y `build`.
   No mergees con CI en rojo.

## Verificación local (obligatoria antes del PR)

```bash
cd backend  && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build
```

## Reglas de oro (las que más se rompen)

- **Dinero**: `Decimal`/`Numeric(12,2)`, nunca `float`. Ver [`BUGS.md`](BUGS.md).
- **Fechas de negocio**: `hoy_art()`/`now_art()` (backend) y `localIsoDate()` (frontend), no UTC.
- **Multi-tenant**: todo endpoint respeta `org_id` + `can_switch_org`. Ver
  [`docs/api/API_RULES.md`](docs/api/API_RULES.md).
- **Esquema**: migración Alembic **+** safety-net en `main.py`. Ver
  [`docs/database/DATABASE_RULES.md`](docs/database/DATABASE_RULES.md).
- **Org A** (`organizacion_id=1`): solo cambios aditivos, nunca modificar datos existentes.
- **Errores**: no usar `except Exception` que enmascara el error real con un mensaje genérico.

## Para agregar cosas

Seguí los playbooks: [`docs/playbooks/`](docs/playbooks/) (módulo, endpoint, banco, parser,
reporte, módulo contable). Y los [comandos de Claude](.claude/commands/) (`/feature`, `/bug`,
`/refactor`, `/review`, …) que encapsulan estos flujos.

## Documentación

Si cambiás comportamiento, actualizá el doc correspondiente en `/docs` (la doc describe el código
tal como está). Cada doc tiene una sección `## Pendiente de revisar` para discrepancias.
