# DOCUMENTACIÓN TÉCNICA
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Versión documentada:** v3.12 — Junio 2026

---

## 1. ARQUITECTURA GENERAL

El sistema implementa una arquitectura de tres capas (three-tier) con separación clara de responsabilidades:

```
┌────────────────────────────────────────────────────────────┐
│  CAPA DE PRESENTACIÓN                                      │
│  ┌──────────────────┐  ┌────────────────┐                 │
│  │   Web App (PWA)  │  │  Mobile App    │                 │
│  │  React 18 + TS   │  │ React Native   │                 │
│  └────────┬─────────┘  └───────┬────────┘                 │
└───────────┼────────────────────┼────────────────────────── ┘
            │ HTTPS/REST         │ HTTPS/REST
┌───────────┼────────────────────┼────────────────────────── ┐
│  CAPA DE NEGOCIO               │                           │
│  ┌────────▼───────────────────▼──────────────────────┐    │
│  │          FastAPI (Python 3.11)                     │    │
│  │  Routers (22) · Services (18) · Models (18)        │    │
│  │  Middleware JWT · Rate Limiting · CORS             │    │
│  └────────────────────────┬───────────────────────────┘    │
└───────────────────────────┼───────────────────────────── ──┘
                            │ SQLAlchemy ORM
┌───────────────────────────┼────────────────────────────────┐
│  CAPA DE DATOS            │                                │
│  ┌────────────────────────▼───────────────────────────┐    │
│  │       PostgreSQL — 18 modelos, 9 migraciones       │    │
│  │       Numeric(12,2) · Soft delete · Audit log      │    │
│  └────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

---

## 2. ARQUITECTURA DEL BACKEND (FastAPI)

### 2.1 Estructura de capas internas

```
app/
├── main.py              # Punto de entrada: lifespan, safety nets, routers, middleware
├── config.py            # Settings por entorno (pydantic-settings, env vars)
├── database.py          # Engine SQLAlchemy, SessionLocal, Base declarativa
├── middleware/auth.py   # Dependencias de autenticación y permisos
├── models/              # Modelos ORM (18 modelos)
├── routers/             # Endpoints HTTP (22 routers)
├── services/            # Lógica de negocio (18 servicios)
└── schemas/             # Validación Pydantic de entrada/salida (8 esquemas)
```

### 2.2 Ciclo de vida de la aplicación (lifespan)

Al iniciar, el servidor ejecuta en orden:

1. **Migraciones automáticas**: `_run_alembic()` aplica migraciones pendientes. Si la base no tiene historial, la sella en `head`.
2. **Safety nets**: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para columnas nuevas que podrían no estar en instancias legadas.
3. **Plan de cuentas**: `PLAN_PATCH` agrega cuentas contables nuevas sin sobrescribir las existentes (idempotente).
4. **Backfill**: vincula clientes existentes a sus cuentas contables por nombre normalizado.
5. **Cleanup de tokens vencidos**: limpia `login_approvals` y `twofa_codes` expirados.
6. **Scheduler APScheduler**: inicia tareas programadas (backup 03:00 ART, alertas push 10:00 ART).

### 2.3 Encodificación de tipos numéricos

Se implementó un encoder JSON personalizado (`_DecimalEncoder`) para serializar transparentemente los tipos `decimal.Decimal` (devueltos por SQLAlchemy para columnas `Numeric`) como valores de punto flotante en las respuestas JSON, sin requerir conversiones explícitas en cada router.

### 2.4 Organización de routers

Los routers se registran con prefijo `/` y etiquetas de OpenAPI. Los endpoints públicos (sin autenticación) se montan en `/p/` y utilizan validación por token de 7 días en lugar de JWT.

---

## 3. ARQUITECTURA DEL FRONTEND (React)

### 3.1 Carga diferida de rutas

Todas las páginas se cargan con `React.lazy()` mediante la función auxiliar `lazyPage<M, K>()`, que proporciona tipado estático completo sobre el módulo y la exportación. Solo `Login`, `RecuperarPassword` y `RestablecerPassword` se cargan de forma ansiosa para garantizar el primer render inmediato.

### 3.2 Gestión de estado global

Seis stores independientes con Zustand:

| Store | Responsabilidad |
|---|---|
| `auth` | Usuario autenticado, token JWT, permisos, roles |
| `org` | Organización activa, cambio de org |
| `theme` | Tema light/dark, persistencia en localStorage |
| `lock` | Estado de bloqueo PIN/biometría |
| `confirm` | Diálogo de confirmación global |
| `toast` | Notificaciones de usuario |

### 3.3 Cliente HTTP centralizado (`api.ts`)

Un único módulo (~25 KB) encapsula todas las llamadas a la API con:
- Interceptor de request: inyección automática del token JWT y `org_id` activo
- Interceptor de respuesta: normalización de errores 422 de Pydantic a string legible
- Retry automático: 3 reintentos con backoff lineal (1.5s/3s/4.5s) ante 502/503/504 y errores de red en GET
- Keep-alive: ping a `/health` cada 14 minutos para mantener el backend activo

### 3.4 Progressive Web App (PWA)

- Service Worker con estrategia `network-first` y fallback a caché
- Web App Manifest para instalación en dispositivos móviles
- Share Target API para recibir archivos desde otras aplicaciones
- Web Push API para notificaciones nativas
- AppLockGuard con PIN + WebAuthn (biometría) en dispositivos compatibles

### 3.5 Soporte de tema (dark/light mode)

Script síncrono en `<head>` de `index.html` para evitar el flash de tema incorrecto antes de que React hidrate. El tema se persiste en localStorage y se aplica mediante clases TailwindCSS.

---

## 4. BASE DE DATOS

### 4.1 Motor y configuración

- **Motor:** PostgreSQL (versión cloud managed)
- **ORM:** SQLAlchemy 2.0 con sesiones síncronas y pool de conexiones
- **Migraciones:** Alembic con historial de 9 versiones
- **Aritmética financiera:** todas las columnas monetarias usan `Numeric(12, 2)` para precisión exacta sin errores de punto flotante

### 4.2 Modelos principales

| Modelo | Tabla | Descripción |
|---|---|---|
| `Organizacion` | organizaciones | Entidad multi-tenant raíz |
| `User` | users | Usuarios del sistema con roles y permisos |
| `Cliente` | clientes | Directorio de entidades pagadoras |
| `ExtractoBancario` | extractos_bancarios | Cabecera de extracto |
| `MovimientoBanco` | movimientos_banco | Líneas del extracto bancario |
| `Planilla` | planillas | Cabecera de planilla de pagos |
| `PlanillaRow` | planilla_rows | Filas de planilla con estado de conciliación |
| `Cheque` | cheques | Cheques con ciclo de vida completo |
| `Portador` | portadores | Catálogo de portadores de cheques |
| `ArqueoDiario` | arqueos_diarios | Arqueos de caja con denominaciones |
| `Egreso` | egresos | Pagos y gastos unificados |
| `CategoriaEgreso` | categorias_egreso | Categorías de egresos configurables |
| `Liquidacion` | liquidaciones | Liquidaciones periódicas |
| `LiquidacionDetalle` | liquidacion_detalles | Líneas de liquidación |
| `PlanCuenta` | plan_cuentas | Plan de cuentas jerárquico |
| `Asiento` | asientos | Asientos contables |
| `AsientoDetalle` | asiento_detalles | Líneas de asiento (partida doble) |
| `AuditoriaLog` | auditoria_logs | Log inmutable de operaciones |
| `PatronAprendido` | patrones_aprendidos | Patrones de conciliación automática |

### 4.3 Columnas de control de soft delete

Los modelos con soft delete incluyen:
- `deleted_at` (timestamp): fecha de eliminación lógica
- `deleted_by_id` (FK): usuario que eliminó el registro
- Queries con filtro `WHERE deleted_at IS NULL` para excluir registros eliminados

### 4.4 Migraciones de esquema

| Migración | Descripción |
|---|---|
| 001_baseline | Esquema inicial con todos los modelos fundacionales |
| 002_soft_delete | Columnas de eliminación lógica |
| 003_password_reset | Modelo `PasswordResetToken` |
| 004_performance_indexes | Índices en columnas de búsqueda frecuente |
| 005_revoked_tokens | Tabla de tokens JWT revocados |
| 006_unique_constraints | Restricciones de unicidad en datos críticos |
| 007_float_to_numeric | Conversión de columnas Float → Numeric(12,2) |
| 008_cliente_comision | Campo `porcentaje_comision` en clientes |
| 009_drop_tablas_viejas | Eliminación de tablas de módulos deprecados |

---

## 5. SEGURIDAD

### 5.1 Autenticación

| Mecanismo | Detalle |
|---|---|
| **JWT** | Tokens firmados con clave secreta, expiración 8h (4h para rol contador) |
| **2FA por email** | Código de 6 dígitos con hash SHA-256, TTL 10 minutos (admin y superadmin) |
| **PIN de bloqueo** | Código numérico de 6 dígitos, verificación local en el dispositivo |
| **WebAuthn (biometría)** | Autenticación con huella o Face ID en dispositivos compatibles |
| **Tokens revocados** | Tabla `RevokedToken` para invalidación explícita de JWT |

### 5.2 Autorización (control de acceso)

El sistema implementa un modelo de permisos en 3 capas:

**Capa 1 — Roles:**
- `SUPERADMIN`: acceso completo a todas las organizaciones
- `ADMIN`: gestión completa de su organización
- `OPERADOR`: operatoria diaria sin borrado de datos
- `REVISOR`: solo lectura contable
- `AUDITOR`: lectura contable y financiera
- `CONTADOR`: operatoria + contabilidad en solo lectura + login por aprobación

**Capa 2 — Permisos funcionales:**
- `upload_files`: subir extractos y planillas
- `reconcile`: conciliar y operar planillas
- `manage_finance`: caja, cheques, pagos, cuentas corrientes
- `view_accounting`: libro diario, mayor, sumas y saldo
- `admin_accounting`: plan de cuentas, reglas, backfill, reset
- `manage_users`: usuarios, organizaciones, liquidaciones
- `view_audit`: módulo de auditoría
- `delete_records`: operaciones de borrado (solo Admin y Superadmin)

**Capa 3 — Guard en backend:**
```python
require_permission("nombre_permiso")  # Decorador en dependencias FastAPI
```

### 5.3 Seguridad de red y endpoints

| Medida | Implementación |
|---|---|
| Rate limiting | slowapi — límites configurados en endpoints de auth |
| CORS | Métodos y headers explícitos, sin wildcard |
| Headers HTTP de seguridad | `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy` |
| HTTPS forzado | Configurado en plataforma de despliegue |
| Validación de entrada | Pydantic v2 en todos los endpoints con tipos estrictos |

### 5.4 Flujo de login especial para rol Contador

1. El contador envía credenciales → servidor no devuelve token
2. Se crea un `LoginApproval` en estado `pending` (expira en 10 minutos)
3. Los superadmins reciben notificación push
4. El cliente del contador hace polling a `/auth/login-approval/{id}`
5. Al aprobar, el servidor genera JWT con expiración de 4 horas
6. Token entregado una única vez (invalidado tras el primer uso)

---

## 6. APIs Y ENDPOINTS PRINCIPALES

### 6.1 Grupos de endpoints

| Prefijo | Módulo | Autenticación |
|---|---|---|
| `/auth/*` | Autenticación y 2FA | Pública + protegida |
| `/me` | Perfil del usuario | JWT |
| `/admin/*` | Gestión de usuarios | JWT + manage_users |
| `/extractos/*` | Extractos bancarios | JWT + upload_files |
| `/planillas/*` | Planillas de pagos | JWT + upload_files/reconcile |
| `/clientes/*` | Directorio de clientes | JWT |
| `/cheques/*` | Gestión de cheques | JWT + manage_finance |
| `/pagos/*` | Módulo de egresos | JWT + manage_finance |
| `/caja/*` | Caja y arqueos | JWT + manage_finance |
| `/contabilidad/*` | Contabilidad | JWT + view/admin_accounting |
| `/liquidaciones/*` | Liquidaciones | JWT + reconcile/manage_users |
| `/auditoria/*` | Log de auditoría | JWT + view_audit |
| `/analisis/*` | Reportes y alertas | JWT |
| `/search/*` | Búsqueda global | JWT |
| `/agente/*` | IA y OCR | JWT |
| `/p/*` | Acceso público | Token de 7 días (sin JWT) |

### 6.2 Formato de respuestas

Todas las respuestas utilizan JSON. Los tipos `Decimal` de SQLAlchemy se serializan automáticamente como números de punto flotante mediante el encoder personalizado `_DecimalEncoder`. Los errores siguen el formato FastAPI estándar con campo `detail`.

---

## 7. INTEGRACIONES EXTERNAS

### 7.1 Google Gemini (IA y OCR)

**Configuración:** variable de entorno `GEMINI_API_KEY`. Si no está presente, las funciones de IA y OCR quedan desactivadas sin errores.

**Modelo utilizado:** `gemini-2.5-flash` (configurable vía `GEMINI_MODEL`)

**Uso:**
- **Chat IA:** function calling con 5 funciones que acceden a datos reales de la base de datos
- **OCR cheques:** envía la imagen como `inline_data` y extrae número, banco, librador, monto, fechas
- **OCR comprobantes:** extrae monto, fecha, beneficiario y referencia de comprobantes de transferencia

**Manejo de errores:** clasificación de errores de API (clave inválida, cuota agotada, modelo no disponible) con mensajes amigables. Reintento automático con espera de 5 segundos ante errores de límite por minuto.

### 7.2 Resend (Email)

**Configuración:** variable de entorno `RESEND_API_KEY`. Sin ella, las funciones de email se deshabilitan (degradación elegante).

**Uso:**
- Código 2FA (asunto: "Código de verificación")
- Recuperación de contraseña (link de restablecimiento)
- Backup diario del sistema (adjunto JSON gzipeado)

### 7.3 Web Push / VAPID

**Configuración:** variables `VAPID_PUBLIC_KEY` y `VAPID_PRIVATE_KEY`. Sin ellas, el scheduler de alertas no se activa.

**Uso:**
- Alertas de cheques próximos a vencer (≤3 días)
- Movimientos sin conciliar por más de 7 días
- Notificación de solicitud de sesión de rol contador
- Push de prueba desde el perfil de administrador

### 7.4 AWS S3 / Cloudflare R2

**Configuración:** variables `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_URL`. Sin ellas, las fotos se almacenan como base64 en la base de datos.

**Uso:** almacenamiento de fotos de comprobantes de egresos y cheques.

### 7.5 Sentry

**Configuración:** variables `SENTRY_DSN` (backend) y `VITE_SENTRY_DSN` (frontend). Opt-in, sin overhead si no se configuran.

**Uso:** captura de excepciones no manejadas en backend y frontend para monitoreo en producción.

---

## 8. AUDITORÍA

El módulo de auditoría registra automáticamente:

| Campo | Descripción |
|---|---|
| `usuario_id` / `usuario_nombre` | Quién realizó la operación |
| `accion` | Tipo de operación (crear, editar, eliminar, conciliar, etc.) |
| `entidad` | Módulo afectado (planilla, cheque, egreso, etc.) |
| `entidad_id` | ID del registro afectado |
| `datos_antes` | Estado del registro antes del cambio (JSON) |
| `datos_despues` | Estado del registro después del cambio (JSON) |
| `ip_address` | Dirección IP del cliente |
| `created_at` | Timestamp UTC del evento |
| `organizacion_id` | Organización en contexto |

Los datos JSON del log son inmutables una vez escritos. La serialización de tipos `Decimal` se resuelve con conversión recursiva antes de persistir.

---

## 9. SCHEDULER (TAREAS PROGRAMADAS)

Implementado con APScheduler en proceso, se inicia en el lifespan de FastAPI:

| Tarea | Hora (ART) | Condición de activación |
|---|---|---|
| Backup JSON gzipeado por email | 03:00 | `RESEND_API_KEY` seteada |
| Alertas push (cheques + movimientos) | 10:00 | `VAPID_PRIVATE_KEY` seteada |
| Cleanup de tokens vencidos | Al iniciar | Siempre |

---

## 10. TIMEZONE Y FECHAS

El servidor corre en UTC. Todas las fechas de negocio (transacciones, operaciones, arqueos, cheques, asientos) se calculan en UTC-3 (America/Argentina/Buenos_Aires) mediante el servicio `app/services/tz.py`:

```python
def hoy_art() -> date:     # date.today() en timezone ART
def now_art() -> datetime:  # datetime.now() en timezone ART
```

Las marcas de auditoría (`created_at`) y expiración de tokens de seguridad permanecen en UTC, lo cual es correcto por convención.

El frontend usa el helper `src/utils/fecha.ts` para construir fechas desde los componentes locales del calendario (año/mes/día) en lugar de `toISOString()` que devuelve UTC.

---

## 11. PROCESAMIENTO OCR

### 11.1 Flujo de OCR de cheques

1. Usuario adjunta fotografía desde el formulario
2. El frontend comprime la imagen (canvas JPEG con fondo blanco)
3. Se envía como base64 a `POST /agente/ocr-cheque`
4. El backend envía a Gemini Flash con prompt específico
5. Gemini devuelve JSON con: número, banco, librador, monto, fecha de emisión, fecha de depósito
6. El frontend pre-completa solo los campos vacíos del formulario

### 11.2 Flujo de OCR de comprobantes de transferencia

1. Usuario adjunta foto del comprobante en el módulo de egresos
2. El frontend comprime la imagen
3. Se envía a `POST /agente/ocr-transferencia`
4. El backend extrae: monto, fecha, beneficiario, referencia
5. El frontend pre-completa campos vacíos

### 11.3 Parseo de montos en formato argentino

Se implementó el helper `parseMonto()` para convertir formatos numéricos argentinos (`"15.000,50"`), estadounidenses (`"15,000.50"`) y planos (`"15000.5"`) a tipo numérico estándar antes de guardar en el formulario.

---

## 12. MOTOR DE CONCILIACIÓN

Ver documento `ACTIVOS_PI.md` para descripción detallada del algoritmo.

**Entrada:** extracto bancario (filas de `MovimientoBanco`) + planilla de pagos (filas de `PlanillaRow`)

**Proceso:**
1. Normalización de texto (NFKD unicode, mayúsculas, tokens)
2. Extracción de identificadores por tipo (CUIT, CBU, número de cuenta, referencia, titular)
3. Scoring multi-criterio para cada par (movimiento, fila)
4. Selección del movimiento con mayor score para cada fila
5. Actualización de estado y registro de auditoría

**Salida:** planilla con estado por fila (`ok`, `pendiente`, `revisar`) y movimiento asignado

---

*Documento generado para expediente de registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
