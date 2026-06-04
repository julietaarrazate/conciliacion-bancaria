# INVENTARIO DE MÓDULOS DEL SISTEMA
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Versión documentada:** v3.12 — Junio 2026

---

## TABLA MAESTRA DE MÓDULOS

| N° | Módulo | Router(s) | Modelo(s) principal(es) | Servicio(s) |
|---|---|---|---|---|
| 1 | Autenticación | auth | User, TwofaCode, LoginApproval, RevokedToken | auth, email_sender, push_service |
| 2 | Perfil de usuario | me | User, PushSubscription | push_service |
| 3 | Gestión de usuarios | admin | User | — |
| 4 | Multi-tenancy | organizaciones | Organizacion | — |
| 5 | Extractos bancarios | extractos | ExtractoBancario, MovimientoBanco | excel_parser, extracto_merger |
| 6 | Planillas de pagos | planillas | Planilla, PlanillaRow | conciliacion, excel_export, pdf_export |
| 7 | Historial | historial | Planilla, PlanillaRow | excel_export |
| 8 | Conciliaciones | historial | PlanillaRow, MovimientoBanco | conciliacion, aprendizaje |
| 9 | Clientes | clientes_dir | Cliente, PlanCuenta | motor_contable |
| 10 | Cheques | cheques | Cheque, Portador | motor_contable, storage |
| 11 | Caja y arqueos | caja | ArqueoDiario | motor_contable |
| 12 | Egresos y pagos | pagos | Egreso, CategoriaEgreso | motor_contable, storage |
| 13 | Liquidaciones | liquidaciones | Liquidacion, LiquidacionDetalle | — |
| 14 | Contabilidad | contabilidad | PlanCuenta, Asiento, AsientoDetalle | motor_contable |
| 15 | Cuentas corrientes | contabilidad | Asiento, AsientoDetalle, Cliente | motor_contable |
| 16 | Análisis y reportes | analisis | (lectura multi-modelo) | — |
| 17 | Auditoría | auditoria | AuditoriaLog | auditoria |
| 18 | Búsqueda global | search | (multi-modelo) | — |
| 19 | Asistente IA | agente | (lectura multi-modelo) | — |
| 20 | OCR | agente | Cheque, Egreso | storage |
| 21 | Notificaciones push | push_router | PushSubscription | push_service |
| 22 | Acceso público | public_router | Planilla, PlanillaRow, Cliente | pdf_export |
| 23 | Papelera de reciclaje | papelera | (multi-modelo) | — |
| 24 | Backup | backup_admin | — | backup_service |
| 25 | Aprobaciones de sesión | auth | LoginApproval | push_service, email_sender |

---

## DETALLE AMPLIADO POR MÓDULO

---

### MÓDULO 1 — AUTENTICACIÓN Y SEGURIDAD

**Objetivo:** Gestionar el acceso al sistema con múltiples mecanismos de seguridad.

**Funcionalidades:**
- Login con usuario y contraseña (hash pbkdf2_sha256)
- Emisión de JWT con expiración configurable (8h estándar, 4h para contador)
- Verificación 2FA por email (código 6 dígitos, TTL 10 min) para roles Admin y Superadmin
- Flujo de login por aprobación para rol Contador (sin token inmediato)
- Recuperación de contraseña por email con link de un solo uso
- Revocación explícita de tokens (tabla `revoked_tokens`)
- Rate limiting en endpoints de autenticación (3 intentos de 2FA por minuto)
- Cleanup automático de tokens vencidos al arrancar

**Dependencias:** Resend (email 2FA), Web Push (notificación de aprobación)

---

### MÓDULO 2 — PERFIL DE USUARIO

**Objetivo:** Permitir al usuario gestionar su propia cuenta y configurar notificaciones.

**Funcionalidades:**
- Ver y editar datos propios (nombre, email)
- Configurar PIN de bloqueo de pantalla
- Activar/desactivar notificaciones push (suscripción VAPID)
- Generar claves VAPID para configuración del sistema (solo superadmin)
- Enviar push de prueba (solo superadmin)

---

### MÓDULO 3 — GESTIÓN DE USUARIOS

**Objetivo:** Administrar usuarios del sistema y sus permisos.

**Funcionalidades:**
- Crear, editar y eliminar usuarios
- Asignar roles (superadmin, admin, operador, revisor, auditor, contador)
- Asignar organización principal y organizaciones accesibles adicionales
- Habilitar/deshabilitar cuentas
- Filtrar usuarios por organización activa
- Visualizar columna de organización asignada

**Dependencias:** organizaciones, permisos `manage_users`

---

### MÓDULO 4 — MULTI-TENANCY (ORGANIZACIONES)

