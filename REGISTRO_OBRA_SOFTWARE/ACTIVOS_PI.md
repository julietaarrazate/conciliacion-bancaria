# ACTIVOS DE PROPIEDAD INTELECTUAL
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Versión documentada:** v3.12 — Junio 2026

---

## 1. INTRODUCCIÓN

Este documento identifica los algoritmos propios, reglas de negocio originales, procesos diferenciales y componentes innovadores del sistema que constituyen activos de propiedad intelectual de la autora.

El nivel de detalle proporcionado es el necesario para identificar la existencia de estos activos sin revelar implementaciones propietarias sensibles.

---

## 2. ALGORITMOS PROPIOS

### 2.1 Motor de Conciliación Bancaria con Scoring Multi-Criterio

**Archivo de referencia:** `backend/app/services/conciliacion.py`

**Descripción:** Algoritmo original que determina automáticamente si un movimiento bancario corresponde a una fila de planilla de pago. No existe una solución estándar para este problema: el sistema implementó una metodología propia.

**Principio de funcionamiento:** Asignación de puntuaciones por nivel de evidencia de identidad, con umbrales de decisión diferenciados según el tipo de coincidencia.

**Escala de puntuaciones:**
| Tipo de identificador | Puntuación |
|---|---|
| CUIT (11 dígitos) | 12 puntos |
| CBU/CVU (22 dígitos) | 10 puntos |
| Número de cuenta largo (10+ dígitos) | 8 puntos |
| Número de referencia (6-9 dígitos) | 6 puntos |
| Nombre titular (2+ palabras) | 5 puntos |
| Nombre titular (1 palabra) | 3 puntos |
| Proximidad de fecha | +1 a +5 puntos adicionales |

**Regla de seguridad:** cuando el mismo monto aparece duplicado en el extracto, el sistema exige obligatoriamente la presencia de un identificador de identidad (no acepta coincidencia solo por monto).

**Innovación:** la combinación de scoring multi-criterio con reglas de seguridad diferenciadas y tolerancia de fecha configurable produce un motor de alta precisión que minimiza falsos positivos.

---

### 2.2 Sistema de Aprendizaje por Patrones

**Archivo de referencia:** `backend/app/services/aprendizaje.py`

**Descripción:** Motor de aprendizaje incremental que mejora automáticamente la tasa de conciliación a lo largo del tiempo, sin necesidad de entrenamiento explícito.

**Principio de funcionamiento:**
1. Cada corrección manual del operador se registra en `PatronAprendido`
2. El patrón incluye la firma de identificación del pagador y el cliente asignado
3. Cuando un patrón acumula 2 o más confirmaciones independientes, se convierte en regla automática
4. En conciliaciones futuras, el patrón se aplica antes del scoring general

**Innovación:** el sistema aprende sin supervisión explícita, aprovechando el trabajo normal del operador para reducir trabajo futuro. La cantidad de confirmaciones requeridas (umbral 2) fue determinada para equilibrar precisión y velocidad de aprendizaje.

---

### 2.3 Motor Contable Automático

**Archivo de referencia:** `backend/app/services/motor_contable.py`

**Descripción:** Motor que genera automáticamente asientos contables de partida doble ante cada operación del sistema, sin requerir intervención manual del usuario.

**Innovación:** el motor conoce el tipo de cuenta correcto para cada flujo financiero y genera el asiento apropiado según el contexto (tipo de operación, tipo de cuenta del cliente, tipo de egreso). Los 18+ módulos de asiento cubren todos los casos del ciclo operativo.

**Características técnicas:**
- Generación de asientos multi-línea (helper `_crear_asiento_multilinea`)
- Numeración correlativa automática (`numero_asiento`)
- Reversión no destructiva (siempre genera un asiento reverso, nunca borra)
- Idempotencia: protege contra asientos duplicados

---

### 2.4 Parser Multi-Banco de Extractos

**Archivo de referencia:** `backend/app/services/excel_parser.py`

**Descripción:** Parser que detecta automáticamente el formato del extracto bancario y extrae los movimientos correctamente, sin requerir que el usuario especifique el banco ni el formato.

**Innovación:** la detección automática de formato elimina una fuente de error manual y soporta múltiples instituciones bancarias con un único punto de entrada.

