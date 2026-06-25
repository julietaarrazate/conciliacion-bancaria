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

Env vars opcionales en Render (feature flags — sin la var, la feature se degrada sola, no rompe):
`RESEND_API_KEY` backup diario + 2FA admin/superadmin · `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` push
· `GEMINI_API_KEY`(+`GEMINI_MODEL`) asistente IA/OCR/transcripción · `SENTRY_DSN` (Render) /
`VITE_SENTRY_DSN` (Vercel) monitoreo errores · `GOOGLE_CLIENT_ID` (Render) /
`VITE_GOOGLE_CLIENT_ID` (Vercel) login Google · `S3_*` (5 vars) storage fotos R2 ·
`ARCA_ENCRYPTION_KEY` ya seteada, módulo ARCA construido pero desactivado a propósito (ver
"Pendiente para próximas sesiones"). Stack: Python 3.11 / Node 20, Neon free tier (puede dormir),
Render free tier (cold start ~30s, mitigado con UptimeRobot + retry en frontend).

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

**Antes de tocar fechas, montos (Decimal), compartir por WhatsApp o detección de banco**: revisar
`BUGS.md` — son las áreas con bugs recurrentes documentados (causa raíz + cómo evitarlos).
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

## Estado actual y changelog

**Versión actual: v3.24.** Historial completo de versiones (v3.6 a v3.24, con detalle de cada
feature/fix/PR) en **`CHANGELOG.md`** — no se carga automáticamente en cada sesión, así que si
necesitás contexto histórico detallado de una versión puntual, leelo directamente.