**Objetivo:** Soportar múltiples organizaciones con aislamiento completo de datos.

**Funcionalidades:**
- Crear y gestionar organizaciones
- Configuración JSON por organización (reglas de conciliación, tolerancias, modo de asiento)
- Superadmin ve y opera todas las organizaciones
- Usuarios normales solo ven su organización asignada
- Contadores pueden operar en organizaciones adicionales de su whitelist
- Selector de organización activa en el sidebar

---

### MÓDULO 5 — EXTRACTOS BANCARIOS

**Objetivo:** Importar y gestionar extractos de cuentas bancarias en múltiples formatos.

**Funcionalidades:**
- Importación de archivos Excel (.xlsx, .xls) con auto-detección de formato bancario
- Soporte para múltiples instituciones bancarias (parsers especializados por banco)
- Deduplicación automática de movimientos al fusionar extractos
- Renombrado inline del nombre del archivo
- Validación post-parse (rechazo si 0 movimientos o montos todos cero)
- Listado con paginación y filtros
- Generación automática de asientos contables al importar (módulo `um_lote`)
- Reversión completa al borrar un lote (asiento reverso, desvinculación de planillas)
- Renumeración automática de `orden` al eliminar un movimiento

**Dependencias:** excel_parser, extracto_merger, motor_contable

---

### MÓDULO 6 — PLANILLAS DE PAGOS

**Objetivo:** Importar planillas de pagos de clientes y gestionarlas hasta su conciliación.

**Funcionalidades:**
- Carga de archivos Excel por cliente
- Carga masiva con auto-conciliación al subir
- Edición inline de filas individuales o en lote
- Exportación al formato Excel requerido para el contador
- Exportación PDF de estado de cuenta por cliente
- Visualización paginada (100 filas por página)
- Eliminación con soft delete (preserva en papelera)
- Descarga del archivo original importado

**Dependencias:** conciliacion, excel_export, pdf_export

---

### MÓDULO 7 — MOTOR DE CONCILIACIÓN

**Objetivo:** Automatizar la asignación de movimientos bancarios a filas de planillas.

**Funcionalidades:**
- Scoring multi-criterio (CUIT, CBU, número de cuenta, referencia, titular)
- Tolerancia de fechas configurable (default: 5 días)
- Regla de seguridad para montos duplicados (exige identidad)
- Aprendizaje por patrones de correcciones manuales (2+ confirmaciones → auto-aplica)
- Re-conciliación desde el historial con nueva fecha de acreditación
- Generación de asiento `um_reclass` al conciliar un movimiento bancario
- Descarte de planillas eliminadas en el proceso de conciliación

**Dependencias:** aprendizaje, motor_contable

---

### MÓDULO 8 — CLIENTES

**Objetivo:** Gestionar el directorio de entidades que realizan pagos al sistema.

**Funcionalidades:**
- Alta, baja y modificación de clientes
- Búsqueda con normalización de nombres (mayúscula inicial, coincidencia insensible)
- Campo CUIT con validación de formato
- Porcentaje de comisión general, por tipo local e interior
- Vinculación con cuenta contable (1:1)
- Botón de creación inline desde el formulario de cheques
- Botón de cuenta corriente con deep-link al módulo de contabilidad
- Renombrar cliente con propagación a movimientos
- Fusionar clientes (reasigna planillas + movimientos al destino)

**Dependencias:** motor_contable

---

### MÓDULO 9 — CHEQUES

**Objetivo:** Gestionar el ciclo de vida completo de cheques de terceros.

**Funcionalidades:**

**Registro:**
- Formulario con cliente, portador, librador, banco, número, CP, fecha de emisión/depósito
- Auto-clasificación local/interior por código postal (CP < 2000 → local)
- OCR automático desde foto (número, banco, librador, monto, fechas)
- Comisión calculada automáticamente desde porcentaje del cliente (local/interior/general)
- Asiento automático: Cheques en cartera (D) / Cliente (H) / Comisiones (H)
- Requiere que el cliente tenga cuenta contable vinculada

**Depósito y acreditación:**
- Tab "Por depósito" con selector de fecha
- Acreditación masiva con selector de banco
- Asiento automático: Banco elegido (D) / Cheques depositados (H) + reversión del tránsito

**Rechazo:**
- Solo desde estado `acreditado`
- Campo gastos bancarios
- 3 asientos automáticos: reversión bancaria + reapertura deuda + gasto por rechazo

**Vistas adicionales:**
- Tab "Todos" con filtros
- Tab "Rechazados"
- Export Excel con filtros (estado, cliente, rango de fechas)
- Edición inline de cheques en estado `registrado`
- Compartir por WhatsApp (foto adjunta vía Web Share API)

