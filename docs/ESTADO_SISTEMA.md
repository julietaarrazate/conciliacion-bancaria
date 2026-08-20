# Cuadra — Sistema de Conciliación Bancaria y Liquidación Impositiva
## Estado completo del sistema (para revisión externa)

> Documento de contexto para analizar qué **modificar, pulir o mejorar**. Autocontenido: describe
> todo lo que el sistema tiene construido hasta hoy. Fecha de corte: **agosto 2026, v3.29**.
> Autora: Julieta Arrazate. Repo privado→público `julietaarrazate/conciliacion-bancaria`.

---

## 1. Qué es y para qué sirve

Sistema web (PWA instalable) para un estudio contable que:
1. Recibe el **extracto bancario mensual** (Excel del banco) y "Últimos Movimientos" diarios del contador.
2. Recibe **planillas de pagos de clientes** en formatos heterogéneos (cada cliente manda su propio Excel).
3. **Concilia** automáticamente: cruza cada pago del cliente contra los movimientos del banco por identidad
   (CUIT, CBU, número de cuenta, titular) + cercanía de fecha, con scoring.
4. Devuelve la planilla con estado por fila + extracto actualizado + **exports** (Excel formato contador, PDF de cierre).
5. Alrededor del núcleo hay módulos operativos (cheques, caja, pagos, contabilidad con partida doble) y
   **5 módulos de liquidación de impuestos** (IVA, Monotributo, Ingresos Brutos, Sueldos/F931).

Es **multi-tenant** (varias organizaciones/estudios) y **multi-usuario** con roles y permisos.

---

## 2. Stack y arquitectura de producción

| Capa | Tecnología | Hosting |
|------|-----------|---------|
| Frontend | React 18 + TypeScript + Vite + TailwindCSS, PWA | Vercel |
| Backend | FastAPI + SQLAlchemy + Python 3.11 | Render (free tier, cold start ~30s) |
| Base de datos | PostgreSQL | Neon (free tier, autosuspende) |
| Auth | JWT 8h · pbkdf2_sha256 · rate limiting (slowapi) · headers de seguridad | — |

- **Keep-alive**: UptimeRobot pinguea `/health` cada 5 min (Render despierto); job interno `db_keepalive`
  (`SELECT 1` cada 4 min) mantiene despierto a Neon.
- **Schedulers** (APScheduler en el proceso FastAPI): keepalive DB (4 min), backup diario 03:00 ART,
  purga de tokens 03:30, alerta de storage 09:00, push de alertas (cheques por vencer + movimientos sin
  conciliar) 10:00.
- **Feature flags por env var** (si falta la var, la feature se degrada sola, no rompe): Resend (email/2FA),
  VAPID (web push), Gemini (asistente IA/OCR/voz), Sentry (observabilidad), Google login, S3/R2 (storage fotos),
  ARCA (facturación electrónica, construida pero **desactivada a propósito**).
- **CI**: GitHub Actions — ruff + pytest (backend), eslint + tsc + vitest + build (frontend).
- **Migraciones**: Alembic (25 migraciones, `001`→`025`) + un "safety-net DDL" idempotente al arranque.

---

## 3. Núcleo: motor de conciliación

Archivo: `services/conciliacion.py`. **Scoring por identidad:**

| Señal | Puntos |
|-------|--------|
| CUIT exacto (10-11 díg.) | 12 |
| CBU/CVU exacto (22 díg.) | 10 |
| Nº cuenta largo (10+ díg.) | 8 |
| Nº referencia (6-9 díg.) | 6 |
| Titular (2 palabras) | 5 |
| Titular (1 palabra) | 3 |
| Bonus fecha cercana | +1 a +5 |

- **Regla fundamental**: monto duplicado en el extracto → SIEMPRE exige identidad (no concilia solo por monto).
- Tolerancia de fecha: 5 días. Deduplicación de UM por `(orden, monto)` o `(fecha, monto, titular_norm)`.
- **IA Nivel 2** (`PatronAprendido`): aprende de correcciones manuales; con 2+ confirmaciones aplica el patrón automático.

**Multi-banco** (`detectar_banco` en `excel_parser.py`) — 16 bancos: Macro, BBVA, Santander, Galicia, ICBC,
Nación, Provincia, Ciudad, HSBC, Mercado Pago, Credicoop, Supervielle, Patagonia, Bancor, Rioja, La Pampa + genérico.

**Estandarización de planillas de clientes** (`services/planilla_mapper.py`): embudo de 3 capas que normaliza
cada planilla al esquema canónico `{monto, cuit, titular, referencia, fecha}` antes de conciliar:
perfil aprendido por cliente → heurística con validación de contenido → IA (Gemini) como fallback.

