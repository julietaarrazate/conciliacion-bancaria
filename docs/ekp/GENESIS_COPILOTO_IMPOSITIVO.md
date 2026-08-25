# Product Genesis: Copiloto impositivo proactivo por WhatsApp — 2026-07-10

> Ejecutado con `generators/product-genesis.md` del repo EKP (julietaarrazate/ekp),
> gate de viabilidad `domains/business/gates/business-viability-gate.md`.
> Inputs de la operadora (interrogación 2026-07-10): cliente = **estudios
> contables** (B2B, white-label) · objetivo = **venture/escalar** (vara alta) ·
> recursos = **solo su tiempo + ~USD 20/mes** hasta la primera venta.
> Guardado en el repo de Cuadra porque el producto hereda su motor de impuestos
> y su segmento; si la validación pasa, nace como canal/módulo de Cuadra antes
> que como código nuevo.

## 0. Veredicto

> ## ⚠️ CONDICIONALMENTE VIABLE
> No hay kill-flag duro — pero las tres dimensiones que sostienen el "sí"
> (disposición a pagar, diferenciación frente a incumbentes, canal a escala)
> están en nivel de evidencia `assumed`. **No se construye nada hasta pasar la
> validación de la semana 1 (§1). El primer milestone es vender, no programar.**

## 1. Informe de viabilidad (12 dimensiones, evidencia etiquetada)

