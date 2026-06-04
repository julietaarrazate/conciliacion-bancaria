# PLAN DE CAPTURAS DE PANTALLA
## Screenshots para evidencia visual del sistema funcionando

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12

---

## 1. PROPÓSITO DE LAS CAPTURAS

Las capturas de pantalla sirven para:
- Evidenciar que el sistema está **completo y funcional**
- Demostrar la **interfaz de usuario** y experiencia
- Mostrar los **módulos principales** en operación
- Acreditar **originalidad en la UX** (diseño personalizado)
- Complementar la documentación técnica con evidencia visual

**Cantidad:** 24 capturas (3-4 por módulo principal)  
**Formato:** PNG con resolución 1280×720 o superior (landscape)  
**Nombre archivo:** `NN_descripcion_corta.png` (ej: `01_login.png`, `02_dashboard.png`)

---

## 2. CAPTURAS DE AUTENTICACIÓN Y BIENVENIDA

### 01_login.png
- **Módulo:** Autenticación
- **Vista:** Página de Login
- **Contenido a capturar:**
  - Formulario de email/contraseña
  - Botón "Ingresar"
  - Texto "¿Olvidaste tu contraseña?"
  - Logo de Cuadra (arriba a la izquierda)
  - Fondo con gradiente (Linear-inspired)
- **Usuario sugerido:** Loguearse con `admin@demo.com`

### 02_dashboard_overview.png
- **Módulo:** Dashboard
- **Vista:** Vista general del Dashboard
- **Contenido a capturar:**
  - Encabezado con nombre de usuario y org
  - Sidebar izquierdo con menú principal (todas las opciones visibles)
  - Área principal con tarjetas de resumen (Extractos, Planillas, Movimientos, etc.)
  - Gráficos de línea/barras con datos de ejemplo
  - Onboarding checklist (si aplica)
- **Nota:** Captura en modo claro (light mode)

### 03_dashboard_dark.png
- **Módulo:** Dashboard
- **Vista:** Dashboard en modo oscuro
- **Contenido a capturar:**
  - Mismo dashboard que 02, pero en dark mode
  - Colores invertidos manteniendo legibilidad
  - Demostración de soporte dual light/dark
- **Nota:** Cambiar tema desde `/perfil` → Switch tema

---

## 3. CAPTURAS DE MÓDULO CONCILIACIÓN (Core)

### 04_extractos_archivo.png
- **Módulo:** Extractos
- **Vista:** Página `ExtractosArchivo`
- **Contenido a capturar:**
  - Lista de extractos bancarios subidos
  - Columnas: Archivo, Banco, Período, Movimientos, Fecha
  - Botón "+ Cargar extracto"
  - Botón de descarga/eliminación por fila
- **Nota:** Al menos 2-3 extractos en la lista

### 05_movimientos_tabla.png
- **Módulo:** Movimientos
- **Vista:** Tabla de movimientos bancarios
- **Contenido a capturar:**
  - Tabla con columnas: Orden, Fecha, Banco, Titular, Monto, Referencia
  - Filtros en encabezados (buscador de banco, fechas, etc.)
  - Botones de acción (editar, eliminar, acreditar)
  - Paginación al pie (ej: "Mostrando 50 de 1200")
- **Nota:** Usar datos demo con varios movimientos visibles

### 06_conciliacion_panel.png
- **Módulo:** Conciliaciones
- **Vista:** Panel de conciliación de planilla
- **Contenido a capturar:**
  - Tabla de filas de planilla (lado izquierdo)
  - Mostrar filas con distintos estados: PENDIENTE (rojo), OK (verde), FALTAN DATOS (amarillo)
  - Columnas: N°, Cliente, CUIT, Monto, Scoring, Estado
  - Resumen al pie (filas conciliadas / total)
- **Nota:** Evidencia del algoritmo de scoring funcionando

