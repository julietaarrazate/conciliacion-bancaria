# MANUAL FUNCIONAL
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Versión documentada:** v3.12 — Junio 2026

---

## 1. INTRODUCCIÓN

Este documento describe los módulos funcionales, flujos operativos y casos de uso del sistema. Está orientado a usuarios con conocimientos contables y financieros que necesitan comprender qué hace el sistema y cómo se opera, sin requerir conocimientos técnicos de programación.

---

## 2. FLUJO OPERATIVO GENERAL

El sistema está diseñado para soportar el ciclo operativo mensual de una organización que recibe pagos de múltiples clientes:

```
INICIO DEL PERÍODO
      │
      ▼
1. IMPORTAR EXTRACTO BANCARIO
   → Subir el archivo Excel del banco
   → El sistema detecta el formato automáticamente
   → Se extraen y numeran los movimientos
   → Se generan asientos contables automáticos
      │
      ▼
2. IMPORTAR PLANILLAS DE PAGOS
   → Subir planillas de cada cliente
   → Auto-conciliación al subir (o manual)
   → El sistema asigna movimientos bancarios a cada fila
      │
      ▼
3. REVISAR Y COMPLETAR CONCILIACIÓN
   → Filas "pendientes" = no conciliadas automáticamente
   → Revisar y asignar manualmente si corresponde
   → El sistema aprende de las correcciones para el próximo mes
      │
      ▼
4. GESTIONAR CHEQUES RECIBIDOS
   → Registrar cheques con datos del formulario (o OCR desde foto)
   → Agrupar por fecha de depósito
   → Acreditar al depositar en el banco
   → Registrar rechazos con gastos bancarios si corresponde
      │
      ▼
5. REGISTRAR EGRESOS
   → Pagos a proveedores, gastos operativos, pagos a clientes
   → Adjuntar comprobante fotográfico
   → El sistema genera el asiento contable
      │
      ▼
6. GENERAR LIQUIDACIONES
   → Seleccionar período
   → Revisar comisiones calculadas
   → Aprobar y registrar el pago
      │
      ▼
7. CIERRE Y REPORTES
   → Resumen ejecutivo mensual
   → Estado de cuenta por cliente
   → Exportación Excel para el contador
   → El libro diario y las cuentas corrientes quedan actualizados
```

---

## 3. MÓDULOS Y CASOS DE USO

---

### 3.1 AUTENTICACIÓN Y ACCESO

**Descripción:** El sistema controla el acceso mediante identificación y contraseña con mecanismos adicionales según el rol.

**Casos de uso:**

**CU-01: Inicio de sesión estándar (roles Admin/Operador)**
1. El usuario ingresa email y contraseña
2. Si el sistema tiene email configurado y el rol es Admin/Superadmin, se envía código 2FA
3. El usuario ingresa el código de 6 dígitos
4. El sistema entrega el token de acceso (válido por 8 horas)

**CU-02: Inicio de sesión con aprobación (rol Contador)**
1. El contador ingresa sus credenciales
2. El sistema notifica a los superadmins por push
3. El contador ve una pantalla de espera
4. Un superadmin aprueba desde `/aprobaciones`
5. El sistema entrega el token (válido por 4 horas)

**CU-03: Recuperación de contraseña**
1. El usuario solicita recuperación desde `/recuperar-password`
2. El sistema envía un email con un link de un solo uso
3. El usuario establece una nueva contraseña desde el link

**CU-04: Bloqueo PIN**
1. Tras un tiempo de inactividad, la pantalla se bloquea
2. El usuario desbloquea con su PIN de 6 dígitos o biometría
3. La sesión continúa sin necesidad de volver a autenticarse

---

### 3.2 EXTRACTOS BANCARIOS

**Descripción:** El sistema recibe archivos Excel de estados de cuenta bancarios y los convierte en movimientos estructurados.

**Casos de uso:**