**Dependencias:** motor_contable, storage

---

### MÓDULO 10 — CAJA Y ARQUEOS

**Objetivo:** Registrar el movimiento de dinero en efectivo con arqueos diarios.

**Funcionalidades:**
- Arqueo diario con registro de denominaciones de billetes
- Cierre y apertura de arqueos
- Operaciones de caja con descripción y asiento automático
- Exportación de movimientos (EFT)
- Eliminación de operaciones (reverso de asiento, restauración de denominaciones)
- Operaciones accesibles por superadmin con `org_id` para multi-org

**Dependencias:** motor_contable

---

### MÓDULO 11 — EGRESOS Y PAGOS

**Objetivo:** Registrar todos los egresos del sistema de forma unificada.

**Funcionalidades:**
- Tipos de egreso: pago a proveedor, gasto operativo, pago a cliente
- Forma de pago: banco o efectivo
- Campo "A favor de" para identificar el destinatario del pago bancario
- Campo "Nro. OP" (número de orden de pago)
- Adjunto de comprobante fotográfico con OCR automático
- Compartir comprobante por WhatsApp (imagen o PDF)
- Categorías de egresos editables por usuario
- Asiento automático según tipo (banco/efectivo/cliente)
- Edición inline de egresos existentes (con reversión y regeneración de asiento)
- Lazy loading de datos auxiliares (clientes/categorías)

**Dependencias:** motor_contable, storage

---

### MÓDULO 12 — LIQUIDACIONES

**Objetivo:** Generar resúmenes periódicos de operaciones con cálculo de comisiones.

**Funcionalidades:**
- Selección de período (fecha desde/hasta)
- Cálculo de comisión ítem por ítem (comisión propia del ítem → del cliente → del form)
- Presets de comisión (1.5% / 1.8% / 2%) y porcentaje manual
- Inclusión solo de planillas (TT)
- Estados: borrador → aprobada → pagada
- Eliminación de borradores para regenerar con distinta configuración
- Aprobación y pago requieren permiso `manage_users`
- Filtro de planillas por `fecha_acred` (fallback a `fecha_carga` si NULL)

---

### MÓDULO 13 — CONTABILIDAD

**Objetivo:** Mantener el libro diario de partida doble y las cuentas contables.

**Funcionalidades:**

**Plan de cuentas:**
- Árbol jerárquico de cuentas
- Identificación de cuentas hoja (sin hijos) para asientos
- PLAN_PATCH idempotente para agregar cuentas en cada deploy

**Libro diario:**
- Listado de asientos con orden DESC por `numero_asiento`
- Filtros tipo Excel (fecha rango, módulo, cuenta)
- Chips de filtros activos
- Ajuste manual de asientos (solo cuentas hoja, validación partida doble)
- Eliminación no destructiva (asiento reverso `ajuste_manual_reverso`)
- Reset y reconstrucción completa del libro diario (dry_run primero)
- Fix de fechas bidireccional (adelantar/atrasar por rango, dry_run)

**Módulos de asiento automáticos:**

| Módulo | Disparador |
|---|---|
| `um_lote` | Importar extracto bancario |
| `um_reclass` | Conciliar planilla con movimiento bancario |
| `cheque_registro` | Registrar cheque |
| `cheque_acred_banco` + `cheque_acred_cliente` | Acreditar cheque |
| `cheque_rechazo_banco` + `cheque_rechazo_cliente` + `cheque_rechazo_gasto` | Rechazar cheque |
| `egreso` | Registrar egreso/pago |
| `caja_op` | Operación de caja |
| `cc_inicial` | Backfill histórico (conciliaciones previas) |
| `ajuste_manual` | Ajuste manual desde la interfaz |
| `*_reverso` | Reversión de cualquier asiento anterior |

**Vinculación cliente↔cuenta:**
- Vinculación manual 1:1 cliente → cuenta contable
- Botón "Crear cuentas faltantes" masivo
- Backfill desde conciliaciones históricas

**Dependencias:** motor_contable

---

### MÓDULO 14 — CUENTAS CORRIENTES

**Objetivo:** Visualizar el saldo y los movimientos de cada cliente derivados del libro diario.

**Funcionalidades:**
- Cartera global: saldo por cliente, último movimiento, estado (deudor/acreedor/equilibrado/sin actividad)
- Detalle por cliente: timeline con filtros por tipo de operación
- Columnas: débito, crédito, saldo acumulado
- Links a planilla y movimiento originales
- Totales en cabecera (débito/crédito/saldo)
- Botón de acceso desde el directorio de clientes

---

### MÓDULO 15 — REPORTES Y ANÁLISIS

**Objetivo:** Proveer información gerencial y operativa en formatos visuales y exportables.