---

### 2.5 Algoritmo de Deduplicación de Movimientos

**Archivo de referencia:** `backend/app/services/extracto_merger.py`

**Descripción:** Algoritmo que elimina movimientos duplicados al fusionar extractos de distintos períodos, usando una combinación de campos como clave de identidad.

**Criterios de deduplicación:** la identidad de un movimiento se determina por la combinación de campos (orden, monto) o (fecha, monto, titular_normalizado), según disponibilidad de datos.

---

## 3. REGLAS DE NEGOCIO ORIGINALES

### 3.1 Cadena de herencia de comisiones

El sistema implementa una cadena de prioridad de 4 niveles para determinar el porcentaje de comisión de cada ítem:

```
1. Override manual en el formulario (máxima prioridad)
   ↓
2. Porcentaje propio del ítem (planilla o cheque)
   ↓
3. Porcentaje del cliente (general o L/I según tipo)
   ↓
4. Porcentaje default de la organización (mínima prioridad)
```

Para cheques, el porcentaje del cliente se deriva automáticamente según la clasificación local/interior:
- Cheque local (CP < 2000) → porcentaje local del cliente
- Cheque interior (CP ≥ 2000) → porcentaje interior del cliente
- Fallback → porcentaje general del cliente

### 3.2 Ciclo de vida del cheque de terceros en 3 fases contables

El sistema modeliza el ciclo contable completo de un cheque de terceros con 3 fases diferenciadas:

| Fase | Estado del cheque | Movimiento contable |
|---|---|---|
| Recepción | `registrado` | Cheques en cartera D / Cliente H |
| Depósito y acreditación | `acreditado` | Banco D / Cheques depositados H + reverso de tránsito |
| Rechazo (si ocurre) | `rechazado` | Reversión bancaria + reapertura deuda + gasto por rechazo |

**Garantía:** las cuentas de tránsito (`Cheques en cartera` y `Cheques depositados`) netean a cero al completar el ciclo, lo que asegura la corrección contable.

### 3.3 Flujo de login con aprobación en tiempo real

Flujo de autenticación original diseñado para roles con acceso controlado:
- El acceso solo se habilita con la aprobación explícita de un administrador
- La aprobación es en tiempo real (notificación push + polling)
- El token tiene expiración diferenciada (4h vs 8h estándar)
- El token se entrega una única vez (uso destructivo)

### 3.4 Gestión de períodos sin lock-out del operador

La arquitectura de soft delete y la ausencia de cierres de período obligatorios permiten que el operador continúe trabajando en todo momento. Las correcciones siempre se registran como nuevos asientos (nunca modifican asientos existentes), garantizando la trazabilidad sin bloquear la operación.

### 3.5 Regla de conciliación: sin auto-match solo por monto cuando hay duplicado

Regla de seguridad que previene conciliaciones incorrectas cuando el extracto contiene dos o más movimientos con el mismo monto. En ese caso, el sistema exige la presencia de al menos un identificador de identidad adicional, evitando asignaciones arbitrarias.

---

## 4. PROCESOS DIFERENCIALES

### 4.1 Backfill de cuentas corrientes desde conciliaciones históricas

Proceso que reconstruye el historial de cuentas corrientes de clientes a partir de la información de conciliaciones ya realizadas. Permite adoptar el módulo de contabilidad en un sistema con datos históricos sin requerir re-ingreso manual.

**Algoritmo:** recorre todas las filas de planilla conciliadas (estado `ok`) cuyo cliente tiene cuenta contable vinculada, y genera un asiento neto Banco/Cliente por cada una. Protege contra duplicados (no procesa filas con asiento `um_reclass` o `cc_inicial` previo).

### 4.2 Reset y reconstrucción del libro diario

Proceso que permite borrar y reconstruir completamente el libro diario desde los datos de origen, garantizando un libro limpio y con numeración correlativa correcta. El proceso incluye un modo `dry_run` que muestra el impacto antes de ejecutar.

### 4.3 Normalización de nombres de clientes

