# Sistema de Conciliación Bancaria — Julieta Arrazate

## Para continuar en un nuevo chat

Decile a Claude: "Soy Julieta Arrazate. Proyecto: conciliacion-bancaria.
Lee el CLAUDE.md del repo julietaarrazate/conciliacion-bancaria para entender el contexto."

---

## Autora

**Julieta Arrazate** — julietaarrazate@gmail.com (superadmin del sistema)

---

## Arquitectura de producción

- Frontend (React + PWA): Vercel — https://conciliacion-bancaria-ten.vercel.app
- Backend (FastAPI): Render — https://conciliacion-api.onrender.com
- Base de datos: Neon PostgreSQL — ep-ancient-hall-anz4pezn.c-6.us-east-1.aws.neon.tech
- Código: GitHub — julietaarrazate/conciliacion-bancaria (PRIVADO)
- Keep-alive: UptimeRobot pinguea /health cada 5 min

IDs públicos: Render service `srv-d7pqt81j2pic73c0c6fg` · Vercel `prj_cVINkspVm6j3B1fxOrdU81B0ehWg`

Credenciales: Superadmin `julietaarrazate@gmail.com` / SUPERADMIN_PASSWORD (env var Render)
Demo (solo debug=true): `admin@julieta.com / admin123`

Deploy manual Render:
  curl -X POST https://api.render.com/v1/services/srv-d7pqt81j2pic73c0c6fg/deploys \
    -H "Authorization: Bearer <RENDER_API_KEY>"

---

## Stack

