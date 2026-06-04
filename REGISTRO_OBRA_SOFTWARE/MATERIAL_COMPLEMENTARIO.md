# MATERIAL COMPLEMENTARIO PARA EL REGISTRO
## Guía de capturas de pantalla, diagramas y evidencia visual

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## 1. CAPTURAS DE PANTALLA RECOMENDADAS

### Criterios generales
- Resolución mínima: 1280×720 px
- Formato: PNG (preferido) o JPG alta calidad
- Incluir tanto modo claro como modo oscuro si es posible
- Los datos deben ser de prueba (no datos reales de clientes)
- Sistema en producción o entorno staging con datos de ejemplo

---

### 1.1 Pantallas de Autenticación y Seguridad

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 1 | Pantalla de login | `01_login.png` | Identifica la interfaz de entrada al sistema | **Alta** |
| 2 | Pantalla de 2FA (código por email) | `02_login_2fa.png` | Evidencia el mecanismo de seguridad 2FA | Media |
| 3 | Pantalla de bloqueo PIN | `03_bloqueo_pin.png` | Muestra la seguridad de dispositivo | Media |
| 4 | Pantalla de recuperación de contraseña | `04_recuperar_password.png` | Evidencia el flujo de autogestión | Baja |

---

### 1.2 Dashboard y Navegación Principal

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 5 | Dashboard principal | `05_dashboard.png` | Vista central del sistema — identifica la obra | **Alta** |
| 6 | Dashboard con onboarding checklist | `06_dashboard_onboarding.png` | Muestra la guía de primeros pasos | Media |
| 7 | Dashboard con alertas activas | `07_dashboard_alertas.png` | Evidencia el sistema de alertas inteligentes | Media |
| 8 | Menú lateral (sidebar) completo | `08_sidebar_menu.png` | Muestra todos los módulos disponibles | **Alta** |
| 9 | Búsqueda global (⌘K) | `09_busqueda_global.png` | Evidencia la función de búsqueda unificada | Media |

---

### 1.3 Gestión de Organizaciones y Usuarios

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 10 | Lista de organizaciones | `10_organizaciones.png` | Evidencia el sistema multi-empresa | **Alta** |
| 11 | Gestión de usuarios | `11_usuarios.png` | Muestra el control de acceso por roles | **Alta** |
| 12 | Detalle de usuario con roles y permisos | `12_usuario_roles.png` | Evidencia el modelo de permisos en 3 capas | Media |

---

### 1.4 Módulo de Extractos y Conciliación

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 13 | Lista de extractos bancarios | `13_extractos_lista.png` | Evidencia la gestión de extractos multi-banco | **Alta** |
| 14 | Dashboard con planilla conciliada (filas OK) | `14_planilla_conciliada.png` | Muestra el resultado de la conciliación automática | **Alta** |
| 15 | Planilla con filas pendientes (mix OK/pendiente) | `15_planilla_pendientes.png` | Evidencia el estado mixto de conciliación | **Alta** |
| 16 | Panel de carga masiva (Bulk) | `16_carga_masiva.png` | Muestra la funcionalidad de importación múltiple | Media |
| 17 | Historial de planillas | `17_historial_planillas.png` | Vista del historial de operaciones | Media |

---

### 1.5 Módulo de Clientes

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 18 | Lista de clientes con chips de comisión | `18_clientes_lista.png` | Evidencia el directorio con configuración de comisiones | **Alta** |
| 19 | Modal de edición de cliente | `19_cliente_edicion.png` | Muestra la gestión de datos del cliente | Media |

---

