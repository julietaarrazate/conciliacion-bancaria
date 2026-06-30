# /bug — Arreglar un bug (reproducir → corregir → regresión)

Propósito: corregir un defecto con disciplina de reproducción primero, para que no vuelva.
La regla de oro: **un test que falla antes del fix y pasa después**.

## Pasos

1. **Documentar** con [`.claude/templates/bug_template.md`](../templates/bug_template.md):
   síntoma, repro, causa raíz, fix, test de regresión.
2. **Revisar [`BUGS.md`](../../BUGS.md) primero** — los bugs recurrentes ya tienen causa raíz y
   forma de evitarlos. Si el síntoma encaja con uno (fechas ART, Decimal vs float, modo claro,
   compartir WhatsApp, borrado con FKs, parseo de montos AR, `useEffect`, detección de banco),
   aplicar la solución documentada, no reinventar.
3. **Reproducir con un test que falle** en `backend/tests/` (o repro mínima en frontend). Si no se
   puede escribir el test todavía, reproducir manualmente y dejar el repro anotado.
4. **Corregir** la causa raíz, no el síntoma. No enmascarar con `except Exception` genérico
   (ver [`docs/api/API_RULES.md`](../../docs/api/API_RULES.md) §5). Respetar las reglas del área:
   Decimal, `hoy_art()`/`localIsoDate()`, filtro `organizacion_id`, Org A solo aditivo.
5. **Confirmar** que el test ahora pasa y dejarlo como **test de regresión** permanente.
6. **Si es un patrón nuevo** (mismo bug podría repetirse en otro lado): agregar una entrada a
   [`BUGS.md`](../../BUGS.md) con causa raíz + cómo evitarlo.

## Verificación

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build   # si tocó frontend
```

## PR

Rama `claude/...` → PR squash a `main`, commits con
`git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>"`. El PR debe incluir el test
de regresión.