Backend: FastAPI + SQLAlchemy + PostgreSQL (Neon) + Python 3.11
Frontend: React 18 + TypeScript + Vite + TailwindCSS + PWA instalable
Auth: JWT 8h · pbkdf2_sha256 · Rate limiting (slowapi) · Headers de seguridad
Diseño: Linear-inspired · Inter font · dark mode (#0B0B0F)

---

## Flujo de negocio

1. Julieta recibe extracto bancario mensual (Excel .xlsx Banco Macro)
2. El contador envía "Últimos Movimientos" (UM) diariamente → se agregan sin duplicar
3. Los clientes envían planillas de pagos (Green, Tucu, David, Smt, Gwinn, Innova, Camparo, Alojando, Pinares, Paraguay…)
4. El sistema concilia: scoring por CUIT/CBU/número/titular
5. Resultado: planilla con estado por fila + extracto actualizado
6. Export Excel para el contador (formato Macro) + PDF de cierre mensual

---

## Estructura del repositorio

```
/backend
  /app/models    — Organizacion, User, Cliente, ExtractoBancario, MovimientoBanco,
                   Planilla, PlanillaRow, AuditoriaLog, PatronAprendido,
                   Liquidacion, CierrePeriodo, Cheque, Pago, Gasto,
                   ArqueoDiario, OrdenDePago, PlanCuenta, ReglaContable,
                   Asiento, AsientoDetalle, PasswordResetToken, PushSubscription
  /app/routers   — auth, me, extractos, planillas, historial, auditoria, admin,
                   clientes_dir, organizaciones, liquidaciones, caja, cheques,
                   pagos_gastos, contabilidad, analisis, search,
                   public_router, push_router
  /app/services  — conciliacion.py, aprendizaje.py, excel_export.py, pdf_export.py,
                   extracto_merger.py, excel_parser.py, motor_contable.py,
                   backup_service.py, backup_scheduler.py, push_service.py,
                   email_sender.py, password_reset.py
  /alembic/versions — 001_baseline, 002_soft_delete, 003_password_reset, 004_performance_indexes,
                      006_unique_constraints, 007_float_to_numeric

/frontend/src
  /pages   — Dashboard (Individual + Carga masiva auto-conciliar), Clientes,
             ExtractosArchivo, Movimientos, Conciliaciones, Historial, Auditoria,
             Usuarios, Perfil, Login, Organizaciones, Liquidaciones, Caja,
             OrdenDePago, Cheques, PagosGastos, Contabilidad, Resumen,
             EstadoCuenta, FlujoCaja, Revision, Actividad,
             PaginaPublica (/p/:token — sin auth), RecuperarPassword, RestablecerPassword,
             Privacidad (/privacidad — sin auth), Terminos (/terminos — sin auth)
  /components — Layout (drawer mobile + ⌘K search), PlanillaPanel (paginado 100 filas,
                bulk edit), FileUpload (compacto, multi-archivo), SearchModal,
                ConfirmModal, charts/LineChart, BarChart, DonutChart
  /store   — auth.ts, org.ts, theme.ts, lock.ts (PIN+biometría), confirm.ts, toast.ts
  /services/api.ts — todos los endpoints + cache SWR (TTL 30-60s)
  /public/sw.js — network-first + share target + web push handler
```

---

## Motor de conciliación (`services/conciliacion.py`)

Scoring por identidad:
  CUIT exacto (10-11 dígitos)          → 12 pts
  CBU/CVU exacto (22 dígitos)          → 10 pts
  Número de cuenta largo (10+ dígitos) →  8 pts
  Número de referencia (6-9 dígitos)   →  6 pts
  Titular (2 palabras)                 →  5 pts
  Titular (1 palabra)                  →  3 pts
  Bonus fecha cercana                  → +1 a +5 pts

Regla fundamental: monto duplicado en extracto → SIEMPRE exigir identidad.
Tolerancia fecha: 5 días · UM deduplicación: (orden, monto) o (fecha, monto, titular_norm)
Bancos soportados: Macro, BBVA, Santander, Galicia, ICBC y genérico.

IA Nivel 2: tabla `PatronAprendido` — aprende de correcciones manuales (2+ confirmaciones → aplica auto).

---

## Multi-tenant

- Organización A = `organizacion_id=1` (NUNCA modificar — solo cambios aditivos)
- Julieta es superadmin: ve y gestiona todas las orgs
- Config por org (JSON): match_rules, tolerancia_monto, dias_tolerancia_fecha, requiere_cierre_periodo

---

## Schedulers (APScheduler en proceso FastAPI)

- **03:00 ART** — backup completo JSON gzipeado por email (Resend). Activo si `RESEND_API_KEY` está seteada.
- **10:00 ART** — push alertas: cheques que vencen en ≤3 días + movimientos sin conciliar >7 días. Activo si `VAPID_PRIVATE_KEY` y `VAPID_PUBLIC_KEY` están seteadas.

---

## Web Push (VAPID)

Setup: `/perfil` → card "⚙️ Setup notificaciones push (admin)" → "Generar VAPID keys" → pegar en Render como `VAPID_PUBLIC_KEY` y `VAPID_PRIVATE_KEY` → Save and Deploy.
Usuarios se suscriben desde `/perfil` → "Activar notificaciones" (requiere PWA instalada en Android Chrome).
Test: botón "Enviar push de prueba" en la misma card de admin.

---

## Features implementadas (estado actual — v3.6)

- Conciliación bancaria multi-extracto con motor de scoring
- Carga masiva con auto-conciliar al subir planillas
- Export Excel contador + PDF cierre mensual + PDF estado de cuenta por cliente
- Búsqueda global ⌘K (clientes, planillas, movimientos, cheques)
- Token público de cliente — link sin auth por 7 días (`/p/:token`)
- Web push notifications — cron 10:00 ART
- Módulos: Cheques, Pagos/Gastos, Caja, Órdenes de Pago, Liquidaciones, Contabilidad
- Resumen ejecutivo mensual + Estado de cuenta por cliente + Flujo de caja
- Soft delete + papelera de reciclaje + reversión contable
- Backup diario por email + export JSON completo
- Recuperación de contraseña por email
- Bloqueo PIN + biometría (WebAuthn) + ConfirmDialog global
- Share target: recibir archivos desde WhatsApp/Galería
- **Aislamiento multi-org completo**: todos los reportes y módulos respetan org seleccionada
- **Aritmética exacta**: columnas financieras en `Numeric(12,2)` (migración 007); JSON encoder Decimal transparente
- **Validaciones Pydantic**: `monto > 0` en cheques y pagos/gastos; CUIT validado al crear cliente
- **Soft-delete hermético**: planillas eliminadas excluidas de stats, insights, liquidaciones y conciliaciones
- **Seguridad hardening**: `/auth/register` requiere superadmin; CORS con métodos/headers explícitos;
  `/contabilidad/stats` autenticado; libro mayor valida org; OP compartir valida org
- **Páginas legales**: `/privacidad` y `/terminos` públicas (Ley 25.326 Argentina)
- **Suite de tests**: 124 tests (29 nuevos en `test_audit_fixes.py`)
- **Storage S3/R2 con fallback**: `app/services/storage.py` sube fotos a S3-compatible si las env vars
  `S3_ENDPOINT/S3_BUCKET/S3_ACCESS_KEY/S3_SECRET_KEY/S3_PUBLIC_URL` están seteadas; si no, mantiene base64 en DB
- **Org isolation completa**: POST `/caja/op/registrar`, PUT `/caja/arqueo/hoy` y GET `/caja/op/exportar-eft`
  ahora aceptan `org_id` para que superadmin escriba/lea en la org seleccionada
- **Landing page pública** (`/`): hero, features, seguridad, FAQ, comparativa, pricing, contacto WhatsApp;
  Fraunces italic en títulos, menú hamburguesa mobile, secciones siempre visibles en mobile
- **Fix conciliación Decimal**: `parse_importe` y `montos_iguales` ahora soportan `Decimal` (SQLAlchemy
  Numeric); antes todas las filas salían "faltan datos" tras la migración 007
- **Plan de cuentas**: sub-cuenta `1-1-1-3-1 Banco Macro` bajo `1-1-1-3 Banco`; PLAN_PATCH idempotente
  agrega cuentas nuevas en cada deploy sin romper instalaciones existentes
- **Renumeración de movimientos**: al borrar un movimiento duplicado, el `orden` de los siguientes se
  decrementa automáticamente (-1 shift); `orden` es un contador secuencial global (NO es número del banco),
  el más alto = el más reciente. Import asigna `max_global + (n-i)`; UM merger continúa desde `max_orden`.
- **Boton Borrar UM**: en `/movimientos`, elimina el último lote UM y desvincula planillas afectadas
  (status queda "ok", `orden_movimiento_acreditado` queda NULL). Al re-subir el UM las planillas
  se re-concilian normalmente o el export usa fallback automático.
- **Export planilla robusto**: si una fila "ok" tiene el link al movimiento roto (FK NULL), el export
  busca el movimiento por monto + cliente en el extracto y rellena igual todas las columnas. Fallback
  a `row.fecha_acred` para la columna Fecha acred.
- **Comisión en liquidaciones**: al generar una liquidación se puede elegir 1.5% / 1.8% / 2% (presets)
  o ingresar un % manual. Si se deja vacío usa el default de la org (1.5%). Aplica a todos los clientes.
- **Comisión por cliente**: campo `porcentaje_comision` en modelo `Cliente` (migración 008, Numeric 5,4).
  Chip inline editable en `/clientes` — muestra `% —` (gris) o `2%` (ámbar). Prioridad al generar liq:
  override manual del form > % propio del cliente > default de la org.
- **Comisión por ítem (v3.5)**: `Planilla` y `Cheque` tienen su propio `porcentaje_comision` (Numeric 5,4).
  Safety net en `main.py` agrega ambas columnas con `ADD COLUMN IF NOT EXISTS`. Cadena de herencia:
  1. Al subir planilla → hereda `cliente.porcentaje_comision` automáticamente.
  2. Al conciliar → si la planilla no tiene %, hereda del cliente.
  3. Al crear cheque → selector de cliente pre-llena el % (editable antes de guardar).
  4. Liquidaciones calcula comisión ítem por ítem (pct propio → fallback del form → 0).
  5. Liquidaciones solo incluye TT (planillas). Cheques se gestionan en su módulo.
- **Renombrar y fusionar clientes**: `PUT /clientes/{id}/renombrar` cambia nombre y propaga a movimientos.
  `POST /clientes/{id}/fusionar` reasigna planillas+movimientos al cliente destino y elimina el origen.
  UI en `/clientes`: botones ✏️ y 🔀 visibles solo en desktop (`hidden md:inline-flex`).
- **Normalización nombres de clientes**: primera letra mayúscula; búsqueda `ilike` en crear cliente,
  subir planilla y caja — "green" y "Green" son el mismo cliente.
- **Fix botón ⬇️ Excel en Historial**: endpoint `/planillas/{id}/download` tenía NameError (`_` vs
  `current_user`) → 500 sin exportar. Corregido. Botón `📁 Exportar` en fila de planilla exporta el
  detalle completo (reemplazó el Excel global que era redundante).
- **Borrar liquidaciones borrador**: endpoint `DELETE /liquidaciones/{id}` + botón 🗑️ en `/liquidaciones`
  visible solo para estado "borrador". Permite re-generar con distinta comisión.
- **Fix liquidaciones período**: filtra por `PlanillaRow.fecha_acred` (no `fecha_carga`); fallback a
  `fecha_carga` cuando `fecha_acred` es NULL; maneja FK de movimiento roto o borrado.
- **Fix auditoria Decimal**: `registrar_log` fallaba con TypeError al guardar `Decimal` en JSON.
  `_serializable()` en `auditoria.py` convierte recursivamente Decimal→float antes de persistir.
- **Safety net startup**: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para `clientes.porcentaje_comision`,
  `planillas.porcentaje_comision` y `cheques.porcentaje_comision` — evita crashes si Alembic falla.
- **Responsive fixes**: Liquidaciones mobile — números usan `text-xs md:text-sm` + `truncate` + tabla
  con `overflow-x-auto`. Clientes mobile — botones ✏️/🔀 ocultos en mobile para que se vea el nombre.
- **Diseño unificado**: header/sidebar usan `bg-ml-blue` (Linear purple-blue #5E6AD2) en light mode
  en lugar del amarillo previo. `btn-yellow` también usa `bg-ml-blue` en light mode. Dark mode sin cambios.

### v3.6 — Contabilidad automática + Cuentas Corrientes (mayo 2026)

- **Asientos automáticos al importar UM**: Banco Macro (1-1-1-3-1) D / No identificado (2-1-1-1) H.
  Modo `agrupado` (un asiento por lote, default) o `individual` (uno por movimiento), elegible desde
  `/movimientos`. Config por org: `modo_asiento_um`. Al borrar lote UM → `reversar_asientos()` (deja
  asiento original + reverso, trazabilidad completa). En `services/motor_contable.py`.
- **Reclasificación al conciliar**: No identificado (2-1-1-1) D / Cliente X (2-1-2-X) H. Se dispara en
  `conciliar_planilla()` cuando `mov.source == "um"` y hay `cliente_id`. Modulo `um_reclass`.
- **Cuenta contable por cliente (1:1)**: `Cliente.cuenta_contable_id` (FK a `plan_cuentas`, safety net
  `ADD COLUMN IF NOT EXISTS`). `_get_o_crear_cuenta_cliente()` resuelve: cuenta vinculada → adopta por
  nombre bajo 2-1-2-0 → crea la próxima 2-1-2-X. NUNCA crea entidades Cliente desde movimientos.
- **Backfill de cuentas al arrancar**: vincula clientes existentes a cuentas por nombre normalizado
  (`unicodedata.normalize NFKD`); sin match claro → queda sin vincular (solo log). Idempotente. En `main.py`.
- **Módulo Contabilidad — tab 🔗 Clientes**: vinculación manual cliente↔cuenta. `GET /contabilidad/clientes-cuentas`,
  `PUT /contabilidad/clientes/{id}/cuenta` (409 si la cuenta ya está tomada — 1:1), `POST .../cuenta/crear`.
  Botón **"+ Crear cuentas faltantes"** → `POST /contabilidad/clientes/cuentas/crear-faltantes` crea/vincula
  la cuenta de todos los clientes sin cuenta (adopta por nombre, no duplica).
- **Cuentas Corrientes = MÓDULO PROPIO** (`/cuentas-corrientes`, permiso `manage_finance`, ícono banco en nav).
  Es el mismo componente `Contabilidad.tsx` con prop `modo="ctacte"`. Vista derivada de asientos (NO genera).
  Cartera global (`GET /contabilidad/cuentas-corrientes`: saldo, último mov, estado deudor/acreedor/equilibrado/
  sin_actividad) + detalle por cliente (`GET /contabilidad/cuenta-corriente`: timeline con filtros Banco/TT/
  Cheques/Ajustes, débito/crédito/saldo, links a planilla/movimiento). Botón "Cta. cte." en `/clientes`
  (ícono banco, deep-link `/cuentas-corrientes?cc=<id>`).
- **Backfill cuentas corrientes desde lo ya conciliado**: botón **"↻ Reconstruir desde conciliaciones"**
  en `/cuentas-corrientes` (solo `admin_accounting`). `POST /contabilidad/backfill-cuentas-corrientes`
  (soporta `?dry_run=true` para previsualizar conteo). Por cada fila de planilla conciliada (status ok)
  de un cliente con cuenta, genera asiento NETO **Banco Macro (D) / Cliente (H)** (modulo `cc_inicial`).
  Se eligió el neto Banco/Cliente para NO dejar "No identificado" en negativo. Idempotente: saltea filas
  con `um_reclass` (flujo normal) o `cc_inicial` previo. **ORDEN DE USO: 1) "+ Crear cuentas faltantes"
  → 2) "↻ Reconstruir desde conciliaciones".** El extracto solo dice que entró plata; la planilla
  conciliada identifica al cliente → por eso el backfill recorre conciliaciones, no el extracto crudo.
