# MEMORIA DESCRIPTIVA DE LA OBRA
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Tipo de obra:** Programa de computación (software)  
**Autora:** Julieta Arrazate  
**Email:** julietaarrazate@gmail.com  
**Nacionalidad:** Argentina  
**Versión registrada:** v3.12  
**Fecha:** Junio 2026  
**Repositorio técnico:** conciliacion-bancaria (privado)

---

## 1. NOMBRE DEL SISTEMA

**Sistema Integral de Gestión Financiera, Contable y Empresarial**

Denominación de trabajo utilizada durante el desarrollo: **Cuadra**. Esta denominación no constituye marca registrada.

El nombre técnico del repositorio es `conciliacion-bancaria`, reflejo del módulo central del sistema.

---

## 2. OBJETIVO

El sistema tiene como objetivo centralizar, automatizar e integrar la gestión financiera, contable y administrativa de organizaciones que operan con flujos de movimientos bancarios, pagos de clientes, cheques, caja y egresos.

Resuelve específicamente la problemática de:
- La **conciliación manual** de extractos bancarios contra pagos de múltiples clientes, proceso altamente propenso a errores cuando se realiza manualmente en planillas de cálculo.
- La **trazabilidad contable automática** de cada operación financiera hacia el libro diario y las cuentas corrientes.
- La **dispersión de información** en múltiples herramientas y archivos no integrados.

---

## 3. ALCANCE

El sistema abarca el ciclo completo de gestión financiero-contable de una o múltiples organizaciones, incluyendo:

1. Importación y procesamiento de extractos bancarios en múltiples formatos
2. Conciliación automática de movimientos bancarios contra planillas de pagos
3. Gestión completa del ciclo de vida de cheques (registro, depósito, acreditación, rechazo)
4. Gestión de caja con arqueos diarios y operaciones
5. Módulo de egresos unificado (gastos, pagos a clientes, proveedores)
6. Liquidaciones periódicas con cálculo de comisiones
7. Contabilidad de partida doble (libro diario, plan de cuentas, cuentas corrientes)
8. Auditoría completa de operaciones
9. Reportes, estados de cuenta y exportaciones
10. Asistente de inteligencia artificial para consultas en lenguaje natural
11. OCR automático para lectura de comprobantes y cheques
12. Gestión multi-empresa (multitenancy)
13. Aplicación web instalable (PWA) y aplicación móvil nativa

---

## 4. DESCRIPCIÓN GENERAL

El sistema es una plataforma de software web y móvil que centraliza la gestión financiera y contable de organizaciones. Está compuesto por tres capas principales:

**Capa de presentación:** Aplicación web desarrollada con React 18 y TypeScript, instalable como Progressive Web App (PWA) en dispositivos móviles, y una aplicación móvil nativa desarrollada con React Native (Expo). Ambas interfaces consumen una API REST central.

**Capa de lógica de negocio:** API REST construida con FastAPI (Python 3.11), que implementa todos los procesos de negocio, incluyendo el motor de conciliación bancaria, el motor contable automático, el motor de aprendizaje por patrones, el procesamiento de archivos Excel, la generación de reportes PDF, y la integración con servicios de IA y OCR.

**Capa de datos:** Base de datos relacional PostgreSQL con 18 modelos de datos principales, aritmética exacta (tipo Numeric 12,2 en todas las columnas financieras), e historial completo de migraciones.

---

## 5. FUNCIONALIDADES PRINCIPALES

### 5.1 Conciliación Bancaria Automatizada
Sistema de comparación automática entre movimientos de extractos bancarios y planillas de pagos de clientes. Utiliza un algoritmo de scoring multi-criterio que asigna puntuaciones según el nivel de coincidencia de identidad (CUIT, CBU, número de cuenta, nombre del titular). El sistema determina automáticamente si una fila de planilla está conciliada, pendiente o requiere revisión manual.

### 5.2 Gestión de Extractos Bancarios
Importación de extractos en formato Excel con soporte multi-banco. El sistema detecta automáticamente el formato (múltiples instituciones bancarias) y extrae los movimientos. Incluye deduplicación automática de movimientos repetidos y fusión de extractos.

