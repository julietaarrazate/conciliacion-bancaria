# Checklist — Code review

Para usar con [`/review`](../commands/review.md). Foco en los riesgos reales del repo.

## Correctitud

- [ ] El cambio hace lo que el PR declara, nada más; casos borde cubiertos.
- [ ] Sin código muerto ni `console.log`/`print` de debug olvidados.

## Decimal / float

- [ ] Todo monto es `Decimal`/`Numeric(12,2)`, nunca `float`.
- [ ] Serialización de `Decimal` a JSON con `str()` o encoder custom (ver [`BUGS.md`](../../BUGS.md)).
- [ ] Parseo de montos AR con `parseMonto()` en frontend (no `parseFloat` directo).

## Fechas

- [ ] Fecha de negocio con `hoy_art()`/`now_art()` (backend) y `localIsoDate()` (frontend), no
      `date.today()`/`datetime.now()`/`new Date().toISOString()`.
- [ ] `created_at` y expiración de tokens siguen en UTC a propósito (no convertir a ART).

## Multi-tenant

- [ ] Toda query nueva filtra por `organizacion_id`; `org_id` validado con `can_switch_org`.
- [ ] Recurso de otra org → 404, no 403.
- [ ] Org A (`organizacion_id=1`) intocable: solo cambios aditivos.

## N+1 / performance

- [ ] Relaciones serializadas con `selectinload`/`joinedload`, no una query por fila.
- [ ] `total` con `.count()` antes de `offset/limit`; `order_by` determinístico antes de paginar.

## Manejo de errores

- [ ] Sin `except Exception` genérico que enmascare; `except HTTPException: raise` primero, luego
      `db.rollback()` + `logger.error(...)`.
- [ ] Códigos HTTP correctos (400/401/403/404/409/413/429/503).

## Tests

- [ ] Trae tests: caso feliz + aislamiento de otra org + 403 sin permiso.
- [ ] Si es bug fix: test de regresión que falla antes y pasa después.
- [ ] Si hay `DELETE` con FKs: test de borrado con datos relacionados.

## Esquema

- [ ] Columna/tabla/índice nuevo: migración Alembic **y** safety-net idempotente en `main.py`.

## Higiene

- [ ] Sin secretos en el diff.
- [ ] Commits con autor `Julieta Arrazate <julietaarrazate@gmail.com>`.
