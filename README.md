# Cuadra — Conciliación Bancaria y Gestión Financiera

Plataforma web y móvil (PWA) para estudios contables y empresas argentinas. Automatiza la
conciliación de transferencias bancarias contra las planillas de cada cliente, y suma una suite
completa de gestión financiera: cheques, pagos, caja, liquidaciones, contabilidad de partida doble,
liquidación de impuestos y un asistente con IA. Multi-tenant, con auditoría completa y permisos
granulares.

## Autora y Propietaria

**Julieta Arrazate** — Desarrolladora, propietaria intelectual y titular de todos los derechos sobre
este sistema.

Este software es propiedad exclusiva de Julieta Arrazate. Queda prohibida su reproducción,
distribución o uso comercial sin autorización expresa de la autora.

---

## Módulos

### Conciliación bancaria
- Importación de extractos bancarios en Excel con **detección automática de formato** de múltiples
  bancos argentinos (Macro, Nación, BBVA, Santander, Galicia, ICBC, HSBC, Ciudad, Provincia…) más un
  parser genérico para cualquier planilla.
- Carga de "Últimos Movimientos" (UM) diarios que se agregan al extracto sin duplicar.
- **Motor de conciliación con scoring por identidad** (CUIT, CBU/CVU, número de cuenta, referencia,
  titular, cercanía de fecha) que cruza el extracto contra la planilla de cada cliente.
- **IA Nivel 2**: aprende de las correcciones manuales (patrones que, tras confirmarse, se aplican
  solos).
- Carga masiva (varias planillas en lote, auto-conciliadas).
- Export Excel formato banco para el contador + PDF de cierre mensual.

### Gestión financiera
- **Cheques** — cartera de cheques con alertas de vencimiento, estados (depositado, acreditado,
  rechazado) y comisiones.
- **Pagos y Gastos** — órdenes de pago con foto del comprobante, OCR del importe/fecha y compartir
  por WhatsApp.
- **Caja** — arqueo diario de efectivo.
- **Liquidaciones** — liquidación de comisiones por cliente y período, con cierre.
- **Contabilidad** — partida doble completa: plan de cuentas, asientos automáticos y manuales, libro
  diario, libro mayor, cuentas corrientes por cliente, sumas y saldos, balance. Export a formatos
  contables (Tango, Holistor, etc.).

### Liquidación de impuestos
- **IVA** — proyección y DDJJ a partir de los asientos contables.
- **Monotributo** — control semestral de facturación contra las escalas de categoría de ARCA.
- **Ingresos Brutos** — proyección con Convenio Multilateral.
- **Sueldos / F931** — liquidador de sueldos y cargas sociales.

### Asistente con IA (Gemini, opt-in)
- Chat en lenguaje natural con acceso a los datos reales (saldos, comisiones, cheques por vencer,
  movimientos sin conciliar).
- OCR de comprobantes y transcripción de voz desde el celular.
- Alertas proactivas (saludo con lo importante del día).

### ARCA — facturación electrónica
- Integración propia con WSFEv1/WSAA (emisión de CAE), con asiento contable automático.
- **Construido pero desactivado a propósito** — se activa por organización cuando un cliente lo
  solicite (ver `CLAUDE.md`).

---

## Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL (Neon) · Python 3.11 · Alembic
- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS · PWA instalable (Android/iOS)
- **Auth**: JWT 8h · `pbkdf2_sha256` · rate limiting (slowapi) · headers de seguridad · 2FA opcional
- **Diseño**: inspirado en Linear · Inter · dark mode

## Arquitectura de producción

- **Frontend** → Vercel — https://conciliacion-bancaria-ten.vercel.app
- **Backend** → Render — https://conciliacion-api.onrender.com
- **Base de datos** → Neon PostgreSQL
- Keep-alive con UptimeRobot (`/health`) para mitigar el cold start del free tier.

---

## Inicio rápido (desarrollo)

### Backend

```bash
cd backend
pip install -r requirements.txt
export SUPERADMIN_PASSWORD="tu_contraseña_segura"
# export DATABASE_URL="postgresql://..."   # opcional; por defecto usa SQLite local
python seed.py                              # siembra org base + plan de cuentas + superadmin
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend && python -m pytest -q     # ~460 tests
cd frontend && npx tsc --noEmit       # type-check
```

---

## Estructura del repositorio

```
conciliacion-bancaria/
├── backend/                      # API FastAPI + PostgreSQL
│   ├── app/
│   │   ├── models/               # Organizacion, User, Cliente, Extracto, Planilla, Cheque,
│   │   │                         #   Pago, Gasto, Liquidacion, Asiento, PlanCuenta, ARCA…
│   │   ├── schemas/              # Pydantic
│   │   ├── services/             # conciliacion, excel_parser/export, motor_contable,
│   │   │                         #   backup, push, email, módulos de impuestos…
│   │   ├── routers/              # auth, extractos, planillas, cheques, pagos, caja,
│   │   │                         #   contabilidad, liquidaciones, iva, monotributo, arca…
│   │   └── middleware/           # Auth JWT + permisos + aislamiento multi-tenant
│   ├── alembic/                  # Migraciones
│   └── seed.py
│
├── frontend/                     # React 18 + TS + Vite + Tailwind + PWA (la app mobile es la PWA instalable)
└── *.md                          # Documentación (ver abajo)
```

