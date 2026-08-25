# Convenciones de base de datos

Reglas transversales del esquema de Cuadra (PostgreSQL / Neon, SQLAlchemy + Alembic). Qué
convenciones seguir al tocar la DB y por qué existen los patrones defensivos.

Fuentes de verdad (código):
- `backend/alembic/versions/*.py` — 20 migraciones versionadas.
- `backend/app/db_safety.py` (`SAFETY_NET_DDL`) — safety nets DDL idempotentes (fuente única).
- `backend/app/main.py` (`_run_alembic`, `_init_db`) — aplica los safety nets + seed en el arranque.
- `backend/app/services/tz.py` — fechas de negocio en ART.
- `backend/app/services/decimal_utils.py` — conversión a `Decimal`.
- `BUGS.md` — bugs recurrentes ("Decimal vs float", "Fechas ART").

Cross-ref: [../architecture/DOMAIN_MODEL](../architecture/DOMAIN_MODEL.md) (entidades),
[../api/API_RULES](../api/API_RULES.md) (serialización en endpoints).

---

## 1. Dinero: SIEMPRE `Numeric(12,2)` → `Decimal`

Toda columna monetaria es `Numeric(12,2)` (hasta `$9.999.999.999,99`); los porcentajes son
`Numeric(5,4)` (ej. `0.0350` = 3,50%). SQLAlchemy las entrega a Python como `Decimal`, **no**
`float`.

- **Regla**: todo cálculo, comparación o parseo de montos asume `Decimal`. Convertir con
  `app/services/decimal_utils.to_decimal(v)` (acepta `None`/`float`/`str`/`Decimal`, nunca
  lanza, devuelve `Decimal("0")` ante valores no convertibles).
- **Serialización a JSON**: convertir explícitamente con `str()` o un encoder custom — el
  default de JSON no maneja `Decimal`.
- **Por qué**: código que asume `float` rompe con `TypeError` (comparaciones, JSON de
  auditoría) o pierde precisión. Ver BUGS.md → "Decimal vs float en cálculos monetarios".

La migración **007** convirtió todas las columnas financieras de `DOUBLE PRECISION` a
`NUMERIC` con precisión específica (montos `12,2`, porcentajes `5,4`) en
`liquidaciones`, `liquidacion_detalles`, `cheques`, `arqueos_diarios`, `ordenes_de_pago`,
`pagos`, `gastos`, `planilla_rows`, `patrones_aprendidos`, `movimientos_banco`,
`asiento_detalle`.

---

## 2. Soft delete (`deleted_at`)

Entidades borrables usan **borrado lógico**: columna `deleted_at` (`DateTime`, nullable).

- `NULL` = registro activo · timestamp = en "papelera".
- Las queries deben filtrar `deleted_at IS NULL` para ver solo activos. Es
  backwards-compatible: queries que no filtran ven todo.
- Introducido en la migración **002** para `extractos_bancarios` y `planillas` (cada una con
  índice sobre `deleted_at`).
- Interactúa con el índice único de fingerprint (§5): borrar y re-subir el mismo extracto debe
  poder crear uno nuevo, por eso el índice excluye los borrados.

---

## 3. Migraciones Alembic + safety nets idempotentes

El esquema se versiona con **Alembic** (`backend/alembic/versions/`), pero `main.py` además
aplica un **safety net DDL idempotente** en cada arranque.

### Por qué existen los safety nets

El esquema lo construyen y mantienen `Base.metadata.create_all()` + los safety-nets DDL; la
cadena de migraciones está desincronizada (ver "Pendiente de revisar"). Por eso `_run_alembic()`
(`main.py`) **solo hace `command.stamp(head)`** — sella `alembic_version` en head para reflejar la
realidad y dejar Alembic usable como tooling (history/autogenerate), sin correr `upgrade` (que
intentaría migraciones derivadas contra un esquema que ya está al día y fallaría). Todo está
envuelto en try/except y solo loguea un warning si falla. En Render (free tier, cold starts,
deploys que pueden interrumpirse) tampoco hay garantía de que Alembic corriera hasta el final:
si faltara alguna columna/tabla/índice, la app rompería al primer query.

