# Sistema de Conciliacion Bancaria — Julieta Arrazate

## Autora y Propietaria

**Julieta Arrazate** — Desarrolladora y propietaria intelectual de este sistema.
Email: julietaarrazate@gmail.com

---

## Que es esto

Sistema web + app movil para conciliar transferencias bancarias contra planillas de clientes.
Multi-tenant: cada empresa tiene datos aislados. Julieta es superadmin con acceso a todo.
Empresa cliente actual: **Caneland SA** (organizacion_id=1).

---

## Arquitectura de produccion (100% gratuita)

- Frontend (React + PWA): Vercel — https://conciliacion-bancaria-ten.vercel.app
- Backend (FastAPI): Render — https://conciliacion-api.onrender.com
- Base de datos: Neon PostgreSQL — ep-ancient-hall-anz4pezn.c-6.us-east-1.aws.neon.tech
- Codigo: GitHub — julietaarrazate/conciliacion-bancaria

Render free tier: duerme tras 15 min sin uso. Primera request del dia tarda ~30 seg.

---

## Credenciales de produccion

- Superadmin: julietaarrazate@gmail.com / password definido via env var SUPERADMIN_PASSWORD en Render
- Admin demo: admin@caneland.com / admin123
- Operador demo: operador@caneland.com / operador123

IMPORTANTE: Antes del primer deploy, definir en Render la variable de entorno:
  SUPERADMIN_PASSWORD=tu_contraseña_segura

API keys para deploy desde Claude Code:
- Render API key: rnd_8Kqkb028Ochfw6eSOYZR3v2O7Cv2
- Vercel token: vcp_5vau9jj3k4E9Pn9yI3m4BMaWBWJSv5mNh3mU9Yd1mkHxbFmFub03rpK8
- Vercel project ID: prj_cVINkspVm6j3B1fxOrdU81B0ehWg
- Render service ID: srv-d7pqt81j2pic73c0c6fg

---

## Flujo de negocio

1. Julieta recibe el extracto bancario del mes (Excel .xlsx de Banco Macro)
2. Diariamente el contador envia "Ultimos Movimientos" (UM) -> se agregan al extracto
3. Los clientes (Green, Tucu, Alojando, etc.) envian sus planillas de pagos
4. El sistema concilia: busca cada monto de la planilla en el extracto
5. Si hay match -> acredita (guarda nombre cliente + fecha)
6. Resultado: planilla con columna Estado + extracto actualizado
7. Se descarga y guarda en: Desktop/clientes/{Cliente}/{Anio}/{Mes}/

---

## Estructura del repositorio

/backend — FastAPI + SQLAlchemy + PostgreSQL
  /app/models — Organizacion, User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog
  /app/routers — auth, me, extractos, planillas, historial, auditoria, admin, clientes_dir, organizaciones
  /app/services — conciliacion.py (configurable por org), excel_parser, excel_export, extracto_merger
  seed.py — Crea org Caneland + usuarios iniciales
  requirements.txt

/frontend — React 18 + TypeScript + Vite + TailwindCSS + PWA
  /src/pages — Dashboard, Clientes, Movimientos, Historial, Bulk, Auditoria, Usuarios, Perfil, Login
  /src/components — Layout, PlanillaPanel, FileUpload, ThemeToggle
  /src/services/api.ts — Todos los endpoints

---

## Multi-tenant (implementado en v2.0)

- Model Organizacion: id, nombre, plan (basic/pro), configuracion (JSON), activo
- Caneland SA es organizacion_id=1 (no cambia nada en su operatoria)
- Nuevos clientes usan su propio organizacion_id
- Julieta (julietaarrazate@gmail.com) es superadmin: ve y gestiona todas las orgs
- Usuarios normales solo ven su organizacion_id

### Configuracion de flujo por org (JSON)
```json
{
  "match_rules": ["referencia", "monto_cuit", "monto_fecha"],
  "tolerancia_monto": 0.01,
  "dias_tolerancia_fecha": 3,
  "estados_habilitados": ["pendiente", "conciliado", "parcial", "vencido", "en_revision"],
  "requiere_cierre_periodo": false,
  "notificaciones_whatsapp": false,
  "exportar_formato_contador": "excel_actual"
}
```