**CU-05: Importar extracto bancario**
1. El usuario va a `/extractos`
2. Sube el archivo Excel del banco (arrastrar o seleccionar)
3. El sistema detecta el formato automáticamente (múltiples bancos soportados)
4. Se muestran los movimientos importados numerados
5. Se generan asientos contables automáticos en el libro diario

**CU-06: Eliminar lote de movimientos**
1. El usuario identifica un lote importado incorrectamente
2. Hace clic en "Borrar UM"
3. El sistema elimina los movimientos del lote
4. Las planillas afectadas quedan desvinculadas (para re-conciliar)
5. El asiento contable se revierte automáticamente

**CU-07: Renombrar extracto**
1. El usuario hace hover sobre el nombre del extracto
2. Hace clic en el ícono de editar
3. Ingresa el nuevo nombre y confirma

---

### 3.3 PLANILLAS DE PAGOS

**Descripción:** Importación de planillas de pagos de clientes con conciliación automática contra el extracto.

**Casos de uso:**

**CU-08: Subir planilla individual**
1. El usuario va al Dashboard o a `/historial`
2. Sube el archivo Excel de la planilla del cliente
3. El sistema identifica el cliente e importa las filas
4. La conciliación se ejecuta automáticamente
5. Las filas aparecen con estado: ✓ ok / ⏳ pendiente

**CU-09: Carga masiva de planillas**
1. El usuario selecciona múltiples archivos
2. El sistema procesa cada uno con auto-conciliación
3. Se muestra el resumen de resultados

**CU-10: Revisar y corregir conciliación**
1. El usuario identifica filas en estado "pendiente"
2. Puede asignar manualmente un movimiento bancario
3. El sistema registra la corrección como patrón de aprendizaje
4. Si el mismo patrón se confirma 2+ veces → se aplica automáticamente en adelante

**CU-11: Exportar planilla al contador**
1. El usuario selecciona la planilla desde el historial
2. Hace clic en "↓ Excel"
3. El sistema genera un Excel en el formato requerido
4. Si hay filas con el link al movimiento roto, el sistema busca el movimiento por monto+cliente y completa igual

---

### 3.4 CLIENTES

**Descripción:** Directorio de entidades que realizan pagos al sistema.

**Casos de uso:**

**CU-12: Registrar nuevo cliente**
1. El usuario va a `/clientes`
2. Hace clic en "Nuevo cliente"
3. Ingresa nombre (normalizado automáticamente), CUIT (opcional), porcentaje de comisión
4. El sistema crea el cliente y puede vincularlo a una cuenta contable

**CU-13: Configurar comisión de cheques**
1. El usuario hace clic en el chip de comisión del cliente
2. Puede ingresar % general, % local y % interior
3. Al crear un cheque del cliente, el % se auto-selecciona según el tipo del cheque

**CU-14: Ver cuenta corriente**
1. El usuario hace clic en el ícono bancario del cliente
2. Navega al módulo de cuentas corrientes filtrado por ese cliente
3. Ve el timeline de débitos/créditos y el saldo acumulado

**CU-15: Fusionar clientes duplicados**
1. El usuario identifica dos registros que corresponden al mismo cliente
2. Usa el botón "🔀 Fusionar" (solo en desktop)
3. Selecciona el cliente destino
4. El sistema reasigna todas las planillas y movimientos al destino y elimina el duplicado

---

### 3.5 CHEQUES

**Descripción:** Gestión completa del ciclo de vida de cheques de terceros.

**Casos de uso:**

**CU-16: Registrar cheque**
1. El usuario va a `/cheques` → "Nuevo cheque"
2. Puede adjuntar una foto: el sistema lee los datos con OCR automáticamente
3. Selecciona el cliente (debe tener cuenta contable vinculada)
4. Completa o revisa: portador, librador, banco, número, CP, fecha de emisión, fecha de depósito
5. El CP auto-clasifica el cheque como local o interior
6. El sistema calcula la comisión según el tipo (local/interior) del cliente
7. Al guardar: asiento contable automático (recepción del cheque)

