# README DEL PAQUETE DE REGISTRO
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate — julietaarrazate@gmail.com  
**Fecha de confección del paquete:** Junio 2026  
**Versión del sistema documentada:** v3.12  
**Commit registrado:** `358f589482db8df36bbec64aa825be6bf367f649`  
**Tag git:** `dnda-software-2026-v1`

---

## 1. QUÉ CONTIENE ESTE PAQUETE

Este paquete contiene la documentación completa preparada para el **registro de obra de software** ante organismos de propiedad intelectual. Fue generado a partir del análisis integral del código fuente, la estructura del repositorio y el historial de desarrollo.

El paquete comprende **19 documentos** organizados en tres grupos:

---

## 2. ÍNDICE COMPLETO DE DOCUMENTOS

### Grupo A — Documentos para presentar ante la DNDA

Documentos imprescindibles para iniciar el trámite. Son los que el organismo evaluará directamente.

| Archivo | Propósito |
|---|---|
| `MEMORIA_DESCRIPTIVA.md` | Descripción formal de la obra — documento central del registro |
| `INVENTARIO_TECNICO.md` | Catálogo completo de tecnologías, estructuras y componentes |
| `DOCUMENTACION_TECNICA.md` | Arquitectura, seguridad, APIs, base de datos e integraciones |
| `MANUAL_FUNCIONAL.md` | Descripción de módulos, flujos y casos de uso (40 casos) |
| `MODULOS_DEL_SISTEMA.md` | Tabla detallada de los 23 módulos con dependencias |
| `EVIDENCIA_AUTORIA.md` | Análisis del historial git y acreditación de autoría exclusiva |
| `ACTIVOS_PI.md` | Identificación de algoritmos, reglas y componentes originales |
| `RESUMEN_EJECUTIVO.md` | Documento de alto nivel para evaluadores no técnicos |

### Grupo B — Documentos de respaldo y auditoría

Evidencia de respaldo que refuerza la solidez del expediente. No son imprescindibles pero agregan valor ante impugnaciones o consultas.

| Archivo | Propósito |
|---|---|
| `EXPEDIENTE_FINAL.md` | Portada formal, carátula e índice del expediente completo |
| `REVISION_EXPEDIENTE.md` | Auditoría general del expediente: coherencia y completitud |
| `REVISION_AUTORIA_FINAL.md` | Auditoría específica: verificación de que no hay referencias a terceros |
| `NOMBRE_DE_OBRA_RECOMENDADO.md` | Análisis y justificación del nombre oficial de la obra |
| `VERSION_A_REGISTRAR.md` | Identificación de la versión exacta a registrar (commit y racional) |
| `MATERIAL_COMPLEMENTARIO.md` | Guía para tomar capturas de pantalla y crear diagramas |

### Grupo C — Guías operativas del proceso de registro

Documentos que describen el proceso de presentación. Para uso interno de la autora; no forman parte del expediente que se entrega.

| Archivo | Propósito |
|---|---|
| `README_REGISTRO.md` | Este archivo — índice y guía del paquete |
| `TAG_REGISTRO.md` | Documentación del tag git permanente de la versión registrada |
| `PAQUETE_FINAL.md` | Estructura del ZIP y lista de archivos para la presentación |
| `CHECKLIST_PRESENTACION.md` | Checklist de 10 fases para el trámite paso a paso |
| `ESTADO_FINAL_REGISTRO.md` | Estado de preparación del expediente y próximos pasos |

---

## 3. ÁRBOL DE ARCHIVOS

```
REGISTRO_OBRA_SOFTWARE/
│
├── README_REGISTRO.md              ← Este archivo (leer primero)
│
├── — Grupo A: Para presentar —
├── EXPEDIENTE_FINAL.md             ← Portada e índice formal
├── MEMORIA_DESCRIPTIVA.md          ← Documento central
├── RESUMEN_EJECUTIVO.md            ← Para evaluadores no técnicos
├── INVENTARIO_TECNICO.md           ← Prueba técnica de la obra
├── DOCUMENTACION_TECNICA.md        ← Arquitectura y seguridad
├── MANUAL_FUNCIONAL.md             ← 40 casos de uso
├── MODULOS_DEL_SISTEMA.md          ← 23 módulos con dependencias
├── EVIDENCIA_AUTORIA.md            ← Acreditación de autoría
├── ACTIVOS_PI.md                   ← Activos de propiedad intelectual
│
├── — Grupo B: Respaldo y auditoría —
├── REVISION_EXPEDIENTE.md          ← Auditoría general
├── REVISION_AUTORIA_FINAL.md       ← Auditoría de referencias a terceros
├── NOMBRE_DE_OBRA_RECOMENDADO.md   ← Nombre oficial justificado
├── VERSION_A_REGISTRAR.md          ← Versión y commit a registrar
└── MATERIAL_COMPLEMENTARIO.md      ← Guía capturas y diagramas
│
└── — Grupo C: Guías operativas —
    ├── TAG_REGISTRO.md             ← Tag git dnda-software-2026-v1
    ├── PAQUETE_FINAL.md            ← Estructura del ZIP
    ├── CHECKLIST_PRESENTACION.md   ← Checklist 10 fases
    └── ESTADO_FINAL_REGISTRO.md    ← Estado final del expediente
```

