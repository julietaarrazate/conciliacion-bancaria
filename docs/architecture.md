# Decisiones de Arquitectura (ADR)
> Registro de decisiones técnicas importantes. Agregar cuando se tome una decisión que no sea obvia.

---

## Formato

```
### ADR-XXX: Título de la decisión
**Fecha:** YYYY-MM-DD
**Estado:** Aceptada / Rechazada / Deprecada
**Contexto:** por qué se necesitaba decidir algo
**Decisión:** qué se decidió
**Consecuencias:** qué implica esta decisión (positivo y negativo)
```

---

## ADR-001: Arquitectura modular con CLAUDE.md por módulo
**Fecha:** 2026-05-21
**Estado:** Aceptada
**Contexto:** El proyecto tiene 4 módulos (backend, frontend, mobile, DB). Cargar todo el contexto junto consume demasiados tokens y genera confusión.
**Decisión:** Cada módulo tiene su propio CLAUDE.md. Claude Code carga solo el módulo que está trabajando. El CLAUDE.md raíz es solo para visión general y reglas de orquestación.
**Consecuencias:**
- (+) Sesiones más eficientes, menos tokens, menos confusión
- (+) Cada módulo puede evolucionar su contexto independientemente
- (-) Requiere disciplina para mantener los archivos actualizados

---

## ADR-002: SQLAlchemy async (no sync)
**Fecha:** 2026-05-21
**Estado:** Aceptada
**Contexto:** FastAPI es async por naturaleza. Usar SQLAlchemy sync bloquea el event loop.
**Decisión:** Usar `AsyncSession` con `asyncpg` driver. Todas las operaciones de DB son `async/await`.
**Consecuencias:**
- (+) Performance real en FastAPI
- (-) Alembic necesita `run_sync` wrapper en las migraciones
- (-) Menos ejemplos en la documentación (pero la documentación oficial lo cubre)

---

## ADR-003: Moneda principal ARS, soporte USD
**Fecha:** 2026-05-21
**Estado:** Aceptada
**Contexto:** Sistema contable argentino, moneda principal ARS.
**Decisión:** Columnas de monto en `NUMERIC(15,2)` + columna `currency VARCHAR(3)`. Nunca mezclar monedas en cálculos sin conversión explícita.
**Consecuencias:**
- (+) Flexibilidad para cuentas en dólares
- (-) La conciliación cross-currency requiere lógica adicional (fase 2)
