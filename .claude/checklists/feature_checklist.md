# Checklist — Feature / módulo nuevo

Para usar con [`/feature`](../commands/feature.md). Referencia completa:
[`docs/playbooks/NEW_MODULE.md`](../../docs/playbooks/NEW_MODULE.md) y
[`docs/playbooks/NEW_API_ENDPOINT.md`](../../docs/playbooks/NEW_API_ENDPOINT.md).

## Backend — modelo

- [ ] Tabla con `id` PK y `organizacion_id` (`ForeignKey("organizaciones.id"), nullable=False,
      default=1, index=True`).
- [ ] Montos `Numeric(12,2)`, porcentajes/tasas `Numeric(5,4)` — nunca `Float`.
- [ ] `created_at = Column(DateTime, default=datetime.utcnow)` (auditoría en UTC).
- [ ] `deleted_at` si el registro se borra desde la app (soft delete).
- [ ] Modelo importado en `backend/app/models/__init__.py`.

## Backend — service

- [ ] Lógica de negocio/cálculo en el service (router fino).
- [ ] Montos en `Decimal`; fechas de negocio con `hoy_art()`/`now_art()`.
- [ ] Si mueve dinero → registra asiento contable (ver `docs/playbooks/NEW_ACCOUNTING_MODULE.md`).

## Backend — router (permisos en 3 capas)

- [ ] Capa 1: `Depends(get_current_user)` + `require_permission("<permiso>")` donde mute o sea sensible.
- [ ] Capa 2: toda query filtra por `organizacion_id`; `org_id` validado con `can_switch_org`;
      recurso de otra org → 404.
- [ ] Listados devuelven `{"items": [...], "total": N}` con `limit`/`offset`.
- [ ] `DELETE` con FKs entrantes: nulificar/reasignar referencias antes de borrar.
- [ ] Sin `except Exception` genérico que enmascare; `except HTTPException: raise` primero.
- [ ] `registrar_log(...)` en operaciones que mutan datos (Decimal → `str` al serializar).
- [ ] Router registrado en `backend/app/main.py` con `include_router(...)`.

## Migración + safety net (idempotente)

- [ ] Migración Alembic en `backend/alembic/versions/`.
- [ ] Safety-net equivalente en `main.py` (`CREATE TABLE / ADD COLUMN / CREATE [UNIQUE] INDEX
      IF NOT EXISTS`) — converge en el arranque aunque Alembic falle.
- [ ] Seed por org idempotente si necesita datos sembrados.

## Opt-in por organización

- [ ] No asume Org A. Data y config scopeadas por `organizacion_id`; flags de activación en la
      config por org, no en constantes de código.

## Tests

- [ ] Service (cálculo) + router (caso feliz + aislamiento otra org 404 + 403 sin permiso).
- [ ] Borrado con datos relacionados si hay `DELETE`.

## Frontend

- [ ] Página en `frontend/src/pages/<Modulo>.tsx`; probada en modo claro y oscuro.
- [ ] Ruta gateada en `App.tsx` (`ProtectedRoute permission="..."`).
- [ ] Item de navegación en `Layout.tsx`.
- [ ] Endpoints en `services/api.ts`.
- [ ] Fechas con `localIsoDate()`, montos con `parseMonto()` (formato AR).

## Docs

- [ ] `docs/` actualizado (ver [`/docs`](../commands/docs.md)); CHANGELOG si corresponde.

## Verificación

- [ ] `cd backend && python -m pytest -q`
- [ ] `cd frontend && npx tsc --noEmit && npm run build`
- [ ] Commits con autor `Julieta Arrazate <julietaarrazate@gmail.com>`.
