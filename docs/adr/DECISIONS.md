# DECISIONS — Registro de decisiones arquitectónicas (ADR)

Registro de las decisiones arquitectónicas **reales** del sistema Cuadra
(conciliación bancaria). Cada entrada está deducida del código y de la
documentación existente (`../../CLAUDE.md`, `../../CHANGELOG.md`,
`../../BUGS.md`). No se incluyen decisiones sin evidencia.

Formato por entrada: **Título · Contexto · Decisión · Consecuencias · Estado**.

Cross-ref:
[../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) ·
[../architecture/ACCOUNTING_ENGINE.md](../architecture/ACCOUNTING_ENGINE.md) ·
[../database/DATABASE_RULES.md](../database/DATABASE_RULES.md) ·
[../security/SECURITY_MODEL.md](../security/SECURITY_MODEL.md) ·
[../ai/AI_GUIDE.md](../ai/AI_GUIDE.md).

---

## ADR-001 — Dinero en `Decimal` / `Numeric`, nunca `float`

- **Contexto:** los cálculos monetarios con `float` pierden precisión y los
  redondeos no son fiables para conciliación contable. La migración Alembic
  `007_float_to_numeric` (ver `../../CLAUDE.md` → estructura) confirma que el
  proyecto arrancó con columnas `Float` y migró a `Numeric`.
- **Decisión:** todas las columnas de monto se declaran como `Numeric(12,2)`
  (o `Numeric(5,4)` para porcentajes/tasas) en los modelos
  (`backend/app/models/cheque.py`, `backend/app/models/contabilidad.py`, etc.).
  En Python todo cálculo o comparación de montos asume `Decimal`.
- **Consecuencias:** los helpers de parseo/comparación
  (`parse_importe`, `montos_iguales`, `_monto` en
  `backend/app/services/motor_contable.py`) deben aceptar `Decimal`. La
  serialización a JSON requiere encoder explícito (`str()`), nunca el default.
- **Estado:** Aceptada y vigente. Es un área de bug recurrente documentada en
  [../../BUGS.md](../../BUGS.md) ("Decimal vs float en cálculos monetarios").

---

## ADR-002 — Soft delete en vez de borrado físico

- **Contexto:** los registros de negocio (extractos, planillas, liquidaciones)
  necesitan papelera/auditoría; el borrado físico rompe integridad referencial
  y trazabilidad.
- **Decisión:** las entidades llevan columna `deleted_at` (ver
  `backend/app/models/extracto.py`, `planilla.py`, `sueldos.py`,
  `liquidacion_tarjeta.py`) y se "borran" seteando esa marca. La migración
  `002_soft_delete` introdujo el patrón; existe un router `papelera.py`.
- **Consecuencias:** los índices únicos deben filtrar `deleted_at IS NULL`
  (p.ej. el unique index de fingerprint en `backend/app/main.py`). Toda query
  de listado debe excluir los soft-deleted.
- **Estado:** Aceptada y vigente.

---

## ADR-003 — Deduplicación de extractos por fingerprint único por organización

- **Contexto:** el contador reenvía "Últimos Movimientos" diariamente; subir el
  mismo extracto dos veces no debe duplicar movimientos.
- **Decisión:** cada extracto guarda un `fingerprint`
  (`hashlib.sha256(...)[:16]` sobre los movimientos, ver
  `backend/app/routers/extractos.py::_fingerprint` y backfill en
  `backend/app/main.py`). El índice
  `uq_extracto_fp_org (fingerprint, organizacion_id) WHERE fingerprint IS NOT NULL AND deleted_at IS NULL`
  garantiza unicidad por org. Si llega un extracto idéntico se hace upsert de
  acreditados en vez de duplicar.
- **Consecuencias:** la unicidad es **por organización**, no global (multi-tenant,
  ver ADR-004). La deduplicación de UM además usa `(orden, monto)` o
  `(fecha, monto, titular_norm)` (ver `../../CLAUDE.md` → motor de conciliación).