---

## 4. Motor contable (partida doble)

`services/motor_contable.py` + `seed_contable.py`. Plan de cuentas jerárquico (`plan_cuentas` con `parent_id`),
reglas contables configurables (`reglas_contables`: cuenta debe/haber por tipo de evento), asientos inmutables
con detalle (`asientos` + `asiento_detalle`).

**Cuentas corrientes por cliente**: cada cliente se vincula a una cuenta contable (`2-1-2-X`). **El saldo NO se
almacena** — se calcula al vuelo sumando `debe − haber` de `asiento_detalle`. Libro mayor, sumas y saldos, balance,
estado de cuenta por cliente y export contable disponibles.

---

## 5. Módulos backend (routers) — inventario completo

- **Núcleo conciliación**: `extractos`, `planillas`, `historial`, `conciliaciones` (en planillas), `analisis` (alertas/diagnóstico).
- **Operativos**: `cheques` (+ `cheques_crud`, `cheques_acreditacion`, `cheques_reportes`, `cheques_common`),
  `caja` (arqueos + órdenes de pago), `pagos`, `tarjetas` (liquidación de tarjetas).
- **Contabilidad**: `contabilidad` (+ `ctb_plan`, `ctb_libro`, `ctb_ctas_corrientes`, `ctb_clientes`, `ctb_common`).
- **Impuestos**: `iva` (proyección + liquidación real), `monotributo`, `iibb`, `sueldos` (F931), `arca` (WSFEv1, desactivado).
- **Plataforma**: `auth`, `google_auth`, `me`, `admin`, `organizaciones`, `clientes_dir`, `auditoria`,
  `search`, `agente` (asistente IA), `papelera` (soft-delete/restore), `backup_admin`, `push_router`,
  `public_router` (páginas sin auth: `/p/:token`, privacidad, términos).

**Servicios de apoyo**: `excel_parser`, `excel_export`, `pdf_export`, `extracto_merger`, `aprendizaje`,
`backup_service`/`backup_scheduler`, `email_sender`, `push_service`, `storage` (R2/base64), `decimal_utils`,
`tz` (zona ART), `reportes_service`, `export_contable`, `sicoss_export`, parsers de ARCA (`arca_wsaa/wsfe/crypto`),
`mis_comprobantes_parser`, `tarjeta_parser`, y servicios por impuesto (`iva_*`, `monotributo_*`, `iibb_*`, `sueldos_*`).
`reset_operativo` (nuevo): limpieza de datos operativos conservando maestros.

---

## 6. Frontend — páginas (inventario completo)

Dashboard (individual + carga masiva auto-conciliar) · Clientes · ExtractosArchivo · Movimientos · Conciliaciones ·
Historial · Bulk · Auditoría · Actividad · Usuarios · Organizaciones · Perfil · Login · RecuperarPassword ·
RestablecerPassword · Caja · Cheques · Pagos · Contabilidad · Resumen · EstadoCuenta · FlujoCaja · Revisión ·
Aprobaciones · Tarjetas · **Impuestos**: Iva, Monotributo, IngresosBrutos, Sueldos, Arca · Papelera · Compartir ·
**Públicas** (sin auth): Landing, PaginaPublica, Privacidad, Términos.

Componentes clave: Layout (drawer mobile + búsqueda ⌘K), PlanillaPanel (paginado 100 filas, bulk edit),
FileUpload multi-archivo, charts (Line/Bar/Donut), ConfirmModal, SearchModal. Stores: auth, org, theme,
lock (PIN + biometría), confirm, toast. Diseño app: Linear-inspired, Inter, dark mode; landing: estilo marketing
distinto (Fraunces + efectos).

---

## 7. Módulos de liquidación de impuestos (implementados)

1. **IVA Proyección y DDJJ** (v3.19).
2. **Control Semestral Monotributo** (v3.20) — escala de categorías, se actualiza por semestre (ARCA).
3. **Ingresos Brutos y Convenio Multilateral** (v3.21).
4. **Liquidador de Sueldos y F931** (v3.22) — convenios, categorías, escala de ganancias, export SICOSS.
5. **IVA Liquidación real "Mis Comprobantes" de ARCA** (v3.26) — importa Excel oficial de ventas/compras,
   depura comprobantes, calcula débito−crédito + saldo técnico arrastrado + retenciones/percepciones.

**ARCA facturación electrónica (WSFEv1)** — construido, cifrado listo, **desactivado a propósito** hasta que
un cliente lo pida (requiere certificado de homologación → producción). Una vez en producción, cada CAE es fiscal e irreversible.

---

## 8. Seguridad y multi-tenant

