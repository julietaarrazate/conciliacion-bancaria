# Sistema de Conciliación Bancaria — Julieta Arrazate

## Para continuar en un nuevo chat

Decile a Claude: "Soy Julieta Arrazate. Proyecto: conciliacion-bancaria.
Lee el CLAUDE.md del repo julietaarrazate/conciliacion-bancaria para entender el contexto."

---

## Autora y Propietaria

**Julieta Arrazate** — Desarrolladora y propietaria intelectual.
Email: julietaarrazate@gmail.com (superadmin del sistema)

---

## Arquitectura de producción

- Frontend (React + PWA): Vercel — https://conciliacion-bancaria-ten.vercel.app
- Backend (FastAPI): Render — https://conciliacion-api.onrender.com
- Base de datos: Neon PostgreSQL — ep-ancient-hall-anz4pezn.c-6.us-east-1.aws.neon.tech
- Código: GitHub — julietaarrazate/conciliacion-bancaria
- Keep-alive: UptimeRobot pinguea /health cada 5 min

IDs publicos (no son secrets):
- Render service ID: srv-d7pqt81j2pic73c0c6fg
- Vercel project ID: prj_cVINkspVm6j3B1fxOrdU81B0ehWg

Tokens/keys: NO van en este archivo (repo es privado pero igual mala practica).
Julieta los maneja en su panel de cada servicio:
- Render API key: dashboard.render.com → Account Settings → API Keys
- Vercel token: vercel.com/account/tokens
- GitHub token: github.com/settings/tokens
- SUPERADMIN_PASSWORD: env var en Render service

Para push a GitHub (Julieta usa sus credenciales locales o el token guardado
en su entorno de trabajo, NO compartirlo aqui).

Para deploy manual de Render:
  curl -X POST https://api.render.com/v1/services/srv-d7pqt81j2pic73c0c6fg/deploys \
    -H "Authorization: Bearer <RENDER_API_KEY>"

---

## Credenciales

- Superadmin: julietaarrazate@gmail.com / ver SUPERADMIN_PASSWORD en Render env vars
- Admin demo: admin@julieta.com / admin123

---

## Stack técnico