- **Estado:** Aceptada y vigente.

---

## ADR-004 — Multi-tenant por `organizacion_id` + cambio de org controlado

- **Contexto:** Julieta (superadmin) opera varias organizaciones; cada una debe
  ver solo sus datos, sin tablas separadas.
- **Decisión:** todas las entidades llevan `organizacion_id`
  (default `1` = Org A). El usuario tiene `is_superadmin` y `allowed_org_ids`
  (JSONB) para habilitar el cambio de organización
  (ver `backend/app/models/user.py`; columna sembrada también como safety net en
  `backend/app/main.py`). La Org A (`organizacion_id=1`) **nunca se modifica**:
  solo cambios aditivos (`../../CLAUDE.md`).
- **Consecuencias:** cada query, índice único y regla contable se scopea por
  `organizacion_id`. Cada módulo nuevo debe ser opt-in por organización, no
  hardcodeado para una sola (ver [../playbooks/NEW_MODULE.md](../playbooks/NEW_MODULE.md)).
- **Estado:** Aceptada y vigente.

---

## ADR-005 — Configuración por organización en JSON

- **Contexto:** distintas orgs necesitan distintas reglas de conciliación y
  tolerancias sin cambiar código.
- **Decisión:** la configuración por org se guarda como JSON con campos
  `match_rules`, `tolerancia_monto`, `dias_tolerancia_fecha`,
  `requiere_cierre_periodo` (ver `../../CLAUDE.md` → multi-tenant). El plan de
  cuentas y las `ReglaContable` también se siembran por org
  (`backend/app/services/seed_contable.py`).
- **Consecuencias:** el motor de conciliación y el motor contable leen su
  comportamiento de datos por org, no de constantes. Permite onboarding de orgs
  nuevas sin deploy.
- **Estado:** Aceptada y vigente.

---

## ADR-006 — Motor contable propio con partida doble e idempotencia

- **Contexto:** se necesita un Libro Diario por partida doble que se genere
  automáticamente desde las operaciones (extractos, planillas, cheques, pagos,
  liquidaciones, ARCA) sin un ERP externo.
- **Decisión:** `backend/app/services/motor_contable.py` postea asientos
  (`Asiento` + `AsientoDetalle`) según `ReglaContable` (evento → cuenta debe /
  haber). Es **idempotente**: nunca crea dos asientos para el mismo
  `(modulo, referencia_id, organizacion_id)` (ver `_ya_existe`). Está siempre
  encapsulado en `try/except`: si el asiento falla, la operación principal
  **no se revierte**.
- **Consecuencias:** cada módulo nuevo que mueva dinero debería registrar su
  asiento llamando a un helper `registrar_*` (ver
  [../playbooks/NEW_ACCOUNTING_MODULE.md](../playbooks/NEW_ACCOUNTING_MODULE.md)
  y el deep dive en
  [../architecture/ACCOUNTING_ENGINE.md](../architecture/ACCOUNTING_ENGINE.md)).
- **Estado:** Aceptada y vigente.

---

## ADR-007 — Integración propia con ARCA (WSFEv1 / WSAA), sin proveedor intermediario

- **Contexto:** la facturación electrónica argentina (ex-AFIP, hoy ARCA)
  requiere autenticación WSAA y emisión WSFEv1. Existen proveedores SaaS
  intermediarios, pero implican costo recurrente y dependencia externa.
- **Decisión:** Cuadra implementa la integración directamente contra los web
  services de ARCA, sin librería SOAP pesada (no hay `zeep`/`suds`): los
  envelopes XML se arman a mano. `backend/app/services/arca_wsaa.py` firma el
  TRA como CMS/PKCS#7 y obtiene token+sign (~12h, cacheados cifrados);
  `backend/app/services/arca_wsfe.py` consulta el último comprobante autorizado
  y pide el CAE. El certificado X.509 + clave de cada org se cifran
  (`backend/app/services/arca_crypto.py`, `ARCA_ENCRYPTION_KEY`).
