# INVENTARIO TÉCNICO DE LA OBRA
## Sistema Integral de Gestión Financiera, Contable y Empresarial
### Denominación de trabajo: Cuadra
> "Cuadra constituye una denominación de trabajo utilizada durante el desarrollo y no implica registro marcario."

**Autora:** Julieta Arrazate  
**Email:** julietaarrazate@gmail.com  
**Repositorio técnico:** conciliacion-bancaria  
**Fecha de relevamiento:** Junio 2026  
**Versión documentada:** v3.12

---

## 1. ESTRUCTURA DE DIRECTORIOS

```
conciliacion-bancaria/
│
├── backend/                          # API REST y lógica de negocio
│   ├── app/
│   │   ├── main.py                   # Punto de entrada FastAPI, lifespan, safety nets
│   │   ├── config.py                 # Configuración por entorno (pydantic-settings)
│   │   ├── database.py               # Motor SQLAlchemy, sesión, base declarativa
│   │   ├── logging_config.py         # Configuración de logs estructurados
│   │   ├── middleware/
│   │   │   └── auth.py               # Middleware de autenticación JWT y permisos
│   │   ├── models/                   # Modelos ORM (SQLAlchemy 2.0)
│   │   │   ├── organizacion.py
│   │   │   ├── user.py
│   │   │   ├── cliente.py
│   │   │   ├── extracto.py
│   │   │   ├── planilla.py
│   │   │   ├── auditoria.py
│   │   │   ├── patron_aprendido.py
│   │   │   ├── liquidacion.py
│   │   │   ├── caja.py
│   │   │   ├── egreso.py
│   │   │   ├── contabilidad.py
│   │   │   ├── cheque.py
│   │   │   ├── portador.py
│   │   │   ├── password_reset.py
│   │   │   ├── push_subscription.py
│   │   │   ├── revoked_token.py
│   │   │   ├── login_approval.py
│   │   │   └── twofa_code.py
│   │   ├── routers/                  # Endpoints HTTP (22 routers)
│   │   │   ├── auth.py
│   │   │   ├── me.py
│   │   │   ├── admin.py
│   │   │   ├── extractos.py
│   │   │   ├── planillas.py
│   │   │   ├── historial.py
│   │   │   ├── auditoria.py
│   │   │   ├── clientes_dir.py
│   │   │   ├── organizaciones.py
│   │   │   ├── liquidaciones.py
│   │   │   ├── caja.py
│   │   │   ├── cheques.py
│   │   │   ├── pagos.py
│   │   │   ├── contabilidad.py
│   │   │   ├── analisis.py
│   │   │   ├── search.py
│   │   │   ├── public_router.py
│   │   │   ├── push_router.py
│   │   │   ├── agente.py
│   │   │   ├── papelera.py
│   │   │   └── backup_admin.py
│   │   ├── services/                 # Servicios de negocio (18 servicios)
│   │   │   ├── conciliacion.py       # Motor de conciliación con scoring
│   │   │   ├── motor_contable.py     # Motor de asientos automáticos
│   │   │   ├── excel_parser.py       # Parser multi-banco de extractos
│   │   │   ├── excel_export.py       # Exportación a formato Excel
│   │   │   ├── pdf_export.py         # Generación de PDFs
│   │   │   ├── extracto_merger.py    # Fusión/deduplicación de extractos
│   │   │   ├── aprendizaje.py        # Motor de aprendizaje por patrones
│   │   │   ├── auditoria.py          # Registro de log de auditoría
│   │   │   ├── email_sender.py       # Envío de emails transaccionales
│   │   │   ├── backup_service.py     # Backup JSON gzipeado
│   │   │   ├── backup_scheduler.py   # Scheduler (backups + alertas push)
│   │   │   ├── push_service.py       # Servicio de notificaciones web push
│   │   │   ├── password_reset.py     # Flujo de recuperación de contraseña
│   │   │   ├── storage.py            # Almacenamiento S3/R2 con fallback DB
│   │   │   ├── cierre_periodo.py     # Servicio de cierre de período contable
│   │   │   ├── tz.py                 # Helper de timezone (UTC-3 Argentina)
│   │   │   └── auth.py               # Utilidades de autenticación
│   │   └── schemas/                  # Esquemas Pydantic de validación (8 schemas)
│   ├── alembic/
│   │   └── versions/                 # 9 migraciones de base de datos
│   │       ├── 001_baseline.py
│   │       ├── 002_soft_delete.py
│   │       ├── 003_password_reset.py
│   │       ├── 004_performance_indexes.py
│   │       ├── 005_revoked_tokens.py
│   │       ├── 006_unique_constraints.py
│   │       ├── 007_float_to_numeric.py
│   │       ├── 008_cliente_comision.py
│   │       └── 009_drop_tablas_viejas.py
│   └── tests/                        # Suite de tests automatizados (156 tests)
│       ├── test_conciliacion.py
│       ├── test_motor_contable.py
│       ├── test_excel_parser.py
│       ├── test_auth.py
│       ├── test_audit_fixes.py
│       ├── test_backup_service.py
│       ├── test_fixes.py
│       ├── test_soft_delete.py
│       ├── test_tz.py
│       └── test_v34_features.py
│
├── frontend/                         # Aplicación web React (PWA)
│   └── src/
│       ├── App.tsx                   # Enrutador raíz, guards de autenticación
│       ├── main.tsx                  # Bootstrap React + Sentry
│       ├── pages/                    # 31 páginas/vistas
│       │   ├── Landing.tsx           # Página pública de presentación
│       │   ├── Login.tsx
│       │   ├── Dashboard.tsx
│       │   ├── Historial.tsx
│       │   ├── Conciliaciones.tsx
│       │   ├── Movimientos.tsx
│       │   ├── ExtractosArchivo.tsx
│       │   ├── Clientes.tsx
│       │   ├── Cheques.tsx
│       │   ├── Pagos.tsx
│       │   ├── Caja.tsx
│       │   ├── Contabilidad.tsx
│       │   ├── Liquidaciones.tsx
│       │   ├── Auditoria.tsx
│       │   ├── Usuarios.tsx
│       │   ├── Organizaciones.tsx
│       │   ├── Perfil.tsx
│       │   ├── Resumen.tsx
│       │   ├── EstadoCuenta.tsx
│       │   ├── FlujoCaja.tsx
│       │   ├── Revision.tsx
│       │   ├── Actividad.tsx
│       │   ├── Aprobaciones.tsx
│       │   ├── Bulk.tsx
│       │   ├── Compartir.tsx
│       │   ├── PaginaPublica.tsx
│       │   ├── Papelera.tsx
│       │   ├── RecuperarPassword.tsx
│       │   ├── RestablecerPassword.tsx
│       │   ├── Privacidad.tsx
│       │   └── Terminos.tsx
│       ├── components/               # 18 componentes reutilizables
│       │   ├── Layout.tsx
│       │   ├── AgenteChat.tsx
│       │   ├── PlanillaPanel.tsx
│       │   ├── FileUpload.tsx
│       │   ├── SearchModal.tsx
│       │   ├── ConfirmDialog.tsx
│       │   ├── AppLockGuard.tsx
│       │   ├── LockScreen.tsx
│       │   ├── CuadraLogo.tsx
│       │   ├── Toaster.tsx
│       │   ├── ThemeToggle.tsx
│       │   ├── Skeleton.tsx
│       │   ├── Button.tsx
│       │   ├── Input.tsx
│       │   ├── ConfirmModal.tsx
│       │   ├── charts/BarChart.tsx
│       │   ├── charts/DonutChart.tsx
│       │   └── charts/LineChart.tsx
│       ├── services/
│       │   └── api.ts                # Cliente HTTP centralizado con cache SWR (~25 KB)
│       ├── store/                    # Estado global Zustand (6 stores)
│       │   ├── auth.ts
│       │   ├── org.ts
│       │   ├── theme.ts
│       │   ├── lock.ts
│       │   ├── confirm.ts
│       │   └── toast.ts
│       ├── utils/
│       │   └── fecha.ts              # Helper timezone UTC-3 Argentina
│       └── public/
│           └── sw.js                 # Service Worker PWA
│
└── mobile/                           # Aplicación móvil React Native (Expo)
    └── src/
        ├── screens/                  # Pantallas móviles
        ├── components/               # Componentes nativos
        ├── navigation/               # Navegación React Navigation
        ├── services/                 # Cliente API móvil
        └── store/                    # Estado global móvil
```

