# /review — Revisar un diff / PR

Propósito: revisar un cambio antes de mergear, con foco en los riesgos reales del repo
(multi-tenant, Decimal, errores enmascarados, N+1, Org A). Es revisión, no implementación.

## Pasos

1. **Leer el diff completo** (`git diff main...HEAD` o el PR) y entender el alcance declarado.
   Verificar que el cambio hace solo lo que dice.
2. **Recorrer** [`.claude/checklists/code_review_checklist.md`](../checklists/code_review_checklist.md)
   punto por punto. Foco:
   - **Correctitud**: hace lo que el PR dice; sin lógica muerta ni casos borde sin cubrir.
   - **Decimal/float**: todo monto es `Decimal`/`Numeric(12,2)`, nunca `float`; serialización a
     JSON con `str()` ([`BUGS.md`](../../BUGS.md)).
   - **Multi-tenant**: toda query nueva filtra por `organizacion_id`; `org_id` validado con
     `can_switch_org`; recurso de otra org → 404, no 403. Org A solo aditivo.
   - **Seguridad**: permisos en 3 capas; sin secretos en código; rate limiting donde corresponda;
     validación de inputs/magic bytes en uploads ([`docs/security/SECURITY_MODEL.md`](../../docs/security/SECURITY_MODEL.md)).
   - **N+1**: relaciones serializadas con `selectinload`/`joinedload`, no una query por fila.
   - **Manejo de errores**: nada de `except Exception` genérico que enmascare; `except HTTPException:
     raise` primero, luego rollback + log ([`docs/api/API_RULES.md`](../../docs/api/API_RULES.md) §5).
   - **Fechas**: `hoy_art()`/`now_art()`/`localIsoDate()`, nunca UTC directo para fecha de negocio.
3. **Migraciones**: si hay columna/tabla/índice nuevo, confirmar que existe la migración Alembic
   **y** el safety-net idempotente equivalente en `main.py` (ambas rutas convergen).
4. **Tests**: el cambio trae tests (caso feliz + aislamiento org + 403 + regresión si es bug fix).
5. **Author del commit**: `Julieta Arrazate <julietaarrazate@gmail.com>` (Vercel bloquea otros).

## Verificación

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build
```

## Salida

Lista de hallazgos clasificados (bloqueante / sugerencia / nit), cada uno con archivo:línea y la
regla o doc que lo respalda. Aprobar solo si no quedan bloqueantes.