- **Permisos en 3 capas** (reemplaza el `view_accounting` monolítico):
  - `view_accounting` — lectura contable formal: Libro diario, Mayor, Sumas y saldo, Balance.
  - `manage_finance` — operación financiera diaria: Cuentas Corrientes.
  - `admin_accounting` — config estructural: Plan de cuentas, Reglas, vinculación cliente↔cuenta, backfill.
  - Mapeo: ADMIN = las 3 · OPERADOR = manage_finance + view_accounting · REVISOR = view_accounting ·
    AUDITOR = view_accounting + manage_finance. Definido en `store/auth.ts` y `middleware/auth.py`.
    Tabs de `/contabilidad` filtradas por permiso; guards `require_permission` en backend.
- **Borrar OP en Caja**: `DELETE /caja/op/{op_id}` (ícono 🗑️ por OP del día, deshabilitado si arqueo
  cerrado). Reversa el asiento `caja_op`, repone denominaciones físicas al arqueo y registra la baja.
- **Fix estado de cuenta Decimal×float**: `total_conciliado` (Numeric 12,2 = Decimal) se convertía a float
  antes de multiplicar por % comisión; sin eso lanzaba TypeError → 500 en clientes con filas conciliadas.
- **Mobile clientes**: se ocultó la flecha gris ▼ de desplegar (tocar el cliente ya despliega).
- **Landing**: FAQ dice "ARCA" en vez de "AFIP".
- **Modulos de asiento (referencia para cta.cte.)**: `um_lote`/`um_mov` (import UM), `um_reclass` (reclasif.),
  `cc_inicial` (backfill histórico Banco/Cliente), `planilla`/`planilla_comision` (TT), `cheque_carga`/
  `cheque_rechazo`, `pago`, `caja_op`/`caja_efectivo`, `*_reverso` (reversos). La cta.cte. del cliente lee
  los `AsientoDetalle` que tocan su `cuenta_contable_id`.