### 5.3 Gestión de Planillas de Pagos
Importación de planillas de pagos de clientes en formato Excel. Carga masiva con auto-conciliación al subir. Edición inline de filas individuales o en lote. Exportación al formato requerido para el contador.

### 5.4 Ciclo Completo de Cheques
Registro, depósito, acreditación y rechazo de cheques con trazabilidad contable completa. Cada fase genera asientos automáticos en el libro diario. OCR automático para leer los datos del cheque desde una fotografía. Acreditación masiva de múltiples cheques. Exportación a Excel por fecha de depósito.

### 5.5 Módulo de Caja
Arqueos diarios con registro de denominaciones de billetes. Operaciones de caja con contabilización automática. Exportación de movimientos.

### 5.6 Módulo de Egresos/Pagos
Gestión unificada de pagos a proveedores, gastos operativos y pagos a clientes. Adjunto de comprobante fotográfico con OCR automático. Compartir comprobante por WhatsApp. Categorías de egresos configurables.

### 5.7 Liquidaciones
Generación de liquidaciones periódicas con cálculo automático de comisiones. Soporte para porcentaje de comisión por organización, por cliente, por planilla y por tipo de cheque (local/interior). Exportación a Excel.

### 5.8 Contabilidad de Partida Doble
Plan de cuentas jerárquico configurable. Generación automática de asientos contables al importar extractos, conciliar planillas, registrar cheques y registrar egresos. Libro diario con filtros avanzados. Mayor contable por cuenta. Sumas y saldos. Cuentas corrientes por cliente. Ajuste manual de asientos. Reset y reconstrucción del libro diario.

### 5.9 Auditoría
Registro automático de todas las operaciones del sistema con usuario, fecha, hora y datos antes/después. Log inmutable. Exportación para revisión externa.

### 5.10 Asistente de Inteligencia Artificial
Interfaz conversacional en lenguaje natural integrada al sistema. Permite realizar consultas sobre datos reales de la base de datos (saldos de caja, cheques pendientes, pagos por cliente, resúmenes financieros) mediante function calling. Soporte para dictado por voz.

### 5.11 OCR para Comprobantes
Extracción automática de datos desde fotografías de cheques (número, banco, librador, monto, fechas) y comprobantes de transferencia (monto, fecha, beneficiario, referencia) mediante modelos de visión artificial.

### 5.12 Reportes y Exportaciones
- Estado de cuenta por cliente (PDF)
- Resumen ejecutivo mensual (PDF)
- Flujo de caja (gráficos interactivos)
- Exportación Excel para contador
- Exportación de extractos bancarios
- Export Excel de cheques con filtros
- Backup completo del sistema (JSON gzipeado)

---

## 6. MÓDULOS DEL SISTEMA

| N° | Módulo | Descripción |
|---|---|---|
| 1 | Autenticación y Seguridad | JWT, 2FA por email, PIN de bloqueo, biometría WebAuthn |
| 2 | Gestión de Usuarios y Roles | 6 roles con permisos granulares en 3 capas |
| 3 | Multi-tenancy (Organizaciones) | Soporte multi-empresa con aislamiento completo |
| 4 | Extractos Bancarios | Importación, parser multi-banco, deduplicación |
| 5 | Planillas de Pagos | Carga, conciliación, edición, exportación |
| 6 | Motor de Conciliación | Scoring multi-criterio, aprendizaje por patrones |
| 7 | Clientes | Directorio, cuentas corrientes, comisiones, fusión |
| 8 | Cheques | Ciclo completo (registro→depósito→acreditación→rechazo) |
| 9 | Caja y Arqueos | Arqueos diarios, operaciones, denominaciones |
| 10 | Egresos/Pagos | Gastos, proveedores, pagos a clientes |
| 11 | Liquidaciones | Períodos, comisiones, aprobación, pago |
| 12 | Contabilidad | Plan cuentas, libro diario, mayor, cuentas corrientes |
| 13 | Reportes y Análisis | Resumen, estado de cuenta, flujo de caja, alertas |
| 14 | Auditoría | Log inmutable de todas las operaciones |
| 15 | Búsqueda Global | Búsqueda unificada ⌘K en toda la aplicación |
| 16 | Asistente IA | Consultas en lenguaje natural, function calling |
| 17 | OCR | Lectura de cheques y comprobantes |
| 18 | Notificaciones Push | Alertas en PWA (vencimientos, movimientos pendientes) |
| 19 | Backup y Recuperación | Backup periódico automático, papelera de reciclaje |
| 20 | Página Pública | Landing page + estado de cuenta público por token |

