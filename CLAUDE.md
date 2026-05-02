# Sistema de Conciliacion Bancaria — Julieta Arrazate

## Que es esto

Sistema web + app movil para conciliar transferencias bancarias contra planillas de clientes.
Desarrollado por y para **Julieta Arrazate** que ofrece servicios contables a empresas.
Empresa cliente actual: **Caneland SA** (y en el futuro otras).

---

## Arquitectura de produccion (100% gratuita)

- Frontend (React + PWA): Vercel — https://conciliacion-bancaria-ten.vercel.app
- Backend (FastAPI): Render — https://conciliacion-api.onrender.com
- Base de datos: Neon PostgreSQL — ep-ancient-hall-anz4pezn.c-6.us-east-1.aws.neon.tech
- Codigo: GitHub — julietaarrazate/conciliacion-bancaria

Render free tier: duerme tras 15 min sin uso. Primera request del dia tarda ~30 seg.
No requiere PC local para funcionar — todo corre en la nube.

---

## Credenciales de produccion

- Admin real: coopagrofuturoadm@gmail.com / admin123 (cambiar password en Mi perfil)
- Admin demo: admin@caneland.com / admin123

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
  /app/models — User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog
  /app/routers — auth, me, extractos, planillas, historial, auditoria, admin, clientes_dir
  /app/services — conciliacion.py (algoritmo core), excel_parser, excel_export, extracto_merger
  seed.py — Crea usuarios iniciales
  requirements.txt

/frontend — React 18 + TypeScript + Vite + TailwindCSS + PWA
  /src/pages — Dashboard, Clientes, Movimientos, Historial, Bulk, Auditoria, Usuarios, Perfil, Login
  /src/components — Layout, PlanillaPanel, FileUpload, ThemeToggle
  /src/services/api.ts — Todos los endpoints

---

## Algoritmo de conciliacion (services/conciliacion.py)

Para cada fila de la planilla del cliente:
1. Buscar movimientos con monto == monto_planilla (tolerancia 0.01)
2. Si monto aparece < 3 veces -> acreditar al primer libre (sin validar CUIT)
3. Si monto aparece >= 3 veces (UMBRAL_COMUN = 3) -> requiere CUIT o titular:
   - El CUIT puede estar en: columna CUIT de planilla, campo titular del extracto
   - Buscar CUIT en campo titular del extracto (regex \d{10,11})
   - Si hay match -> ok, si no -> "faltan datos"
4. Sin movimientos libres -> "duplicado" o "acreditado DD/MM"
5. Monto no existe -> "no esta"

---

## Features implementadas

Backend:
- Auth JWT 8h con pbkdf2_sha256 (sin bcrypt)
- Roles: admin, operador, revisor, auditor
- Extracto bancario: upload, listar, filtrar, exportar Excel, borrar
- Ultimos Movimientos (UM): agregar sin duplicar (clave: orden+monto), filas marcadas con source='um'
- Planillas: upload, conciliar, detalle, download (Hoja1 cliente + Hoja2 extracto), borrar
- Historial agrupado por cliente/mes
- Auditoria automatica de todas las operaciones
- Gestion de usuarios (crear, cambiar rol, activar/desactivar)
- Change password / update profile
- Guardar en carpetas locales: Desktop/clientes/{Cliente}/{Anio}/{Mes}/

Frontend:
- PWA instalable como app en celular (Android + iOS)
- Dashboard con KPIs + conciliaciones recientes
- Seccion Clientes: arbol Anio -> Mes -> archivos
- Movimientos con filtros Excel inline en headers + tab UM editable (doble clic para editar)
- Historial con preview y descarga (Hoja1+Hoja2)
- Bulk: multiples planillas a la vez
- Dark mode con toggle persistido
- Layout responsive (desktop sidebar / mobile bottom nav)
- Swipe derecha para cerrar paneles

---

## Pendientes / Roadmap

Alta prioridad:
- Multi-tenant: cada empresa tiene datos aislados (model Organizacion, Julieta como super-admin)
- Exportar extracto actualizado al contador al final del dia
- Mejorar dark mode contraste en tablas y headers
- Keep-alive de Render (ping cada 14 min para no dormir)

Media prioridad:
- Notificaciones cuando Render se despierta
- Multiples formatos de extracto (otros bancos)
- PDF de conciliacion mensual

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

## Clientes configurados

Green, Tucu, David, Smt, Gwinn, Innova, Camparo, Alojando, Pinares, Paraguay

---

## Modelo multi-tenant futuro

Cuando sumes otras empresas, el sistema necesita:
- Model Organizacion (id, nombre, plan)
- Usuario.organizacion_id (Julieta super-admin con acceso a todas)
- Todos los modelos filtrados por organizacion_id
- Por ahora todo bajo un unico tenant (Caneland)

Generado — Proyecto iniciado Mayo 2026