- **Consecuencias:** sólo se implementan las operaciones que Cuadra necesita
  (`FECompUltimoAutorizado`, `FECAESolicitar`). Coherente con el estilo liviano
  del resto (excel_parser, motor_contable tampoco usan frameworks externos).
- **Estado:** Aceptada. Construida pero **desactivada a propósito** (ver ADR-011).

---

## ADR-008 — Feature flags por variable de entorno con degradación elegante

- **Contexto:** funcionalidades opcionales (email/backup, push, IA, Sentry,
  login Google, storage R2) no deben romper el arranque si faltan sus secretos.
- **Decisión:** cada feature se activa por env var y, sin ella, se degrada sola
  sin romper (ver `../../CLAUDE.md` → arquitectura de producción). Ejemplos:
  `RESEND_API_KEY` (backup/2FA), `VAPID_*` (push), `GEMINI_API_KEY` (IA/OCR),
  `SENTRY_DSN`/`VITE_SENTRY_DSN`, `GOOGLE_CLIENT_ID`, `S3_*` (ver ADR-009). El
  storage chequea `_is_configured()` antes de usar R2
  (`backend/app/services/storage.py`).
- **Consecuencias:** el sistema corre completo en local/free-tier sin ningún
  secreto; cada flag se prueba por separado. Los schedulers (backup 03:00 ART,
  push 10:00 ART) sólo se montan si su flag está presente.
- **Estado:** Aceptada y vigente.

---

## ADR-009 — Storage de fotos: base64 en DB por defecto, R2/S3 opt-in

- **Contexto:** las fotos de OPs y cheques deben persistir sin obligar a
  contratar storage externo desde el día uno.
- **Decisión:** por defecto las fotos se guardan como data URL base64 en la DB.
  Si las 5 env vars `S3_*` están seteadas, `backend/app/services/storage.py`
  sube a S3/R2 (Cloudflare R2 recomendado) y guarda la URL pública. El fallback
  es transparente: registros viejos en base64 siguen funcionando.
- **Consecuencias:** activar R2 es solo crear el bucket y pegar env vars; no hay
  migración de datos. Caso particular de la filosofía de feature flags (ADR-008).
- **Estado:** Aceptada y vigente. Activación de R2 pendiente en el roadmap.

---

## ADR-010 — Safety nets idempotentes en `main.py` además de Alembic

- **Contexto:** Render free tier + Neon pueden desincronizar el estado de
  migraciones; se necesita que el esquema converja en cada arranque sin
  intervención manual.
- **Decisión:** además de las migraciones Alembic
  (`backend/alembic/versions/`), `backend/app/main.py` corre en background un
  bloque de safety nets idempotentes: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
  `CREATE TABLE IF NOT EXISTS`, `CREATE [UNIQUE] INDEX IF NOT EXISTS`, seed de
  org/plan de cuentas y backfill de fingerprints. Todo tolerante a fallos
  (no bloquea el arranque).
- **Consecuencias:** el esquema converge aunque Alembic falle; cada módulo nuevo
  añade su `CREATE TABLE IF NOT EXISTS` aquí como red de seguridad (ver
  [../playbooks/NEW_MODULE.md](../playbooks/NEW_MODULE.md) y
  [../database/DATABASE_RULES.md](../database/DATABASE_RULES.md)). Las
  sentencias deben ser estrictamente idempotentes.
- **Estado:** Aceptada y vigente.

---

## ADR-011 — ARCA construido pero desactivado a propósito

- **Contexto:** el módulo ARCA (v3.24) está completo y `ARCA_ENCRYPTION_KEY` ya
  está seteada en Render, pero emitir en ambiente producción genera CAE reales
  e irreversibles (IVA débito fiscal real, numeración correlativa). Ningún
  cliente lo solicitó todavía.