### v3.7 — Rol contador de prueba + login por aprobación (mayo 2026)

- **Rol `CONTADOR`** (RoleEnum backend + UserRole frontend): opera (sube, concilia, finanzas,
  liquidaciones) y ve contabilidad + auditoría en solo lectura. Permisos:
  `upload_files, reconcile, manage_finance, view_accounting, view_audit`. NO ve Usuarios/Orgs/
  Papelera/Actividad. El panel Actividad es cross-org de superadmin → queda fuera.
- **Permiso `delete_records`** (nuevo): solo ADMIN + OPERADOR (+ superadmin) lo tienen. Todos los
  DELETE destructivos pasaron a `require_permission("delete_records")`: cheques (+foto), caja OP,
  clientes, planillas/filas, extractos, movimientos, mov-UM, liquidaciones. pagos/gastos y purgar
  papelera ya eran admin/superadmin-only. El contador NO puede borrar nada (devuelve 403).
- **Liquidaciones**: nav/route pasó de `manage_users` a `reconcile` (el contador genera borradores;
  aprobar/pagar siguen siendo `manage_users`).
- **Login por aprobación en vivo (solo contador)**: el login NO devuelve token; crea un
  `LoginApproval` (tabla `login_approvals`, vía `create_all`) en estado `pending` (caduca a 10 min),
  notifica a los superadmins por push y devuelve 202 con `{approval_id, poll_secret}`. El cliente del
  contador hace polling a `GET /auth/login-approval/{id}?secret=` hasta recibir el token (1 sola vez).
  El superadmin aprueba/rechaza en `/aprobaciones` (`GET /auth/pending-approvals`, `POST
  .../decide`). Al aprobar se genera el JWT con **expiración de 4h** (`CONTADOR_SESSION_MINUTES`);
  pasadas las 4h expira y se repite la aprobación. `push_service.send_push_to_user()` nuevo.
  Robusto sin push: el panel `/aprobaciones` y el login del contador pollean igual.
