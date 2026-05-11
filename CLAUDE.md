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

API keys para deploy:
- Render API key: rnd_8Kqkb028Ochfw6eSOYZR3v2O7Cv2
- Render service ID: srv-d7pqt81j2pic73c0c6fg
- Vercel token: vcp_7WrBR4fh27c7GFUQXxsF4IhzCQbvigylOwnG7RtzUD2cuadbOL2lz0D9
- Vercel project ID: prj_cVINkspVm6j3B1fxOrdU81B0ehWg

Para push a GitHub:
  git push "https://julietaarrazate:TOKEN@github.com/julietaarrazate/conciliacion-bancaria.git" main

Para deploy manual de Render:
  curl -X POST https://api.render.com/v1/services/srv-d7pqt81j2pic73c0c6fg/deploys \
    -H "Authorization: Bearer rnd_8Kqkb028Ochfw6eSOYZR3v2O7Cv2"

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
                Liquidacion, LiquidacionDetalle, CierrePeriodo
  /app/routers — auth, me, extractos (incluye conciliaciones_router),
                 planillas, historial, auditoria, admin, clientes_dir,
                 organizaciones, liquidaciones, caja
  /app/services — conciliacion.py, aprendizaje.py, excel_export.py,
                  extracto_merger.py, excel_parser.py
  seed.py — Crea org Caneland + usuarios

/frontend — React 18 + TypeScript + Vite + TailwindCSS + PWA
  /src/pages — Dashboard, Clientes (jerarquia org→cliente→mes→archivos),
               Movimientos, Conciliaciones (cross-extracto), Historial, Bulk,
               Auditoria, Usuarios, Perfil, Login, Organizaciones,
               Liquidaciones, Caja, OrdenDePago, Revision, Actividad
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

- Contraseñas: pbkdf2_sha256
- JWT: 8 horas, sin refresh token
- Rate limiting: login 10/min, register 5/min por IP (slowapi)
- Headers de seguridad: X-Frame-Options, HSTS, XSS-Protection, etc.
- Auditoría completa de todas las operaciones
- Botón "Borrar todo" requiere escribir "BORRAR"
- SUPERADMIN_PASSWORD nunca en código — env var en Render

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

## Versión v2.1 — 2026-05-11 (snapshot estable)

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
