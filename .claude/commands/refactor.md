# /refactor — Refactor seguro sin cambiar comportamiento

Propósito: mejorar estructura/legibilidad/duplicación SIN alterar el comportamiento observable.
Si el comportamiento cambia, no es un refactor: es una feature o un bug fix.

## Pasos

1. **Tests verdes ANTES**. Correr la suite y confirmar que pasa. Si el área no tiene cobertura,
   agregar tests de caracterización primero (capturan el comportamiento actual) — recién después
   refactorizar.

   ```bash
   cd backend && python -m pytest -q
   cd frontend && npx tsc --noEmit && npm run build
   ```
2. **Mapear** con [`/analyze`](./analyze.md) qué archivos toca y qué reglas viven ahí, para no
   alterarlas sin querer.
3. **Cambios mecánicos** solamente: renombrar, extraer función/helper, dedup, mover código,
   tipar. **No** tocar lógica de negocio, scoring de conciliación, cálculos financieros ni el
   contrato de los endpoints.
4. **Preservar invariantes** del repo aunque "se vean feos": Decimal en montos, `hoy_art()`/
   `localIsoDate()` en fechas, filtro `organizacion_id` en cada query, doble fuente DDL
   (Alembic + safety net en `main.py`) sincronizada, Org A intacta.
5. **Tests verdes DESPUÉS**, idénticos a antes (mismos casos pasando). Si algún test cambió de
   resultado, el refactor alteró comportamiento → revisar.

## Verificación

Misma suite que en el paso 1, sin regresiones. `tsc --noEmit` + `build` sin nuevos errores.

## PR

Rama `claude/...` → PR squash a `main`, commits atómicos con
`git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>"`. Describir en el PR que es
refactor sin cambio de comportamiento.