---

## 4. QUÉ COMPONENTES FORMAN PARTE DE LA OBRA

La obra registrada comprende la totalidad del código fuente del sistema, organizado en:

### 4.1 Backend (API REST)
- **22 routers** que implementan todos los endpoints del sistema
- **18 servicios** que encapsulan la lógica de negocio
- **18 modelos** de datos con su esquema relacional
- **8 esquemas** de validación Pydantic
- **9 migraciones** de base de datos (historial completo de evolución del esquema)
- **10 archivos de tests** con 156 pruebas automatizadas

### 4.2 Frontend Web (PWA)
- **31 páginas** React con TypeScript
- **18 componentes** reutilizables
- **1 cliente HTTP** centralizado (~25 KB)
- **6 stores** de estado global
- **Service Worker** para PWA, push y share target
- **Utilidades** de manejo de fechas, formateo y validación

### 4.3 Aplicación Móvil
- **Pantallas nativas** React Native (Expo)
- **Navegación** nativa con React Navigation
- **Estado global** y cliente API

### 4.4 Infraestructura y configuración
- **Configuración de despliegue** (Render, Vercel)
- **Scripts de inicialización** y datos de prueba
- **Documentación técnica** embebida en el repositorio

---

## 5. IDENTIFICACIÓN DE LA VERSIÓN REGISTRADA

| Dato | Valor |
|---|---|
| **Versión** | v3.12 |
| **Commit** | `358f589482db8df36bbec64aa825be6bf367f649` |
| **Tag git** | `dnda-software-2026-v1` |
| **Rama base** | `claude/software-registration-docs-8aGy3` |
| **Fecha del tag** | 4 de junio de 2026 |
| **Repositorio** | julietaarrazate/conciliacion-bancaria (privado) |

El tag `dnda-software-2026-v1` es anotado (inmutable). Ver `TAG_REGISTRO.md` para instrucciones de publicación desde la máquina local.

---

## 6. INSTRUCCIONES PARA USO DEL PAQUETE

### Para registro de obra ante la DNDA:

1. **Completar** los campos `[COMPLETAR]` en `EVIDENCIA_AUTORIA.md` (fecha de inicio, contexto laboral) y `EXPEDIENTE_FINAL.md` (DNI)
2. **Tomar** las capturas de pantalla según la guía en `MATERIAL_COMPLEMENTARIO.md`
3. **Exportar** los documentos del Grupo A a PDF
4. **Armar** el ZIP según la estructura en `PAQUETE_FINAL.md`
5. **Presentar** siguiendo el `CHECKLIST_PRESENTACION.md`

### Orden de lectura recomendado:

Para entender el expediente: `ESTADO_FINAL_REGISTRO.md` → `EXPEDIENTE_FINAL.md` → `MEMORIA_DESCRIPTIVA.md`  
Para verificar la autoría: `EVIDENCIA_AUTORIA.md` → `REVISION_AUTORIA_FINAL.md`  
Para entender el sistema: `INVENTARIO_TECNICO.md` → `DOCUMENTACION_TECNICA.md` → `MANUAL_FUNCIONAL.md`

---

## 7. DATOS IDENTIFICATORIOS DE LA OBRA

| Campo | Valor |
|---|---|
| **Nombre de la obra** | Sistema Integral de Gestión Financiera, Contable y Empresarial |
| **Denominación de trabajo** | Cuadra (sin registro marcario) |
| **Nombre del repositorio** | conciliacion-bancaria |
| **Tipo de obra** | Programa de computación |
| **Autora** | Julieta Arrazate |
| **Email de la autora** | julietaarrazate@gmail.com |
| **Nacionalidad** | Argentina |
| **Versión registrada** | v3.12 |
| **Fecha de la versión** | Junio 2026 |
| **Idioma de la interfaz** | Español (Argentina) |
| **Repositorio** | Privado — julietaarrazate/conciliacion-bancaria |
| **Tecnología principal** | Python (FastAPI) + TypeScript (React) |
| **Base de datos** | PostgreSQL |
| **Licencia** | Todos los derechos reservados |

---

## 8. DECLARACIÓN DE CONFIDENCIALIDAD

Este paquete de documentación es **confidencial**. Su distribución está restringida a:
- La autora (Julieta Arrazate)
- Profesionales legales que asistan en el proceso de registro
- Organismos de propiedad intelectual ante quienes se presente

Ningún documento de este paquete revela:
- Claves de acceso, tokens o credenciales
- Variables de entorno de producción
- Secretos comerciales operativos
- Información de clientes o terceros

---

## 9. NOTAS FINALES

Este paquete fue generado mediante análisis integral del código fuente y la documentación del repositorio. Todos los datos técnicos provienen directamente del código; no se inventaron ni supusieron funcionalidades.

La autoría de la obra corresponde exclusivamente a **Julieta Arrazate**.

Para consultas: **julietaarrazate@gmail.com**

---

*Paquete de documentación para registro de obra de software — Todos los derechos reservados — Julieta Arrazate — Junio 2026*
