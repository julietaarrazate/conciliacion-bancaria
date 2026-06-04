# EVIDENCIA DE AUTORÍA
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Email:** julietaarrazate@gmail.com  
**Repositorio:** conciliacion-bancaria (privado)  
**Fecha de relevamiento:** Junio 2026

---

## 1. AUTORÍA ÚNICA Y EXCLUSIVA

La totalidad del código fuente de la obra fue desarrollada de forma exclusiva por **Julieta Arrazate**. El análisis del historial de control de versiones (git) confirma esta atribución de manera objetiva y verificable.

---

## 2. IDENTIDADES DE AUTOR EN GIT

El repositorio registra commits bajo dos configuraciones de autor que corresponden a la misma persona:

| Nombre registrado | Commits | Observación |
|---|---|---|
| `Julieta Arrazate` | 65 | Configuración principal |
| `julietaarrazate` | 56 | Configuración alternativa (mismo autor, distinto perfil de git) |
| **TOTAL** | **121** | **100% de los commits son de la autora** |

**Nota:** La diferencia de nombre de usuario entre ambas configuraciones es técnica (distintos perfiles de git en distintos entornos de trabajo) y no indica la participación de otra persona.

---

## 3. ESTADÍSTICAS DE CONTRIBUCIÓN

| Métrica | Valor |
|---|---|
| Total de commits | 121 |
| Autores distintos | 1 (Julieta Arrazate) |
| Porcentaje de autoría única | 100% |
| Rama principal | `main` |
| Repositorio | Privado |

---

## 4. CRONOLOGÍA DE DESARROLLO

### 4.1 Período de desarrollo verificado en repositorio

| Fase | Período | Actividad principal |
|---|---|---|
| Fundacional | Mayo 2026 | Arquitectura base, autenticación, modelos de datos, conciliación bancaria |
| Crecimiento | Mayo 2026 | Multi-tenancy, exportaciones, módulos financieros |
| Expansión | Mayo 2026 | Contabilidad automática, cuentas corrientes, roles avanzados |
| Madurez | Junio 2026 | IA, OCR, ciclo completo de cheques, hardening de seguridad |
| Estabilización | Junio 2026 | Tests, correcciones, documentación, registro |

### 4.2 Hitos evolutivos del sistema

| Versión | Período | Descripción |
|---|---|---|
| v1.x | Mayo 2026 | Sistema base de conciliación bancaria |
| v2.x | Mayo 2026 | Motor de conciliación con scoring, multi-extracto |
| v3.0 | Mayo 2026 | Multi-tenant, exportaciones, seguridad |
| v3.1–v3.4 | Mayo 2026 | Comisiones, módulos financieros, landing page |
| v3.6 | Mayo 2026 | Contabilidad automática, cuentas corrientes, permisos en 3 capas |
| v3.7 | Mayo 2026 | Rol contador, login por aprobación en vivo, switch de org |
| v3.8 | Mayo 2026 | Reset/rebuild libro diario, filtros Excel, numeración correlativa |
| v3.9 | Mayo 2026 | Módulo Pagos unificado, asistente IA Gemini, OCR de comprobantes |
| v3.9.2 | Mayo 2026 | Módulo cheques mejorado, portadores, local/interior |
| v3.10 | Junio 2026 | Ciclo contable completo cheques (3 fases, 7 tipos de asiento) |
| v3.11 | Junio 2026 | 2FA por email, ajuste manual libro diario, hardening permisos |
| v3.12 | Junio 2026 | Edición de pagos, íconos SVG, fix OCR, documentación de registro |

---

## 5. TIPOS DE CONTRIBUCIONES REGISTRADAS

El historial de commits refleja el trabajo integral de la autora en todas las capas del sistema:

| Tipo de commit | Descripción | Ejemplos |
|---|---|---|
| `feat:` | Nuevas funcionalidades | Motor IA, ciclo cheques, módulo pagos |
| `fix:` | Corrección de errores | OCR, fechas, concurrencia, UI |
| `security:` | Mejoras de seguridad | 2FA, rate limiting, validaciones |
| `docs:` | Documentación | CLAUDE.md, README, este paquete |
| `refactor:` | Mejoras de código | Unificación de módulos |

---

## 6. NATURALEZA ORIGINAL DE LA OBRA

### 6.1 Componentes desarrollados por la autora

Todo el código fuente es original, incluyendo:

- **Motor de conciliación bancaria**: algoritmo de scoring multi-criterio desarrollado específicamente para el sistema
- **Motor contable automático**: lógica de generación de asientos automáticos por módulo (18+ tipos)
- **Sistema de aprendizaje por patrones**: tabla `PatronAprendido` con lógica de aprendizaje incremental
- **Parser multi-banco**: soporte para múltiples formatos de extractos bancarios
- **Sistema de permisos en 3 capas**: modelo propio de autorización granular
- **Flujo de aprobación de sesión en vivo**: sistema de login con aprobación por push en tiempo real
- **Ciclo contable completo de cheques**: 3 fases con 7 tipos de asiento diferenciados
- **Sistema de backup automático**: backup periódico gzipeado con envío por email
- **Integración VAPID / Web Push**: notificaciones nativas sin costo de terceros

### 6.2 Uso de librerías de terceros

Las librerías utilizadas son dependencias de código abierto estándar en la industria. La obra original consiste en la integración, configuración, lógica de negocio y código propietario construido sobre estas bases.

---

## 7. EVIDENCIAS ADICIONALES DE AUTORÍA

| Evidencia | Descripción |
|---|---|
| Repositorio privado | El código fuente reside en repositorio privado de propiedad de la autora |
| 121 commits firmados | Todos bajo identidades de la misma autora |
| Commits de seguridad | Muestran conocimiento profundo de toda la arquitectura |
| 156 tests escritos | Tests integrales que demuestran dominio completo del sistema |
| Documentación técnica | CLAUDE.md exhaustivo escrito por la autora describiendo cada versión |
| Configuración de producción | Archivos de deploy (render.yaml, vercel.json, railway.json) |

---

## 8. DECLARACIÓN DE ORIGINALIDAD

La autora declara que:

1. La totalidad del código fuente fue desarrollada de forma personal y original.
2. No se utilizó código de terceros sin licencia que lo permita.
3. Las librerías de terceros utilizadas son de código abierto bajo licencias permisivas (MIT, Apache, BSD).
4. El algoritmo de conciliación, el motor contable y los demás componentes de negocio son creaciones originales.
5. No existen contratos de cesión de derechos en favor de terceros sobre esta obra.

---

## 9. INFORMACIÓN ADICIONAL — COMPLETADO POR LA AUTORA

**Fecha de inicio del desarrollo:** A partir de abril de 2026. Los primeros commits del repositorio datan del 2 de junio de 2026, pero el desarrollo conceptual y arquitectónico se inició en abril de 2026.

**Evidencia de desarrollo previo:** Existe un cuaderno escrito que contiene el brainstorming inicial del proyecto, diseños preliminares y especificaciones funcionales previas al repositorio git. Este material documenta la fase conceptual del sistema.

**Contexto laboral y contractual:** La autora desarrolló la obra de forma **completamente independiente**, utilizando equipos propios, sin relación de dependencia laboral con terceros, y sin contrato de cesión de derechos. La obra fue desarrollada por iniciativa y financiamiento personal de la autora.

---

*Documento generado para expediente de registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