- **Asignar organización al crear usuario** (superadmin): `PATCH /admin/users/{id}` acepta
  `organizacion_id`; selector de org en el alta de `/usuarios`. Para que los contadores de prueba
  operen en la **org de prueba** y NO en la Organización A (datos reales).
- **Perfil**: la card de setup VAPID ya estaba gateada por `is_superadmin` → el contador no ve datos
  de superadmin en `/perfil` (ve solo su propia cuenta + PIN/push).
- **Switch de org para contadores (`allowed_org_ids`)**: campo JSON en `User` con la lista de orgs
  extra a las que puede cambiar. `can_switch_org(user, org_id)` (en `middleware/auth.py`) reemplaza
  los chequeos `is_superadmin and org_id` en 9 routers (extractos, historial, clientes_dir, caja,
  auditoria, cheques, pagos_gastos, contabilidad, liquidaciones). `get_current_user` lee `?org_id=`
  del request y hace **override en memoria** (`db.expunge(user)` para NO persistir) si el ID está en
  la whitelist o es superadmin. `GET /me/allowed-orgs` lista las orgs disponibles; selector en el
  sidebar visible para contadores; multi-select de orgs al crear un CONTADOR en `/usuarios`.
  Safety net: `ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_org_ids JSONB DEFAULT '[]'`.
