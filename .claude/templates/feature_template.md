# Feature — <título>

Plantilla para describir una feature antes de implementarla. Usar con
[`/feature`](../commands/feature.md). Borrar las guías entre paréntesis al completar.

## Problema / motivación

(Qué necesidad de negocio resuelve. Quién lo pide. Para quién — Julieta superadmin, contador,
operador, cliente.)

## Alcance

- **Incluye:** (qué entra en esta unidad de trabajo)
- **No incluye:** (qué queda explícitamente afuera, para no gold-platear)
- **Opt-in por org:** (cómo se activa/configura por organización — no hardcodear para Org A)

## Archivos a tocar

(Mapear ANTES de paralelizar; marcar los compartidos que serializan el trabajo.)

| Capa | Archivo | Compartido |
|------|---------|:----------:|
| Modelo | `backend/app/models/<modulo>.py` | |
| Service | `backend/app/services/<modulo>_service.py` | |
| Router | `backend/app/routers/<modulo>.py` | |
| Migración | `backend/alembic/versions/<rev>_<modulo>.py` | |
| Safety net | `backend/app/main.py` | ✅ |
| Frontend página | `frontend/src/pages/<Modulo>.tsx` | |
| API client | `frontend/src/services/api.ts` | ✅ |
| Rutas | `frontend/src/App.tsx` | ✅ |
| Nav | `frontend/src/components/Layout.tsx` | ✅ |

## Plan (sub-pasos atómicos, commit por paso)

1.
2.
3.

## Reglas a respetar

- [ ] Montos `Decimal`/`Numeric(12,2)`; fechas `hoy_art()`/`localIsoDate()`.
- [ ] Multi-tenant: filtro `organizacion_id` + `can_switch_org`; Org A solo aditivo.
- [ ] Permisos en 3 capas; permiso usado: `____`.
- [ ] Migración Alembic + safety-net idempotente en `main.py`.

## Criterios de aceptación

- [ ]
- [ ]

## Test plan

- [ ] Backend: caso feliz + aislamiento otra org (404) + 403 sin permiso (+ borrado con FKs si hay `DELETE`).
- [ ] Frontend: modo claro y oscuro; `tsc --noEmit` + `build`.
- [ ] Verificación: `cd backend && python -m pytest -q` · `cd frontend && npx tsc --noEmit && npm run build`.