**CU-17: Agrupar cheques por fecha de depósito**
1. El usuario va a la tab "Por depósito"
2. Selecciona una fecha de depósito
3. Ve los cheques agrupados con resumen local/interior
4. Puede exportar a Excel esa fecha específica

**CU-18: Acreditar cheque(s)**
1. El usuario selecciona uno o más cheques en la tab "Por depósito"
2. Hace clic en "✓ Acreditar"
3. Selecciona la cuenta bancaria donde se depositaron
4. El sistema genera 2 asientos: acreditación bancaria + reversión del tránsito

**CU-19: Rechazar cheque**
1. El usuario identifica un cheque en estado "acreditado" que fue rechazado
2. Hace clic en "Rechazar"
3. Ingresa fecha de rechazo, si se tiene el cheque físico, y gastos bancarios del rechazo
4. El sistema genera 3 asientos automáticos (reversión completa + gastos)

**CU-20: Editar cheque**
1. El usuario identifica un cheque en estado "registrado" con datos incorrectos
2. Hace clic en "✏️"
3. Modifica los campos necesarios
4. El sistema actualiza el registro

---

### 3.6 CAJA Y ARQUEOS

**Descripción:** Control del dinero en efectivo con arqueos diarios.

**Casos de uso:**

**CU-21: Abrir arqueo del día**
1. El usuario va a `/caja`
2. Selecciona la fecha del arqueo
3. El sistema carga el arqueo existente o permite crear uno nuevo
4. Registra los billetes por denominación (saldo de apertura)

**CU-22: Registrar operación de caja**
1. Con el arqueo abierto, el usuario agrega una operación
2. Ingresa monto, tipo (ingreso/egreso) y descripción
3. El sistema registra la operación y genera el asiento contable

**CU-23: Cerrar arqueo**
1. El usuario verifica que los totales coincidan con el efectivo físico
2. Cierra el arqueo del día
3. Los arqueos cerrados no pueden modificarse

---

### 3.7 EGRESOS Y PAGOS

**Descripción:** Registro unificado de todos los egresos de la organización.

**Casos de uso:**

**CU-24: Registrar egreso**
1. El usuario va a `/pagos` → "Nuevo"
2. Selecciona tipo: pago a proveedor, gasto operativo, o pago a cliente
3. Selecciona forma de pago: banco o efectivo
4. Ingresa monto, fecha, "A favor de" o cliente, número de OP, concepto
5. Puede adjuntar foto del comprobante (OCR automático pre-completa monto, fecha, referencia)
6. Al guardar: asiento contable automático

**CU-25: Compartir comprobante**
1. El usuario ve un egreso registrado
2. Hace clic en el botón de compartir
3. El sistema genera un PDF con los datos y la foto del comprobante
4. Se abre el menú de compartir del sistema (WhatsApp, email, etc.)

**CU-26: Editar egreso**
1. El usuario identifica un egreso con datos incorrectos
2. Hace clic en "✏️"
3. Modifica los campos necesarios
4. El sistema reversa el asiento anterior y genera uno nuevo

---

### 3.8 LIQUIDACIONES

**Descripción:** Generación de resúmenes periódicos con cálculo de comisiones.

**Casos de uso:**

**CU-27: Generar liquidación**
1. El usuario va a `/liquidaciones`
2. Selecciona el período (fecha desde/hasta)
3. Configura el porcentaje de comisión (preset o manual)
4. El sistema calcula ítem por ítem usando el porcentaje más específico disponible
5. Se genera un borrador de liquidación

**CU-28: Aprobar y registrar pago de liquidación**
1. El usuario revisa el borrador
2. Aprueba la liquidación (requiere permiso `manage_users`)
3. Registra el pago cuando se efectiviza
4. El borrador puede eliminarse para regenerar con distinta comisión

---

### 3.9 CONTABILIDAD

**Descripción:** Libro diario de partida doble con generación automática de asientos.