- **Fix email dominios reservados**: `UserRegister`/`UserLogin` dejaron de usar `EmailStr` (rechazaba
  `.test`, `.local`) y usan validación de formato básica → permite crear cuentas de prueba con mails
  inventados (`contador1@cuadra.test`). `ForgotPasswordRequest` mantiene `EmailStr` (manda mail real).
- **Fix crash React #31**: el interceptor de respuesta de axios (`services/api.ts`) normaliza el
  `detail` de errores 422 de Pydantic (array de objetos `{type, loc, msg, ...}`) a un string legible
  antes de llegar a los componentes. Evita "Objects are not valid as a React child" al renderizar
  `err.response.data.detail` (afectaba los 25 sitios con ese patrón).
- **Pendiente (UX)**: ocultar los botones de borrar en el frontend para quien no tiene
  `delete_records` (hoy el backend bloquea con 403, pero el botón sigue visible).

---

## Storage de fotos (S3/R2 opcional)

Por defecto las fotos de OPs y cheques se guardan como base64 en la DB. Para activar storage externo
(recomendado Cloudflare R2 — 10 GB gratis, S3-compatible), setear en Render:

```
S3_ENDPOINT     = https://<accountid>.r2.cloudflarestorage.com
S3_BUCKET       = conciliacion-fotos
S3_ACCESS_KEY   = <de R2>
S3_SECRET_KEY   = <de R2>
S3_PUBLIC_URL   = https://pub-xxxx.r2.dev   (o tu dominio custom apuntado al bucket)
S3_REGION       = auto                       (opcional, R2 acepta "auto")
```

