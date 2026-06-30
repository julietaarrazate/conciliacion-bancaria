# Módulo — <nombre> (scaffold)

Plantilla/scaffold mental para un módulo nuevo de Cuadra. Alineada con el patrón establecido y
con [`docs/playbooks/NEW_MODULE.md`](../../docs/playbooks/NEW_MODULE.md). Antes de empezar, leé un
módulo análogo y copiá su estructura: **Cheques** (CRUD operativo con foto/OCR) o **IVA /
Monotributo / IIBB / Sueldos** (liquidación de impuestos).

## Identidad del módulo

- **Nombre:** `<modulo>`
- **Qué resuelve:** (1–2 líneas de negocio)
- **Permiso(s):** (`manage_finance` / `admin_accounting` / `delete_records` / otro)
- **¿Mueve dinero?** (sí → integra con motor contable, ver `docs/playbooks/NEW_ACCOUNTING_MODULE.md`)
- **Activación opt-in por org:** (cómo se prende/configura por organización)

## Estructura a crear

```
backend/app/models/<modulo>.py            # tabla(s): id PK, organizacion_id (FK, nullable=False,
                                          #   default=1, index), montos Numeric(12,2),
                                          #   tasas Numeric(5,4), created_at UTC, deleted_at si borra
backend/app/services/<modulo>_service.py  # lógica/cálculo financiero (Decimal, hoy_art())
backend/app/routers/<modulo>.py           # 3 capas: get_current_user + require_permission +
                                          #   filtro organizacion_id / can_switch_org
backend/alembic/versions/<rev>_<modulo>.py# migración
backend/app/main.py                       # safety-net idempotente (CREATE/ALTER ... IF NOT EXISTS)
                                          #   + include_router(<modulo>.router) + seed por org
backend/tests/test_<modulo>.py            # service + router (feliz / aislamiento 404 / 403 / DELETE)
frontend/src/pages/<Modulo>.tsx           # página (probar modo claro y oscuro)
frontend/src/services/api.ts              # endpoints del módulo
frontend/src/App.tsx                      # ruta gateada (ProtectedRoute permission=...)
frontend/src/components/Layout.tsx        # item de navegación
```

## Reglas no negociables

- Multi-tenant: data y config scopeadas por `organizacion_id`; nunca asumir Org A; Org A solo aditivo.
- Dinero en `Decimal`; fechas de negocio con `hoy_art()`/`now_art()` (back) y `localIsoDate()` (front).
- Permisos en 3 capas; recurso de otra org → 404.
- Migración Alembic **y** safety-net idempotente convergen al mismo esquema.
- Frontend: `parseMonto()` para montos AR.

## Orden de merge

backend → frontend → splits/docs. Archivos compartidos (`main.py`, `api.ts`, `App.tsx`,
`Layout.tsx`) van en serie si se paraleliza. Commit por sub-paso.

## Terminado (verificable)

`cd backend && python -m pytest -q` · `cd frontend && npx tsc --noEmit && npm run build` ·
esquema converge en arranque · datos visibles solo dentro de la org del usuario ·
docs y CHANGELOG actualizados.
