# Product Genesis (gate corto): Conciliación de billeteras virtuales — 2026-07-10

> Gate de viabilidad EKP corrido sobre la idea 2 de la operadora. Inputs
> heredados de la sesión: objetivo venture · recursos mínimos (~USD 20/mes).
> Registro deliberadamente corto: el gate frenó en la dimensión 4.

## 0. Veredicto

> ## ⛔ NOT VIABLE (yet) — como producto standalone para comercios
> Kill-flag en **competencia (dim. 4)**: incumbentes atrincherados y fondeados
> hacen exactamente esto en Argentina — [Nubceo](https://www.nubceo.com/)
> ("conciliá tus ventas integrando pasarelas de pago, puntos de venta y ERP
> automáticamente") e Increase (conciliación de cobros con tarjetas/medios de
> pago, años en el mercado). Con runway de USD 20/mes y sin cuña definida
> contra ellos, la vara venture no se cumple. "Competirle a Nubceo con menos
> recursos y el mismo pitch" no es una cuña.
>
> ## ✅ VIABLE — como feature de Cuadra (reencuadre propuesto)
> La misma capacidad, para OTRO cliente que los incumbentes no atienden así:
> los **estudios contables** que ya concilian extractos bancarios en Cuadra y
> hoy no pueden conciliar los movimientos de Mercado Pago/Ualá de sus
> clientes. Es extender el parser multi-banco existente a extractos de
> billeteras — el mismo motor, la misma UI, el mismo cliente que ya paga(rá).
> Las billeteras ya concentran [más de la mitad de las compras online](https://www.ambito.com/finanzas/la-argentina-acelera-la-revolucion-fintech-las-billeteras-digitales-ya-dominan-mas-la-mitad-las-compras-online-n6279159)
> y [43% del valor operado en puntos de venta (2025)](https://www.infobae.com/economia/2026/05/14/para-2030-mas-de-la-mitad-de-los-pagos-a-comercios-se-hara-con-billeteras-y-transferencias-sin-usar-tarjetas/)
> — la porción no-bancaria de la conciliación crece sola.

## Consecuencia (BDR-008: el NO también produce dirección)

No se abre producto nuevo. Se agrega al roadmap de Cuadra:
**"Parser de extractos de billeteras (Mercado Pago primero, Ualá después) en
el motor multi-banco existente"** — prioridad tras los 3 bloqueadores
operativos de la auditoría (infra paga, restore, branch protection).

### Validación (aún más barata que la del copiloto)
La operadora es su propia usuaria: tomar el extracto de actividad de Mercado
Pago de UN cliente real del estudio y conciliarlo a mano contra su planilla.
Si el dolor es real (¿cuánto tardó? ¿cuántos cruces manuales?), el feature se
construye en una sesión Sonnet+Opus como cualquier parser nuevo (el patrón
`detección automática de formato` ya existe).

### Trigger de revisión del veredicto standalone
Reabrir solo si aparece una cuña real contra Nubceo/Increase (p. ej. un
segmento que ellos ignoren + canal propio probado) Y recursos de venture.