### 1.6 Módulo de Cheques

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 20 | Lista de cheques — tab "Todos" | `20_cheques_lista.png` | Evidencia el módulo de gestión de cheques | **Alta** |
| 21 | Formulario de nuevo cheque | `21_cheque_formulario.png` | Muestra la carga con datos del cheque | **Alta** |
| 22 | Tab "Por depósito" con agrupación | `22_cheques_por_deposito.png` | Evidencia la agrupación por fecha de depósito | **Alta** |
| 23 | Tab "Rechazados" | `23_cheques_rechazados.png` | Muestra el tracking de rechazos | Media |
| 24 | OCR en proceso (formulario con datos pre-cargados) | `24_cheque_ocr.png` | Evidencia la lectura automática con IA | **Alta** |
| 25 | Modal de acreditación masiva | `25_cheques_acreditar.png` | Muestra la operación masiva | Media |

---

### 1.7 Módulo de Caja y Egresos

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 26 | Caja — arqueo del día con denominaciones | `26_caja_arqueo.png` | Evidencia el módulo de caja con denominaciones | **Alta** |
| 27 | Lista de egresos/pagos | `27_pagos_lista.png` | Muestra el módulo unificado de egresos | **Alta** |
| 28 | Formulario de nuevo egreso con OCR | `28_pago_formulario_ocr.png` | Evidencia el OCR en comprobantes de transferencia | **Alta** |

---

### 1.8 Módulo de Contabilidad

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 29 | Plan de cuentas jerárquico | `29_plan_cuentas.png` | Evidencia el sistema contable con plan propio | **Alta** |
| 30 | Libro diario con asientos | `30_libro_diario.png` | Vista central de la contabilidad | **Alta** |
| 31 | Libro diario con filtros activos | `31_libro_diario_filtros.png` | Muestra la funcionalidad de filtrado tipo Excel | Media |
| 32 | Modal de ajuste manual de asiento | `32_asiento_manual.png` | Evidencia el ajuste contable | Media |
| 33 | Cuentas corrientes — cartera global | `33_cuentas_corrientes_cartera.png` | Vista de saldos por cliente | **Alta** |
| 34 | Detalle de cuenta corriente de cliente | `34_cuenta_corriente_detalle.png` | Timeline de movimientos de un cliente | **Alta** |
| 35 | Vinculación cliente↔cuenta contable | `35_clientes_cuentas.png` | Evidencia la vinculación contable | Media |

---

### 1.9 Módulo de Liquidaciones

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 36 | Lista de liquidaciones | `36_liquidaciones.png` | Evidencia el módulo de liquidaciones | **Alta** |
| 37 | Detalle de liquidación con comisiones | `37_liquidacion_detalle.png` | Muestra el cálculo de comisiones | Media |

---

### 1.10 Módulo de Auditoría

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 38 | Log de auditoría con registros | `38_auditoria.png` | Evidencia el registro inmutable | **Alta** |
| 39 | Detalle de un registro de auditoría (antes/después) | `39_auditoria_detalle.png` | Muestra el nivel de detalle del log | Media |

---

### 1.11 Asistente de IA

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 40 | Asistente IA abierto con conversación | `40_ia_chat.png` | Evidencia la funcionalidad de IA conversacional | **Alta** |
| 41 | Resultado de consulta IA con datos reales | `41_ia_resultado.png` | Muestra el function calling con datos del sistema | **Alta** |

---

### 1.12 Reportes y Análisis

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 42 | Resumen ejecutivo mensual | `42_resumen_mensual.png` | Evidencia los reportes gerenciales | Media |
| 43 | Estado de cuenta de cliente (PDF generado) | `43_estado_cuenta_pdf.png` | Muestra el reporte exportable | Media |
| 44 | Flujo de caja con gráfico | `44_flujo_caja.png` | Evidencia los gráficos financieros | Media |

---

### 1.13 Configuración y Perfil

| N° | Pantalla | Nombre de archivo sugerido | Motivo | Prioridad |
|---|---|---|---|---|
| 45 | Perfil de usuario | `45_perfil.png` | Muestra la gestión de cuenta y push | Baja |
| 46 | Landing page del sistema | `46_landing.png` | Evidencia la presencia web pública | Media |

---

## 2. EVIDENCIA FUNCIONAL POR PROCESO

### 2.1 Proceso de conciliación bancaria (secuencia de 3 capturas)