### 07_conciliacion_scoring.png
- **Módulo:** Conciliaciones
- **Vista:** Detalle de scoring de una fila
- **Contenido a capturar:**
  - Modal o panel lateral con scoring breakdown
  - Puntos por: CUIT exacto (+12), CBU (+10), Titular (+5), etc.
  - Movimiento candidato seleccionado
  - Botón "Aceptar conciliación"
- **Nota:** Demostración del motor de conciliación

---

## 4. CAPTURAS DE MÓDULO FINANCIERO

### 08_cheques_registro.png
- **Módulo:** Cheques
- **Vista:** Tab "Todos" con lista de cheques
- **Contenido a capturar:**
  - Tabla de cheques registrados
  - Columnas: Estado, Fecha, Cliente, Monto, Banco, Número, CP, L/I
  - Botones: Editar (✏️), Depositar, Rechazar, Borrar
  - Estados visibles: registrado, depositado, acreditado (chips de colores)
- **Nota:** Demostración del ciclo contable de cheques

### 09_cheques_deposito.png
- **Módulo:** Cheques
- **Vista:** Tab "Por depósito"
- **Contenido a capturar:**
  - Selector de fecha de depósito (dropdown)
  - Tabla de cheques agrupados por depósito
  - Resumen por local/interior (cards)
  - Botón "Acreditar (N)" y "↓ Excel"
- **Nota:** Demostración de acreditación masiva

### 10_cheques_ocr.png
- **Módulo:** Cheques
- **Vista:** Formulario de nuevo cheque con OCR
- **Contenido a capturar:**
  - Formulario con campos de cheque (número, banco, titular, monto, fechas)
  - Botón de cámara (📷) para capturar foto
  - Foto del cheque cargada (visible arriba o lateral)
  - Campos pre-llenados por OCR (números, fechas extraídos)
- **Nota:** Evidencia de la tecnología OCR de Gemini

### 11_pagos_listado.png
- **Módulo:** Pagos
- **Vista:** Tabla de egresos (pagos/gastos)
- **Contenido a capturar:**
  - Tabla con tipo de egreso: proveedor, gasto, pago_cliente
  - Columnas: Fecha, Tipo, Beneficiario, Monto, Concepto, Forma pago
  - Botones: Editar, Compartir WhatsApp, Borrar
- **Nota:** Módulo unificado de egresos

### 12_pagos_nuevo.png
- **Módulo:** Pagos
- **Vista:** Formulario de nuevo pago
- **Contenido a capturar:**
  - Selector de tipo: Pago a cliente | Gasto | Pago a proveedor
  - Campos: Beneficiario, Monto, Fecha, Concepto, Forma pago, Foto
  - Botón de cámara (📷)
  - Botón "Guardar"
- **Nota:** Demostración de captura de foto

### 13_caja_arqueo.png
- **Módulo:** Caja
- **Vista:** Panel de Arqueo diario
- **Contenido a capturar:**
  - Tablas de denominaciones (billetes/monedas)
  - Campos: Denominación, Cantidad, Subtotal
  - Total calculado automáticamente
  - Botón "Cerrar arqueo"
  - Historial de arqueos previos
- **Nota:** Funcionalidad de caja chica

---

## 5. CAPTURAS DE MÓDULO CONTABILIDAD

### 14_libro_diario.png
- **Módulo:** Contabilidad
- **Vista:** Libro Diario
- **Contenido a capturar:**
  - Tabla de asientos contables
  - Columnas: N°, Fecha, Concepto, Cuenta, Debe, Haber
  - Filtros (fecha, concepto, cuenta)
  - Total de debe = total de haber (partida doble)
- **Nota:** Evidencia de sistema contable automático

### 15_libro_mayor.png
- **Módulo:** Contabilidad
- **Vista:** Libro Mayor
- **Contenido a capturar:**
  - Tabla de movimientos por cuenta
  - Columnas: Fecha, Concepto, Debe, Haber, Saldo
  - Saldo acumulado correctamente
  - Cuentas expandibles (jerarquía de plan)
- **Nota:** Estructura de plan de cuentas