**Sub-módulos:**
- **Resumen ejecutivo:** métricas clave del período, gráficos interactivos
- **Estado de cuenta por cliente:** PDF exportable con todas las operaciones del período
- **Flujo de caja:** gráfico de líneas de ingresos vs egresos
- **Revisión:** vista de control pre-cierre

**Alertas inteligentes:**
- Cheques urgentes (vence ≤3 días)
- Cheques vencidos
- Filas de planilla atrasadas (sin conciliar)
- Movimientos bancarios sin asignar

---

### MÓDULO 16 — AUDITORÍA

**Objetivo:** Mantener un registro inmutable de todas las operaciones del sistema.

**Funcionalidades:**
- Log automático generado por el servicio `auditoria.py` en cada operación
- Vista filtrable por acción, entidad, usuario, rango de fechas
- Exportación del log (solo lectura para roles con `view_audit`)
- Serialización recursiva de tipos Decimal para persistencia en JSON

---

### MÓDULO 17 — BÚSQUEDA GLOBAL

**Objetivo:** Localizar registros de cualquier módulo desde una interfaz unificada.

**Funcionalidades:**
- Atajo de teclado ⌘K / Ctrl+K
- Búsqueda simultánea en clientes, planillas, movimientos bancarios y cheques
- Resultados con tipo de entidad y navegación directa

---

### MÓDULO 18 — ASISTENTE DE INTELIGENCIA ARTIFICIAL

**Objetivo:** Responder consultas en lenguaje natural sobre los datos del sistema.

**Funcionalidades:**
- Chat conversacional con función de historial
- Function calling con acceso a datos reales de la base de datos
- Funciones disponibles: `consultar_pagos_cliente`, `consultar_cheques`, `consultar_saldo_caja`, `buscar_cliente`, `resumen_financiero`
- Dictado por voz (SpeechRecognition API nativa, Chrome/Android)
- Botón flotante con logo del sistema, auto-hide al scrollear
- Manejo de errores de API (clave inválida, cuota, modelo no disponible)
- Reintento automático ante errores de límite por minuto

**Dependencias:** Google Gemini Flash API

---

### MÓDULO 19 — OCR (RECONOCIMIENTO ÓPTICO DE CARACTERES)

**Objetivo:** Extraer datos automáticamente de documentos fotográficos.

**Sub-módulos:**
- **OCR de cheques:** número de cheque, banco, librador, monto, fecha de emisión, fecha de depósito
- **OCR de comprobantes:** monto, fecha, beneficiario, referencia de transferencia

**Características técnicas:**
- Compresión de imagen en canvas JPEG con fondo blanco antes de envío
- Parseo de formato de montos argentinos (helpers `parseMonto()`)
- Pre-llenado solo de campos vacíos (no sobreescribe datos ya ingresados)
- Fallback silencioso ante errores de API

**Dependencias:** Google Gemini Flash Vision

---

### MÓDULO 20 — NOTIFICACIONES PUSH

**Objetivo:** Enviar alertas proactivas a los dispositivos de los usuarios.

**Funcionalidades:**
- Suscripción desde `/perfil` (requiere PWA instalada)
- Alertas programadas (03:00 ART): cheques por vencer y movimientos sin conciliar
- Notificaciones instantáneas: aprobación de sesión de contador
- Push de prueba desde el panel de administración
- Manejo del Service Worker para recibir push en background

**Dependencias:** pywebpush (VAPID), VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY

---

### MÓDULO 21 — ACCESO PÚBLICO

**Objetivo:** Permitir a clientes externos ver su estado de cuenta sin autenticación.

**Funcionalidades:**
- Generación de token de 7 días por planilla (`/p/:token`)
- Vista de estado de cuenta en formato público (sin datos internos)
- Descarga de PDF desde la vista pública
- Ruta `/privacidad` y `/terminos` públicas (Ley 25.326 Argentina)

---

### MÓDULO 22 — PAPELERA DE RECICLAJE

**Objetivo:** Preservar registros eliminados con posibilidad de recuperación.

**Funcionalidades:**
- Soft delete en planillas, extractos, clientes, cheques y egresos
- Vista de papelera con todos los registros eliminados
- Recuperación con reversión contable del asiento asociado
- Purgado definitivo (solo Admin/Superadmin)

---

### MÓDULO 23 — BACKUP Y RECUPERACIÓN

**Objetivo:** Garantizar la preservación de los datos del sistema.

**Funcionalidades:**
- Backup diario automático (03:00 ART) en formato JSON gzipeado
- Envío por email al superadmin (Resend)
- Export JSON completo bajo demanda desde el panel de admin
- Documentación de procedimientos de recuperación

---

*Documento generado para expediente de registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