Sistema de normalización que garantiza que "green" y "Green" y "GREEN" se identifiquen como el mismo cliente. La normalización incluye:
- Conversión NFKD Unicode (manejo de caracteres con tilde)
- Primera letra en mayúscula
- Búsqueda insensible a mayúsculas (ilike)
- Previene la creación de duplicados en alta manual, importación de planillas y operaciones de caja

### 4.4 Fallback robusto en exportación de planillas

Cuando una fila conciliada tiene el vínculo al movimiento bancario roto (por eliminación posterior del movimiento), el proceso de exportación busca el movimiento correspondiente por monto + cliente en el extracto y completa todas las columnas igualmente. Esta lógica de fallback garantiza que el archivo del contador siempre se pueda generar.

---

## 5. COMPONENTES INNOVADORES

### 5.1 Contabilidad derivada (sin datos redundantes)

Las cuentas corrientes de clientes se calculan en tiempo real a partir de los asientos del libro diario, en lugar de almacenarse como datos separados. Esta arquitectura garantiza automáticamente la coherencia entre el libro diario y las cuentas corrientes, sin posibilidad de desincronización.

### 5.2 Middleware de permisos en 3 capas ortogonales

Sistema de autorización que combina 3 dimensiones independientes:
1. **Rol** (admin, operador, contador, etc.): define el alcance general
2. **Permiso funcional** (upload_files, reconcile, manage_finance, etc.): granularidad por función
3. **Organización** (organizacion_id): aislamiento de datos por empresa

El mecanismo de override de organización en memoria (`db.expunge(user)`) permite que un contador opere en una organización diferente a la suya sin persistir el cambio ni comprometer el aislamiento.

### 5.3 Aritmética financiera exacta en toda la stack

Las columnas financieras de la base de datos usan `Numeric(12, 2)` (exacto) en lugar de `Float` (impreciso). El encoder JSON personalizado maneja la serialización de `decimal.Decimal` a números JSON de forma transparente. Los parsers de montos en el frontend tratan formatos argentinos y estadounidenses antes de operar.

### 5.4 Safety nets de startup

El sistema implementa un mecanismo de autocorrección al arrancar: ejecuta una serie de `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` y `UPDATE ... SET ... WHERE ... IS NULL` para garantizar que el esquema de la base de datos sea correcto incluso si una migración de Alembic no llegó a ejecutarse. Este mecanismo hace el sistema resiliente a actualizaciones parciales.

### 5.5 Degradación elegante por ausencia de servicios opcionales

Cada integración externa (IA, email, push, storage) tiene una condición de activación basada en la presencia de variables de entorno. Si la variable no existe, la funcionalidad se deshabilita en lugar de lanzar errores. El sistema funciona en cualquier subconjunto de sus capacidades sin configuración adicional.

### 5.6 Encoder JSON Decimal transparente

El `JSONResponse` personalizado serializa automáticamente todos los tipos `decimal.Decimal` como números de punto flotante en las respuestas, sin requerir conversiones explícitas en cada endpoint. Esta decisión de diseño centraliza el manejo de tipos y previene una clase entera de errores de serialización.

---

## 6. ELEMENTOS POTENCIALMENTE REGISTRABLES

| Activo | Tipo de protección sugerida |
|---|---|
| Código fuente completo del sistema | Registro de obra de software |
| Motor de conciliación con scoring | Componente del registro de software |
| Motor contable automático | Componente del registro de software |
| Sistema de aprendizaje por patrones | Componente del registro de software |
| Ciclo contable de cheques en 3 fases | Componente del registro de software |
| Flujo de login con aprobación en vivo | Componente del registro de software |
| Diseño visual y experiencia de usuario | Registro separado de obra artística (opcional) |
| Denominación de trabajo "Cuadra" | Registro marcario (pendiente, fuera del alcance de este expediente) |

---

## 7. NOTA SOBRE EL NIVEL DE DIVULGACIÓN

Este documento describe los activos de propiedad intelectual al nivel necesario para su identificación y acreditación, sin exponer detalles de implementación que representen un secreto comercial operativo. Los algoritmos y procesos se describen por sus principios de funcionamiento, no por su código fuente.

El código fuente completo constituye el activo principal de la obra y se presenta como parte del expediente de registro (repositorio privado `conciliacion-bancaria`).

---

*Documento elaborado para expediente de registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