- Todo dato cuelga de `organizacion_id`; aislamiento por organización en cada query.
- Julieta = superadmin (ve/gestiona todas las orgs). Roles/permisos en 3 capas por módulo.
- Config por organización (JSON): reglas de match, tolerancias, si requiere cierre de período.
- Auditoría (`auditoria`): registra INSERT/UPDATE/DELETE con antes/después.
- Soft-delete + papelera (restore). 2FA (Resend) para admin/superadmin. Rate limiting. Headers de seguridad.

---

## 9. Deuda técnica y bugs recurrentes conocidos (candidatos a pulir)

Documentados en `BUGS.md` con causa raíz + cómo evitarlos. **Áreas de riesgo recurrente:**

1. **Fechas en zona ART (UTC-3)** — el bug más recurrente. Usar siempre `localIsoDate()` (frontend) y
   `hoy_art()`/`now_art()` (backend), nunca `toISOString()`/`date.today()` sin tz. Aparece solo entre 21:00-03:00 ART.
2. **Decimal vs float** en montos — todo cálculo/comparación monetaria debe asumir `Decimal`, no `float`.
3. **Estado de cheque** — nunca filtrar por `estado == "pendiente"` (siempre da 0); usar constantes
   `CHEQUE_EN_CARTERA`/`CHEQUE_PENDIENTE_COBRO`. Ya causó alertas y push que nunca disparaban.
4. **Light mode** — páginas dark-first sin variante `dark:` quedan ilegibles; probar ambos modos al crear páginas.
5. **Compartir por WhatsApp (mobile)** — race condition de canvas + "transient activation" (llamar `navigator.share()`
   temprano, sin `await` a backend antes).
6. **Detección de banco por texto** — colisión de substrings ("rio" → Santander vs Rioja/La Pampa); usar palabra completa.
7. **Borrado con FK** — todo `DELETE` sobre entidad con FKs entrantes necesita test explícito con datos relacionados.
8. **`useEffect` con deps incompletas** — no silenciar `exhaustive-deps`; modelar deps async (`activeOrgId`).
9. **Parseo de montos argentinos** ("15.000,50") — `type="number"`+`parseFloat` no alcanza; usar `parseMonto()`.
10. **Deadlock de DDL en deploy caliente** — DDL de arranque debe ir por `_exec_startup_ddl` (lock_timeout + commit por sentencia).

**Robustez de plataforma**: Render/Neon free tier (cold start ~30s, DB autosuspende) — mitigado con keepalive + retry
en frontend, pero es un límite real de performance/UX. Sin observabilidad activa aún (Sentry cableado, falta pegar DSN).

---

## 10. Pendientes / roadmap (según el equipo)

- **🔔 Activar Sentry** (observabilidad): código 100% cableado, falta que Julieta pegue los DSN en Render/Vercel.
  El backend ya loguea `SLOW` las requests > 1500ms y expone `X-Process-Time` → decidir foco de performance con datos reales.
- **Activar R2** (storage de fotos): código listo, solo crear bucket y pegar 5 env vars.
- **Próximo módulo impositivo**: candidato "Intake Exportador de Servicios".
- **Actualizar escala de Monotributo** (semestral, julio/agosto 2026) — valores sembrados vencen.
- **Activar ARCA en producción** — diferido, sólo cuando haya cliente que quiera facturar.
- **IA Nivel 3** — predicción automática (requiere 3-6 meses de datos reales).
- **Pendiente menor**: automatizar import del Excel de retenciones/percepciones de ARCA (hoy carga manual).

---

## 11. Estado de tests

~575 tests backend (39 archivos de test) + ~40 tests frontend (Testing Library/jsdom) pasando en CI.

---

## 12. Cómo pedirle mejoras a ChatGPT (sugerencia de foco)

Áreas donde una revisión externa aporta más valor:
- **Precisión del motor de conciliación**: casos borde de scoring, falsos positivos/negativos, tolerancias.
- **Robustez de parsers** (bancos + planillas heterogéneas): formatos raros, encodings, headers cambiantes.
- **Corrección impositiva**: fórmulas de IVA/IIBB/Monotributo/Sueldos vs normativa argentina vigente.
- **UX**: flujos de carga masiva, conciliación manual, mobile/PWA, ambos modos de color.
- **Performance**: cold start, queries N+1, saldos calculados al vuelo vs materializados, paginación.
- **Deuda técnica de la sección 9** (fechas, Decimal, estados de cheque) — patrones a erradicar de raíz.

> Nota: los datos operativos se acaban de resetear a cero (agosto 2026) conservando clientes y plan de cuentas;
> el sistema arranca "limpio" para registrar todo desde ahora.