```
01. Antes:  extracto importado + planilla con filas PENDIENTE
            → captura: 15_planilla_pendientes.png

02. Durante: asignación manual de un movimiento a una fila
             → captura nueva: 50_conciliacion_asignacion_manual.png

03. Después: planilla con todas las filas OK
             → captura: 14_planilla_conciliada.png
```

### 2.2 Proceso OCR de cheque (secuencia de 2 capturas)

```
01. Formulario vacío con foto adjuntada
    → captura nueva: 51_ocr_foto_adjunta.png

02. Formulario con campos pre-completados por OCR
    → captura: 24_cheque_ocr.png
```

### 2.3 Proceso de generación de asiento contable (secuencia de 2 capturas)

```
01. Operación registrada (ej: importar extracto)
    → captura: 13_extractos_lista.png

02. Libro diario mostrando el asiento generado
    → captura: 30_libro_diario.png
```

---

## 3. MATERIAL TÉCNICO COMPLEMENTARIO

### 3.1 Diagrama de arquitectura

**Archivo:** `DIAGRAMAS/arquitectura_sistema.png`

**Contenido mínimo:**
- 3 capas: Presentación (Web/Móvil) → API (FastAPI) → Base de datos (PostgreSQL)
- Servicios externos conectados: Gemini AI, Resend, S3/R2, Sentry, Web Push
- Flechas con protocolos: HTTPS, SQL

**Herramienta sugerida:** draw.io (app.diagrams.net — gratuito), Excalidraw, Figma

### 3.2 Diagrama de base de datos (ER simplificado)

**Archivo:** `DIAGRAMAS/base_de_datos_er.png`

**Entidades a incluir (al menos las principales):**
- Organizacion ← User, Cliente
- ExtractoBancario → MovimientoBanco
- Planilla → PlanillaRow ← Cliente
- Cheque ← Cliente, Portador
- Asiento → AsientoDetalle ← PlanCuenta
- ArqueoDiario, Egreso, Liquidacion

**Herramienta sugerida:** dbdiagram.io, draw.io, pgAdmin (genera ER automáticamente)

### 3.3 Diagrama de módulos

**Archivo:** `DIAGRAMAS/modulos_sistema.png`

**Contenido:**
- 23 módulos organizados por área:
  - Seguridad y acceso
  - Operaciones bancarias
  - Contabilidad
  - Reportes
  - IA y OCR
  - Infraestructura

### 3.4 Diagrama de flujo de conciliación

**Archivo:** `DIAGRAMAS/flujo_conciliacion.png`

**Contenido:**
```
INICIO
  ↓
Importar extracto bancario (Excel)
  ↓
Parser detecta formato del banco
  ↓
Extraer movimientos → Deduplicar → Numerar
  ↓
Importar planilla de pagos
  ↓
Para cada fila de planilla:
  ├─ Buscar patrones aprendidos → match? → CONCILIADO
  └─ Calcular scoring multi-criterio
      ├─ Score ≥ umbral → CONCILIADO (asigna movimiento)
      ├─ Score medio → REVISAR (propone candidato)
      └─ Score bajo → PENDIENTE
  ↓
Generar asiento contable (um_reclass)
  ↓
FIN: Planilla con estado por fila
```

---

## 4. ESTRUCTURA RECOMENDADA DEL ZIP FINAL

