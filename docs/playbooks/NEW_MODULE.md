# NEW_MODULE — Agregar un módulo nuevo a Cuadra

Guía paso a paso para agregar un módulo siguiendo el **patrón establecido** del
repo (ver `../../CLAUDE.md` → "Patrón establecido" y "Protocolo de orquestación
ultracode"). El patrón, en una línea:

> modelo + service + router con permisos en 3 capas + migración + safety net en
> `main.py` + tests + página frontend + item de navegación, **opt-in por
> organización** (no hardcodeado para una sola org).

Cross-ref:
[../api/API_RULES.md](../api/API_RULES.md) ·
[../database/DATABASE_RULES.md](../database/DATABASE_RULES.md) ·
[../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md) ·
[NEW_API_ENDPOINT.md](NEW_API_ENDPOINT.md) ·
[NEW_ACCOUNTING_MODULE.md](NEW_ACCOUNTING_MODULE.md) (si el módulo mueve dinero) ·
[../adr/DECISIONS.md](../adr/DECISIONS.md) (ADR-004 multi-tenant, ADR-010 safety nets).

## Módulos de referencia (plantillas reales)

Antes de empezar, leé un módulo análogo y copiá su estructura:

- **CRUD operativo con foto / OCR / carga masiva → Cheques.**
  - Modelo: `backend/app/models/cheque.py`, `backend/app/models/portador.py`
  - Routers (agregador + splits): `backend/app/routers/cheques.py`,
    `cheques_crud.py`, `cheques_common.py`, `cheques_acreditacion.py`,
    `cheques_crud.py`, `cheques_reportes.py`
  - Service contable: `registrar_cheque` / `acreditar_cheque` / `rechazar_cheque`
    en `backend/app/services/motor_contable.py`
  - Página: `frontend/src/pages/Cheques.tsx`
- **Módulo de liquidación de impuestos → IVA / Monotributo / IIBB / Sueldos.**
  - Modelos: `backend/app/models/proyeccion_iva.py`, `monotributo.py`,
    `iibb.py`, `sueldos.py`
  - Services: `backend/app/services/iva_service.py`, `monotributo_service.py`,
    `iibb_service.py`, `sueldos_service.py`
  - Routers: `backend/app/routers/iva.py`, `monotributo.py`, `iibb.py`,
    `sueldos.py`

Estos módulos están descriptos en `../../CHANGELOG.md` (v3.19–v3.24).

---

## Checklist accionable

### 1. Modelo SQLAlchemy (`backend/app/models/<modulo>.py`)

- [ ] Tabla con `id` PK y **`organizacion_id = Column(Integer, ForeignKey("organizaciones.id"), nullable=False, default=1, index=True)`**
      (ADR-004 — multi-tenant). Es obligatorio en toda tabla nueva.
- [ ] Montos como `Numeric(12,2)`; porcentajes/tasas como `Numeric(5,4)`
      (ADR-001 — nunca `Float`). Ver `backend/app/models/cheque.py`.
- [ ] `created_at = Column(DateTime, default=datetime.utcnow)` (auditoría en UTC,
      ADR-014).
- [ ] Si el registro se borra desde la app: columna `deleted_at` para soft delete
      (ADR-002).
- [ ] Importar el modelo donde se registran todos (revisar
      `backend/app/models/__init__.py`) para que cree la tabla.

### 2. Service (`backend/app/services/<modulo>_service.py`)

- [ ] Lógica de negocio/cálculo financiero acá, no en el router (router fino).
- [ ] Fechas de negocio con `hoy_art()` / `now_art()` de
      `backend/app/services/tz.py` (ADR-014).
- [ ] Cálculos monetarios siempre en `Decimal` (ADR-001).
- [ ] Si el módulo mueve dinero → registrar asiento contable; ver
      [NEW_ACCOUNTING_MODULE.md](NEW_ACCOUNTING_MODULE.md).

### 3. Router con permisos en 3 capas (`backend/app/routers/<modulo>.py`)

El patrón de 3 capas (ver [../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md)):

1. **Autenticación:** `current_user: User = Depends(get_current_user)`.
2. **Autorización por permiso/rol:** `Depends(require_permission("<permiso>"))`
   de `backend/app/middleware/auth.py`. Permisos disponibles (rol `admin`):
   `upload_files`, `reconcile`, `manage_users`, `view_audit`, `view_accounting`,
   `manage_finance`, `admin_accounting`, `delete_records`. El superadmin tiene
   todos. Ejemplo real: `cheques_crud.py` usa `require_permission("delete_records")`
   en el `DELETE`.
3. **Scope por organización:** filtrar **siempre** las queries por
   `organizacion_id` del usuario (helper `_org_id(...)` en `cheques_common.py`).
   Nunca devolver datos de otra org.

- [ ] Endpoints siguen [NEW_API_ENDPOINT.md](NEW_API_ENDPOINT.md) y
      [../api/API_RULES.md](../api/API_RULES.md).
- [ ] Si hay endpoints `DELETE` con FKs entrantes: nulificar/reasignar
      referencias antes de borrar y testear el borrado con datos relacionados
      (bug recurrente — ver `../../BUGS.md`).
- [ ] Registrar el router en `backend/app/main.py` con
      `app.include_router(<modulo>.router)` (junto a los otros `include_router`).

### 4. Migración + safety net idempotente (ADR-010)

- [ ] Migración Alembic en `backend/alembic/versions/` (`alembic revision`).
- [ ] **Además**, agregar la tabla a los safety nets de `backend/app/main.py`
      como `CREATE TABLE IF NOT EXISTS <tabla> (...)` y cada columna nueva como
      `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` — estrictamente idempotente.
      Esto garantiza convergencia del esquema en cada arranque aunque Alembic
      falle. Ver [../database/DATABASE_RULES.md](../database/DATABASE_RULES.md).
- [ ] Si el módulo necesita datos sembrados por org (cuentas, categorías,
      config): agregar al seed por org (patrón de
      `backend/app/services/seed_contable.py`), idempotente.

### 5. Opt-in / configurable por organización

- [ ] El módulo NO debe asumir Org A. Toda su data y config se scopea por
      `organizacion_id` (ADR-004/ADR-005). Si tiene flags de activación, van en
      la config por org, no en constantes de código.

### 6. Tests (`backend/tests/`)

- [ ] Tests del service (cálculo) y del router (permisos + scope por org).
- [ ] Caso de borrado con datos relacionados si hay `DELETE`.
- [ ] Verificación: `pytest` (suite total: 440 tests pasando, ver
      `../../CLAUDE.md`).

### 7. Frontend: página + navegación

- [ ] Página en `frontend/src/pages/<Modulo>.tsx` (referencia:
      `frontend/src/pages/Cheques.tsx`). Probarla en **modo claro y oscuro**
      desde el inicio (bug recurrente — `../../BUGS.md`).
- [ ] Registrar la ruta en `frontend/src/App.tsx` con `lazyPage(...)` y
      `<Route path="/<modulo>" element={<ProtectedRoute permission="<permiso>">...`
      (ver rutas existentes como `/caja`, `/pagos`).
- [ ] Agregar el item de navegación en `frontend/src/components/Layout.tsx`.
- [ ] Endpoints del módulo en `frontend/src/services/api.ts`.
- [ ] Fechas de negocio con `localIsoDate()`, montos con `parseMonto()` (formato
      argentino) — ambos por bugs recurrentes (`../../BUGS.md`).
- [ ] Verificación frontend: `tsc --noEmit` + `build`.

---

## Orden de merge sugerido (protocolo de orquestación)

Según `../../CLAUDE.md`: backend → frontend → splits/docs. Mapear qué archivos
toca cada subtarea antes de paralelizar; si dos tocan el mismo archivo
(`main.py`, `api.ts`, `App.tsx`, `Layout.tsx`) van en serie. Commit por sub-paso.

## Criterio de "terminado" (verificable)

`pytest` verde · `tsc --noEmit` sin errores · `build` ok · esquema converge en
arranque (safety net) · datos visibles sólo dentro de la org del usuario.

## Pendiente de revisar

- La lista canónica de permisos por rol vive en
  `backend/app/middleware/auth.py`; los roles distintos de `admin` no se
  detallaron aquí. Documentar el mapa completo en
  [../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md).