Resumen muy breve de dónde está el sistema hoy: motor de conciliación + multi-banco (16 bancos) +
multi-tenant funcionando en producción; módulos operativos completos (Cheques, Pagos, Caja,
Liquidaciones, Contabilidad con cuentas corrientes); 4 módulos de liquidación de impuestos
(IVA, Monotributo, Ingresos Brutos, Sueldos/F931); asistente IA con OCR/voz/proactividad (Gemini);
ARCA (facturación electrónica WSFEv1) construido pero desactivado a propósito (ver "Pendiente para
próximas sesiones" abajo). 440 tests pasando.

---

### Pendiente para próximas sesiones

- **Próximos módulos del plan de liquidación de impuestos** (ver "Plan de expansión" abajo): orden a
  decidir con Julieta por valor — candidato: Intake Exportador de Servicios.
- **⏰ RECORDATORIO SEMESTRAL — actualizar escala de Monotributo**: ARCA actualiza los límites de
  facturación anual por categoría cada semestre (ajuste por IPC, próxima actualización
  julio/agosto 2026). Los valores sembrados en `monotributo_service.py` (`_LIMITES_VIGENTES`)
  vencen con esa actualización. Cuando se abra una sesión después de esa fecha: ir a
  arca.gob.ar/monotributo/categorias.asp (el fetch directo devuelve 403 por anti-bot — usar
  WebSearch cruzando 2-3 medios especializados como Ámbito/iProfesional, o pedirle el dato a
  Julieta) y actualizar la escala vía `PUT /monotributo/categorias/{id}` o re-sembrando el array.
- **Activación de ARCA en producción — diferida a pedido**: el módulo (`v3.24`) ya está mergeado y
  `ARCA_ENCRYPTION_KEY` ya está seteada en Render, pero Julieta decidió NO activarlo todavía — lo
  dejó listo "por si algún cliente lo solicita" más adelante. Falta, recién cuando haya un cliente
  real interesado en facturar electrónicamente desde Cuadra:
  1. Sacar el certificado de **homologación** en ARCA (gratis, sirve para probar sin validez
     fiscal) y probar el flujo completo en `/arca` antes de tocar producción.
  2. Cuando el cliente confirme que quiere usarlo en serio, gestionar en ARCA (Administrador de
     Relaciones de Clave Fiscal) el certificado de **producción** autorizado para el servicio
     **WSFEv1**, a nombre del CUIT que va a facturar.
  3. Subir ese certificado en `/arca` → tab Config (requiere `admin_accounting`), cambiar
     `ambiente` a `produccion` y recién ahí los CAE emitidos cuentan fiscalmente.
  **Importante**: una vez que se emite con ambiente producción, cada factura genera un CAE real
  ante ARCA (cuenta como IVA débito fiscal real, numeración correlativa sin posibilidad de
  resetear) — no es reversible ni para "probar". Cualquier prueba va siempre en homologación.

---

## Plan de expansión: módulos de liquidación de impuestos

Inspirado en un diagrama de agentes (Codex local) con dos managers: **Manager de Liquidación
Mensual** (IVA Proyección y DDJJ, Liquidador Sueldos y F931, Ingresos Brutos y Convenio
Multilateral) y **Manager Exportadores de Servicios** (Intake Exportador, Control Semestral
Monotributo). Decisión de Julieta: implementarlo de verdad en Cuadra (no quedarse en el diagrama),
mejor que Codex, como sistema robusto y escalable, e iterar módulo por módulo priorizando por valor.

**Patrón establecido**: cada módulo es opt-in/configurable por organización (no algo hardcodeado
para una sola org), sigue la estructura de Tarjetas/Cheques (modelo + service + router con permisos
en 3 capas + tests + página dedicada), y se delega a Opus para la lógica financiera compleja y a
Sonnet para el CRUD/UI del frontend, por el protocolo de orquestación ya documentado.

- **v3.19 — IVA Proyección y DDJJ** ✅ implementado (ver CHANGELOG.md). Primer módulo del plan.
- **v3.20 — Control Semestral Monotributo** ✅ implementado (ver CHANGELOG.md). Segundo módulo del plan.
- **v3.21 — Ingresos Brutos y Convenio Multilateral** ✅ implementado (ver CHANGELOG.md). Tercer módulo del plan.
- **v3.22 — Liquidador de Sueldos y F931** ✅ implementado (ver CHANGELOG.md). Cuarto módulo del plan.
- Pendientes a priorizar: Intake Exportador de Servicios.

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

1. **Activar R2 en producción** — código ya está listo, solo crear bucket y pegar env vars en Render
2. **IA Nivel 3** — predicción automática (requiere 3-6 meses de datos reales)
3. Ver "Pendiente para próximas sesiones" arriba para lo más reciente y concreto.

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

### Protocolo de orquestación ultracode (definido por Julieta, junio 2026)

El modelo orquestador (Fable) se reserva SOLO para: diseño y descomposición en tareas atómicas,
detección de dependencias (archivos compartidos → secuenciar), resolución de conflictos de merge
y auditoría de resultados cuando se requiera. Todo lo demás se delega para no gastar de más:
- **Opus** — implementación compleja (motor contable, parsers, migraciones, lógica financiera).
- **Sonnet** — implementación estándar (CRUD, UI, refactors mecánicos, tipado).
- **Haiku** — tareas simples (renombres, docs menores, búsquedas).

Reglas del bucle (cuanto más corta y verificable cada unidad, más robusto el bucle):
1. Unidad de trabajo atómica (~30-45 min por agente); módulos grandes se parten en 2-3 agentes.
2. Prompt por agente: reglas del repo destiladas (~5 líneas: author git, Decimal, safety nets,
   Org A) + tarea puntual + comando de verificación exacto. Sin contexto de más.
3. Commit por sub-paso, no al final — una muerte de sesión pierde minutos, no horas.
4. Mapear qué archivos toca cada tarea ANTES de paralelizar; si dos tocan el mismo, van en serie.
5. Orden de merge planificado de antemano (backend → frontend → splits/docs).
6. Criterio de terminado verificable en el prompt: pytest + tsc --noEmit + build.
7. Si un agente muere: auditar el worktree (`git log` + `git status`) y relanzar uno nuevo que
   continúe desde el estado exacto, con instrucción de no terminar sin pushear.

**Checkpoints/tags**: ver `CHANGELOG.md` → sección "Checkpoints / releases" para la lista completa
con descripción por versión. Son en su mayoría referencias documentales, no siempre tags físicos de
git — antes de un `git checkout vX.Y` correr `git tag` y confirmar que existe; tags reales hoy:
`v2.1`, `v2.2`, `v3.14-stable`, `v3.22`, `dnda-software-2026-v1`.

---

## Registro de Obra de Software (DNDA)

**Estado:** expediente preparado, trámite pendiente de inicio por la autora.

**Carpeta:** `REGISTRO_OBRA_SOFTWARE/` — documentación completa del expediente.

**Contenido preparado:**
- 9 PDFs legibles para el portal DNDA (en `/home/user/PDFS_DNDA/` en la máquina de trabajo)
- `CODIGO_FUENTE.zip` (596 KB, 241 archivos) — para el link de 72hs que envía DNDA
- Docs internos: DNDA_CHECKLIST_FINAL.md, DNDA_CAPTURAS.md, DNDA_PRIVACIDAD.md, DNDA_EXCLUSIONES.md

**Pasos que quedan para la autora:**
1. Crear `CAPTURAS.pdf` con las 27 capturas del sistema y agregarlo al portal
2. Iniciar el trámite en tramites.argentina.gob.ar → Inscripción de Obra Publicada — Software
3. Pagar $3.800 (trámite) + 0.2% del valor declarado → guardar comprobantes y subirlos al portal
4. Esperar mail de `dndadigital@jus.gov.ar` con link de 72hs para subir el código
5. Cifrar el ZIP con contraseña AES-256 (7-Zip en Windows) y subirlo por el link

**Privacidad del expediente:** sin datos de terceros, sin IDs de infraestructura, sin nombres
de empleadores. Rutas locales normalizadas a `~/Desktop`. Scripts de testing excluidos del ZIP.

---

Proyecto iniciado Mayo 2026 · Autora: Julieta Arrazate · Versión actual: v3.24