| # | Dimensión | Hallazgo | Evidencia | Kill-flag |
|---|---|---|---|---|
| 1 | Problema | Real y recurrente por diseño legal: recategorización obligatoria 2×/año (enero/julio), vencimientos mensuales, exclusión de oficio por exceso de tope. El costo de un olvido es dinero (recargos, exclusión). | reported ([ARCA](https://www.afip.gob.ar/monotributo/ayuda/recategorizacion.asp), [iProfesional](https://www.iprofesional.com/impuestos/448478-monotributo-2026-claves-primer-vencimiento-escalas-actualizadas)) | no |
| 2 | Cliente | Nombrable y alcanzable: estudios contables argentinos con cartera de monotributistas/pymes. La operadora pertenece al segmento y tiene acceso directo (Cuadra). | reported | no |
| 3 | Alternativa actual / switching | El estudio hoy avisa a mano (WhatsApp personal, planillas) o su software alerta por email/dentro de la plataforma. Switching bajo si es aditivo (no reemplaza su sistema), PERO el dolor residual tras esas alertas es **assumed**. | assumed ⚠️ | no |
| 4 | Competencia | El feature central ya existe en incumbentes: [SOS-Contador](https://www.sos-contador.com/) alerta al superar 90% del tope de categoría; [FiscalPyME](https://fiscalpyme.app/blog/vencimientos-arca-julio-2026) arma calendario por CUIT con alertas por email (freemium). Espacio de software para estudios poblado (Witmi, Taxes, Errepar Mi Estudio, Aconpy, Colppy, Xubio). Ninguno detectado como **WhatsApp-first white-label al cliente final del estudio** — esa es la cuña. | reported | no, pero estrecho |
| 5 | Diferenciación / moat | Como producto standalone: **débil** — una capa de alertas por WhatsApp es un feature copiable en un trimestre por cualquier incumbente. Como canal de Cuadra: defendible — el copiloto responde con los datos reales del cliente (conciliación + contabilidad + impuestos ya integrados), que el incumbente de alertas no tiene. | inferred ⚠️ | no (solo si va atado a Cuadra) |
| 6 | Propuesta de valor | En boca del estudio: *"Mis clientes reciben en su WhatsApp, con mi marca, el aviso de que se pasan de categoría o se les vence algo — sin que mi equipo pierda las mañanas avisando uno por uno."* | inferred | no |
| 7 | Modelo de negocio | El estudio paga suscripción mensual por cartera cubierta (hipótesis: escalones por cantidad de CUITs monitoreados). Disposición a pagar real: **assumed** — nadie la midió todavía, y los incumbentes regalan alertas por email. | assumed ⚠️ | no |
| 8 | Canal de adquisición | Cliente #1–10: acceso directo de la operadora al gremio (medido en Cuadra). Cliente #1000 (vara venture): **assumed** — no hay canal probado a escala; los consejos profesionales/comunidades de contadores son hipótesis. | assumed ⚠️ | no |
| 9 | Unit economics | WhatsApp Cloud API directa (sin BSP, sin abono): plantilla utility ≈ [USD 0,06 en Argentina](https://www.basework.com.ar/blog/whatsapp-business-api-argentina); ~6–10 mensajes proactivos/CUIT/mes ≈ USD 0,4–0,6/CUIT/mes de costo variable. Con precio de USD 0,5–1/CUIT/mes al estudio, margen bruto ≥ 40% y mejora a escala. Sublineal en costo: el motor de cálculo ya existe (Cuadra). | reported | no |
| 10 | Buildability | Alta y **medida**: la due-diligence de Cuadra (docs/AUDITORIA_EKP_2026-07.md) confirma motor de impuestos (4 módulos), multi-tenant, 558 tests, compartir-por-WhatsApp ya resuelto en UI. Falta solo: adaptador WhatsApp Cloud API + scheduler de reglas de alerta (el scheduler ya existe: APScheduler). | measured | no |
| 11 | Costo y runway | USD 20/mes alcanza para el piloto (Cloud API directa sin abono; infra ya paga por Cuadra si se ejecuta como módulo). NO alcanza para adquisición a escala venture — coherente solo si la validación se hace vendiendo antes de construir. | reported | no |
| 12 | Riesgo regulatorio | Datos fiscales de terceros: ya bajo el mismo régimen que Cuadra (Ley 25.326; inscripción AAIP pendiente en el roadmap de Cuadra — aplica a ambos). WhatsApp: usar plantillas utility aprobadas, opt-in explícito del cliente final (lo pide Meta). Sin bloqueo legal detectado. | reported | no |

**Veredicto compuesto (nunca promedio):** sin kill-flag duro → no es NOT VIABLE.
Con 7 (pago), 5 (moat standalone) y 8 (canal a escala) en `assumed` siendo
load-bearing para la vara venture → **CONDICIONALMENTE VIABLE**.

### El supuesto más riesgoso
**"Los estudios contables pagarán por alertas proactivas white-label por
WhatsApp, aunque su software actual ya les da alertas por email/plataforma
gratis o casi gratis."** Si esto es falso, no hay producto — hay un feature
que los incumbentes ya regalan por un canal menos efectivo.

### El test más barato que puede falsificarlo esta semana
1. **5 conversaciones de venta reales** (no encuestas): estudios que la
   operadora conoce. Pregunta única: *"¿Pagarías $X por CUIT/mes para que tus
   monotributistas reciban esto en su WhatsApp con tu marca?"* — mostrando 3
   capturas simuladas (aviso de 90% del tope, vencimiento, recategorización).
2. **Piloto concierge en el estudio propio** (2 semanas, USD 0): mandar los
   avisos A MANO por WhatsApp normal a 10–20 clientes reales usando los datos
   que Cuadra ya calcula. Medir: ¿los clientes respondieron/agradecieron?
   ¿el estudio los dejaría de mandar?
3. Criterio de decisión: **≥2 de 5 estudios dicen "sí" a un precio concreto**
   (no "qué lindo") → pasar a construir M1. Menos → pivotar o archivar.

### Trigger de revisión
Reabrir el veredicto si: (a) el test de ventas da ≥2/5 síes con precio,
(b) un incumbente lanza WhatsApp white-label (mata la cuña standalone), o
(c) ARCA lanza notificaciones proactivas propias al contribuyente.

## 2. Descubrimiento (resumen)

- **Job-to-be-done del estudio**: "mantener a mi cartera fuera de problemas con
  ARCA sin que mi equipo queme horas en avisos manuales, y que el cliente
  perciba que YO lo cuido" (retención de clientela).
- **Job del cliente final**: "que no me sorprendan una exclusión, un recargo o
  una recategorización que no entiendo" — en el canal donde vive (WhatsApp),
  no en un email que no abre.
- **Usuarios**: contador titular (compra) · administrativo del estudio
  (configura) · monotributista/pyme (recibe; no paga, no configura).
- **Métrica de éxito del piloto**: tasa de respuesta/lectura de los avisos +
  renovación del estudio al mes 2.
- **Hipótesis explícitas**: H1 = pagan (test §1) · H2 = el cliente final lo
  valora y no lo bloquea · H3 = 6–10 msg/mes es la dosis (más = spam).

## 3. PRD — núcleo irreducible (solo si el test §1 pasa)

**M1 "esqueleto que camina"** — un solo flujo de punta a punta:
1. El estudio marca N clientes de Cuadra como "suscriptos a avisos" con su
   número de WhatsApp (opt-in registrado).
2. Un job diario evalúa 3 reglas — (a) facturación > 85% del tope de categoría,
   (b) vencimiento de pago mensual T-3 días, (c) ventana de recategorización
   abierta — usando datos que Cuadra ya tiene.
3. Dispara plantilla utility aprobada vía WhatsApp Cloud API, con la marca del
   estudio, y registra el envío (auditoría, idempotencia: nunca dos veces el
   mismo aviso).

**Explícitamente FUERA del MVP**: chat bidireccional con IA, OCR, más reglas,
panel propio (se administra desde Cuadra), multi-canal, app.

## 4. Arquitectura (boceto — vía `generators/architecture.md` en detalle si pasa el gate)

Módulo `notificaciones_fiscales` DENTRO de Cuadra (no repo nuevo): reutiliza
multi-tenant, permisos, motor de impuestos, APScheduler y el patrón feature-flag
(sin `WHATSAPP_TOKEN` la feature se apaga sola — regla existente del repo).
Piezas nuevas: adaptador WhatsApp Cloud API (webhook + envío de plantillas),
tabla `avisos_enviados` (idempotencia + auditoría), reglas como servicios puros
testeables. Cero infraestructura nueva.

## 5. Stack — decisión y ADR propuesto

Alternativas: (a) módulo en Cuadra (FastAPI/Python existente), (b) servicio
nuevo aparte, (c) herramienta no-code (Zapier/n8n + planillas).
**Factor decisivo**: el valor diferencial ES el acceso a los datos vivos de
Cuadra (dimensión 5); separarlo duplica el multi-tenant y la seguridad ya
auditados; no-code no puede leer la DB multi-tenant con las garantías de
permisos existentes. → **(a) módulo en Cuadra**. Registrar como ADR-0005 del
repo al momento de construir (formato `docs/adr/`), citando este dossier.

## 6. Plan de implementación (dependencias en orden; costo estimado por hito)

| Hito | Qué | Quién | Criterio de aceptación |
|---|---|---|---|
| **M0 — Validación** (esta semana, USD 0) | Test §1: 5 ventas + concierge en estudio propio | Operadora (la IA prepara las 3 capturas simuladas y el guion de la llamada) | ≥2/5 síes con precio concreto; registro escrito de cada conversación |
| M1 — Esqueleto (1 semana de sesiones) | §3 completo tras M0 verde; cuenta Meta Business + plantillas utility aprobadas | Sonnet (CRUD/adaptador) + Opus (reglas fiscales) + operadora (alta en Meta) | Un cliente real del estudio propio recibe los 3 tipos de aviso desde datos vivos; test de idempotencia verde |
| M2 — Piloto pago | 2–3 estudios del test M0 onboardeados, precio real cobrado | Operadora vende; IA opera | Primer peso facturado; churn 0 al mes 2 |
| M3 — Decisión de escala | Con datos de M2: ¿canal a escala? (dimensión 8) — recién acá se piensa en venture | Operadora + PGE re-run | Veredicto actualizado con evidencia measured |

## 7. Ciclo de vida

Si M2 pasa: el módulo entra al loop estándar de Cuadra (due-diligence
periódica, TECH_DEBT, STATUS) — sin expediente nuevo. Si M0 falla: archivar
este dossier con el resultado del test anotado (el NO documentado también es
conocimiento, P5) y correr PGE sobre la idea 2 (conciliación de billeteras).