### Caneland SA config (no modificar)
```json
{
  "match_rules": ["monto_cuit"],
  "tolerancia_monto": 0.01,
  "dias_tolerancia_fecha": 0,
  "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
  "requiere_cierre_periodo": false
}
```

---

## Algoritmo de conciliacion (services/conciliacion.py)

Para cada fila de la planilla del cliente:
1. Si org tiene "referencia" en match_rules: buscar por referencia en titular del extracto
2. Buscar movimientos con monto == monto_planilla (tolerancia configurable)
3. Si monto aparece < 3 veces -> acreditar al primer libre
4. Si monto aparece >= 3 veces -> requiere CUIT o titular
5. Si org tiene EN_REVISION habilitado: marcar como EN_REVISION en vez de "faltan datos"

Caneland sigue usando: monto + CUIT (algoritmo original sin cambios).

---

## Estados de conciliacion

### Base (Caneland y todas las orgs)
- ok / no está / duplicado / faltan datos / acreditado DD/MM / pendiente

### Ricos (solo orgs con estados_habilitados extendidos)
- PAGO_PARCIAL
- CONCILIADO_CON_DIFERENCIA
- VENCIDO
- EN_REVISION

---

## Cola de revision manual

Para orgs con requiere_cierre_periodo: true:
- GET  /planillas/{id}/revision              — lista EN_REVISION
- POST /planillas/{id}/revision/{row_id}/resolver  — resuelve con {accion, comentario}
  acciones: aprobar, rechazar, pago_parcial, diferencia, vencido

---

## Admin endpoints (solo superadmin)

- GET  /admin/organizaciones        — lista todas
- POST /admin/organizaciones        — crea nueva
- PUT  /admin/organizaciones/{id}   — actualiza config de flujo

---

## Features implementadas

Backend v2.0:
- Auth JWT 8h con pbkdf2_sha256
- Roles: admin, operador, revisor, auditor + superadmin
- Multi-tenant completo con Organizacion model
- Flujo personalizable por org via JSON config
- Estados ricos de conciliacion (opt-in por org)
- Cola de revision manual (opt-in)
- Match configurable: referencia / monto+cuit / monto+fecha
- Endpoints admin de organizaciones
- Extracto bancario: upload, listar, filtrar, exportar, borrar
- Ultimos Movimientos (UM): agregar sin duplicar
- Planillas: upload, conciliar, detalle, download, borrar
- Historial agrupado por cliente/mes
- Auditoria automatica
- Gestion de usuarios
- Migraciones aditivas sin borrar datos

Frontend:
- PWA instalable (Android + iOS)
- Dashboard con KPIs + conciliaciones recientes
- Seccion Clientes: arbol Anio -> Mes -> archivos
- Movimientos con filtros Excel inline
- Dark mode persistido
- Layout responsive

---

## Pendientes / Roadmap

Alta prioridad:
- Login con Google (OAuth2) — pendiente implementacion frontend + backend
- Autenticacion biometrica (huella dactilar) — para app movil, fase futura
- Keep-alive de Render (ping cada 14 min)
- Exportar extracto actualizado al contador al final del dia

Media prioridad:
- Notificaciones WhatsApp cuando Render se despierta
- Multiples formatos de extracto (otros bancos)
- PDF de conciliacion mensual
- App movil React Native

---

## Para continuar en un nuevo chat

Decirle a Claude: "Soy Julieta Arrazate. Continuamos el proyecto de conciliacion bancaria.
Lee el CLAUDE.md del repo julietaarrazate/conciliacion-bancaria para entender el contexto."

Comandos de deploy (Python):
  Vercel: POST https://api.vercel.com/v13/deployments con gitSource github/julietaarrazate
  Render: POST https://api.render.com/v1/services/srv-d7pqt81j2pic73c0c6fg/deploys

Para push a GitHub:
  git push "https://julietaarrazate:TOKEN@github.com/julietaarrazate/conciliacion-bancaria.git" main

---

## Clientes configurados (Caneland)

Green, Tucu, David, Smt, Gwinn, Innova, Camparo, Alojando, Pinares, Paraguay

---

Generado — Proyecto iniciado Mayo 2026 | Autora: Julieta Arrazate
