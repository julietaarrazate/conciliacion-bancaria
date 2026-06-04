# RESUMEN EJECUTIVO
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Versión:** v3.12 — Junio 2026

---

## 1. SÍNTESIS

**Sistema Integral de Gestión Financiera, Contable y Empresarial** (denominación de trabajo: *Cuadra*) es una plataforma de software diseñada para automatizar y centralizar la gestión financiero-contable de organizaciones que procesan múltiples pagos de clientes contra extractos bancarios.

El sistema transforma un proceso que típicamente insume horas de trabajo manual en planillas de cálculo en una operación automatizada de minutos, con trazabilidad contable completa, auditoría de cada operación y acceso desde cualquier dispositivo.

---

## 2. PROBLEMA QUE RESUELVE

### Situación sin el sistema

Las organizaciones que reciben pagos de múltiples clientes enfrentan mensualmente:

- **Conciliación manual:** comparar línea por línea el extracto bancario contra planillas de pagos individuales de cada cliente. Proceso propenso a errores, duplicaciones y omisiones.
- **Dispersión de información:** los datos financieros se distribuyen en múltiples archivos de Excel sin integración entre sí.
- **Falta de trazabilidad contable:** la vinculación entre movimientos bancarios y asientos contables se realiza manualmente o no se realiza.
- **Gestión de cheques manual:** sin ciclo de vida formal ni asientos diferenciados por fase.
- **Ausencia de alertas:** vencimientos de cheques o movimientos sin identificar se detectan tarde.

### Solución aportada por el sistema

| Proceso | Sin el sistema | Con el sistema |
|---|---|---|
| Conciliación mensual | Horas de trabajo manual | Automática al subir los archivos |
| Asientos contables | Manual o inexistente | Automáticos por cada operación |
| Estado de cuenta de cliente | Cálculo manual | Tiempo real, derivado de asientos |
| Vencimiento de cheques | Revisión manual periódica | Alertas push automáticas |
| Backup de datos | Depende de cada usuario | Automático diario por email |
| Acceso remoto | Imposible | Desde cualquier dispositivo (web + móvil) |

---

## 3. MERCADO OBJETIVO

El sistema está orientado a:

- **Organizaciones con gestión de pagos recurrentes:** que reciben transferencias de múltiples clientes y requieren conciliarlas contra extractos bancarios.
- **Estudios de gestión contable-financiera:** que administran carteras de clientes con cobros, cheques y liquidaciones.
- **PyMEs con volumen de operaciones financieras:** que necesitan trazabilidad contable sin implementar un ERP de gran escala.
- **Operadores financieros:** que procesan cheques de terceros y necesitan control del ciclo completo (recepción, depósito, acreditación, rechazo).

**Idioma:** Español (Argentina). Adaptado a la normativa, denominaciones y formatos locales (CUIT, CBU, Numeric argentino, timezone UTC-3).

---

## 4. ALCANCE Y CAPACIDADES

### 4.1 Módulos activos

| Área | Capacidades |
|---|---|
| **Conciliación** | Importación multi-banco, scoring automático, aprendizaje por patrones |
| **Cheques** | Ciclo completo 3 fases + OCR desde foto + acreditación masiva |
| **Contabilidad** | Plan de cuentas, libro diario, mayor, cuentas corrientes, asientos automáticos |
| **Caja** | Arqueos diarios, operaciones, denominaciones de billetes |
| **Egresos** | Gastos, proveedores, pagos a clientes, comprobante fotográfico |
| **Liquidaciones** | Períodos, comisiones por nivel (org/cliente/ítem), aprobación |
| **Reportes** | Estado de cuenta, resumen mensual, flujo de caja, exportación Excel/PDF |
| **IA** | Asistente conversacional + OCR para cheques y comprobantes |
| **Seguridad** | 2FA, PIN + biometría, roles granulares, auditoría inmutable |
| **Multi-empresa** | Aislamiento completo de datos por organización |

