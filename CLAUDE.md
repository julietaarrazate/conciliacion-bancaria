# Sistema de Conciliacion Bancaria — Julieta Arrazate

## Para continuar en un nuevo chat

"Soy Julieta Arrazate. Proyecto: conciliacion-bancaria.
Lee el CLAUDE.md del repo julietaarrazate/conciliacion-bancaria para entender el contexto."

---

## Autora y Propietaria

Julieta Arrazate — julietaarrazate@gmail.com — propietaria intelectual exclusiva.

---

## Produccion

- Frontend: https://conciliacion-bancaria-ten.vercel.app
- Backend: https://conciliacion-api.onrender.com
- DB: Neon PostgreSQL — ep-ancient-hall-anz4pezn.c-6.us-east-1.aws.neon.tech
- GitHub: julietaarrazate/conciliacion-bancaria
- Keep-alive: UptimeRobot pinguea /health cada 5 min

API keys:
- Render key: rnd_8Kqkb028Ochfw6eSOYZR3v2O7Cv2
- Render service ID: srv-d7pqt81j2pic73c0c6fg
- Vercel token: vcp_5vau9jj3k4E9Pn9yI3m4BMaWBWJSv5mNh3mU9Yd1mkHxbFmFub03rpK8
- Vercel project ID: prj_cVINkspVm6j3B1fxOrdU81B0ehWg

Deploy Render: curl -X POST https://api.render.com/v1/services/srv-d7pqt81j2pic73c0c6fg/deploys -H "Authorization: Bearer rnd_8Kqkb028Ochfw6eSOYZR3v2O7Cv2"

---

## Credenciales

- Superadmin: julietaarrazate@gmail.com / ver SUPERADMIN_PASSWORD en Render env vars
- Admin demo: admin@julieta.com / admin123

---

## Stack

Backend: FastAPI + SQLAlchemy + PostgreSQL + Python
Frontend: React 18 + TypeScript + Vite + TailwindCSS + PWA instalable
Diseno: Linear-inspired, Inter font, dark #0B0B0F, verde #22C55E en dark mode
Auth: JWT 8h, pbkdf2_sha256, rate limiting slowapi

---

## Flujo de negocio Caneland

1. Extracto bancario mensual Banco Macro (.xlsx) -> subir al sistema
2. Diariamente: Ultimos Movimientos (UM) -> agregar sin duplicar
3. Clientes envian planillas de pagos -> conciliar automaticamente
4. Revisar casos sin datos / no coincide en seccion Revision
5. Exportar extracto conciliado para el contador (boton "Para contador")
6. Pagos en efectivo a proveedores: registrar como OP en seccion Caja

---

## Modelos (backend/app/models/)

Organizacion, User (is_superadmin, organizacion_id), Cliente, ExtractoBancario,
MovimientoBanco (titular, monto, cliente_acreditado, fecha_acred, source),
Planilla, PlanillaRow (status, monto_acreditado, comentario_revision),
AuditoriaLog, PatronAprendido (titular_fragmento, numeros_clave, veces_correcto),
Liquidacion, LiquidacionDetalle, CierrePeriodo,
ArqueoDiario (denominaciones JSON, cruce auto), OrdenDePago (foto_base64)

---

## Routers (backend/app/routers/)

auth, me, extractos, planillas, historial, auditoria, admin, clientes_dir,
organizaciones (CRUD + actividad + backup + primer-usuario),
liquidaciones (generar/aprobar/exportar/cerrar-periodo),
caja (arqueo del dia + registrar OP + exportar EFT)

---

## Motor de conciliacion (services/conciliacion.py)

Scoring por identidad (mayor score = mejor match):
  CUIT exacto (10-11 digitos)     = 12 pts
  CBU/CVU exacto (22 digitos)     = 10 pts
  Numero cuenta largo (10+ dig.)  =  8 pts
  Numero referencia (6-9 dig.)    =  6 pts
  Titular 2 palabras              =  5 pts
  Titular 1 palabra               =  3 pts
  Bonus fecha (mismo dia)         = +5 pts
  Bonus fecha (1-2 dias)          = +4 pts
  Bonus fecha (3-4 dias fds)      = +3 pts
  Bonus fecha (5-7 feriado)       = +2 pts

