# Quickstart — correr el backend en 2 minutos

Esta guía corre el backend con **SQLite** (sin Docker, sin PostgreSQL).

## 1. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

## 2. Crear BD + usuario admin

```bash
python seed.py
```

Esto crea:
- `admin@caneland.com` / `admin123` (rol **admin**)
- `operador@caneland.com` / `operador123` (rol **operador**)

## 3. Levantar el server

```bash
uvicorn app.main:app --reload
```

API disponible en: http://localhost:8000

Documentación Swagger: http://localhost:8000/docs

## 4. Probar el login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@caneland.com", "password": "admin123"}'
```

Te devuelve un `access_token` para usar en las próximas requests:

```bash
curl http://localhost:8000/me \
  -H "Authorization: Bearer <pegar-token-aqui>"
```

## Producción (PostgreSQL)

Para usar PostgreSQL en lugar de SQLite, definir variable de entorno:

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
python seed.py
uvicorn app.main:app
```

O usar el `docker-compose.yml` que ya está configurado.