---

## 2. TECNOLOGÍAS Y FRAMEWORKS

### 2.1 Backend

| Tecnología | Versión | Rol |
|---|---|---|
| **Python** | 3.11 | Lenguaje principal del servidor |
| **FastAPI** | 0.115.0 | Framework web API REST asíncrono |
| **SQLAlchemy** | 2.0.36 | ORM de base de datos |
| **Alembic** | 1.13.3 | Migraciones de esquema de base de datos |
| **PostgreSQL** | — | Base de datos relacional |
| **Pydantic** | 2.9.2 | Validación de datos y esquemas |
| **pydantic-settings** | 2.6.0 | Gestión de configuración por entorno |
| **python-jose** | 3.3.0 | JWT (JSON Web Tokens) |
| **passlib** | — | Hashing de contraseñas (pbkdf2_sha256) |
| **openpyxl** | 3.1.5 | Lectura y escritura de archivos Excel |
| **xlrd** | 2.0.1 | Lectura de Excel (.xls legacy) |
| **reportlab** | 4.2.5 | Generación de documentos PDF |
| **slowapi** | 0.1.9 | Rate limiting de endpoints |
| **APScheduler** | 3.10.4 | Scheduler de tareas programadas |
| **pywebpush** | ≥1.14.0 | Notificaciones Web Push (VAPID) |
| **boto3** | 1.35.49 | Cliente AWS S3 / Cloudflare R2 |
| **google-generativeai** | 0.8.3 | SDK de Gemini AI |
| **sentry-sdk[fastapi]** | — | Monitoreo de errores en producción |
| **pytest** | 8.3.4 | Framework de tests |
| **httpx** | 0.27.2 | Cliente HTTP para tests |

