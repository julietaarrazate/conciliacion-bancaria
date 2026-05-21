# CLAUDE.md — Sistema de Conciliación Bancaria
> **Este archivo es memoria viva. Actualizarlo al final de cada sesión.**

---

## 🧭 QUÉ ES ESTE PROYECTO

Sistema de conciliación bancaria para automatizar el matching entre extractos bancarios y registros contables.

**Stack:**
- Backend: FastAPI + Python 3.11
- Frontend Web: React 18 + TypeScript + Vite
- Mobile: React Native (Expo)
- Base de datos: PostgreSQL 15
- ORM: SQLAlchemy + Alembic
- Auth: JWT

**Repositorio:** https://github.com/julietaarrazate/conciliacion-bancaria

---

## 🏗️ ARQUITECTURA DEL PROYECTO

```
conciliacion-bancaria/
├── CLAUDE.md                   ← este archivo (maestro)
├── .claude/
│   ├── settings.json           ← config Claude Code
│   └── commands/               ← comandos slash personalizados
├── backend/
│   ├── CLAUDE.md               ← contexto solo de FastAPI/Python
│   └── app/
├── frontend/
│   ├── CLAUDE.md               ← contexto solo de React/TS
│   └── src/
├── mobile/
│   ├── CLAUDE.md               ← contexto solo de React Native
│   └── src/
├── database/
│   ├── CLAUDE.md               ← contexto solo de DB/migraciones
│   └── migrations/
└── docs/
    ├── architecture.md         ← decisiones de arquitectura (ADR)
    ├── errors-log.md           ← errores conocidos y soluciones
    └── api-contracts.md        ← contratos de API entre módulos
```

---

## 🚦 REGLAS DE ORQUESTACIÓN (LEER ANTES DE CADA SESIÓN)

### 1. Cargar solo el contexto necesario
- Para trabajo en **backend**: leer solo `backend/CLAUDE.md`
- Para trabajo en **frontend**: leer solo `frontend/CLAUDE.md`
- Para trabajo en **mobile**: leer solo `mobile/CLAUDE.md`
- Para trabajo en **DB**: leer solo `database/CLAUDE.md`
- Para trabajo **cross-módulo**: leer este archivo + el módulo afectado

### 2. Antes de empezar cualquier tarea
1. Leer `docs/errors-log.md` — verificar si el error/tema ya fue resuelto
2. Leer el CLAUDE.md del módulo correspondiente
3. NO leer código que no sea relevante para la tarea

### 3. Al finalizar cualquier sesión
1. Si hubo errores nuevos → agregarlos a `docs/errors-log.md`
2. Si hubo decisiones arquitecturales → agregarlas a `docs/architecture.md`
3. Si cambió algún contrato de API → actualizar `docs/api-contracts.md`
4. Si cambió algo importante del módulo → actualizar su CLAUDE.md

---

## ⚠️ REGLAS ANTI-DELIRIO

- **NUNCA inventar** endpoints, modelos o comportamientos que no existan en el código
- **NUNCA asumir** que algo funciona sin verificarlo
- **SIEMPRE** verificar el schema de DB antes de escribir queries
- **SIEMPRE** consultar `docs/api-contracts.md` antes de cambiar endpoints
- Si no sabes algo → preguntar, no inventar
- Si el contexto se vuelve confuso → parar y releer el CLAUDE.md del módulo

---

## 💡 DOMINIO: CONCILIACIÓN BANCARIA

### Conceptos clave
- **Extracto bancario**: movimientos que reporta el banco (fuente de verdad externa)
- **Asiento contable**: registros internos del sistema
- **Conciliación**: proceso de hacer coincidir extracto ↔ asientos
- **Partida conciliada**: ítem que tiene match confirmado
- **Partida pendiente**: ítem sin match (requiere atención)
- **Diferencia**: discrepancia entre saldo banco y saldo contable

### Flujo principal
```
Importar extracto → Auto-matching → Revisión manual → Confirmar → Cerrar período
```

### Entidades principales
- `BankAccount` (cuenta bancaria)
- `BankStatement` (extracto mensual)
- `BankTransaction` (línea del extracto)
- `AccountingEntry` (asiento contable)
- `Reconciliation` (proceso de conciliación)
- `ReconciliationItem` (match individual)

---

## 🔧 COMANDOS RÁPIDOS

```bash
# Levantar todo
docker-compose up -d

# Solo backend
cd backend && uvicorn app.main:app --reload

# Solo frontend
cd frontend && npm run dev

# Migraciones
cd backend && alembic upgrade head

# Tests backend
cd backend && pytest

# Tests frontend
cd frontend && npm test
```

---

## 📋 ESTADO ACTUAL DEL PROYECTO

> Actualizar esta sección en cada sesión

| Módulo      | Estado       | Notas |
|-------------|--------------|-------|
| Backend     | 🔧 En desarrollo | |
| Frontend    | 🔧 En desarrollo | |
| Mobile      | 🔧 En desarrollo | |
| Database    | 🔧 En desarrollo | |
| Auth        | ⏳ Pendiente | |
| Tests       | ⏳ Pendiente | |
| Deploy      | ⏳ Pendiente | |

---

## 🧠 HISTORIAL DE SESIONES

> Agregar una línea por sesión con fecha y resumen de lo hecho

- `2026-05-21` — Configuración inicial del proyecto y Claude Code