REGLA CRITICA: monto aparece 2+ veces -> SIEMPRE exigir identidad.
Tolerancia fecha: 5 dias (feriados + fin de semana automatico).
Mensajes: "sin datos (N mov.)", "no coincide (N mov.)", "ambiguo"

---

## IA Nivel 2 (services/aprendizaje.py)

PatronAprendido: guarda patron titular -> cliente desde correcciones manuales.
Con 2+ confirmaciones: se usa automaticamente en futuras conciliaciones.
Bootstrapped el 05/05/2026 con 505 planillas historicas de Caneland (Nov25-May26).
Script de importacion: importar_patrones.ps1 (en el repo).
GET /auditoria/patrones — lista patrones
GET /auditoria/insights — estadisticas + tasa exito

---

## Multi-tenant

Caneland SA = organizacion_id=1 (nunca modifica operatoria).
Julieta = superadmin: ve todas las orgs desde el switcher del sidebar.
Panel de Actividad (/actividad): alertas, tasa exito, EN_REVISION pendientes por org.
Config de flujo por org: match_rules, tolerancia, estados, comisiones en JSON.

---

## Modulo Caja + OP

ArqueoDiario: SI + pesos_agregados + ingresos - pagos OPs = caja_restante.
Arqueo fisico por denominacion (20000..100) -> cruce debe ser 0.
OrdenDePago: cliente libre (crea si no existe), beneficiario, foto base64 comprimida.
Compartir WhatsApp: Web Share API con foto, nombre = nombre del proveedor.
Exportar EFT: /caja/op/exportar-eft -> Excel formato identico planilla manual.
  Hoja 1 Historico: Fecha | Cliente | Importe (header verde)
  Hoja 2 Diario: totales por fecha

---

## Modulo Liquidaciones

POST /liquidaciones/generar: calcula comisiones segun config org, crea borrador.
Flujo: borrador -> aprobar -> marcar-pagada.
Excel 3 hojas: resumen ejecutivo, detalle por cliente, log revisiones.
POST /liquidaciones/periodos/cerrar: valida EN_REVISION -> genera liquidacion.
Comisiones configurables en JSON de la org (por cliente por nombre).

---

## Multi-banco (services/excel_parser.py)

detectar_banco(): identifica Macro, BBVA, Santander, Galicia, ICBC, Nacion, etc.
detectar_columnas(): busca headers en espanol e ingles.
parsear_generico(): adapta a cualquier formato.
_parse_monto(): formato argentino con punto/coma, con/sin $.
_parse_fecha(): DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY.
Prueba todas las hojas, toma la que tiene mas movimientos.

---

## Pendientes del roadmap

- Google OAuth / login con Google
- PDF de conciliacion mensual por cliente
- IA Nivel 3 prediccion con ML (necesita 3-6 meses de datos)
- App movil nativa React Native
- WhatsApp notifications
- Historial OP visual en la app (backend ya tiene GET /caja/op/historial)

---

## Secciones frontend (menu)

Conciliar, Clientes, Bulk, Movimientos, Historial,
Caja, Nueva OP, Revision, Liquidaciones, Actividad,
Auditoria, Usuarios, Orgs, Mi perfil

---

## Clientes Caneland

Green, Tucu, David, Smt, Gwinn, Innova, Camparo, Alojando, Pinares, Paraguay

---

## Skill Cowork instalado

conciliar-planillas: guia paso a paso para conciliar sin saber del proyecto.
Activar diciendo: "tengo que conciliar", "llego la planilla de [cliente]", etc.

---

## IMPORTANTE para Claude

- Todo va DIRECTO a GitHub. Clonar en /tmp, trabajar, push, rm -rf.
- Caneland NUNCA cambia operatoria. Cambios siempre aditivos.
- Token GitHub NO tiene scope "workflow" — no crear GitHub Actions.
- No hay Python local — usar PowerShell para scripts si hace falta.
- Render service ID: srv-d7pqt81j2pic73c0c6fg
- Vercel project ID: prj_cVINkspVm6j3B1fxOrdU81B0ehWg

Generado: Mayo 2026 | Autora: Julieta Arrazate