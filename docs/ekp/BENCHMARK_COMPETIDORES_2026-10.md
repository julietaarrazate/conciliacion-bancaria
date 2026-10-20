# Benchmark de competidores — cómo resuelven lo que Cuadra todavía no resuelve bien

**Fecha:** octubre 2026 · **Competidores:** Xubio, Colppy, Contabilium, Alegra (AR), LaPyme,
Holistor, Tango, SOS-Contador, Onvio (Thomson Reuters), Aconpy.
**Objetivo (pedido de la operadora):** que Cuadra junte en un solo lugar lo mejor de cada
herramienta — mirar cómo resuelve cada competidor los temas donde Cuadra flojea y decidir qué
incorporar.

## Método y límites

- Solo fuentes **públicas**: ayudas oficiales, páginas de precios, blogs, reseñas. Sin cuentas,
  sin logins, sin descompilar nada. Las notas por competidor (con todas las URLs) están en el
  laboratorio de ingeniería inversa (`julietaarrazate/laboratorio-rea`,
  `notas/competidores-gestion-ar.md`).
- REA/Ghidra no aplica acá: son productos web (SaaS), no programas compilados.
- **Límite importante:** desde el entorno de la sesión no se pudieron abrir los sitios oficiales
  (bloqueo de red/DNS), así que casi todo sale de resúmenes de buscador. Lo marcado ⚠️ no está
  confirmado. Holistor y Tango quedaron casi sin datos. Antes de construir algo inspirado en un
  competidor, verificar el flujo en su prueba gratis o su centro de ayuda.
- Las brechas de Cuadra salen de los `## Pendiente de revisar` de `/docs`,
  `.claude/memory/PROJECT_MEMORY.md` y la auditoría EKP de julio 2026, hoy fuera del repo (no de pruebas en producción).

## Lo que Cuadra ya hace mejor (no perderlo)

- **Matching por identidad.** Xubio y Colppy concilian por fecha + monto. Cuadra puntúa por
  CUIT/CBU/cuenta/referencia/titular y exige identidad ante montos duplicados.
- **Planillas de terceros heterogéneas.** Nadie más cruza la planilla de pagos de un cliente
  (cualquier formato, `planilla_mapper.py`) contra el extracto.
- **Carga de extractos flexible.** Colppy exige CSV con `;`, plantilla propia y ~100 filas por
  vez; Alegra exige su plantilla. Cuadra detecta 16 bancos sobre el Excel original.
- **Aprendizaje de correcciones** (`PatronAprendido`).

Anti-patrones vistos en la competencia (evitar): integraciones que pisan datos sin preview
(quejas de Contabilium con Mercado Libre), importaciones que no se pueden deshacer (importador de
faltantes de Colppy), soporte lento (Contabilium), conexión bancaria solo en planes caros.

## Brecha por área: cómo lo resuelven otros

| Área | Brecha en Cuadra | Quién lo resuelve mejor y cómo |
|---|---|---|
| Entrada del extracto | Solo Excel subido a mano | **Xubio**: Open Finance vía Interbanking (50+ bancos; credenciales API del cliente, cuentas "consultivas", trae desde la activación). **Colppy**: "Conecta tu banco" (24-48 h, solo planes altos). **Alegra**: extracto en **PDF o imagen leído con IA** (⚠️ guías de otros países) |
| Pendientes de conciliar | Hay que ir a otro módulo a registrar lo que falta | **Xubio**: desde un movimiento pendiente se crea cobranza, pago o asiento sin salir de la pantalla; filtro "diferencia no justificada" |
| Comprobantes de ARCA | Se importa el Excel de "Mis Comprobantes" solo en IVA Liquidación | **Colppy**: "importador de faltantes" — detecta lo que está en ARCA y no en el sistema y lo trae con revisión previa. **SOS-Contador**: baja Mis Comprobantes **cada noche, solo** (⚠️ mecanismo no documentado; probablemente con clave fiscal) |
| Compras con IA | Ya existe (v3.30), recepción por mail sin activar | **Contabilium**: casilla por empresa, valida que el CUIT receptor coincida, rechaza comprobantes de más de 60 días, crea el proveedor si no existe, lee percepciones. **LaPyme**: borrador → revisión → compra (igual que Cuadra) |
| Retenciones y percepciones | Carga manual, sin importador ni exportación a aplicativos | **Xubio**: calcula retenciones (Ganancias, IVA, SUSS, IIBB) **al pagar** según lo configurado en el proveedor, padrón actualizado mensualmente, exporta **TXT de SICORE** y SIRE. **Contabilium**: "Reportes impositivos" con TXT para Libro IVA Digital, ARBA y SIFERE |
| Cobranzas | Solo link público de solo lectura; sin recordatorios ni pago online | **Colppy**: **Portal de Clientes** — el cliente ve sus facturas y paga con Mercado Pago; el recibo se genera solo. Cobranzas con echeq, cheque diferido, transferencia, tarjeta |
| Gestión del estudio | Sin calendario de vencimientos ni tareas por cliente | **Onvio**: grilla de vencimientos de todos los clientes + **procesos masivos multi-empresa** (importar IVA, generar asientos, liquidar sueldos para todos a la vez) + portal del cliente con pedidos de documentación y tareas. **Aconpy**: calendario automático, panel de monotributo por cliente, tareas asignables a empleados |
| Billeteras / e-commerce | Mercado Pago solo como CSV | **Colppy** y **Contabilium**: integración con Mercado Pago; Contabilium/LaPyme con Mercado Libre y Tiendanube |
| Tesorería | Sin multimoneda; avisos de cheques pendientes | **Colppy**: multimoneda y echeqs de terceros desde Cobranzas |
| Contabilidad para estudios | Sin estados contables formales | **Onvio**: módulo de estados contables (balance, resultados, evolución del PN, flujo de efectivo, notas y anexos). **SOS-Contador**: ajuste por inflación con asistente paso a paso |
| IA como canal | Asistente interno con Gemini | **LaPyme**: conector **MCP** para operar el sistema desde Claude/ChatGPT, más API pública documentada |
| Sueldos | Estimación de costo laboral, no recibo legal | Holistor / SOS-Contador (Libro de Sueldos Digital) — ⚠️ sin detalle confirmado |