- **Decisión:** dejar el módulo mergeado y listo, pero **no activarlo**. Cualquier
  prueba va siempre en homologación. La activación requiere certificado de
  homologación, luego de producción autorizado para WSFEv1, y cambiar
  `ambiente` a `produccion` desde `/arca` (requiere permiso `admin_accounting`).
- **Consecuencias:** decisión de negocio reversible que difiere el riesgo fiscal
  hasta que haya un cliente real. Detalle del procedimiento en `../../CLAUDE.md`
  → "Activación de ARCA en producción — diferida a pedido".
- **Estado:** Aceptada y vigente (diferida a pedido de la autora).

---

## ADR-012 — PWA instalable en vez de app nativa

- **Contexto:** Julieta y clientes usan mobile (Android/Chrome) para cargar
  fotos, compartir por WhatsApp y recibir notificaciones, sin presupuesto para
  apps nativas en dos tiendas.
- **Decisión:** el frontend es una PWA instalable (React 18 + Vite) con
  `frontend/public/manifest.webmanifest` y service worker
  `frontend/public/sw.js` (network-first + share target + web push). El push
  usa VAPID (ver `../../CLAUDE.md` → Web Push).
- **Consecuencias:** una sola base de código web; web push y "compartir" tienen
  trampas mobile documentadas (transient activation, race de canvas) en
  [../../BUGS.md](../../BUGS.md). Ver también
  [../ux/UX_RULES.md](../ux/UX_RULES.md).
- **Estado:** Aceptada y vigente.

---

## ADR-013 — Detección multi-banco por palabra completa (no substring)

- **Contexto:** detectar el banco del extracto por texto con `substring in nombre`
  produce falsos positivos al sumar bancos con nombres parecidos (p.ej. `"rio"`
  de Santander captura "Banco de La Rioja").
- **Decisión:** la detección usa coincidencia de palabra completa con `\b`
  (`backend/app/services/excel_parser.py::_kw_en_texto`) y prueba primero las
  keywords más largas/específicas (`candidatos.sort(...)`). Hay además detección
  por estructura de columnas (Mercado Pago).
- **Consecuencias:** agregar un banco nuevo exige revisar colisiones de keywords
  (ver [../playbooks/NEW_PARSER.md](../playbooks/NEW_PARSER.md) y
  [../playbooks/NEW_BANK.md](../playbooks/NEW_BANK.md)). Bug recurrente
  documentado en [../../BUGS.md](../../BUGS.md).
- **Estado:** Aceptada y vigente.

---

## ADR-014 — Fechas de negocio en hora Argentina (ART), auditoría en UTC

- **Contexto:** Render corre en UTC; entre 21:00 y 03:00 ART, `date.today()` /
  `new Date().toISOString()` devuelven la fecha de mañana, corrigiendo mal las
  fechas de negocio.
- **Decisión:** las fechas de negocio usan helpers ART: backend
  `backend/app/services/tz.py` (`hoy_art()` / `now_art()` con
  `ZoneInfo("America/Argentina/Buenos_Aires")`), frontend `localIsoDate()`.
  **Excepción a propósito:** timestamps de auditoría (`created_at`, expiración de
  tokens 2FA/reset) se mantienen en UTC.
- **Consecuencias:** todo módulo nuevo usa `hoy_art()`/`now_art()` para fechas de
  negocio. Bug más recurrente del proyecto, documentado en
  [../../BUGS.md](../../BUGS.md).
- **Estado:** Aceptada y vigente.

---

## Pendiente de revisar

- La forma exacta de persistencia de la config por org (ADR-005) se documenta en
  `../../CLAUDE.md` como JSON pero no se confirmó aquí el modelo/columna
  concretos en `backend/app/models/organizacion.py`. Verificar al documentar
  [../architecture/DOMAIN_MODEL.md](../architecture/DOMAIN_MODEL.md).
- Los docs cross-referenciados de este mapa (architecture/, database/,
  security/, ux/) están aún por escribir; los enlaces quedan listos para cuando
  existan.
