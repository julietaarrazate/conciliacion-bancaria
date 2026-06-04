# README DEL PAQUETE DE REGISTRO
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate — julietaarrazate@gmail.com  
**Fecha de confección del paquete:** Junio 2026  
**Versión del sistema documentada:** v3.12

---

## 1. QUÉ CONTIENE ESTE PAQUETE

Este paquete contiene la documentación completa preparada para el **registro de obra de software** ante organismos de propiedad intelectual. Fue generado a partir del análisis integral del código fuente, la estructura del repositorio y el historial de desarrollo.

### Documentos incluidos

| Archivo | Propósito |
|---|---|
| `README_REGISTRO.md` | Este archivo — guía del paquete |
| `INVENTARIO_TECNICO.md` | Catálogo completo de tecnologías, estructuras y componentes |
| `MEMORIA_DESCRIPTIVA.md` | Documento formal de descripción de la obra para registro |
| `MANUAL_FUNCIONAL.md` | Descripción de módulos, flujos y casos de uso |
| `DOCUMENTACION_TECNICA.md` | Arquitectura, seguridad, APIs, base de datos e integraciones |
| `MODULOS_DEL_SISTEMA.md` | Tabla detallada de todos los módulos con dependencias |
| `EVIDENCIA_AUTORIA.md` | Análisis del historial git y estadísticas de autoría |
| `RESUMEN_EJECUTIVO.md` | Documento de alto nivel para presentación a terceros |
| `ACTIVOS_PI.md` | Identificación de algoritmos, reglas y componentes originales |

---

## 2. CÓMO ESTÁ ESTRUCTURADO

```
REGISTRO_OBRA_SOFTWARE/
├── README_REGISTRO.md          ← Este archivo (leer primero)
├── MEMORIA_DESCRIPTIVA.md      ← Documento central para el registro
├── RESUMEN_EJECUTIVO.md        ← Para presentación a terceros
├── INVENTARIO_TECNICO.md       ← Prueba técnica de la obra
├── DOCUMENTACION_TECNICA.md    ← Descripción técnica profunda
├── MANUAL_FUNCIONAL.md         ← Descripción funcional completa
├── MODULOS_DEL_SISTEMA.md      ← Inventario modular detallado
├── EVIDENCIA_AUTORIA.md        ← Acreditación de autoría
└── ACTIVOS_PI.md               ← Activos de propiedad intelectual
```

---

## 3. QUÉ COMPONENTES FORMAN PARTE DE LA OBRA

La obra registrada comprende la totalidad del código fuente del sistema, organizado en:

### 3.1 Backend (API REST)
- **22 routers** que implementan todos los endpoints del sistema
- **18 servicios** que encapsulan la lógica de negocio
- **18 modelos** de datos con su esquema relacional
- **8 esquemas** de validación Pydantic
- **9 migraciones** de base de datos (historial completo de evolución del esquema)
- **10 archivos de tests** con 156 pruebas automatizadas

### 3.2 Frontend Web (PWA)
- **31 páginas** React con TypeScript
- **18 componentes** reutilizables
- **1 cliente HTTP** centralizado (~25 KB)
- **6 stores** de estado global
- **Service Worker** para PWA, push y share target
- **Utilidades** de manejo de fechas, formateo y validación

### 3.3 Aplicación Móvil
- **Pantallas nativas** React Native (Expo)
- **Navegación** nativa con React Navigation
- **Estado global** y cliente API

### 3.4 Infraestructura y configuración
- **Configuración de despliegue** (Render, Vercel, Railway)
- **Scripts de inicialización** y datos de prueba
- **Documentación técnica** embebida en el repositorio

---

## 4. QUÉ DOCUMENTACIÓN ACOMPAÑA AL SOFTWARE

| Documento | Audiencia | Uso en el expediente |
|---|---|---|
| `MEMORIA_DESCRIPTIVA.md` | Organismos de registro | Descripción formal de la obra |
| `EVIDENCIA_AUTORIA.md` | Organismos de registro | Acreditación de autoría única |
| `INVENTARIO_TECNICO.md` | Evaluadores técnicos | Prueba de existencia y alcance |
| `DOCUMENTACION_TECNICA.md` | Evaluadores técnicos | Descripción técnica detallada |
| `ACTIVOS_PI.md` | Asesores legales | Identificación de activos protegibles |
| `MANUAL_FUNCIONAL.md` | Evaluadores funcionales | Descripción operativa del sistema |
| `MODULOS_DEL_SISTEMA.md` | Evaluadores técnicos | Inventario modular verificable |
| `RESUMEN_EJECUTIVO.md` | Terceros / socios | Presentación no técnica |

---

## 5. INSTRUCCIONES PARA USO DEL PAQUETE

### Para registro de obra ante DNDA (Argentina) u organismo equivalente:

1. **Presentar** `MEMORIA_DESCRIPTIVA.md` como documento principal de descripción
2. **Adjuntar** `EVIDENCIA_AUTORIA.md` como prueba de autoría
3. **Incluir** extracto del código fuente (al menos un módulo representativo)
4. **Completar** los campos marcados como `[COMPLETAR]` en los documentos antes de presentar

### Campos que requieren completación manual por la autora:

Buscar la cadena `[COMPLETAR]` en todos los documentos. Se encontrarán en:
- `EVIDENCIA_AUTORIA.md`: fecha de inicio exacta del desarrollo, equipos utilizados, contexto laboral/contractual

---

## 6. DATOS IDENTIFICATORIOS DE LA OBRA

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

## 7. DECLARACIÓN DE CONFIDENCIALIDAD

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

## 8. NOTAS FINALES

Este paquete fue generado mediante análisis integral del código fuente y la documentación del repositorio. Todos los datos técnicos provienen directamente del código; no se inventaron ni supusieron funcionalidades.

Para consultas: **julietaarrazate@gmail.com**

---

*Paquete de documentación para registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