### 16_plan_cuentas.png
- **Módulo:** Contabilidad
- **Vista:** Plan de Cuentas
- **Contenido a capturar:**
  - Árbol jerárquico de cuentas (padres e hijas)
  - Estructura: 1 (Activo) > 1-1 (Corriente) > 1-1-1 (Caja y Bancos)
  - Iconos/indicadores de cuenta hoja vs. padre
  - Campos: Código, Nombre, Tipo
- **Nota:** Demostración de estructura contable completa

### 17_cuentas_corrientes.png
- **Módulo:** Cuentas Corrientes (en Contabilidad)
- **Vista:** Resumen de cartera de clientes
- **Contenido a capturar:**
  - Tabla: Cliente, Saldo, Último movimiento, Estado (deudor/acreedor)
  - Chips de estado con colores (rojo=deudor, verde=acreedor)
  - Botón "Ver detalle cta.cte." por cliente
- **Nota:** Módulo de cuentas corrientes (reemplazo de estado de cuenta)

---

## 6. CAPTURAS DE ANÁLISIS Y REPORTING

### 18_resumen_mensual.png
- **Módulo:** Resumen
- **Vista:** Resumen ejecutivo mensual
- **Contenido a capturar:**
  - Tabla de ingresos por cliente (nombre, período, monto total)
  - Gráfico de barras de ingresos mensuales
  - Indicador de variación (↑ sube / ↓ baja)
  - Total del mes
- **Nota:** Reportería de ingresos

### 19_flujo_caja.png
- **Módulo:** Flujo de Caja
- **Vista:** Proyección de flujo de caja
- **Contenido a capturar:**
  - Gráfico de línea con saldo proyectado (días futuros)
  - Movimientos estimados (ingresos/egresos)
  - Tabla resumen: Hoy, Próximos 7 días, Próximos 30 días
- **Nota:** Análisis prospectivo del flujo

### 20_estado_cuenta_cliente.png
- **Módulo:** Estado de Cuenta
- **Vista:** Estado de cuenta de cliente
- **Contenido a capturar:**
  - Encabezado: Nombre cliente, Período
  - Tabla de movimientos (cheques, pagos, planillas, transf)
  - Saldo inicial, Saldo final
  - Resumen de comisiones
- **Nota:** Documento exportable a PDF

---

## 7. CAPTURAS DE AUDITORÍA Y ADMINISTRACIÓN

### 21_auditoria_log.png
- **Módulo:** Auditoría
- **Vista:** Log de auditoría
- **Contenido a capturar:**
  - Tabla: Fecha, Usuario, Acción, Módulo, Antes/Después, IP
  - Ejemplo: "Usuario X reconcilió planilla Y"
  - Resumen de últimas acciones (últimos 50 registros)
- **Nota:** Evidencia de trazabilidad completa

### 22_usuarios_rol.png
- **Módulo:** Usuarios
- **Vista:** Gestión de usuarios y roles
- **Contenido a capturar:**
  - Tabla de usuarios: Email, Nombre, Rol (Admin/Operador/Contador), Org
  - Botones: Editar, Cambiar rol, Borrar
  - Formulario de agregar usuario
- **Nota:** Sistema de roles (ADMIN, OPERADOR, CONTADOR, REVISOR, AUDITOR)

### 23_papelera_reciclaje.png
- **Módulo:** Papelera
- **Vista:** Papelera de reciclaje
- **Contenido a capturar:**
  - Tabla de registros borrados (planillas, cheques, pagos)
  - Columnas: Tipo, Nombre/Descripción, Fecha borrado, Usuario
  - Botones: Restaurar, Borrar permanentemente
  - Información: "N elementos en papelera"
- **Nota:** Soft-delete y reversibilidad de operaciones

---

## 8. CAPTURA DE INFORMACIÓN ADICIONAL