### 4.2 Capacidad de usuarios y roles

| Rol | Descripción |
|---|---|
| Superadmin | Acceso total al sistema, gestión de todas las organizaciones |
| Admin | Gestión completa de su organización |
| Operador | Operatoria diaria sin borrado de datos |
| Revisor | Solo lectura de datos contables y financieros |
| Auditor | Lectura contable + financiera |
| Contador | Operatoria + contabilidad en solo lectura |

---

## 5. DIFERENCIADORES TÉCNICOS

### 5.1 Motor de conciliación propio
Algoritmo original de scoring multi-criterio que evalúa simultáneamente múltiples identificadores del pagador (CUIT, CBU, número de cuenta, nombre del titular, fecha). No depende de servicios externos. Aprende de las correcciones manuales.

### 5.2 Contabilidad automática sin configuración
Cada operación del sistema genera asientos contables de partida doble en forma automática. El usuario no necesita conocer contabilidad para que el sistema mantenga el libro diario actualizado.

### 5.3 IA con datos reales de la empresa
El asistente de inteligencia artificial accede a los datos reales del sistema (no solo documentos) mediante function calling, permitiendo consultas como "¿cuánto tiene pendiente el cliente X?" o "¿qué cheques vencen esta semana?".

### 5.4 OCR integrado sin costo adicional
La lectura automática de cheques y comprobantes utiliza modelos de visión artificial de capa gratuita (no requiere pago adicional por uso básico).

### 5.5 PWA instalable
La aplicación web funciona como app nativa en dispositivos móviles sin necesidad de distribución a través de tiendas de aplicaciones. Recibe notificaciones push, puede recibir archivos de otras apps.

### 5.6 Sin lock-in a plataforma contable
La arquitectura es independiente de software contable de terceros. El sistema puede exportar al formato requerido por cualquier herramienta de contabilidad.

---

## 6. CAPACIDADES TÉCNICAS

| Capacidad | Tecnología |
|---|---|
| API REST asíncrona | FastAPI (Python 3.11) |
| Base de datos relacional | PostgreSQL con ORM tipado |
| Interfaz web reactiva | React 18 + TypeScript |
| Aplicación móvil nativa | React Native (iOS + Android) |
| Progressive Web App | Service Worker + Web Push |
| Inteligencia artificial | Google Gemini Flash API |
| OCR de documentos | Gemini Vision API |
| Aritmética financiera exacta | Numeric(12,2) — sin errores de punto flotante |
| Tests automatizados | 156 tests (pytest + vitest) |
| Monitoreo de errores | Sentry (opt-in) |
| Autenticación segura | JWT + 2FA + PIN + WebAuthn |
| Almacenamiento de archivos | S3/Cloudflare R2 (opt-in) |

---

## 7. ARQUITECTURA DE DESPLIEGUE

```
Usuarios → Frontend (Vercel CDN global)
              ↓ HTTPS
         API REST (Render — backend Python)
              ↓ TCP
         PostgreSQL (Neon — cloud serverless)
              ↓ opcionales
    [Gemini AI] [S3/R2 Storage] [Resend Email] [Sentry]
```

- **Disponibilidad:** 24/7 con monitoreo automático
- **Escalabilidad:** arquitectura stateless horizontal
- **Seguridad:** HTTPS forzado, headers de seguridad HTTP, rate limiting, tokens revocados

---

## 8. ESTADO DE MADUREZ

| Dimensión | Estado |
|---|---|
| Funcionalidades | Completas (v3.12) |
| Tests automatizados | 156 pasando |
| Documentación técnica | Exhaustiva |
| Producción | Activo |
| Versiones | 12+ versiones mayores documentadas |
| Historial de cambios | 121 commits documentados |

---

*Documento elaborado para presentación a terceros y registro de propiedad intelectual. Información confidencial. Todos los derechos reservados. Julieta Arrazate — 2026.*