Setup R2:
1. Crear cuenta en Cloudflare → R2 Object Storage
2. Crear bucket con visibilidad pública (o configurar dominio custom)
3. Crear API token con permisos Read/Write sobre el bucket
4. Pegar las 5 env vars en Render → Save and Deploy
5. Las OPs nuevas guardarán URL; las viejas siguen funcionando como base64 (compatibilidad transparente)

---

## Roadmap (por valor / esfuerzo)

1. **2FA para superadmin** — código por email al login (medio esfuerzo, alta seguridad)
2. **Google OAuth** — login con Google (medio esfuerzo, mejor UX)
3. **Rate limiting global** — slowapi en todos los endpoints, no solo auth
4. **Activar R2 en producción** — código ya está listo, solo crear bucket y pegar env vars
5. **IA Nivel 3** — predicción automática (requiere 3-6 meses de datos reales)
6. **App móvil nativa** React Native (alto esfuerzo, cuando la PWA se quede corta)

---

## CRÍTICO para Claude

**Autor de commits** (Vercel bloquea builds con otro author):
```
git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>" -m "..."
```

Si se olvida, fix con commit vacío:
```
git commit --allow-empty --author="Julieta Arrazate <julietaarrazate@gmail.com>" -m "trigger deploy"
```

**Rama de trabajo:** el harness asigna rama nueva (`claude/...`). Merge a `main` via PR squash.
**Keys/tokens:** NUNCA en este archivo. Están en Render, Vercel y GitHub de Julieta.
**Org A:** NUNCA modificar datos existentes — solo cambios aditivos.

Checkpoints disponibles:
- `v3.1-stable-checkpoint` — antes de las 5 features de mayo 2026
- `v3.2-stable-checkpoint` — después de seguridad hardening + Numeric migration + legal pages (mayo 2026)
- `v3.3-stable-checkpoint` — después de export robusto, comisiones, landing page, Borrar UM
- `v3.4-stable-checkpoint` — después de comisión por ítem, fusionar clientes, responsive fixes (mayo 2026)
- `v3.6` — contabilidad automática UM, cuentas corrientes como módulo propio, permisos en 3 capas,
  backfill de cuentas corrientes, borrar OP (mayo 2026 — PRs #36–#39 mergeados a main)
- `v3.7-stable-checkpoint` — rol CONTADOR + login por aprobación + PDF Cuadra + switch de org para
  contadores (allowed_org_ids) + fix email .test + fix crash React #31 (mayo 2026 — PRs #56-#58
  mergeados a main)

---

Proyecto iniciado Mayo 2026 · Autora: Julieta Arrazate · Versión actual: v3.7
