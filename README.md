# Sistema de Conciliación Bancaria

Plataforma web y móvil para automatizar la conciliación de transferencias bancarias contra planillas de clientes, con autenticación, auditoría completa, multi-tenant y permisos granulares. fix deploy

## Autora y Propietaria

**Julieta Arrazate** — Desarrolladora, propietaria intelectual y titular de todos los derechos sobre este sistema.

Este software es propiedad exclusiva de Julieta Arrazate. Queda prohibida su reproducción, distribución o uso comercial sin autorización expresa de la autora.

## Inicio Rápido

### Backend

```bash
cd backend
pip install -r requirements.txt
export SUPERADMIN_PASSWORD="tu_contraseña_segura"
python seed.py
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Estructura del Proyecto

```
conciliacion-bancaria/
├── backend/                    # API FastAPI + BD PostgreSQL
│   ├── app/
│   │   ├── models/            # SQLAlchemy: Organizacion, User, Cliente, Extracto, Planilla
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # conciliacion.py, excel_parser, excel_export
│   │   ├── routers/           # auth, me, extractos, planillas, admin, organizaciones
│   │   └── middleware/        # Auth JWT + superadmin
│   └── seed.py
│
├── frontend/                   # React 18 + TypeScript + Vite + TailwindCSS + PWA
└── mobile/                     # App móvil (React Native — en desarrollo)
```

## Características

### Backend (FastAPI)
- Autenticación JWT con roles y permisos
- **Multi-tenant**: cada organización tiene datos aislados
- **Superadmin** (Julieta Arrazate): acceso a todas las organizaciones
- Configuración de flujo personalizable por cliente (JSON)
- Estados ricos de conciliación por organización
- Cola de revisión manual para orgs con cierre de período
- Match configurable: por referencia, monto+CUIT, monto+fecha
- Auditoría automática de todas las operaciones
- Exportación Excel con Hoja1 (planilla) + Hoja2 (extracto)

### Frontend (React)
- PWA instalable en Android e iOS
- Dashboard con KPIs
- Gestión de clientes, extractos y planillas
- Dark mode persistido
- Login con usuario/contraseña
- **Próximamente**: Login con Google / OAuth2

## Roles y Permisos

| Rol | Permisos |
|---|---|
| **Superadmin** | Todo — acceso a todas las organizaciones |
| **Admin** | Usuarios, auditoría, conciliación |
| **Operador** | Subir archivos, conciliar |
| **Revisor** | Solo lectura de resultados |
| **Auditor** | Solo auditoría y reportes |

## Flujo de Conciliación

1. Cargar extracto bancario (.xlsx Banco Macro)
2. Seleccionar cliente y cargar su planilla de pagos
3. Ejecutar conciliación (algoritmo configurable por organización)
4. Revisar resultados y descargar Excel acreditado

### Estados de Fila (Caneland)
- **ok** — Coincidencia exacta encontrada
- **no está** — Monto no existe en banco
- **duplicado** — Ya fue acreditado antes
- **faltan datos** — Monto común, sin CUIT/titular
- **acreditado DD/MM** — Ya acreditado a otro cliente

### Estados Ricos (orgs Pro)
- **PAGO_PARCIAL** — Pago parcial registrado
- **CONCILIADO_CON_DIFERENCIA** — Conciliado con diferencia de monto
- **VENCIDO** — Pago vencido sin acreditar
- **EN_REVISION** — En cola de revisión manual

## API Endpoints Principales

### Auth
- `POST /auth/login` — Login y obtener JWT

### Extractos
- `POST /extractos/upload` — Subir extracto bancario
- `GET /extractos` — Listar extractos

### Planillas
- `POST /planillas/upload` — Subir planilla cliente
- `POST /planillas/{id}/conciliar` — Ejecutar conciliación
- `GET /planillas/{id}/revision` — Cola de revisión (orgs Pro)
- `POST /planillas/{id}/revision/{row_id}/resolver` — Resolver revisión

### Admin (superadmin)
- `GET /admin/organizaciones` — Listar organizaciones
- `POST /admin/organizaciones` — Crear organización
- `PUT /admin/organizaciones/{id}` — Actualizar configuración

## Producción

- Frontend: [conciliacion-bancaria-ten.vercel.app](https://conciliacion-bancaria-ten.vercel.app)
- Backend: [conciliacion-api.onrender.com](https://conciliacion-api.onrender.com)
- Base de datos: Neon PostgreSQL

## Seguridad

- Contraseñas hasheadas (pbkdf2_sha256)
- JWT tokens con expiración de 8h
- SQL injection prevention (ORM SQLAlchemy)
- CORS configurado
- Auditoría completa de cambios
- Contraseña de superadmin vía variable de entorno (nunca en código)
- **Roadmap**: autenticación biométrica (huella dactilar) para acceso móvil

## Licencia

© 2026 **Julieta Arrazate** — Todos los derechos reservados.

Este software es propiedad intelectual exclusiva de Julieta Arrazate.
Desarrollado a partir de Mayo 2026.
