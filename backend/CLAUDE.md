# CLAUDE.md — Backend (FastAPI)
> Contexto específico del módulo backend. Actualizar cuando cambien modelos, endpoints o patrones.

---

## Stack

- **FastAPI** 0.111+ con Python 3.11
- **SQLAlchemy** 2.0 (async) + **Alembic** para migraciones
- **Pydantic** v2 para schemas
- **PostgreSQL** 15 via `asyncpg`
- **JWT** para autenticación (python-jose)
- **pytest** + `httpx` para tests

---

## Estructura

```
backend/
├── app/
│   ├── main.py              ← app FastAPI, routers registrados aquí
│   ├── core/
│   │   ├── config.py        ← settings (usa pydantic-settings)
│   │   ├── database.py      ← async engine + sesión
│   │   └── security.py      ← JWT, hash passwords
│   ├── models/              ← modelos SQLAlchemy (un archivo por entidad)
│   ├── schemas/             ← schemas Pydantic (request/response)
│   ├── routers/             ← endpoints organizados por dominio
│   ├── services/            ← lógica de negocio (sin DB directa)
│   └── dependencies.py      ← get_db, get_current_user, etc.
├── tests/
│   ├── conftest.py          ← fixtures compartidas
│   └── test_*.py
├── alembic.ini
└── requirements.txt
```

---

## Patrones establecidos

### Async everywhere
```python
# SIEMPRE async en routers y servicios
@router.get("/")
async def list_items(db: AsyncSession = Depends(get_db)):
    ...
```

### Servicios sin acceso directo a DB
```python
# Los routers llaman servicios, los servicios reciben la sesión como parámetro
# NO importar db directamente en services
async def get_reconciliations(db: AsyncSession, account_id: int) -> list[Reconciliation]:
    ...
```

### Response schemas siempre tipados
```python
@router.post("/", response_model=ReconciliationResponse, status_code=201)
```

---

## Modelos de datos

> Actualizar cuando se hagan migraciones

| Modelo              | Tabla                  | Descripción |
|---------------------|------------------------|-------------|
| `BankAccount`       | `bank_accounts`        | Cuentas bancarias del cliente |
| `BankStatement`     | `bank_statements`      | Extracto mensual importado |
| `BankTransaction`   | `bank_transactions`    | Línea individual del extracto |
| `AccountingEntry`   | `accounting_entries`   | Asiento contable interno |
| `Reconciliation`    | `reconciliations`      | Proceso de conciliación |
| `ReconciliationItem`| `reconciliation_items` | Match individual tx ↔ asiento |
| `User`              | `users`                | Usuarios del sistema |

---

## Endpoints registrados

> Actualizar con cada endpoint nuevo. Ver `docs/api-contracts.md` para detalle completo.

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/auth/login` | Login, devuelve JWT |
| GET | `/accounts/` | Listar cuentas |
| POST | `/accounts/` | Crear cuenta |
| POST | `/statements/upload` | Importar extracto bancario |
| GET | `/reconciliations/` | Listar conciliaciones |
| POST | `/reconciliations/` | Crear nueva conciliación |
| POST | `/reconciliations/{id}/auto-match` | Ejecutar auto-matching |
| PATCH | `/reconciliations/{id}/items/{item_id}` | Conciliar ítem manualmente |

---

## Variables de entorno requeridas

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/conciliacion_db
SECRET_KEY=         # para JWT, mínimo 32 chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Errores conocidos en este módulo

> Ver también `docs/errors-log.md` para historial completo

- Al usar `AsyncSession` con SQLAlchemy 2.0, usar `await db.execute(select(...))` no `db.query(...)`
- Los schemas Pydantic v2 usan `model_validate()` no `from_orm()`
- Alembic con async: usar `run_sync` en las migraciones

---

## Estado actual

> Actualizar en cada sesión

- [ ] Modelos de datos definidos
- [ ] Migraciones iniciales
- [ ] Auth (login/JWT)
- [ ] CRUD cuentas bancarias
- [ ] Import de extractos (CSV/OFX)
- [ ] Algoritmo de auto-matching
- [ ] Conciliación manual
- [ ] Reportes
- [ ] Tests unitarios
- [ ] Tests de integración
