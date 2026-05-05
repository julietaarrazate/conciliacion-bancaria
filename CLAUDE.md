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
- Vercel token: vcp_5vau9jj3k4E9Pn9yI3m4BMaWBWJSv5mNh3mU9Yd1mkHxbFmFub03rpK8
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
  /app/routers — auth, me, extractos, planillas, historial, auditoria,
                 admin, clientes_dir, organizaciones, liquidaciones
  /app/services — conciliacion.py, aprendizaje.py, excel_export.py,
                  extracto_merger.py, excel_parser.py
  seed.py — Crea org Caneland + usuarios

/frontend — React 18 + TypeScript + Vite + TailwindCSS + PWA
  /src/pages — Dashboard, Clientes, Movimientos, Historial, Bulk,
               Auditoria, Usuarios, Perfil, Login, Organizaciones,
               Liquidaciones
  /src/components — Layout (drawer mobile), PlanillaPanel, FileUpload
  /src/store — auth.ts, org.ts, theme.ts
  /src/services/api.ts — Todos los endpoints

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

---

## IMPORTANTE para Claude

- Todos los cambios van DIRECTO a GitHub. No hay nada en la PC local.
- Caneland NUNCA se modifica — todos los cambios son aditivos.
- El repo se clona en /tmp para trabajar y se limpia al terminar.
- Para deployar Render: usar curl con la API key arriba.
- El token de GitHub NO tiene scope "workflow" — no se pueden crear GitHub Actions.

Generado — Proyecto iniciado Mayo 2026 | Autora: Julieta Arrazate