### 24_perfil_usuario.png
- **Módulo:** Perfil
- **Vista:** Página de Perfil del usuario
- **Contenido a capturar:**
  - Datos personales: Email, Nombre
  - Campo de contraseña (nuevo/actual/confirmar)
  - Sección de seguridad: 2FA, PIN, Biometría
  - Sección de notificaciones: Activar push
  - Selector de tema: Light/Dark
- **Nota:** Demostración de seguridad (2FA, PIN, WebAuthn)

---

## 9. INSTRUCCIONES PARA CAPTURAR

### Requisitos técnicos:
- **Resolución:** 1280×720 o 1920×1080 (landscape)
- **Formato:** PNG (transparente o fondo blanco)
- **Nombre archivo:** `NN_descripcion.png` (ej: `01_login.png`)
- **Herramienta:** Screenshot nativa, Snagit, o DevTools (F12 → Ctrl+Shift+P → "Screenshot")

### Preparación del sistema:
1. Loguearse con `admin@demo.com / admin123` (cuenta demo)
2. Navegar a cada módulo mencionado
3. Crear datos demo si es necesario (extractos, planillas, cheques)
4. Capturar tanto light mode como dark mode para UI critical

### Datos demo recomendados:
- Extracto: "Banco Macro - Junio 2026.xlsx" (crear si no existe)
- Planilla: "Clientes - Junio 2026" con filas en distintos estados
- Cheques: 10-15 cheques en estados registrado, depositado, acreditado
- Pagos: 5-10 pagos/gastos con fotos adjuntas

### Post-captura:
- [ ] Guardar todas en carpeta `/expediente/CAPTURAS/`
- [ ] Cambiar nombre a `NN_descripcion.png`
- [ ] Verificar legibilidad (texto legible en pantalla pequeña)
- [ ] No incluir datos reales de clientes o movimientos
- [ ] Borrar capturas anteriores o defectuosas

---

## 10. CHECKLIST DE CAPTURAS

- [ ] 01_login.png — Página de login
- [ ] 02_dashboard_overview.png — Dashboard light mode
- [ ] 03_dashboard_dark.png — Dashboard dark mode
- [ ] 04_extractos_archivo.png — Lista de extractos
- [ ] 05_movimientos_tabla.png — Tabla de movimientos
- [ ] 06_conciliacion_panel.png — Panel de conciliación
- [ ] 07_conciliacion_scoring.png — Detalle de scoring
- [ ] 08_cheques_registro.png — Tabla de cheques
- [ ] 09_cheques_deposito.png — Tab "Por depósito"
- [ ] 10_cheques_ocr.png — Formulario con OCR
- [ ] 11_pagos_listado.png — Tabla de pagos
- [ ] 12_pagos_nuevo.png — Formulario nuevo pago
- [ ] 13_caja_arqueo.png — Panel de arqueo
- [ ] 14_libro_diario.png — Libro Diario
- [ ] 15_libro_mayor.png — Libro Mayor
- [ ] 16_plan_cuentas.png — Plan de Cuentas
- [ ] 17_cuentas_corrientes.png — Cartera de clientes
- [ ] 18_resumen_mensual.png — Resumen ejecutivo
- [ ] 19_flujo_caja.png — Flujo de Caja
- [ ] 20_estado_cuenta_cliente.png — Estado de Cuenta
- [ ] 21_auditoria_log.png — Log de auditoría
- [ ] 22_usuarios_rol.png — Gestión de usuarios
- [ ] 23_papelera_reciclaje.png — Papelera
- [ ] 24_perfil_usuario.png — Perfil y seguridad

---

## 11. NOTAS FINALES

- **Tiempo estimado:** 1.5-2 horas (capturar y renombrar)
- **Tamaño total:** ~12-15 MB (24 × 500-600 KB)
- **Prioridad:** Capturas 1-8 son imprescindibles (auth, conciliación, cheques)
- **Flexibilidad:** Si algunos módulos no tendrán datos, usar placeholders/datos demo
- **Confidencialidad:** Verificar que NO haya datos reales de clientes en las capturas

---

*Documento de plan de capturas para expediente DNDA — Julieta Arrazate — Junio 2026*
