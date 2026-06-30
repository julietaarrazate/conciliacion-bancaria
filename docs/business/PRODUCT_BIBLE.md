# Product Bible — Cuadra

> Biblia de producto: qué es Cuadra, para quién, su propuesta de valor y el panorama
> de módulos desde la óptica de negocio. Las reglas técnicas detalladas viven en
> [`BUSINESS_RULES.md`](./BUSINESS_RULES.md) y los flujos end-to-end en
> [`WORKFLOWS.md`](./WORKFLOWS.md). Para arquitectura, ver
> [`../architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md).

Fuentes: [`../../README.md`](../../README.md), [`../../CLAUDE.md`](../../CLAUDE.md)
(sección "Flujo de negocio") y los componentes de landing en
`frontend/src/components/landing/`.

---

## Qué es Cuadra

Cuadra es una **plataforma web y móvil (PWA instalable)** para automatizar la
conciliación de transferencias bancarias y la gestión financiera de un estudio
contable o una empresa. Cruza el extracto bancario contra las planillas de pagos
de cada cliente, deja cada movimiento explicado (quién pagó, cuándo, con qué
identidad) y suma una suite completa: cheques, pagos, caja, liquidaciones,
contabilidad de partida doble, liquidación de impuestos y un asistente con IA.

Es **multi-tenant**, con auditoría completa y permisos granulares
(ver [`../../README.md`](../../README.md) → "Roles y permisos").

El nombre interno del repositorio es `conciliacion-bancaria`; el producto se
llama **Cuadra**.

---

## Para quién

- **Estudios contables argentinos** que concilian extractos de varios bancos
  contra planillas de múltiples clientes cada mes (caso de uso central).
- **Empresas argentinas** que necesitan ordenar su operación financiera:
  cheques, pagos con comprobante, arqueo de caja, contabilidad e impuestos.

El público objetivo está reflejado en los testimoniales de la landing
(`frontend/src/components/landing/data.tsx`): estudios contables, contadores
independientes y áreas de administración de distribuidoras/comercios.

---

## Propuesta de valor

Tomada de la landing (`data.tsx` → `STATS`, `COMPARISON`) y del
[`../../README.md`](../../README.md):

| Tarea | Con Excel | Con Cuadra |
|---|---|---|
| Conciliar 100 movimientos | 4–6 horas | ~2 minutos |
| Errores humanos | Frecuentes | Mínimos (auto-detección) |
| Acceso desde el celular | No | Sí, PWA desde cualquier teléfono |
| Multi-empresa | Un archivo por empresa | Todo en un sistema |
| Backup automático | Manual o ninguno | Diario, encriptado |
| Auditoría de cambios | Ninguna | Log completo (quién/qué/cuándo/dónde) |
| Trabajo en equipo | Conflictos al editar | En tiempo real |

Pilares:
- **Detección automática de formato de banco** (parsers por banco + genérico).
- **Motor de conciliación con scoring por identidad** que explica cada fila.
- **IA que aprende** de las correcciones manuales (Nivel 2).
- **Cero instalación**: PWA, operativo en ~24 hs según la landing.

---

## Modelo SaaS multi-tenant

- Cada **organización** es un tenant aislado: ve **solo sus propios datos**. El
  aislamiento se aplica endpoint por endpoint
  (ver [`../security/SECURITY_MODEL.md`](../security/SECURITY_MODEL.md)).
- La **Organización A** (`organizacion_id=1`) es la org base productiva: por
  regla del repo, sus datos existentes **nunca se modifican** (solo cambios
  aditivos — ver [`../../CLAUDE.md`](../../CLAUDE.md)).
- **Superadmin** (Julieta Arrazate) ve y gestiona **todas** las organizaciones.
- Cada org configura su comportamiento por JSON (`match_rules`,
  `tolerancia_monto`, `dias_tolerancia_fecha`, `requiere_cierre_periodo`,
  `comisiones`). El detalle de cómo afecta al motor está en
  [`BUSINESS_RULES.md`](./BUSINESS_RULES.md).
- **Roles** con permisos granulares: Superadmin, Admin, Contador, Operador,
  Auditor, Revisor (ver tabla en [`../../README.md`](../../README.md)).

Cada módulo nuevo es **opt-in/configurable por organización** (no hardcodeado
para una sola org) — patrón establecido en [`../../CLAUDE.md`](../../CLAUDE.md).

---

## Panorama de módulos (óptica de producto)

> El "cómo" de cada regla está en [`BUSINESS_RULES.md`](./BUSINESS_RULES.md);
> los flujos en [`WORKFLOWS.md`](./WORKFLOWS.md).

### Conciliación bancaria — núcleo del producto
Importa el extracto bancario mensual (Excel) con **detección automática** de
varios bancos argentinos, acumula los "Últimos Movimientos" (UM) diarios del
contador **sin duplicar**, y cruza el extracto contra la planilla de pagos de
cada cliente con scoring por identidad (CUIT, CBU/CVU, número de cuenta,
referencia, titular, cercanía de fecha). Soporta carga masiva (varias planillas
auto-conciliadas) y exporta Excel formato banco + PDF de cierre mensual.

### Cheques
Cartera de cheques con ciclo de vida (registrado → depositado → acreditado →
rechazado/anulado), alertas de vencimiento, OCR de la imagen del cheque y
comisión diferenciada **local/interior** según el código postal.

### Pagos y Gastos
Órdenes de pago / egresos con **foto del comprobante**, **OCR** del importe y la
fecha (Gemini, opt-in) y opción de **compartir por WhatsApp**.

### Caja
Arqueo diario de efectivo.

### Liquidaciones
Liquidación de **comisiones por cliente y período**, con generación de
borrador, aprobación (que postea asientos contables) y **cierre de período**
que vuelve inmutables los registros del rango.

### Contabilidad (partida doble)
Plan de cuentas, asientos automáticos y manuales, libro diario, libro mayor,
cuentas corrientes por cliente, sumas y saldos, balance, y export a formatos
contables (Tango, Holistor, etc.). Es la **fuente de los módulos de impuestos**.
Ver [`../architecture/ACCOUNTING_ENGINE.md`](../architecture/ACCOUNTING_ENGINE.md).

### Liquidación de impuestos (4 módulos)
Todos **proyectan** sobre los asientos contables (no presentan DDJJ oficiales):
- **IVA** — proyección de débito/crédito fiscal y DDJJ.
- **Monotributo** — control semestral de facturación contra las escalas de ARCA.
- **Ingresos Brutos (IIBB)** — proyección simple o con Convenio Multilateral.
- **Sueldos / F931** — liquidador de sueldos y cargas sociales.

### ARCA — facturación electrónica
Integración propia con WSFEv1/WSAA (emisión de CAE) con asiento contable
automático. **Construido pero desactivado a propósito**: se activa por
organización cuando un cliente lo solicite (ver [`../../CLAUDE.md`](../../CLAUDE.md)
→ "Activación de ARCA en producción").

### Asistente con IA (Gemini, opt-in)
Chat en lenguaje natural con acceso a los datos reales (saldos, comisiones,
cheques por vencer, movimientos sin conciliar), OCR de comprobantes,
transcripción de voz y alertas proactivas. Detalle en
[`../ai/AI_GUIDE.md`](../ai/AI_GUIDE.md).

---

## Integraciones opcionales (feature flags)

Toda integración se **degrada sola** si su variable no está seteada (ninguna
rompe el sistema). Listado completo de variables en
[`../../README.md`](../../README.md) → "Integraciones opcionales": `GEMINI_API_KEY`,
`RESEND_API_KEY`, `VAPID_*`, `S3_*`, `SENTRY_DSN`/`VITE_SENTRY_DSN`,
`GOOGLE_CLIENT_ID`, `ARCA_ENCRYPTION_KEY`.

---

## Pendiente de revisar

- La landing (`data.tsx` → `FAQ` y `STATS`) menciona "10+ bancos" y lista
  "Macro, BBVA, Santander, Galicia, ICBC + genérico"; el [`../../README.md`](../../README.md)
  agrega Nación, HSBC, Ciudad, Provincia; [`../../CLAUDE.md`](../../CLAUDE.md)
  habla de "16 bancos". El número exacto de parsers debe verificarse contra
  `backend/app/services/excel_parser.py` y documentarse de forma única (candidato
  a vivir en [`BUSINESS_RULES.md`](./BUSINESS_RULES.md)).