Por eso, después de Alembic, `main.py` ejecuta listas de DDL **idempotente** que garantizan el
esquema mínimo aunque Alembic no haya corrido:

- `SAFETY_NET_DDL` (en `app/db_safety.py`, aplicada por `_run_alembic`):
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`,
  `CREATE [UNIQUE] INDEX IF NOT EXISTS`, `DROP INDEX IF EXISTS`. Cubren columnas de
  comisión, `cuenta_contable_id`, `numero_asiento`, portadores/cheques, twofa, liquidaciones
  de tarjeta, índices de contabilidad, IVA, monotributo, IIBB, sueldos, ganancias y ARCA.
  Está extraída a un módulo importable para poder testearla: `tests/test_db_safety.py`
  **exige que toda sentencia sea idempotente** (falla en CI si aparece un `ADD COLUMN` sin
  `IF NOT EXISTS`, que crashearía el 2º boot) y que no haya índices con nombre duplicado.
- `indexes` (en `_init_db`): `CREATE INDEX IF NOT EXISTS` de performance.
- `migrations` (en `_init_db`): `ALTER TABLE ... ADD COLUMN` sin `IF NOT EXISTS`, cada uno en
  su propio try/except que ignora "column already exists" (porque `IF NOT EXISTS` no está
  disponible en todas las versiones de Postgres para algunas sentencias).
- `backfills`: `UPDATE` idempotentes (multi-tenant `organizacion_id=1`, propagar `tipo` a
  subcuentas, normalizar `mes`, etc.).

**Regla al agregar una columna/tabla/índice nuevo**: escribir la migración Alembic *y* agregar
la sentencia idempotente equivalente a `SAFETY_NET_DDL` (`app/db_safety.py`). Las dos rutas deben converger
al mismo esquema. El seed contable (`seed_contabilidad_org`) corre también en cada boot, por
organización, e igualmente es idempotente (ver [ACCOUNTING_ENGINE](../architecture/ACCOUNTING_ENGINE.md)).

### Orden de arranque (`_init_db`)

1. `Base.metadata.create_all()` — crea tablas faltantes.
2. `_run_alembic()` — `stamp head` (sella la versión; no corre `upgrade`) + safety
   net de columnas/tablas.
3. Índices de performance idempotentes.
4. Migraciones de columnas legacy (try/except).
5. Normalizaciones y backfills (`organizacion_id`, `mes`, fingerprints).
6. Seed de la Organización A (id=1) y seed contable + categorías por organización.
7. Backfill de asientos contables para extractos/planillas existentes.

---

## 4. Índices de performance

Definidos en migraciones **004**, **010**, **012** y replicados en los safety nets de
`main.py`. Patrón general: indexar por `organizacion_id` (presente en casi todos los filtros) +
la columna de orden/join más frecuente.

- **004** — analítica y conciliación: `movimientos_banco (org,fecha)`, `planillas
  (org,deleted_at)`, `planilla_rows (planilla_id,status)`, `cheques (org,estado)`,
  `pagos`/`gastos (org,fecha)`, `auditoria (org,fecha)`.
- **010** — índices faltantes en `clientes` y `plan_cuentas`.
- **012** — contabilidad (Libro Diario / Cuentas Corrientes): `asientos (organizacion_id)`,
  `asientos (org,fecha)`, `asientos (modulo)`, `asiento_detalle (asiento_id)`,
  `asiento_detalle (cuenta_id)`, `asiento_detalle (cuenta_id,asiento_id)`. Sin estos,
  `asientos.organizacion_id` (en TODOS los filtros contables) haría full scan.
- **011** — índice sobre `asientos.numero_asiento` (numeración correlativa + orden).

Todos los `CREATE INDEX` del safety net usan `IF NOT EXISTS` → seguros de re-ejecutar.

---

## 5. Constraints únicos

Migración **006** agrega tres índices únicos **parciales** (parciales para no romper data
legacy con NULLs):

- `uq_asiento_modulo_ref_org` — `asientos (modulo, referencia_id, organizacion_id)` cuando
  ninguno es NULL. Es la base de la **idempotencia del motor contable**: dos requests en
  paralelo no crean dos veces el mismo asiento (ver
  [ACCOUNTING_ENGINE](../architecture/ACCOUNTING_ENGINE.md) §1).
- `uq_arqueo_org_fecha` — `arqueos_diarios (organizacion_id, fecha)`: un arqueo por día y org.
- `uq_extracto_fp_org` — `extractos_bancarios (fingerprint, organizacion_id)` donde
  `fingerprint IS NOT NULL`: no se sube dos veces el mismo archivo en paralelo dentro de la
  misma org (por org, no global, para que orgs distintas puedan coincidir).

La migración **020** redefine `uq_extracto_fp_org` para **excluir extractos borrados**
(`... WHERE fingerprint IS NOT NULL AND deleted_at IS NULL`): así borrar y re-subir el mismo
archivo crea uno nuevo en vez de chocar contra la fila borrada. El safety net de `main.py`
hace `DROP INDEX IF EXISTS` + recrea con la definición nueva para reemplazar la de 006.

---

## 6. Multi-tenant: `organizacion_id`

Casi todas las tablas de negocio llevan `organizacion_id` (FK a `organizaciones`, default 1).

- **Regla**: toda query de negocio filtra por `organizacion_id`; la resolución del org activo
  está centralizada en `_org_id(current_user, org_id)` (`ctb_common.py` y equivalentes) — un
  superadmin puede operar sobre otra org vía `?org_id=`, el resto queda en su propia org.
- La **Organización A (id=1)** es la org principal: solo cambios **aditivos**, nunca modificar
  datos existentes (ver CLAUDE.md). Se siembra en el arranque si no existe.
- Backfill: `UPDATE ... SET organizacion_id=1 WHERE organizacion_id IS NULL` en `_init_db`
  cubre filas legacy previas al multi-tenant.

Ver [../security/SECURITY_MODEL](../security/SECURITY_MODEL.md) para el aislamiento por org.

---

## 7. Zona horaria: `created_at` UTC vs fechas de negocio ART

Render corre en **UTC**. `date.today()` / `datetime.now()` (sin tz) y
`new Date().toISOString()` (frontend) dan fecha UTC — entre las 21:00 y 03:00 ART eso produce
la fecha de mañana/ayer. Es el bug más recurrente del proyecto.

- **Fechas de NEGOCIO** (egresos, cheques, arqueos, asientos, fechas de acreditación): usar
  `app/services/tz.py` → `hoy_art()` / `now_art()` (con
  `ZoneInfo("America/Argentina/Buenos_Aires")`). En frontend, `localIsoDate()`.
- **Timestamps de auditoría** (`created_at`, expiración de tokens 2FA/reset): se quedan en
  **UTC** a propósito — es correcto y consistente. **No** usar `hoy_art()` ahí.
- En los modelos, `created_at = Column(DateTime, default=datetime.utcnow)` (UTC) mientras que
  las columnas `fecha` de negocio se setean con `hoy_art()` desde los servicios.
- Fix retroactivo de filas con fecha corrida: `POST /contabilidad/fix-fechas-utc`
  (dry_run + adelantar/atrasar por rango).

Ver BUGS.md → "Fechas en zona horaria Argentina (UTC-3)".

---

## 8. Las 20 migraciones (`alembic/versions/`)

| Rev | Archivo | Qué hace |
|-----|---------|----------|
| 001 | `001_baseline.py` | Baseline — sella el estado actual de la DB al incorporar Alembic |
| 002 | `002_soft_delete.py` | `deleted_at` + índice en `extractos_bancarios` y `planillas` (soft delete) |
| 003 | `003_password_reset.py` | Tabla de tokens para recuperación de contraseña |
| 004 | `004_performance_indexes.py` | Índices de analítica/conciliación (movimientos, planillas, rows, cheques, pagos, gastos, auditoría) |
| 005 | `005_revoked_tokens.py` | Tabla de JWT revocados (logout efectivo) |
| 006 | `006_unique_constraints.py` | Índices únicos parciales: asiento, arqueo, extracto fingerprint (anti-duplicado por concurrencia) |
| 007 | `007_float_to_numeric.py` | Migra columnas financieras de FLOAT a NUMERIC(12,2)/(5,4) |
| 008 | `008_cliente_comision.py` | `porcentaje_comision` en `clientes` |
| 009 | `009_drop_tablas_viejas.py` | Drop de tablas obsoletas: `ordenes_de_pago`, `pagos`, `gastos` |
| 010 | `010_performance_indexes_2.py` | Índices faltantes en `clientes` y `plan_cuentas` |
| 011 | `011_asientos_numero_index.py` | Índice en `asientos.numero_asiento` |
| 012 | `012_contabilidad_indexes.py` | Índices críticos en `asientos` y `asiento_detalle` (Libro Diario, Cuentas Corrientes) |
| 013 | `013_iva_proyeccion.py` | Módulo IVA Proyección y DDJJ |
| 014 | `014_monotributo.py` | Módulo Control Semestral Monotributo |
| 015 | `015_iibb.py` | Módulo Ingresos Brutos (IIBB) y Convenio Multilateral |
| 016 | `016_sueldos.py` | Módulo Liquidador de Sueldos y F931 |
| 017 | `017_ganancias.py` | Retención de Ganancias 4ta categoría (opt-in, independiente de Sueldos) |
| 018 | `018_total_retencion.py` | Total de retención de Ganancias 4ta en el período de liquidación de sueldos |
| 019 | `019_arca.py` | Módulo ARCA (ex-AFIP) — facturación electrónica WSFEv1/WSAA |
| 020 | `020_extracto_fp_excl_borrados.py` | Redefine `uq_extracto_fp_org` para excluir extractos borrados (soft delete) |

---

## Pendiente de revisar

- **⚠️ La cadena Alembic está desincronizada del esquema real (verificado jul 2026)**. Hallazgos
  de correr la cadena contra un Postgres descartable:
  1. **`alembic/env.py` importaba clases inexistentes** (`OrdenDePago`, `Pago`, `Gasto` —
     unificadas en `Egreso`). Como `env.py` se carga en *cada* comando de alembic, `command.upgrade`
     y `command.stamp` **fallaban al importar**, y como `_run_alembic()` traga la excepción y solo
     loguea un warning, **Alembic no corría en producción**: el esquema lo sostienen `create_all()`
     + los safety-nets. **Corregido**: `env.py` ahora importa los módulos de modelo (no clases
     sueltas), robusto ante renombres.
  2. **La cadena NO se puede construir desde cero**: `001_baseline` es un `pass` (stamp baseline,
     asume que las tablas ya existen por `create_all()`). El camino real de arranque —`create_all()`
     + `stamp head`— **sí funciona** (verificado: sella `020`, 44 tablas, safety-nets idempotentes
     sobre PG real).
  3. **Migraciones históricas referencian tablas ya dropeadas**: 007 hace `ALTER TABLE
     ordenes_de_pago …` y 009 las dropea (`DROP TABLE IF EXISTS … CASCADE`, guardado ✓). Sobre un
     esquema moderno (`create_all`) un `upgrade` incremental desde una revisión vieja falla en 007
     porque esas tablas ya no existen. En la DB de producción histórica no falló porque esas tablas
     **sí existían** cuando 007 corrió.
  → **Decisión (jul 2026)**: mantener `create_all` + safety-nets como fuente de verdad y que
  Alembic **solo selle** (`_run_alembic` hace `stamp head`, no `upgrade`). No se tocan migraciones
  históricas ya aplicadas. Un re-baseline (colapsar el esquema actual en un baseline nuevo) queda
  como mejora futura opcional, para una sesión dedicada.
- **Doble fuente de DDL**: el esquema vive a la vez en migraciones Alembic y en los safety nets
  (`app/db_safety.py`). Son intencionalmente redundantes (resiliencia ante fallos de Alembic en
  Render — que de hecho no corría, ver arriba). El guard `tests/test_db_safety.py` verifica que
  toda sentencia del safety-net sea idempotente, pero **no** que converja con las migraciones a
  mano; mantenerlas sincronizadas al agregar columnas/índices.
- **`CONFIG_DEFAULT`**: `main.py` importa `CONFIG_DEFAULT` de `models/organizacion` pero define
  un `config_org` inline al sembrar la Organización A. Revisar si `CONFIG_DEFAULT` es la fuente
  canónica de configuración por org y si conviene unificar.