## Qué incorporar — priorizado por valor / esfuerzo

Criterio: primero lo que **reutiliza piezas que Cuadra ya tiene** y refuerza su diferencial
(conciliación), después lo que abre la venta a estudios, y al final lo que depende de terceros.

### Ola 1 — rápido, reutiliza lo que ya existe

1. ✅ **Extracto en PDF** — resuelto en v3.31 (lector propio + IA de respaldo para escaneados +
   cuadre de saldos). Queda solo aceptar **fotos** (JPG/PNG) del extracto. Idea original (Alegra): Reutiliza el helper de Gemini del OCR de
   cheques y facturas; entrega al parser el mismo esquema que un Excel. Cubre bancos que solo dan PDF.
2. ✅ **Resolver pendientes sin salir de la conciliación** (Xubio) — v3.32 para débitos (pago
   vinculado + % de egresos explicados). Incluye vincular un pago ya cargado. Desde un movimiento sin match:
   "crear pago", "crear cobranza", "crear gasto/asiento" con los datos precargados.
3. ✅ **Importador de faltantes de ARCA** (Colppy) — v3.33: comparar antes de importar, elegir y
   deshacer; además marca importes distintos y lo que está en Cuadra y no en ARCA.
4. **Controles de Contabilium en Comprobantes por revisar**: CUIT receptor = CUIT de la org,
   antigüedad máxima, alta automática del proveedor. Y activar la recepción por mail (pendiente
   de configuración, ver CLAUDE.md).

### Ola 2 — lo que hace que un estudio elija Cuadra

5. **Grilla de vencimientos por cliente** (Onvio/Aconpy) sobre los módulos de impuestos que ya
   existen (IVA, IIBB, Monotributo, F931), con avisos push y el panel de monotributo por cliente.
6. **Portal del cliente con pago** (Colppy): evolucionar el link público de estado de cuenta a
   "ver deuda + pagar con Mercado Pago + recibo automático", más pedido de documentación (Onvio).
7. **Retenciones al pagar + export SICORE/SIRE/ARBA/SIFERE** (Xubio/Contabilium), con el
   importador de retenciones y percepciones que ya está pendiente.
8. **Procesos masivos multi-cliente** (Onvio): correr una acción (importar ARCA, generar
   asientos, liquidar) para todas las orgs del estudio de una vez.

### Ola 3 — depende de terceros o es grande

9. **Conexión bancaria directa** (Xubio vía Interbanking / Open Finance). Requiere convenio y
   costo; evaluar cuando haya clientes que paguen. Ofrecerla en todos los planes sería un
   diferencial (Colppy la reserva a planes caros).
10. **Integración Mercado Pago por API** (no solo CSV), con preview antes de impactar.
11. **Descarga automática de Mis Comprobantes** (SOS-Contador) — investigar primero el mecanismo
    legal y técnico (manejo de clave fiscal = riesgo de seguridad alto).
12. **Conector MCP / API pública** (LaPyme).
13. Estados contables formales y ajuste por inflación; sueldos con recibo legal.

### Base de la excelencia (antes de vender, transversal)

De la auditoría EKP de julio 2026: infraestructura sin cold start (salir del free tier), ensayo de
restore del backup, branch protection en `main`, E2E de los flujos críticos. Ningún competidor
gana por estas cosas, pero un estudio abandona un sistema que tarda 30 s en abrir o pierde datos.

## Pendiente de revisar

- Confirmar con acceso directo (pruebas gratis o centros de ayuda): bancos argentinos de Alegra,
  flujo de match de Colppy, todo Holistor y Tango, precios vigentes.
- Validar con 2-3 estudios cuáles de la Ola 2 pagarían (hoy la prioridad es inferida).
