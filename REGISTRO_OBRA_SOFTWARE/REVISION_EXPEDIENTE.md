# REVISIÓN DEL EXPEDIENTE DE REGISTRO
## Auditoría de los documentos generados
### Sistema Integral de Gestión Financiera, Contable y Empresarial

**Fecha de revisión:** Junio 2026  
**Documentos auditados:** 9 archivos en `REGISTRO_OBRA_SOFTWARE/`

---

## 1. HALLAZGOS CRÍTICOS (requieren corrección antes de presentar)

### 1.1 Nombre de cliente real en ACTIVOS_PI.md — CORREGIDO

| Archivo | Línea original | Problema | Estado |
|---|---|---|---|
| `ACTIVOS_PI.md` | 163 | El ejemplo usaba `"green"` y `"Green"` — nombre de un cliente real del sistema | **CORREGIDO** — reemplazado por `"empresa abc"` / `"Empresa Abc"` |

### 1.2 Campos marcados [COMPLETAR] — PENDIENTES DE LA AUTORA

Solo en `EVIDENCIA_AUTORIA.md`, sección 9. Tres campos que nadie puede completar excepto la autora:

| Campo | Descripción | Impacto si no se completa |
|---|---|---|
| Fecha de inicio del desarrollo | Mes/año antes del primer commit git | Menor: el repositorio ya acredita la fecha |
| Evidencia de desarrollo previo | Bocetos, prototipos, archivos locales anteriores | Menor: solo fortalece el expediente |
| Contexto laboral/contractual | Equipos propios, relación de empleo | **Importante**: necesario para descartar cesión implícita |

**Recomendación:** completar el campo 3 (contexto laboral) antes de presentar. Los campos 1 y 2 son opcionales.

---

## 2. HALLAZGOS MODERADOS (son correctos técnicamente pero conviene evaluar)

### 2.1 Menciones de proveedores/plataformas de infraestructura

Los siguientes nombres de servicios de terceros aparecen en varios documentos:

| Servicio | Documentos que lo mencionan | Evaluación |
|---|---|---|
| Google / Gemini | INVENTARIO, DOCUMENTACION, MODULOS, RESUMEN, EVIDENCIA | Correcto: es una dependencia técnica real del sistema |
| Vercel | INVENTARIO, RESUMEN, README | Correcto: plataforma de deploy del frontend |
| Render | INVENTARIO, RESUMEN, README | Correcto: plataforma de deploy del backend |
| Neon PostgreSQL | INVENTARIO, RESUMEN | Correcto: proveedor de base de datos |
| Resend | INVENTARIO, DOCUMENTACION, MODULOS | Correcto: servicio de email transaccional |
| AWS S3 / Cloudflare R2 | INVENTARIO, DOCUMENTACION | Correcto: almacenamiento externo opcional |
| Sentry | INVENTARIO, DOCUMENTACION, RESUMEN | Correcto: monitoreo de errores opt-in |
| WhatsApp | MANUAL, MODULOS, MEMORIA | Correcto: protocolo de compartir nativo del SO |

**Veredicto:** Estas menciones son técnicamente apropiadas y necesarias para describir la arquitectura del sistema. No revelan secretos comerciales. Son aceptables en un expediente de registro.

**Nota WhatsApp:** se menciona como funcionalidad de compartir (Web Share API del sistema operativo). No es una integración técnica directa; el sistema usa la API nativa del SO. Las menciones son correctas.

### 2.2 Mención de "CLAUDE.md" en EVIDENCIA_AUTORIA.md

| Archivo | Referencia | Evaluación |
|---|---|---|
| `EVIDENCIA_AUTORIA.md` líneas 85 y 120 | `CLAUDE.md` como documento técnico del repositorio | Correcto: es literalmente el nombre del archivo de documentación del proyecto |

**Veredicto:** No genera ambigüedad. `CLAUDE.md` es el nombre del archivo de documentación interna del proyecto (visible en el repositorio). No requiere cambio.

### 2.3 Mención del rol "contador" en múltiples documentos

La palabra "contador" aparece 15+ veces en los documentos. En todos los casos se refiere al rol de usuario del sistema (`CONTADOR` enum en el código), no a ninguna persona física.

**Veredicto:** Correcto y necesario. No identifica a ninguna persona ni tercero.

---

## 3. HALLAZGOS MENORES (mejoras opcionales)

### 3.1 Redundancia entre documentos

| Información | Aparece en |
|---|---|
| Tabla de 20 módulos | MEMORIA_DESCRIPTIVA + MODULOS_DEL_SISTEMA (versión extendida) |
| Stack tecnológico | INVENTARIO_TECNICO + RESUMEN_EJECUTIVO + DOCUMENTACION_TECNICA |
| Estadísticas de autoría (121 commits) | EVIDENCIA_AUTORIA + README_REGISTRO |
| Motor de conciliación con scoring | MEMORIA_DESCRIPTIVA + ACTIVOS_PI + DOCUMENTACION_TECNICA |

**Veredicto:** La redundancia es intencional y apropiada para un expediente. Cada documento es autónomo (puede presentarse por separado). No es un defecto.

### 3.2 Código de cuenta "1-1-1-3-1" en MANUAL_FUNCIONAL.md

La tabla de partida doble referencia el código de plan de cuentas `1-1-1-3-1`. En el código fuente del sistema ese código corresponde a "Banco Macro". En el documento se lo llama genéricamente "Banco (1-1-1-3-1)" y "Banco principal", lo cual es correcto.

**Veredicto:** No hay exposición del nombre del banco en los documentos de registro. Correcto.

### 3.3 Inconsistencia en conteo de roles

`MEMORIA_DESCRIPTIVA.md` dice "5 roles con permisos granulares", pero el sistema tiene 6 roles: superadmin, admin, operador, revisor, auditor, contador.

**Recomendación:** Corregir en `MEMORIA_DESCRIPTIVA.md` a "6 roles" o "múltiples roles".

### 3.4 Versión del sistema en múltiples documentos

Todos los documentos indican `v3.12` como versión registrada. Es consistente.

---

## 4. INFORMACIÓN SENSIBLE: RESULTADO FINAL

| Tipo de información | ¿Presente? | Observaciones |
|---|---|---|
| Claves / tokens / passwords | NO | Correcto |
| Variables de entorno con valores | NO | Solo se mencionan nombres de vars (GEMINI_API_KEY, etc.) |
| Nombres de clientes reales | 1 CORREGIDO | "green" → reemplazado por ejemplo genérico |
| Nombres de asesores / contadores / socios | NO | Ninguno |
| Secretos comerciales operativos | NO | Los algoritmos se describen por principios, no por código |
| Datos de producción (URLs privadas, IPs) | NO | Correcto |
| Información de terceros identificables | NO | Correcto |

---

## 5. RESUMEN EJECUTIVO DE LA AUDITORÍA

| Estado | Cantidad | Descripción |
|---|---|---|
| Crítico corregido | 1 | Nombre de cliente real → reemplazado |
| Pendiente manual | 1 | Campo laboral/contractual en EVIDENCIA_AUTORIA |
| Corrección menor | 1 | "5 roles" → "6 roles" en MEMORIA_DESCRIPTIVA |
| Sin acción necesaria | Todo lo demás | El expediente está limpio |

**Conclusión:** El expediente es presentable. Solo resta completar el campo contractual en EVIDENCIA_AUTORIA.md y opcionalmente corregir el conteo de roles.

---

*Auditoría realizada sobre el material existente. Julieta Arrazate — Junio 2026*