**Casos de uso:**

**CU-29: Revisar el libro diario**
1. El usuario va a `/contabilidad` → tab "Libro Diario"
2. Ve los asientos en orden DESC (más reciente arriba)
3. Puede filtrar por fecha, módulo o cuenta
4. Cada asiento muestra número correlativo, fecha, módulo, descripción y cuentas involucradas

**CU-30: Ingresar asiento manual**
1. El usuario hace clic en "Nuevo asiento" (solo `admin_accounting`)
2. Selecciona cuentas hoja para Debe y Haber
3. Ingresa monto, fecha y descripción
4. El sistema valida la partida doble antes de guardar

**CU-31: Eliminar asiento manual**
1. El usuario identifica un asiento `ajuste_manual` incorrecto
2. Hace clic en "🗑️"
3. El sistema genera un asiento reverso (no borra físicamente)
4. La trazabilidad queda completa

**CU-32: Reconstruir libro diario**
1. El usuario (solo superadmin) detecta asientos duplicados o incorrectos
2. Hace clic en "⚠️ Reset Libro Diario"
3. El sistema muestra un dry_run con el conteo de asientos a borrar y crear
4. Al confirmar: borra todos los asientos y los reconstruye desde cero
5. Numeración correlativa desde 1

**CU-33: Ver cuenta corriente de cliente**
1. El usuario va a `/cuentas-corrientes`
2. Ve la cartera global con saldo por cliente
3. Hace clic en un cliente para ver el detalle
4. Ve cada movimiento que afectó la cuenta: banco, TT, cheques, ajustes
5. Saldo acumulado calculado en tiempo real desde el libro diario

**CU-34: Vincular clientes a cuentas contables**
1. El usuario va a `/contabilidad` → tab "Clientes"
2. Hace clic en "Crear cuentas faltantes" → el sistema crea/vincula en masa
3. Puede hacer vincul

ación manual 1:1 para casos especiales

---

### 3.10 AUDITORÍA

**Descripción:** Registro de todas las operaciones del sistema para trazabilidad.

**Caso de uso:**

**CU-35: Consultar log de auditoría**
1. El usuario (con permiso `view_audit`) va a `/auditoria`
2. Filtra por acción, módulo, usuario o rango de fechas
3. Cada registro muestra quién, qué, cuándo y los datos antes/después del cambio
4. El log es inmutable: no puede modificarse ni eliminarse

---

### 3.11 ASISTENTE DE INTELIGENCIA ARTIFICIAL

**Descripción:** Consultas en lenguaje natural sobre los datos del sistema.

**Caso de uso:**

**CU-36: Consultar al asistente IA**
1. El usuario hace clic en el botón flotante (logo del sistema)
2. Escribe o dicta una consulta: "¿Qué cheques vencen esta semana?" o "¿Cuánto tiene pendiente el cliente X?"
3. El asistente accede a los datos reales del sistema (no solo documentos)
4. Devuelve la respuesta con los datos actuales
5. El historial de la conversación se mantiene durante la sesión

---

### 3.12 OCR (RECONOCIMIENTO ÓPTICO DE CARACTERES)

**Descripción:** Lectura automática de datos desde fotografías de documentos.

**Casos de uso:**

**CU-37: OCR de cheque**
1. En el formulario de cheque, el usuario adjunta una foto
2. El sistema envía la imagen al motor de visión artificial
3. Extrae automáticamente: número de cheque, banco, librador, monto, fechas
4. Pre-completa los campos vacíos del formulario (sin sobreescribir lo ya ingresado)
5. El usuario revisa y confirma los datos

**CU-38: OCR de comprobante de transferencia**
1. En el formulario de egresos, el usuario adjunta una foto del comprobante
2. El sistema extrae: monto, fecha, beneficiario, referencia
3. Pre-completa los campos correspondientes

---

### 3.13 NOTIFICACIONES PUSH

**Descripción:** Alertas proactivas enviadas al dispositivo del usuario sin necesidad de tener la app abierta.