### 2.2 Frontend Web

| Tecnología | Versión | Rol |
|---|---|---|
| **React** | 18.2.0 | Biblioteca UI declarativa |
| **TypeScript** | 5.3.0 | Tipado estático |
| **Vite** | 5.0.0 | Bundler y servidor de desarrollo |
| **TailwindCSS** | 3.4.0 | Framework de estilos utilitarios |
| **React Router DOM** | 6.20.0 | Enrutamiento SPA |
| **Zustand** | 4.4.0 | Gestión de estado global |
| **Axios** | 1.6.0 | Cliente HTTP con interceptores |
| **jsPDF** | 4.2.1 | Generación de PDFs en cliente |
| **vite-plugin-pwa** | 1.2.0 | Progressive Web App |
| **@sentry/react** | 10.56.0 | Monitoreo de errores frontend |

### 2.3 Aplicación Móvil

| Tecnología | Versión | Rol |
|---|---|---|
| **React Native** | 0.73.6 | Framework móvil nativo |
| **Expo** | ~50.0.0 | Plataforma de desarrollo móvil |
| **React Navigation** | 6.x | Navegación nativa |
| **TypeScript** | 5.3.0 | Tipado estático |
| **Zustand** | 4.4.0 | Gestión de estado |
| **expo-secure-store** | ~12.8.1 | Almacenamiento seguro de credenciales |
| **expo-document-picker** | ~11.10.1 | Selección de documentos |

---

## 3. DEPENDENCIAS PRINCIPALES