---

## Roles y permisos

El acceso se controla por permisos granulares según el rol (más el flag **superadmin**, que ve y
gestiona todas las organizaciones).

| Rol | Permisos principales |
|---|---|
| **Superadmin** | Todo, en todas las organizaciones |
| **Admin** | Usuarios, auditoría, conciliación, finanzas y contabilidad completa, borrado |
| **Contador** | Conciliación, finanzas, contabilidad (lectura), auditoría |
| **Operador** | Subir archivos, conciliar, finanzas, contabilidad (lectura) |
| **Auditor** | Auditoría, contabilidad (lectura), finanzas |
| **Revisor** | Solo lectura de resultados y contabilidad |

Cada organización ve **solo sus propios datos**: el aislamiento multi-tenant se aplica en cada
endpoint de lectura y escritura.

## Motor de conciliación

Scoring por identidad (a mayor puntaje, mayor confianza del match):

| Señal | Puntos |
|---|---|
| CUIT exacto (10-11 dígitos) | 12 |
| CBU/CVU exacto (22 dígitos) | 10 |
| Número de cuenta largo (10+ dígitos) | 8 |
| Número de referencia (6-9 dígitos) | 6 |
| Titular (2 palabras / 1 palabra) | 5 / 3 |
| Bonus por fecha cercana | +1 a +5 |

**Regla fundamental**: si un monto está duplicado en el extracto, siempre se exige identidad
(CUIT/CBU/referencia) para acreditar. Tolerancia de fecha configurable por organización.

---

## Integraciones opcionales (feature flags)

Todo se degrada solo si la variable no está seteada — ninguna rompe el sistema:

| Variable(s) | Función |
|---|---|
| `GEMINI_API_KEY` | Asistente IA, OCR y transcripción de voz |
| `RESEND_API_KEY` | Backup diario por email + 2FA admin/superadmin |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Notificaciones push (Web Push) |
| `S3_*` (5 vars) | Storage de fotos en Cloudflare R2 / S3 (por defecto, base64 en DB) |
| `SENTRY_DSN` / `VITE_SENTRY_DSN` | Monitoreo de errores y performance |
| `GOOGLE_CLIENT_ID` / `VITE_GOOGLE_CLIENT_ID` | Login con Google |
| `ARCA_ENCRYPTION_KEY` | Cifrado de certificados ARCA (módulo opt-in por org) |
| `SLOW_REQUEST_MS` | Umbral del log de requests lentas (default 1500 ms) |

---

## Seguridad

- Contraseñas con `pbkdf2_sha256` (nunca en texto plano).
- JWT con expiración de 8 h · rate limiting contra fuerza bruta · 2FA opcional para admin/superadmin.
- Aislamiento multi-tenant en cada endpoint.
- Prevención de inyección SQL vía ORM (SQLAlchemy) · CORS restringido al dominio de producción.
- Headers de seguridad bancaria (HSTS, X-Frame-Options, etc.).
- Auditoría completa: quién hizo qué, cuándo y desde dónde.
- Backup automático diario (cuando está configurado) · contraseña de superadmin solo por env var.
- PIN + biometría para bloqueo de la app en mobile.

---

## Documentación

Este README es el **índice**. La documentación detallada vive en [`docs/`](docs/README.md).

### 📚 Documentación técnica especializada — [`docs/`](docs/README.md)
Arquitectura, modelo de dominio, motor contable, reglas de negocio, API, base de datos, seguridad,
UX/diseño, decisiones (ADR) y **playbooks** para extender el sistema. Empezá por
[`docs/README.md`](docs/README.md).

### 🧭 Orientación y proceso
| Archivo | Contenido |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Orientación rápida del repo + puntero a `/docs` |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Cómo contribuir, setup, reglas de oro |
| [`SECURITY.md`](SECURITY.md) | Política de seguridad y reporte de vulnerabilidades |
| [`SUPPORT.md`](SUPPORT.md) | Canales de soporte |
| [`.claude/`](.claude/) | Comandos, checklists, templates y [memoria de ingeniería](.claude/memory/PROJECT_MEMORY.md) para Claude Code |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de versiones (v3.6 → v3.24) |
| [`BUGS.md`](BUGS.md) | Bitácora de bugs recurrentes (causa raíz + cómo evitarlos) |
| [`ROADMAP.md`](ROADMAP.md) | Roadmap por valor/esfuerzo |

### 🚀 Operación
| Archivo | Contenido |
|---|---|
| [`DEPLOY.md`](DEPLOY.md) | Guía de despliegue |
| [`BACKUP_Y_RECUPERACION.md`](BACKUP_Y_RECUPERACION.md) | Backups y recuperación |
| [`PROBAR_EN_CELULAR.md`](PROBAR_EN_CELULAR.md) | Cómo probar la PWA en el celular |
| [`COSTEO.md`](COSTEO.md) | Costeo de infraestructura |

> **CI**: cada push/PR corre tests del backend + type-check/build del frontend
> ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## Licencia

© 2026 **Julieta Arrazate** — Todos los derechos reservados.

Software de propiedad intelectual exclusiva de Julieta Arrazate. Desarrollado a partir de Mayo 2026.