Backend: FastAPI + SQLAlchemy + PostgreSQL (Neon) + Python 3.11
Frontend: React 18 + TypeScript + Vite + TailwindCSS + PWA (instalable)
Auth: JWT 8h, pbkdf2_sha256
Diseño: Linear-inspired, Inter font, dark mode profundo (#0B0B0F)

---

## Flujo de negocio

1. Julieta recibe extracto bancario mensual (Excel .xlsx Banco Macro)
2. Diariamente el contador envía "Últimos Movimientos" (UM) → se agregan sin duplicar
3. Los clientes (Green, Tucu, David, Smt, etc.) envían sus planillas de pagos
4. El sistema concilia: motor de match con scoring por CUIT/CBU/número/titular
5. Resultado: planilla con estado por fila + extracto actualizado
6. Se exporta para el contador (Excel profesional, formato Macro)

---

## Estructura del repositorio

/backend — FastAPI + SQLAlchemy + PostgreSQL
  /app/models — Organizacion, User, Cliente, ExtractoBancario, MovimientoBanco,
                Planilla, PlanillaRow, AuditoriaLog, PatronAprendido,
                Liquidacion, LiquidacionDetalle, CierrePeriodo,
                Cheque, Pago, Gasto, ArqueoDiario, OrdenDePago,
                PlanCuenta, ReglaContable, Asiento, AsientoDetalle
  /app/routers — auth, me, extractos (incluye conciliaciones_router),
                 planillas, historial, auditoria, admin, clientes_dir,
                 organizaciones, liquidaciones, caja, cheques,
                 pagos_gastos, contabilidad
  /app/services — conciliacion.py, aprendizaje.py, excel_export.py,
                  extracto_merger.py, excel_parser.py, motor_contable.py
  seed.py — Crea org Caneland + usuarios

/frontend — React 18 + TypeScript + Vite + TailwindCSS + PWA
  /src/pages — Dashboard (tabs: Individual + Carga masiva, campo Comisión%),
               Clientes (jerarquia org→cliente→mes→archivos),
               ExtractosArchivo (jerarquia año→mes→extracto),
               Movimientos, Conciliaciones (cross-extracto), Historial,
               Auditoria, Usuarios, Perfil, Login, Organizaciones,
               Liquidaciones, Caja (calendario diario + historial),
               OrdenDePago (foto+WhatsApp, sin denominaciones),
               Cheques, PagosGastos, Contabilidad,
               Revision, Actividad
  /src/components — Layout (drawer mobile), PlanillaPanel (editor estados +
                    bulk edit), FileUpload
  /src/store — auth.ts, org.ts, theme.ts
  /src/services/api.ts — Todos los endpoints
  /public/sw.js — Service worker manual (network-first, sin precache de
                  assets); index.html tiene watchdog que limpia caches viejos
                  si la app no monta en 8s (rescate PWA rotas)

---

## Motor de conciliación (services/conciliacion.py)

Sistema de scoring por identidad:
  CUIT exacto (10-11 dígitos)           → 12 puntos
  CBU/CVU exacto (22 dígitos)           → 10 puntos
  Número de cuenta largo (10+ dígitos)  →  8 puntos
  Número de referencia (6-9 dígitos)    →  6 puntos
  Titular (2 palabras)                  →  5 puntos
  Titular (1 palabra)                   →  3 puntos
  + bonus fecha cercana (progresivo)    → +1 a +5 puntos

Regla fundamental: si el monto aparece 2+ veces → SIEMPRE exigir identidad.
Solo acredita directo si el monto es único en el extracto.
Mensajes: "sin datos (N mov.)", "no coincide (N mov.)", "ambiguo"

Tolerancia fecha: 5 días (cubre feriados + fin de semana)
Bonus fecha: mismo día +5, 1-2 días +4, 3-4 días +3, 5-7 días +2

UM deduplicación: clave (orden, monto) o (fecha, monto, titular_normalizado)

---

## IA Nivel 2 — Aprendizaje de correcciones

Tabla PatronAprendido: guarda patrones extraídos de correcciones manuales.
Cuando el usuario cambia "sin datos" → "ok", el sistema extrae:
  - fragmento del titular del extracto
  - números clave de la planilla
Con 2+ confirmaciones, el sistema usa el patrón automáticamente en futuras conciliaciones.
Ver GET /auditoria/patrones y GET /auditoria/insights.

---

## Multi-tenant

- Caneland SA = organizacion_id=1 (nunca cambia)
- Julieta es superadmin: ve y gestiona todas las orgs
- Config de flujo por org (JSON): match_rules, tolerancia, estados, comisiones
- Switcher de org en el sidebar (solo superadmin)

Config Caneland (NO modificar):
  match_rules: ["monto_cuit"]
  tolerancia_monto: 0.01
  dias_tolerancia_fecha: 5
  requiere_cierre_periodo: false

---

## Módulo Liquidaciones

Para orgs con comisiones y cierre de período.
Flujo: Generar borrador → Aprobar → Marcar pagada
Excel 3 hojas: resumen ejecutivo, detalle por cliente, log revisiones.
POST /liquidaciones/periodos/cerrar valida EN_REVISION antes de cerrar.
Caneland: requiere_cierre_periodo: false — no le afecta.

---

## Seguridad

### Implementado
- Contraseñas: pbkdf2_sha256 (no reversible)
- JWT: 8 horas, sin refresh token
- Rate limiting: login 10/min, register 5/min por IP (slowapi)
- Headers de seguridad: X-Frame-Options, HSTS, XSS-Protection, Referrer-Policy
- CORS cerrado: solo dominio Vercel prod + previews + localhost dev
  (puede ampliarse con env var EXTRA_CORS_ORIGINS="https://otro.com,...")
- Auditoría completa de todas las operaciones (tabla auditoria)
- Botón "Borrar todo" requiere escribir "BORRAR"
- SUPERADMIN_PASSWORD nunca en código — env var en Render
- Repo GitHub PRIVADO
- HTTPS forzado (Vercel + Render + Neon Postgres SSL)
- Multi-tenant aislado por organizacion_id en todas las queries

### Cifrado de datos
- En transito: HTTPS/TLS 1.2+ (todas las capas)
- En reposo: Neon Postgres encripta el disco automaticamente
- A nivel aplicacion: NO se cifran campos individuales (titular, CUIT, monto)
  porque rompe el motor de conciliacion (no se puede ILIKE/filtrar campos
  cifrados). Es estandar para apps de conciliacion B2B.

### Pendientes de seguridad (roadmap)
- 2FA opcional para superadmin
- Tabla de JWT revocados (hoy un token comprometido vive 8hs)
- Bloqueo por inactividad / biometria en mobile (PWA reabre logueada)
- Procedimiento de rotacion de credenciales (que hacer si se compromete una key)
- Sanitizar logs (verificar que no escupan datos sensibles)
- Cron de backup automatico del JSON a S3/Drive (hoy es manual)

### Backup y recuperacion (ver BACKUP_Y_RECUPERACION.md en raiz)
- Snapshot manual de Neon antes de cambios grandes (2 min)
- Point-in-Time Recovery: 7 dias en plan gratuito
- Export JSON completo: GET /admin/organizaciones/{id}/backup-completo
- Export sistema completo: GET /admin/organizaciones/backup-completo-todo
- Procedimiento + plan de desastre documentados en BACKUP_Y_RECUPERACION.md

---

## Pendientes del roadmap

- Módulo OP (Órdenes de Pago) + Caja — requiere implementar Caja primero
- Google OAuth / login con Google
- PDF de conciliación mensual
- Soporte otros bancos (BBVA, Santander, Galicia)
- Panel de actividad por org
- IA Nivel 3 — predicción (requiere volumen de datos, 3-6 meses de uso)
- App móvil nativa (React Native) — elimina swipe Android

---

## Clientes configurados (Caneland)

Green, Tucu, David, Smt, Gwinn, Innova, Camparo, Alojando, Pinares, Paraguay
(la lista crece — se pueden crear nuevos desde la pantalla /clientes con el
botón "+ Nuevo cliente" de cada organización)

---

## Versión v2.7 — 2026-05-24 (Backup automatico diario por email)

Sin tag git. Agrega backup automatico sin tocar el flujo de la app.

### Scheduler interno (APScheduler)
- `backend/app/services/backup_scheduler.py`: BackgroundScheduler que
  corre dentro del mismo proceso de FastAPI. Cron diario a `03:00 ART`
  (configurable via `BACKUP_HOUR_ART`).
- Misfire grace de 1h: si el server estaba dormido al horario, igual
  lo ejecuta cuando despierta (siempre que sea dentro de la hora).
- max_instances=1 + coalesce=True: nunca se solapan dos backups.
- Render free tier se mantiene despierto con UptimeRobot, por lo que
  el cron dispara puntual.

### Envio por email (Resend)
- Generaa JSON completo (todas las orgs) usando `export_org_backup` ya existente
- Lo gzippea (queda en ~10-30% del tamano original)
- Lo manda como attachment a `BACKUP_EMAIL_TO` (default julietaarrazate@gmail.com)
- Usa Resend HTTP API (https://resend.com), free tier 3000 emails/mes,
  con remitente default `onboarding@resend.dev` (no requiere DNS).
- Email HTML con resumen de tablas y conteos.
- Si `RESEND_API_KEY` esta vacio, el scheduler simplemente no arranca
  (modo dev / opt-in, no crashea).

### Endpoints admin
- `GET /admin/backup/status` -> estado: activo, configurado, hora del cron,
  proximo run, ultimo intento/OK/error, tamano del ultimo backup.
- `POST /admin/backup/run-now` -> dispara backup manual on-demand (util
  para testear que llega el email sin esperar al cron).
- Ambos requieren superadmin.

### Auditoria
- Cada ejecucion queda registrada en la tabla auditoria con accion
  `BACKUP_AUTO_OK` o `BACKUP_AUTO_ERROR` y el detalle (tamano, orgs,
  destinatario o mensaje de error).
- El actor del log es el primer superadmin (Julieta).

### Frontend
- `/papelera` (admin) muestra una card arriba con:
  - Estado del scheduler (verde/amarillo)
  - Hora del cron, destinatario, proximo run
  - Ultimo OK con timestamp y tamano
  - Boton "Backup ahora" para disparar manualmente

### Setup en produccion
1. Crear cuenta en resend.com (gratis)
2. Generar API key (re_xxxxx)
3. En Render: env var `RESEND_API_KEY=re_xxxxx`
4. Save & deploy. Listo, anda solo.

### Por que email y no GitHub/S3
- Cero infraestructura nueva (solo 1 env var)
- Searchable y versionado por fecha en Gmail
- Si el sistema cae, Gmail sigue funcionando (canal independiente)
- Resend free tier ultrasobra (1 email/dia = 30/mes, hay 3000)
- Si el backup crece >20MB en el futuro, cambiamos a storage externo.

---

## Versión v2.6 — 2026-05-24 (Share Target — recibir archivos desde WhatsApp)

Tag git: pendiente. Agrega sobre v2.5 la capacidad de recibir archivos
compartidos desde otras apps (WhatsApp, Galeria, Drive) directamente en la PWA.

### Share Target API (Web Manifest + Service Worker)
- `manifest.webmanifest`: nuevo bloque `share_target` apuntando a `/compartir`
  via POST multipart/form-data. Acepta `image/*`, `application/pdf`, `.jpg`,
  `.jpeg`, `.png`, `.webp`, `.heic`. La PWA aparece como destino en el
  menu "Compartir" del SO (Android Chrome).
- `sw.js`: intercepta POST a `/compartir`, guarda los archivos en una Cache
  llamada `conciliacion-share-inbox` con keys `/__share__/file-N` y un
  `/__share__/meta` con metadatos (nombres, tipos, sizes). Despues redirige
  con 303 a `/compartir?source=share`. Tambien sirve esa cache para GET.
- El activate del SW preserva la share-inbox (no la borra junto a las viejas).
- CACHE_NAME bumpeado a `conciliacion-shell-v4` para forzar reinstall.

### Pagina /compartir
- Nueva ruta `/compartir` (no requiere permiso especial, la usuaria ya esta
  logueada en la PWA).
- Al montarse, lee `/__share__/meta` y descarga los blobs. Convierte cada uno
  a base64 dataUrl para mostrar preview (imagenes) o icono (PDF).
- Botones para enrutar el archivo al modulo correcto:
  - **Cheque** -> `/cheques?compartido=1` (abre modal de nuevo cheque con la foto cargada)
  - **Pago** -> `/pagos-gastos?compartido=pago` (abre tab Pagos)
  - **Gasto** -> `/pagos-gastos?compartido=gasto` (abre tab Gastos)
  - **OP** -> `/op?compartido=1` (salta al paso "datos" con la foto cargada)
- Los archivos viajan por `sessionStorage` (`compartido:archivos` como JSON con
  dataUrls). Cada destino los lee, precarga el form y limpia el sessionStorage.

### Integracion en modulos destino
- `Cheques.tsx`: detecta `?compartido=1`, abre el modal "Nuevo cheque" con
  `formFoto` precargada. Limpia el query param para no re-disparar al recargar.
- `OrdenDePago.tsx`: detecta `?compartido=1`, salta al step `datos` con
  `foto` y `fotoPreview` ya seteados.
- `PagosGastos.tsx`: selecciona el tab (pagos/gastos) segun el query param.

### Limitaciones
- Funciona en Android (Chrome y Edge instalados como PWA). iOS Safari NO
  soporta Web Share Target para archivos en PWAs (limitacion de Apple).
- Requiere instalar la PWA: si la usuaria solo usa el browser, no aparece
  como destino de "Compartir". Para que aparezca tiene que tocar "Agregar a
  pantalla de inicio" la primera vez.

---

## Versión v2.5 — 2026-05-24 (hardening: seguridad, observabilidad, recovery)

Sin tag git aun. Agrega sobre v2.4 una capa completa de robustez productiva,
sin cambios funcionales para el usuario final (todo bajo el capot).

### Seguridad
- Mensajes de error genericos al usuario: ya no se expone `str(e)` con paths
  internos, stack traces o nombres de librerias. El error real va a logs.
- SECRET_KEY validada al boot: si esta en el valor por defecto en produccion,
  log critico avisando al admin (Render ya tenia env var seteada).
- Usuario demo `admin@julieta.com/admin123` solo se crea con DEBUG=true.
  Antes se sembraba en cada deploy de produccion.
- Validacion de tamaño de archivo antes de leerlo a memoria (50 MB max).
  Previene DoS por upload de archivo gigante.

### Alembic — migraciones versionadas de DB
- `backend/alembic.ini` + `backend/alembic/env.py` con `DATABASE_URL` del entorno.
- Auto-stamp on first boot: si la DB no tiene `alembic_version` la sella como
  baseline v001 sin ejecutar SQL. Si ya esta, aplica las migraciones pendientes.
- Migraciones aplicadas:
  - `001_baseline.py`: vacia, representa el estado al incorporar Alembic
  - `002_soft_delete.py`: agrega `deleted_at` a extractos_bancarios y planillas
- Los `ALTER TABLE` viejos de `main.py` se mantienen como red de seguridad
  (idempotentes con try/except). Limpiarlos cuando se valide 100% Alembic.

### Logging estructurado (reemplaza 56 print())
- `backend/app/logging_config.py`: setup central con niveles INFO/WARNING/ERROR.
- Cada modulo usa `logger = logging.getLogger(__name__)`.
- Formato: `2026-05-24 12:34:56 [LEVEL] app.routers.extractos: mensaje`
- Permite filtrar por nivel y modulo en Render logs.
- PYTHONUNBUFFERED=1 en render.yaml para que los logs salgan al instante.

### Performance — N+1 queries eliminados
- `joinedload(usuario)` en `/auditoria` (antes 1 query por log).
- `joinedload(cliente) + selectinload(rows)` en `/auditoria/insights`.
- `joinedload + selectinload` en backup de organizaciones.
- `selectinload(rows)` en panel actividad por org.
- Impacto: `/admin/organizaciones/{id}/backup` paso de ~200 queries a 3 con 50 planillas.

### Backup completo en JSON (ver BACKUP_Y_RECUPERACION.md)
- Servicio `backend/app/services/backup_service.py`: `export_org_backup(db, org_id)`
  devuelve dict con TODAS las tablas (extractos+movs, planillas+rows, cheques,
  pagos, gastos, caja+OPs, liquidaciones, contabilidad+lineas, patrones IA,
  auditoria ultimos 50k logs).
- NUNCA exporta `hashed_password` (verificado por test).
- Aislamiento por organizacion_id.
- Endpoints:
  - `GET /admin/organizaciones/{id}/backup-completo` -> JSON por org
  - `GET /admin/organizaciones/backup-completo-todo` -> JSON con todas las orgs
- Doc `BACKUP_Y_RECUPERACION.md` en raiz: 4 tipos de backup, procedimientos,
  comandos curl, calendario, plan de desastre.

### Soft delete (papelera de reciclaje)
- Columna `deleted_at` en `extractos_bancarios` y `planillas` (via Alembic 002).
- DELETE /extractos/{id} y DELETE /planillas/{id} ahora hacen soft delete:
  marcan `deleted_at = now()` pero conservan datos y relaciones.
- Listados (GET /extractos, /historial) filtran `deleted_at IS NULL`.
- Nuevo router `/admin/papelera`:
  - `GET /admin/papelera` -> lista borrados agrupados por tipo
  - `POST /admin/papelera/restaurar/{tipo}/{id}` -> quita deleted_at
  - `DELETE /admin/papelera/purgar/{tipo}/{id}?confirmar=BORRAR` -> borrado definitivo
- Pagina frontend `/papelera` (permission manage_users) con tabla, restaurar
  y purgar (pide escribir 'BORRAR' como confirmacion).

### Reversion contable (preserva trazabilidad al borrar)
- Nueva funcion `motor_contable.reversar_asientos(modulo, ref_id, org_id, ...)`:
  crea asiento con debe<->haber invertidos y modulo `{original}_reverso`.
  NO borra el original — ambos quedan en el libro para auditoria.
- Idempotente: si ya existe un reverso para ese asiento, no crea otro.
- Conectado a:
  - DELETE /pagos/{id} -> reversa modulo 'pago'
  - DELETE /gastos/{id} -> reversa modulo 'gasto'
  - DELETE /cheques/{id} -> reversa 'cheque_carga' y 'cheque_comision'
  - POST /admin/papelera/purgar/extracto -> reversa 'extracto'
  - POST /admin/papelera/purgar/planilla -> reversa 'planilla' y 'planilla_comision'
- Trazabilidad: descripcion del reverso dice quien lo elimino y por que.

### Testing — 49 tests cubriendo logica financiera critica
- `tests/test_motor_contable.py` (22 tests):
  happy path, idempotencia, regla faltante, monto cero/negativo, comisiones,
  re-conciliacion (solo_pendientes), upsert efectivo, invariante de partida
  doble en todo asiento, reversion (6 tests).
- `tests/test_conciliacion.py` (9 tests, reescrito):
  parseo importes, normalizacion CUIT/CBU, matching monto unico, regla
  critica de monto duplicado con/sin identidad, deduplicacion.
- `tests/test_backup_service.py` (10 tests):
  contenido completo, NUNCA exporta passwords (verificacion paranoica),
  serializable a JSON, estructura anidada correcta, aislamiento multi-tenant.
- `tests/test_soft_delete.py` (8 tests):
  marca deleted_at, queries filtradas, restauracion, ciclo completo sin
  perdida de datos.
- `backend/requirements-dev.txt` separa pytest de prod (no se instala en Render).

### Mobile UX
- Fix de seleccion de texto al tocar UI: `body { user-select: none }` con
  excepciones para input, textarea, td, .monto, code, pre, .selectable.
- Long-press en cards/botones ya no abre menu copy ni resalta texto.
- Sigue funcionando seleccionar montos en tablas e inputs editables.
- `-webkit-tap-highlight-color: transparent` quita el flash gris azulado.

---

## Versión v2.4 — 2026-05-23 (snapshot estable)

Tag git: v2.4 · agrega sobre v2.3:

### Módulo Cheques
- CRUD completo: GET/POST /cheques, PATCH /cheques/{id}, DELETE /cheques/{id}
- Flujos: POST /cheques/{id}/acreditar y /rechazar
- Foto comprobante: POST/GET/DELETE /cheques/{id}/foto (base64, compresión canvas)
- Importación masiva: POST /cheques/importar (Excel flexible, mapeo de columnas)
- Motor contable: carga_cheque, acred_rechazo_banco, acred_rechazo_pasivo, carga_cheque_comision
- Página /cheques: tabla con filtros, stats, paginación, visor de foto, import Excel

### Módulo Pagos y Gastos
- GET/POST /pagos, PATCH /pagos/{id} (admin+), DELETE /pagos/{id} (admin+)
- GET/POST /gastos, PATCH /gastos/{id} (admin+), DELETE /gastos/{id} (admin+)
- Motor contable: pago_cliente_banco/efectivo, asig_gasto_banco/efectivo
- Página /pagos-gastos: tabs Pagos/Gastos, modal crear+editar, botones ✏✕ solo para admin/superadmin
- Modo claro/oscuro: todos los colores usan pares light/dark (white/5 → bg-white dark:bg-white/5)

### Módulo Caja — calendario diario
- Arqueo guardado por día (no se borra), historial 60 días navegable
- Header de fecha en 2 filas: flechas + fecha corta en mobile, larga en desktop
- Panel historial: click en fila navega al día, dot verde/rojo = cruce
- OP de proveedor ahora genera asiento: Gastos(D) / Efectivo(H) via asig_gasto_efectivo
- Pesos_agregados genera asiento: Efectivo(D) / Banco(H) via carga_efectivo (upsert)
- Denominaciones eliminadas del form de OP — solo se registran en el arqueo manual

### Módulo Contabilidad (Fase 1+2)
- 4 tablas: plan_cuentas (24 nodos), reglas_contables (12 reglas), asientos, asiento_detalle
- Motor contable conectado a TODOS los módulos: extractos, planillas, cheques, pagos, gastos, OPs, efectivo
- Reglas sembradas: carga_extracto, carga_planilla, carga_planilla_comision, carga_efectivo,
  carga_cheque, carga_cheque_comision, acred_rechazo_banco, acred_rechazo_pasivo,
  pago_cliente_banco, pago_cliente_efectivo, asig_gasto_banco, asig_gasto_efectivo
- Comisión de planilla: campo "Comisión %" en Dashboard → genera asiento carga_planilla_comision
- Reportes: GET /contabilidad/sumas-saldo, /balance, /libro-mayor
- Página /contabilidad: 6 tabs en grid 3×2 — Plan de cuentas, Reglas, Libro diario (fila 1) /
  Sumas y saldo, Balance, Libro mayor (fila 2)

### Fixes de zona horaria
- Todos los exports Excel y fecha_acred usan ZoneInfo('America/Argentina/Buenos_Aires')
- Reemplazado datetime.utcnow() por datetime.now(_ARG) en planillas, extractos, excel_export

---

## Versión v2.3 — 2026-05-22 (snapshot estable)

Tag git: v2.3 · agrega sobre v2.2:

### Exportacion y conciliacion mejoradas
- Fix export extracto (sort None-safe en fechas, ya no falla silenciosamente)
- Re-conciliar planillas desde Historial: boton "Reonciliar", elige fecha
  (Hoy / Ayer / custom), solo re-procesa filas no acreditadas (solo_pendientes)
- Bidireccional extracto ↔ planilla: acreditar un movimiento desde la vista
  Movimientos actualiza la fila correspondiente en la planilla del cliente
  y viceversa, todo en el mismo db.commit()

### Vista Movimientos mejorada
- Editar/quitar acreditaciones directas desde la tabla de movimientos
  (click en cliente o fecha para abrir modal de acreditacion)
- Filtro importe: detecta formato automaticamente (punto decimal, coma decimal,
  separador de miles) y filtra exacto, no rango
- Modales (editar movimiento + acreditar) siempre visibles — fix Fragment JSX
- Delete extracto: bulk SQL en lugar de loop ORM (1800+ rows en <1s)

### PlanillaPanel — Ver / Editar
- Fix panel en blanco: detalle endpoint ya no crashea si el extracto fue borrado
  (maneja null con fallbacks en extracto_nombre, cliente_nombre, usuario_nombre)
- Fecha acred. en filas OK: ahora muestra row.fecha_acred como fallback cuando
  el movimiento vinculado no tiene fecha_acred propio
- Error visible si la carga falla (antes era pantalla en blanco sin aviso)

### Carpeta de extractos
- Nueva pagina /extractos-archivo: jerarquia año → mes → extracto, colapsable
  igual que /clientes. Muestra movimientos totales y % acreditados.
  Boton "Ver" lleva a /movimientos?extracto=ID, boton ".xlsx" descarga directo.

### Carga masiva integrada al Conciliar
- "Bulk" eliminado del menu, integrado como tab "📂 Carga masiva" en /dashboard
- Tab "📄 Individual" conserva el flujo de 3 pasos existente
- Carga masiva comparte el extracto activo seleccionado

### Confirmacion de borrado corregida
- Dialogo de borrar extracto ya no dice que borra planillas (no las borra, solo
  desvincula los movimientos)

## Versión v2.2 — 2026-05-11 (snapshot estable)

Tag git: v2.2 · agrega sobre v2.1:
- Acreditacion manual desde comprobante (Cuenta DNI / Mercado Pago / foto):
  endpoint POST /clientes/{id}/buscar-movimiento con campos opcionales
  (importe, fecha, referencia, origen — al menos 1) + POST
  /clientes/movimientos/{id}/acreditar que ademas crea una Planilla manual
  con 1 fila para que aparezca en la carpeta del cliente del mes.
- Modal "💸 Acreditar" en cada cliente de /clientes con campo separado
  "Fecha de acreditacion" (default hoy, editable).
- Borrado de cliente desde /clientes (boton 🗑): valida planillas y pide
  force=true. Limpia cliente_acreditado en movimientos asociados.
- Tabla en Movimientos y Conciliaciones con pl-1 (arrima al margen izq).
- Exports Excel con altura de fila = 15 (alto 15 estandar Excel, ~25px).
- Descarga planilla: nombre "{cliente} acreditado {d.m}.xlsx".
- CRITICO documentado: commits deben tener author Julieta para pasar
  Vercel seatBlock COMMIT_AUTHOR_REQUIRED.

## Versión v2.1 — 2026-05-11

Tag git: v2.1 · commits clave: a642a5f, 1eb419f, fae2c18, 51cef80, 1488c8a, b7796207

Cambios incorporados en esta versión:

### Parser de extracto
- Lee las columnas "Cliente acreditado" y "Fecha acred." que vienen en el Excel
- Al re-subir el mismo extracto (mismo fingerprint), upsertea acreditaciones en
  vez de tirar 409: se actualiza con los datos nuevos sin perder los viejos
- Normaliza el campo "mes" a numero (1-12), no "Mayo 2026"

### Merger UM
- Match por (saldo, monto) con tolerancia 0.01 (cubre redondeos de float)
- Asigna ordenes secuenciales: el mas nuevo del UM recibe max_orden + n,
  el mas viejo de los nuevos recibe max_orden + 1
- Detecta el corte automaticamente buscando el saldo del top del extracto
  en el UM, ignora desde ahi para abajo
- Migracion al boot que normaliza "mes" en movimientos viejos via SQL

### Conciliaciones cross-extracto (nuevo)
- Endpoint GET /conciliaciones lista TODAS las acreditaciones de TODOS los
  extractos. Filtros: cliente, titular, rango fecha, rango monto
- Endpoint GET /conciliaciones/export genera Excel con los filtros aplicados
- Pagina /conciliaciones en el frontend con autocomplete de cliente, debounce
  800ms y suma total acumulada

### Clientes con jerarquia
- GET /clientes/archivos devuelve organizaciones → clientes → año/mes → archivos
- Compatibilidad legacy: devuelve tambien { clientes: [...] } plano para SW
  cacheados viejos
- POST /clientes crea cliente nuevo (dedup case-insensitive por org)
- Pagina /clientes con 4 niveles desplegables y boton "+ Nuevo cliente"
- "Caneland SA" siempre visible como carpeta raiz

### Editor de estados
- Boton "Revisar y editar estados" en Dashboard despues de conciliar
- PlanillaPanel: edicion por fila + bulk edit (cambia estado a multiples filas
  seleccionadas con checkbox)
- Cada correccion alimenta PatronAprendido (IA Nivel 2)

### Exports Excel — filas 15px
- Altura fija 11.25pt (~15px) y wrap_text=False en todas las filas de datos
- Aplicado en export_movimientos, export_extracto_contador, export_conciliaciones

### Vista en pantalla — filas 15px
- Clase .row-15 con CSS plano (height:15px + py:0 + leading:13px + text:11px)
  con !important para ganar a la herencia de text-xs del table
- Debounce de filtros: 400ms → 800ms (mas tiempo para escribir)
- Columna "Mes" muestra solo el numero, derivado de la fecha

### Mobile / PWA
- Service worker reescrito: network-first puro, sin precache de assets
- Sacado vite-plugin-pwa (causaba conflictos con el SW manual)
- Eliminado manifest.json duplicado
- Watchdog en index.html: si la app no monta en 8s, hace unregister del SW +
  clear caches + reload (rescata PWAs viejas con cache roto)
- accept="*/*" en file inputs (Android no muestra .xls/.xlsx en algunos cels)

---

## IMPORTANTE para Claude

- Todos los cambios van DIRECTO a GitHub. No hay nada en la PC local.
- Caneland NUNCA se modifica — todos los cambios son aditivos.
- El repo se clona en /tmp para trabajar y se limpia al terminar.
- Para deployar Render: usar curl con la API key arriba.
- El token de GitHub NO tiene scope "workflow" — no se pueden crear GitHub Actions.

### CRITICO — autor de commits para Vercel

Vercel tiene activado **seatBlock COMMIT_AUTHOR_REQUIRED**: bloquea el build
si el autor del commit NO es julietaarrazate@gmail.com (el dueño de la cuenta).
Resultado: los pushes con otro autor pasan a GitHub pero Vercel los marca
ERROR y sigue sirviendo el frontend viejo.

**SOLUCION OBLIGATORIA** — todos los commits deben llevar:

  git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>" -m "..."

Si te olvidas y ya commitaste con otro author, un commit vacio extra arregla:

  git commit --allow-empty --author="Julieta Arrazate <julietaarrazate@gmail.com>" -m "trigger deploy"

(Vercel deploya el HEAD; si el HEAD tiene el author correcto pasa el seat check.)

Para desactivarlo de raiz: Vercel Dashboard → Settings → Spend Management →
desactivar "Require commit author authorization".

Generado — Proyecto iniciado Mayo 2026 | Autora: Julieta Arrazate
