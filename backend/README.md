# Backend - Sistema Conciliación Bancaria

API FastAPI para la plataforma de conciliación bancaria.

## Características

- **Autenticación JWT** con roles y permisos granulares
- **API RESTful** completa para:
  - Gestión de usuarios y autenticación
  - Carga y procesamiento de extractos bancarios
  - Carga de planillas de clientes
  - Conciliación automática con algoritmo inteligente
- **Base de datos PostgreSQL** con modelo relacional robusto
- **Auditoría completa** de todas las operaciones
- **Parseo automático** de Excel con detección de columnas
- **Tests unitarios** para componentes críticos

## Setup Rápido

### Con Docker (recomendado)

```bash
cd backend
docker-compose up
```

La API estará disponible en `http://localhost:8000`

### Sin Docker (desarrollo local)

```bash
# 1. Crear ambiente virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env

# 4. Ejecutar servidor
uvicorn app.main:app --reload
```

## Estructura del Proyecto

```
backend/
├── app/
│   ├── main.py              # Aplicación FastAPI
│   ├── config.py            # Configuración
│   ├── database.py          # Setup SQLAlchemy
│   ├── models/              # Modelos de BD
│   ├── schemas/             # Schemas Pydantic para API
│   ├── services/            # Lógica de negocio
│   │   ├── auth.py          # Autenticación
│   │   ├── conciliacion.py  # Algoritmo de matching
│   │   └── excel_parser.py  # Parseo Excel
│   ├── routers/             # Endpoints agrupados
│   │   ├── auth.py
│   │   ├── extractos.py
│   │   └── planillas.py
│   └── middleware/          # Middleware (auth, permisos)
├── tests/                   # Tests unitarios
├── docker-compose.yml       # Orquestación Docker
├── Dockerfile              # Imagen Docker
└── requirements.txt        # Dependencias Python
```

## API Endpoints

### Autenticación

- `POST /auth/register` - Registrar nuevo usuario
- `POST /auth/login` - Autentica y retorna JWT token

### Extractos Bancarios

- `POST /extractos/upload` - Sube archivo Excel de extracto
- `GET /extractos/{extracto_id}` - Obtiene detalles del extracto

### Planillas de Clientes

- `POST /planillas/upload` - Sube planilla de cliente
- `GET /planillas/{planilla_id}` - Obtiene detalles de planilla
- `POST /planillas/{planilla_id}/conciliar` - Ejecuta conciliación

## Tests

```bash
cd backend
pytest tests/
```

## Variables de Entorno

Ver `.env.example`. Configurar en `.env` (no subir a git):

```env
DATABASE_URL=postgresql://user:password@localhost:5432/db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=False
```

## Autenticación

### JWT Token

Incluir en headers:
```
Authorization: Bearer <token>
```

### Roles Disponibles

- **admin**: Acceso completo
- **operador**: Subir archivos y reconciliar
- **revisor**: Solo lectura
- **auditor**: Solo auditoría

## Algoritmo de Conciliación

Migrado desde `watcher.py` original:

1. Parsea planilla de cliente (detecta headers automáticamente)
2. Para cada fila:
   - Busca movimiento en extracto por monto
   - Si monto es único: acredita directamente
   - Si monto es común (3+ veces): valida por CUIT o titular
   - Marca status: "ok", "no está", "duplicado", "faltan datos"
3. Retorna estadísticas y guarda resultado en BD

## Desarrollo

### Agregar nuevo endpoint

1. Crear función en `routers/nuevo.py`:
   ```python
   from fastapi import APIRouter
   
   router = APIRouter(prefix="/nuevo", tags=["nuevo"])
   
   @router.get("/")
   def get_datos():
       return {"data": "value"}
   ```

2. Incluir en `main.py`:
   ```python
   from app.routers import nuevo
   app.include_router(nuevo.router)
   ```

### Agregar nuevo modelo

1. Crear en `models/nuevo.py`
2. Importar en `models/__init__.py`
3. Los modelos se crean automáticamente en la BD

## Deploy

Usar `docker-compose` para un deploy simple local:

```bash
docker-compose up -d
```

Para producción, ver la sección de Deploy en el plan general.

## Documentación Interactiva

FastAPI genera automáticamente documentación Swagger:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Troubleshooting

### Error de conexión a BD

Asegurarse que PostgreSQL está corriendo:
```bash
docker-compose ps
```

### Tests fallan

Limpiar y reinstalar:
```bash
pip install --upgrade -r requirements.txt
pytest tests/ -v
```

## Licencia

Privado - Caneland SA
