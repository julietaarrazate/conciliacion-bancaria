# INVENTARIO DE CAPTURAS DE PANTALLA
## Evidencia visual del sistema en funcionamiento

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12 (build v3.10 visible en perfil)

---

## 1. RESUMEN

Se capturaron **27 pantallas** del sistema en funcionamiento real, con datos
de producción (organización de producción). Las capturas demuestran que la obra
está **completa, operativa y en uso productivo**, cubriendo la totalidad de los
módulos principales.

| Característica | Detalle |
|---|---|
| Total de capturas | 27 |
| Modo de visualización | Claro (mayoría) + Oscuro (Resumen) |
| Origen de datos | Producción real (https://conciliacion-bancaria-ten.vercel.app) |
| Usuario | Julieta Arrazate (Superadmin) |
| Organización | organización de producción (14 clientes, 46 conciliaciones) |
| Formato | PNG |

---

## 2. INVENTARIO COMPLETO DE CAPTURAS

### Grupo A — Panel general y reportería

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `01_resumen_ejecutivo.png` | Resumen ejecutivo | Tarjetas Conciliado/Pendiente/Tasa/Movimientos banco ($77.291.276), cheques en cartera, selector hoy/semana/mes/rango, export PDF cierre y Excel |
| `02_resumen_dark.png` | Resumen (modo oscuro) | Mismo panel en dark mode: top clientes, cheques en cartera, gráfico "Evolución conciliado 6 meses" |
| `19_flujo_caja.png` | Flujo de Caja | Ingresos $726.466.398, Egresos $49.361.400, Neto $677.104.998, gráfico Neto mensual (3 meses) |
| `20_flujo_caja_detalle.png` | Flujo de Caja (detalle) | Gráfico de barras Ingresos vs Egresos + tabla mensual con tasa de conciliación (05/26 = 95%) |
| `21_flujo_caja_6meses.png` | Flujo de Caja (6 meses) | Serie completa 01/26–06/26 con detalle mensual de ingresos, egresos, neto, conciliado y tasa |

### Grupo B — Motor de conciliación (núcleo del sistema)

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `03_conciliar_dashboard.png` | Conciliar transferencias | 1270 movimientos sin asignar, Precisión 98%, 2.455 movimientos, flujo de 3 pasos (Extracto → Cliente/planilla → Resultado), Individual / Carga masiva |
| `04_extractos_archivo.png` | Archivo de Extractos | Organización banco/año/mes (Banco Macro → 2026 → Mayo, 2.455 movs, 776 acreditados 32%), botones Ver / descargar .xlsx |
| `05_movimientos_extracto.png` | Movimientos del extracto | Tabla de 2.455 movimientos con Orden/Fecha/Titular-CUIT/Importe/Saldo/Cliente, asiento agrupado, Agregar/Borrar UM, filas UM en verde |
| `06_conciliaciones.png` | Conciliaciones | 776 movimientos conciliados, total $211.689.798,03, filtros por cliente/titular/fecha/monto, transferencias asignadas a clientes |
| `07_historial.png` | Historial | 46 planillas, 822/857 (96%), tarjetas por planilla (Alojando 19/19 OK 100%, Green 40/42 OK 95%) con Ver/Editar, Re-conciliar, Exportar |

### Grupo C — Gestión de clientes

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `08_clientes.png` | Clientes | Cartera organización de producción (14 clientes, 46 conciliaciones), chips comisión 2%, botones Estado / Cta. cte. / Acreditar / editar / fusionar |

### Grupo D — Módulo de cheques (ciclo contable completo)

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `09_cheques_listado.png` | Cheques | Stats Pendientes/Acreditados ($7.422.528,75)/Rechazados, tabs Todos/Por depósito/Rechazados/Carga masiva, importar/exportar Excel |
| `10_cheques_editar.png` | Editar cheque (modal) | Cliente, portador, librador, banco origen, monto, **comisión auto-calculada 2% = $139.450,58**, código postal + Local/Interior, fechas emisión/depósito |

### Grupo E — Módulo de pagos (egresos unificados)

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `11_pagos_nuevo.png` | Nuevo pago | Tipo (Proveedor/Gasto/Pago a cliente), forma de pago (Banco/Efectivo), cliente, "A favor de", importe, Nro. OP, comprobante foto |
| `12_pagos_historial.png` | Pagos (historial) | Lista de pagos a clientes con montos, forma Efectivo, foto de comprobante, editar/borrar, filtros por tipo/forma/fecha |

### Grupo F — Caja y tesorería

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `13_caja_arqueo.png` | Caja (arqueo diario) | Saldo inicial $15.999.100, pagos del día -$3.442.500, caja restante $12.556.600, arqueo físico por denominación de billetes |

### Grupo G — Contabilidad y cuentas corrientes

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `14_contabilidad_modulos.png` | Contabilidad | Tabs Plan de cuentas / Reglas / **Libro diario (903 asientos)** / Sumas y saldo / Balance / Libro mayor / Clientes |
| `15_plan_cuentas_activo_pasivo.png` | Plan de cuentas (Activo/Pasivo) | Jerarquía: Banco Macro (1-1-1-3-1), Banco 2, Cheques en cartera, cuentas de cliente (2-1-2-X), Cheques depositados/a depositar |
| `16_plan_cuentas_resultado.png` | Plan de cuentas (Resultado) | Ingresos (Comisiones, Comisiones cheques 3-1-3-0), Gastos (Gastos bancarios, Gastos de rechazos 3-2-2-1) |
| `17_cuentas_corrientes.png` | Cuentas Corrientes | Cartera por cliente: saldo, último mov., estado deudor/acreedor, cuenta contable; botones Reconstruir, Reset Libro Diario, Fix fechas UTC, Ver gaps |
| `18_liquidaciones.png` | Liquidaciones | Período 05/2026 (borrador): Conciliado $234.147.876,03, Comisión $4.682.957,52, Neto $229.464.918,51 |

### Grupo H — Auditoría e inteligencia

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `22_auditoria_inteligencia.png` | Auditoría e Inteligencia | Auto-conciliadas 822/857, **tasa de éxito 95.9%**, 25 correcciones manuales, sistema de aprendizaje por patrones, actividad por tipo de operación |
| `23_auditoria_log.png` | Auditoría (Log) | Tabla de auditoría: Fecha/Usuario/Acción (INSERT/UPDATE)/Tabla/Detalles JSON, filtros por tabla y acción |

### Grupo I — Inteligencia artificial y herramientas

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `24_asistente_ia.png` | Asistente IA Cuadra | Chat flotante "IA Cuadra · datos en tiempo real", sugerencias en lenguaje natural, dictado por voz (micrófono) |

### Grupo J — Administración, seguridad y respaldo

| Archivo sugerido | Pantalla | Contenido evidenciado |
|---|---|---|
| `25_papelera.png` | Papelera de reciclaje | Backup automático activo (cron 03:00 ART), papelera vacía con restaurar/purgar |
| `26_perfil_datos.png` | Mi perfil (datos) | Datos de acceso (nombre, email), cambio de contraseña, Rol: Admin, build v3.10 |
| `27_perfil_seguridad_ia.png` | Mi perfil (seguridad e IA) | Bloqueo con PIN, notificaciones push, **Gemini IA uso diario (OCR 2/150, Chat 0/200)**, setup VAPID push (admin) |

---

## 3. COBERTURA POR MÓDULO

| Módulo del sistema | ¿Capturado? | Captura(s) |
|---|---|---|
| Resumen ejecutivo | ✓ | 01, 02 |
| Flujo de Caja | ✓ | 19, 20, 21 |
| Conciliación (dashboard) | ✓ | 03 |
| Extractos | ✓ | 04 |
| Movimientos | ✓ | 05 |
| Conciliaciones | ✓ | 06 |
| Historial | ✓ | 07 |
| Clientes | ✓ | 08 |
| Cheques | ✓ | 09, 10 |
| Pagos | ✓ | 11, 12 |
| Caja | ✓ | 13 |
| Contabilidad | ✓ | 14, 15, 16 |
| Cuentas Corrientes | ✓ | 17 |
| Liquidaciones | ✓ | 18 |
| Auditoría / Inteligencia | ✓ | 22, 23 |
| Asistente IA | ✓ | 24 |
| Papelera / Backup | ✓ | 25 |
| Perfil / Seguridad | ✓ | 26, 27 |

**Cobertura:** 18/18 módulos principales documentados visualmente ✓

---

## 4. VALOR PROBATORIO DE LAS CAPTURAS

Las capturas acreditan ante la DNDA que la obra:

1. **Está completa y funcional** — Todos los módulos operativos con datos reales.
2. **Implementa los algoritmos originales declarados:**
   - Motor de conciliación con scoring (captura 03: precisión 98%)
   - Sistema de aprendizaje por patrones (captura 22: 95.9%, patrones aprendidos)
   - Motor contable automático (captura 14: 903 asientos en libro diario)
   - Ciclo contable de cheques (capturas 09, 10, 15, 16)
   - Parser multi-banco (captura 04: extracto Banco Macro procesado)
3. **Tiene características diferenciales:**
   - Asistente IA con datos en tiempo real (captura 24)
   - OCR con control de uso (captura 27: Gemini OCR 2/150)
   - Auditoría completa con trazabilidad JSON (captura 23)
   - Soft-delete con papelera + backup automático (captura 25)
   - Modo claro/oscuro (capturas 01 vs 02)
4. **Está en uso productivo** — Datos financieros reales por más de $200M conciliados.

---

## 5. NOTA SOBRE PRIVACIDAD EN LAS CAPTURAS

Las capturas contienen datos operativos reales del sistema en producción
(nombres de clientes y montos de operatoria real). Estos datos:

- Corresponden al uso productivo del sistema por parte de la autora, no exponen datos de terceros ajenos.
- Los nombres de clientes son denominaciones de trabajo, no datos personales sensibles de individuos.
- No se exponen CUIT/CBU completos identificables de personas físicas en forma destacada.
- Para la presentación ante la DNDA, los datos refuerzan la prueba de uso productivo real.

**Recomendación opcional:** Si se prefiere mayor reserva, pueden difuminarse los
nombres de clientes y montos antes de presentar, sin que ello afecte el valor
probatorio (lo relevante es la funcionalidad demostrada, no los datos puntuales).

---

## 6. UBICACIÓN EN EL PAQUETE

Las 27 capturas se almacenan en la carpeta `CAPTURAS/` del ZIP final, nombradas
según la columna "Archivo sugerido" de la sección 2.

```
CAPTURAS/
├── 01_resumen_ejecutivo.png
├── 02_resumen_dark.png
├── 03_conciliar_dashboard.png
├── 04_extractos_archivo.png
├── 05_movimientos_extracto.png
├── 06_conciliaciones.png
├── 07_historial.png
├── 08_clientes.png
├── 09_cheques_listado.png
├── 10_cheques_editar.png
├── 11_pagos_nuevo.png
├── 12_pagos_historial.png
├── 13_caja_arqueo.png
├── 14_contabilidad_modulos.png
├── 15_plan_cuentas_activo_pasivo.png
├── 16_plan_cuentas_resultado.png
├── 17_cuentas_corrientes.png
├── 18_liquidaciones.png
├── 19_flujo_caja.png
├── 20_flujo_caja_detalle.png
├── 21_flujo_caja_6meses.png
├── 22_auditoria_inteligencia.png
├── 23_auditoria_log.png
├── 24_asistente_ia.png
├── 25_papelera.png
├── 26_perfil_datos.png
└── 27_perfil_seguridad_ia.png
```

---

*Inventario de capturas para expediente DNDA — Julieta Arrazate — Junio 2026*