### 3.1 Dependencias de Backend (`requirements.txt`)

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
python-jose[cryptography]==3.3.0
pydantic==2.9.2
pydantic[email]==2.9.2
pydantic-settings==2.6.0
email-validator==2.2.0
python-multipart==0.0.12
openpyxl==3.1.5
xlrd==2.0.1
python-dotenv==1.0.1
requests==2.32.3
slowapi==0.1.9
alembic==1.13.3
apscheduler==3.10.4
reportlab==4.2.5
pywebpush>=1.14.0
boto3==1.35.49
google-generativeai==0.8.3
sentry-sdk[fastapi]
```

---

## 4. COMPONENTES DEL SISTEMA

### 4.1 Capa de API (Backend)

| Router | Función principal |
|---|---|
| `auth` | Autenticación, registro, 2FA, aprobación de sesión |
| `me` | Perfil del usuario autenticado |
| `admin` | Gestión de usuarios y roles (superadmin/admin) |
| `extractos` | Importación y gestión de extractos bancarios |
| `planillas` | Carga y gestión de planillas de pagos |
| `historial` | Historial de operaciones y búsqueda |
| `clientes_dir` | Directorio de clientes y entidades |
| `organizaciones` | Gestión multi-empresa (multitenancy) |
| `liquidaciones` | Generación y gestión de liquidaciones |
| `caja` | Módulo de caja, arqueos y operaciones |
| `cheques` | Gestión completa del ciclo de cheques |
| `pagos` | Módulo unificado de egresos y pagos |
| `contabilidad` | Libro diario, plan de cuentas, cuentas corrientes |
| `analisis` | Análisis, reportes, alertas inteligentes |
| `auditoria` | Log de auditoría de operaciones |
| `search` | Búsqueda global del sistema |
| `public_router` | Endpoints públicos sin autenticación |
| `push_router` | Suscripciones a notificaciones push |
| `agente` | Asistente IA + OCR (Gemini) |
| `papelera` | Soft delete y recuperación de registros |
| `backup_admin` | Gestión de backups del sistema |

### 4.2 Capa de Servicios (Backend)

| Servicio | Función |
|---|---|
| `conciliacion` | Motor de conciliación bancaria con scoring |
| `motor_contable` | Generación automática de asientos contables |
| `excel_parser` | Parser multi-banco de extractos Excel |
| `excel_export` | Exportación de datos a Excel |
| `pdf_export` | Generación de PDFs de reportes y estados |
| `extracto_merger` | Fusión y deduplicación de extractos bancarios |
| `aprendizaje` | Aprendizaje por patrones de correcciones manuales |
| `auditoria` | Registro centralizado de trazabilidad |
| `backup_service` | Backup periódico en JSON gzipeado |
| `backup_scheduler` | Scheduler de backups y alertas automáticas |
| `push_service` | Envío de notificaciones Web Push vía VAPID |
| `email_sender` | Envío de correos transaccionales |
| `password_reset` | Flujo seguro de recuperación de contraseña |
| `storage` | Gestión de archivos S3/R2 con fallback base64 |
| `cierre_periodo` | Cierre y validación de períodos contables |
| `tz` | Normalización de timezone (UTC-3 Argentina) |

---

## 5. SERVICIOS EXTERNOS UTILIZADOS

| Servicio | Propósito | Requerimiento |
|---|---|---|
| **PostgreSQL / Neon** | Base de datos relacional | Obligatorio |
| **Google Gemini Flash** | IA conversacional + OCR | Opcional (GEMINI_API_KEY) |
| **Resend** | Emails transaccionales (2FA, backups, password reset) | Opcional (RESEND_API_KEY) |
| **AWS S3 / Cloudflare R2** | Almacenamiento de archivos e imágenes | Opcional (S3_* vars) |
| **Sentry** | Monitoreo de errores en producción | Opcional (SENTRY_DSN) |
| **Web Push (VAPID)** | Notificaciones push en PWA | Opcional (VAPID_* vars) |

---

## 6. ARQUITECTURA GENERAL

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENTES                                │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Navegador Web │  │  PWA móvil  │  │ App React Native│ │
│  │  (React + TS)  │  │  instalada  │  │  (Expo)       │  │
│  └───────┬────────┘  └──────┬───────┘  └──────┬────────┘  │
└──────────┼─────────────────┼────────────────┼─────────────┘
           │ HTTPS            │ HTTPS          │ HTTPS
           ▼                  ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    API REST                                  │
│                FastAPI (Python 3.11)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Auth/JWT │ │ Routers  │ │ Services │ │  Middleware   │  │
│  │  2FA     │ │  (22)    │ │   (18)   │ │  (auth, rate) │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ SQLAlchemy ORM
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               POSTGRESQL (Neon Cloud)                        │
│  18 modelos · 9 migraciones · Aritmética Numeric(12,2)      │
└─────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼───────────────────┐
          ▼                 ▼                   ▼
    ┌──────────┐    ┌──────────────┐    ┌──────────────┐
    │  Gemini   │    │  S3 / R2     │    │  Resend      │
    │  AI + OCR │    │  Storage     │    │  Email       │
    └──────────┘    └──────────────┘    └──────────────┘
```

---

## 7. MÉTRICAS CUANTITATIVAS DEL CÓDIGO FUENTE

| Métrica | Valor |
|---|---|
| **Routers (endpoints HTTP)** | 22 |
| **Servicios de negocio** | 18 |
| **Modelos de base de datos** | 18 |
| **Esquemas de validación** | 8 |
| **Migraciones de BD** | 9 |
| **Páginas frontend** | 31 |
| **Componentes frontend** | 18 |
| **Stores de estado global** | 6 |
| **Archivos Python (backend)** | ~74 |
| **Archivos TypeScript/TSX** | ~61 |
| **Archivos de tests** | 10 |
| **Tests automatizados** | 156 |
| **Commits en repositorio** | 121 |
| **Rama principal** | main |

---

## 8. PLATAFORMAS DE DESPLIEGUE

| Componente | Plataforma | Observaciones |
|---|---|---|
| **Frontend (web)** | Vercel | Deploy automático por push a main |
| **Backend (API)** | Render | Servicio web, free tier con keep-alive |
| **Base de datos** | Neon PostgreSQL | Cloud serverless, pool de conexiones |
| **Archivos/fotos** | Cloudflare R2 / AWS S3 | Opcional, fallback a base64 en DB |
| **Monitoreo** | Sentry | Opt-in, requiere DSN configurado |

---

*Documento generado para expediente de registro de obra de software — Todos los derechos reservados — Julieta Arrazate — 2026*