---

## 7. INNOVACIONES FUNCIONALES

### 7.1 Motor de Conciliación con Scoring Multi-Criterio
Algoritmo original que asigna puntuaciones diferenciadas según el nivel de identificación del pagador (CUIT, CBU, número de cuenta, nombre del titular). La suma de puntuaciones determina si una coincidencia es válida o requiere confirmación manual. Incluye tolerancia de fechas configurable y regla de seguridad para montos duplicados.

### 7.2 Aprendizaje Incremental por Patrones
El sistema aprende de las correcciones manuales del operador. Cuando una asociación manual se confirma dos o más veces, el sistema la incorpora como patrón automático y la aplica en futuras conciliaciones sin intervención humana.

### 7.3 Generación Automática de Asientos Contables
Cada operación del sistema genera asientos contables de partida doble en forma automática. El motor contable conoce el tipo de cuenta correspondiente a cada flujo financiero y registra los asientos sin requerir intervención del usuario.

### 7.4 Ciclo Contable de Cheques en 3 Fases
Sistema original que modela las tres etapas contables de un cheque de terceros: (1) recepción/registro, (2) depósito bancario y (3) acreditación o rechazo. Cada fase genera asientos diferenciados que garantizan la trazabilidad completa y el balance correcto de las cuentas de tránsito.

### 7.5 Login con Aprobación en Vivo
Flujo de autenticación original para roles externos: el usuario no recibe token inmediatamente, sino que el sistema notifica a los administradores por push y el token solo se entrega cuando un administrador aprueba la sesión manualmente. Incluye expiración diferenciada para este tipo de sesiones.

### 7.6 Contabilidad de Cuentas Corrientes Derivada de Asientos
El saldo de la cuenta corriente de cada cliente se calcula en tiempo real a partir de los asientos contables existentes, en lugar de almacenarse como dato redundante. Esta arquitectura garantiza la coherencia automática entre el libro diario y las cuentas corrientes.

---

## 8. CARACTERÍSTICAS TÉCNICAS DESTACADAS

| Característica | Descripción |
|---|---|
| **Aritmética exacta** | Columnas financieras con tipo `Numeric(12,2)` para evitar errores de punto flotante |
| **Soft delete** | Los registros eliminados se preservan en papelera, recuperables con reversión contable |
| **Aislamiento multi-tenant** | Todos los módulos respetan el `organizacion_id` activo |
| **Timezone correcto** | Todas las fechas de negocio se calculan en UTC-3 (Argentina) |
| **Retry automático** | El frontend implementa reintentos con backoff ante errores transitorios |
| **PWA instalable** | Funciona como app nativa en Android Chrome sin instalación desde store |
| **Share target** | Puede recibir archivos desde otras apps (WhatsApp, Galería) |
| **Degradación elegante** | Funciones opcionales (IA, push, email, storage) desactivables por ausencia de env vars |
| **Tests automatizados** | 156 tests que cubren conciliación, contabilidad, autenticación, parsers y timezone |
| **Seguridad hardening** | Rate limiting, headers HTTP de seguridad, 2FA, tokens revocados |

---

## 9. ESTADO AL MOMENTO DEL REGISTRO

- **Versión:** v3.12
- **Estado:** Producción activa
- **Tests:** 156 pasando
- **Idioma de interfaz:** Español (Argentina)
- **Jurisdicción de diseño:** Argentina (denominaciones, formatos, normativa fiscal local)

---

## 10. DECLARACIÓN DE LA AUTORA

La autora declara que la obra descrita en este documento es una creación intelectual original, desarrollada de forma personal e independiente, y que posee todos los derechos de autor sobre la misma.

**Julieta Arrazate**  
julietaarrazate@gmail.com  
Junio 2026

---

*Documento elaborado para expediente de registro de obra informática. Todos los derechos reservados. Prohibida su reproducción total o parcial sin autorización expresa de la autora.*
