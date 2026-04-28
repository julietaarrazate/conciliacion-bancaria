# Sistema de Conciliación Bancaria - Aplicación Moderna

Plataforma web y móvil para automatizar la conciliación de transferencias bancarias contra planillas de clientes, con autenticación, auditoría completa y permisos granulares.

## 🚀 Inicio Rápido

### Con Docker (Recomendado)

```bash
cd backend
docker-compose up
```

Esto inicia:
- API FastAPI: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Frontend (en otra terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend en: http://localhost:3000

## 📁 Estructura del Proyecto

```
AppConciliacionBancaria/
├── backend/                    # API FastAPI + BD
│   ├── app/
│   │   ├── models/            # Modelos SQLAlchemy
│   │   ├── schemas/           # Schemas Pydantic
│   │   ├── services/          # Lógica de negocio
│   │   ├── routers/           # Endpoints
│   │   └── middleware/        # Auth, permisos
│   ├── tests/                 # Tests unitarios
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── frontend/                   # Aplicación React
│   ├── src/
│   │   ├── components/        # UI componentes
│   │   ├── pages/            # Páginas
│   │   ├── services/         # API client
│   │   ├── store/            # Estado global
│   │   ├── types/            # TypeScript types
│   │   └── styles/           # Estilos
│   ├── vite.config.ts
│   └── package.json
│
├── mobile/                     # App React Native (próximamente)
└── watcher.py                 # Script original (referencia)
```

## ✨ Características

### Backend (FastAPI)
- ✅ Autenticación JWT con roles y permisos
- ✅ API RESTful completa
- ✅ Base de datos PostgreSQL robusta
- ✅ Auditoría de operaciones
- ✅ Parseo automático de Excel
- ✅ Algoritmo inteligente de matching (migrado de watcher.py)
- ✅ Tests unitarios

### Frontend (React)
- ✅ Login seguro con JWT
- ✅ Dashboard intuitivo
- ✅ Upload con drag-and-drop
- ✅ Gestión de estado (Zustand)
- ✅ TypeScript completo
- ✅ Diseño responsivo (TailwindCSS)

## 📝 Documentación

- [Backend README](./backend/README.md) - API y setup
- [Frontend README](./frontend/README.md) - Interfaz web

## 🔑 Roles y Permisos

| Rol | Permisos |
|---|---|
| **Admin** | Todo (usuarios, auditoría, reconciliación) |
| **Operador** | Subir archivos, reconciliar |
| **Revisor** | Solo lectura de resultados |
| **Auditor** | Solo auditoría y reportes |

## 🔄 Flujo de Conciliación

1. **Cargar Extracto** → Parsea banco.xlsx automáticamente
2. **Seleccionar Cliente** → Identifica cliente
3. **Cargar Planilla** → Parsea planilla.xlsx del cliente
4. **Conciliar** → Algoritmo busca matches por monto, CUIT, titular
5. **Resultados** → Estadísticas y status por fila

### Estados de Fila
- **ok** - Coincidencia exacta encontrada
- **no está** - Monto no existe en banco
- **duplicado** - Ya fue acreditado antes
- **faltan datos** - Monto común, sin CUIT/titular para validar
- **acreditado DD/MM** - Ya acreditado a otro cliente

## 🛠️ Desarrollo

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm run dev
```

### Tests
```bash
cd backend
pytest tests/
```

## 🚢 Deployment

### Producción (Docker)
```bash
docker-compose -f docker-compose.yml up -d
```

Para producción, actualizar:
- `SECRET_KEY` en `.env`
- `DATABASE_URL` a servidor PostgreSQL externo
- `CORS_ORIGINS` en FastAPI
- `API_URL` en frontend .env

## 📊 API Endpoints

### Auth
- `POST /auth/register` - Registrar usuario
- `POST /auth/login` - Login y obtener JWT

### Extractos
- `POST /extractos/upload` - Subir extracto bancario
- `GET /extractos/{id}` - Obtener detalles

### Planillas
- `POST /planillas/upload` - Subir planilla cliente
- `GET /planillas/{id}` - Obtener detalles
- `POST /planillas/{id}/conciliar` - Ejecutar conciliación

## 🧪 Testing

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
cd frontend && npm test
```

## 📱 Próximas Fases

- [ ] App móvil (React Native)
- [ ] Reportes avanzados (PDF, gráficos)
- [ ] Historial y auditoría visual
- [ ] Notificaciones en tiempo real
- [ ] Descarga de resultados en Excel

## 🔒 Seguridad

- ✅ Contraseñas hasheadas (bcrypt)
- ✅ JWT tokens con expiración
- ✅ SQL injection prevention (ORM)
- ✅ CORS configurado
- ✅ Auditoría completa de cambios
- ✅ Validación de input en todos lados

## 📞 Soporte

Para problemas o preguntas, ver README en backend/ o frontend/

## 📄 Licencia

Privado - Caneland SA

---

**Versión:** 1.0.0 (MVP)  
**Última actualización:** 2026-04-28