```
REGISTRO_OBRA_SOFTWARE_v3.12.zip
│
├── DOCUMENTACION/
│   ├── 00_README_REGISTRO.md (o .pdf)
│   ├── 01_MEMORIA_DESCRIPTIVA.pdf          ← IMPRESCINDIBLE
│   ├── 02_EVIDENCIA_AUTORIA.pdf            ← IMPRESCINDIBLE
│   ├── 03_INVENTARIO_TECNICO.pdf           ← IMPRESCINDIBLE
│   ├── 04_ACTIVOS_PI.pdf
│   ├── 05_DOCUMENTACION_TECNICA.pdf
│   ├── 06_MANUAL_FUNCIONAL.pdf
│   ├── 07_MODULOS_DEL_SISTEMA.pdf
│   ├── 08_RESUMEN_EJECUTIVO.pdf
│   └── 09_EXPEDIENTE_FINAL.pdf
│
├── SOFTWARE/
│   ├── backend/                            ← código Python (limpio)
│   ├── frontend/                           ← código React/TS (limpio)
│   └── mobile/                             ← código React Native (limpio)
│
├── CAPTURAS/
│   ├── 01_login.png
│   ├── 05_dashboard.png
│   ├── 08_sidebar_menu.png
│   ├── 10_organizaciones.png
│   ├── 11_usuarios.png
│   ├── 13_extractos_lista.png
│   ├── 14_planilla_conciliada.png
│   ├── 15_planilla_pendientes.png
│   ├── 18_clientes_lista.png
│   ├── 20_cheques_lista.png
│   ├── 21_cheque_formulario.png
│   ├── 22_cheques_por_deposito.png
│   ├── 24_cheque_ocr.png
│   ├── 26_caja_arqueo.png
│   ├── 27_pagos_lista.png
│   ├── 28_pago_formulario_ocr.png
│   ├── 29_plan_cuentas.png
│   ├── 30_libro_diario.png
│   ├── 33_cuentas_corrientes_cartera.png
│   ├── 34_cuenta_corriente_detalle.png
│   ├── 36_liquidaciones.png
│   ├── 38_auditoria.png
│   ├── 40_ia_chat.png
│   └── 41_ia_resultado.png
│
├── DIAGRAMAS/
│   ├── arquitectura_sistema.png
│   ├── base_de_datos_er.png
│   ├── modulos_sistema.png
│   └── flujo_conciliacion.png
│
└── HISTORIAL_GIT.txt
```

---

## 5. EVIDENCIA DE VERSIÓN

| Campo | Valor |
|---|---|
| **Commit registrado** | `b846c1753aac4363321311537f74a47fe96569c4` |
| **Hash corto** | `b846c17` |
| **Tag recomendado** | `v3.12-registro` |
| **Versión del sistema** | v3.12 |
| **Fecha** | Junio 2026 |
| **Rama** | `main` (post-merge del PR #111) |

Para verificar el commit en cualquier momento:
```bash
git show b846c1753aac4363321311537f74a47fe96569c4 --stat
```

---

## 6. CHECKLIST DE MATERIAL COMPLEMENTARIO

### Capturas de prioridad Alta (mínimo recomendado)

- [ ] `01_login.png`
- [ ] `05_dashboard.png`
- [ ] `08_sidebar_menu.png`
- [ ] `10_organizaciones.png`
- [ ] `11_usuarios.png`
- [ ] `13_extractos_lista.png`
- [ ] `14_planilla_conciliada.png`
- [ ] `15_planilla_pendientes.png`
- [ ] `18_clientes_lista.png`
- [ ] `20_cheques_lista.png`
- [ ] `21_cheque_formulario.png`
- [ ] `22_cheques_por_deposito.png`
- [ ] `24_cheque_ocr.png`
- [ ] `26_caja_arqueo.png`
- [ ] `27_pagos_lista.png`
- [ ] `28_pago_formulario_ocr.png`
- [ ] `29_plan_cuentas.png`
- [ ] `30_libro_diario.png`
- [ ] `33_cuentas_corrientes_cartera.png`
- [ ] `34_cuenta_corriente_detalle.png`
- [ ] `36_liquidaciones.png`
- [ ] `38_auditoria.png`
- [ ] `40_ia_chat.png`
- [ ] `41_ia_resultado.png`

### Diagramas

- [ ] `arquitectura_sistema.png`
- [ ] `base_de_datos_er.png`
- [ ] `modulos_sistema.png`
- [ ] `flujo_conciliacion.png`

---

*Documento elaborado para expediente de registro de obra de software — Julieta Arrazate — Junio 2026*