**Caso de uso:**

**CU-39: Recibir alerta de cheque por vencer**
1. A las 10:00 ART, el sistema verifica cheques con vencimiento en ≤3 días
2. Envía una notificación push a los usuarios suscritos
3. Al tocar la notificación, navega directamente al módulo de cheques

---

### 3.14 ACCESO PÚBLICO PARA CLIENTES

**Descripción:** Portal de consulta sin autenticación para que clientes externos vean su estado de cuenta.

**Caso de uso:**

**CU-40: Compartir estado de cuenta con cliente externo**
1. El usuario genera un token público para la planilla del cliente
2. Comparte el link `/p/:token` por WhatsApp o email
3. El cliente accede sin necesidad de crear una cuenta
4. Ve su estado de cuenta y puede descargar el PDF
5. El token expira a los 7 días

---

## 4. PROCESOS CONTABLES

### 4.1 Partida doble automática

Cada operación del sistema genera asientos contables sin intervención del usuario:

| Operación | Debe | Haber |
|---|---|---|
| Importar extracto bancario | Banco (1-1-1-3-1) | No identificado (2-1-1-1) |
| Conciliar planilla | No identificado (2-1-1-1) | Cliente X (2-1-2-X) |
| Registrar cheque | Cheques en cartera (1-1-2-1) | Cliente X (2-1-2-X) |
| Acreditar cheque (parte 1) | Banco (1-1-1-3-1) | Cheques depositados (2-1-3-1) |
| Acreditar cheque (parte 2) | Cheques en cartera (reverso) | — |
| Rechazar cheque | Banco (reverso) + Cliente (reapertura) + Gastos rechazo | Banco |
| Egreso bancario | Gasto / Cliente | Banco (1-1-1-3-1) |
| Egreso efectivo | Gasto / Cliente | Efectivo (1-1-1-2) |
| Operación de caja | Según tipo | Según tipo |

### 4.2 Jerarquía del plan de cuentas

```
1. ACTIVO
  1-1 Activo corriente
    1-1-1 Disponibilidades
      1-1-1-2 Efectivo (caja)
      1-1-1-3 Bancos
        1-1-1-3-1 Banco principal
    1-1-2 Cheques
      1-1-2-1 Cheques en cartera (tránsito)

2. PASIVO
  2-1 Pasivo corriente
    2-1-1 Cuentas por identificar
      2-1-1-1 No identificado (pasivo transitorio)
    2-1-2 Cuentas de clientes
      2-1-2-X Por cliente (vinculado dinámicamente)
    2-1-3 Cheques
      2-1-3-1 Cheques depositados

3. RESULTADOS
  3-1 Ingresos
    3-1-3-0 Comisiones cheques
  3-2 Egresos
    3-2-0-0 Gastos generales
    3-2-2-1 Gastos de rechazos
```

---

## 5. GESTIÓN DOCUMENTAL

### 5.1 Formatos de entrada soportados

| Tipo de documento | Formato | Módulo |
|---|---|---|
| Extracto bancario | Excel (.xlsx, .xls) | Extractos |
| Planilla de pagos | Excel (.xlsx) | Planillas |
| Comprobante de transferencia | Foto (JPG, PNG) | Egresos (OCR) |
| Cheque físico | Foto (JPG, PNG) | Cheques (OCR) |

### 5.2 Formatos de salida generados

| Documento | Formato | Módulo |
|---|---|---|
| Planilla exportada para contador | Excel (.xlsx) | Historial |
| Estado de cuenta por cliente | PDF | Clientes / Público |
| Resumen ejecutivo | PDF | Reportes |
| Comprobante de egreso | PDF | Egresos |
| Detalle de cheques por depósito | Excel (.xlsx) | Cheques |
| Export completo de cheques | Excel (.xlsx) | Cheques |
| Backup del sistema | JSON gzipeado (.json.gz) | Backup |

---

*Documento generado para expediente de registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
