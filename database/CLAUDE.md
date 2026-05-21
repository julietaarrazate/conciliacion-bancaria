# CLAUDE.md — Base de Datos (PostgreSQL + Alembic)
> Contexto específico de la DB. SIEMPRE leer antes de crear migraciones o tocar modelos.

---

## Stack

- **PostgreSQL 15**
- **SQLAlchemy 2.0** (async) en el backend
- **Alembic** para migraciones versionadas

---

## Esquema actual

> Actualizar con cada migración aplicada

### `users`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| email | VARCHAR(255) UNIQUE | |
| hashed_password | VARCHAR | |
| is_active | BOOLEAN | default true |
| created_at | TIMESTAMPTZ | |

### `bank_accounts`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| name | VARCHAR(100) | Nombre descriptivo |
| account_number | VARCHAR(50) | |
| bank_name | VARCHAR(100) | |
| currency | VARCHAR(3) | default 'ARS' |
| user_id | FK → users | |
| created_at | TIMESTAMPTZ | |

### `bank_statements`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| account_id | FK → bank_accounts | |
| period_start | DATE | |
| period_end | DATE | |
| opening_balance | NUMERIC(15,2) | |
| closing_balance | NUMERIC(15,2) | |
| status | VARCHAR(20) | draft/processing/closed |
| imported_at | TIMESTAMPTZ | |

### `bank_transactions`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| statement_id | FK → bank_statements | |
| transaction_date | DATE | |
| description | TEXT | |
| amount | NUMERIC(15,2) | positivo=crédito, negativo=débito |
| reference | VARCHAR(100) | referencia del banco |
| is_reconciled | BOOLEAN | default false |

### `accounting_entries`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| account_id | FK → bank_accounts | |
| entry_date | DATE | |
| description | TEXT | |
| amount | NUMERIC(15,2) | |
| reference | VARCHAR(100) | |
| is_reconciled | BOOLEAN | default false |

### `reconciliations`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| statement_id | FK → bank_statements | |
| status | VARCHAR(20) | open/in_progress/closed |
| difference | NUMERIC(15,2) | saldo banco - saldo contable |
| created_at | TIMESTAMPTZ | |
| closed_at | TIMESTAMPTZ | nullable |

### `reconciliation_items`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | |
| reconciliation_id | FK → reconciliations | |
| bank_transaction_id | FK → bank_transactions | nullable |
| accounting_entry_id | FK → accounting_entries | nullable |
| match_type | VARCHAR(20) | auto/manual |
| matched_at | TIMESTAMPTZ | |
| matched_by | FK → users | nullable |

---

## Reglas críticas

- **NUNCA** usar `NUMERIC` con float en Python — siempre `Decimal`
- **SIEMPRE** `TIMESTAMPTZ` (con timezone) para fechas, nunca `TIMESTAMP`
- Los montos en ARS y USD se guardan separados — no mezclar monedas en un campo
- Índices mínimos requeridos: `bank_transactions(statement_id)`, `accounting_entries(account_id)`, `reconciliation_items(reconciliation_id)`

---

## Migraciones

```bash
# Generar migración desde cambios en modelos
cd backend && alembic revision --autogenerate -m "descripcion_corta"

# Aplicar
alembic upgrade head

# Rollback una versión
alembic downgrade -1

# Ver historial
alembic history
```

Las migraciones viven en `database/migrations/versions/`.

---

## Estado actual de migraciones

> Actualizar con cada migración

| Revisión | Descripción | Estado |
|----------|-------------|--------|
| (ninguna aún) | | |
