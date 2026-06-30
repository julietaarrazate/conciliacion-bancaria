# Bug — <título corto>

Plantilla para registrar y arreglar un bug. Usar con [`/bug`](../commands/bug.md). Si el patrón
puede repetirse en otro lado, además agregar entrada a [`BUGS.md`](../../BUGS.md).

## Síntoma

(Qué se observa. Quién lo reportó. Mensaje de error exacto si lo hay. ¿Solo entre 21:00–03:00 ART?
→ sospechar fecha UTC. ¿`TypeError` en montos? → sospechar Decimal vs float.)

## Reproducción

(Pasos exactos para reproducir. Entorno: prod / local. Datos mínimos necesarios.)

1.
2.
3.

**Resultado esperado:**
**Resultado actual:**

## Causa raíz

(El "por qué" real, no el síntoma. ¿Coincide con un patrón ya documentado en `BUGS.md`?
fechas ART · Decimal/float · modo claro · compartir WhatsApp · borrado con FKs · parseo montos AR ·
`useEffect` deps · detección de banco por substring.)

## Fix

(Qué se cambió y por qué corrige la causa raíz. Archivos tocados. Respetar reglas del área:
Decimal, `hoy_art()`/`localIsoDate()`, filtro `organizacion_id`, Org A aditivo, sin `except`
genérico que enmascare.)

## Test de regresión

(Test que **falla antes** del fix y **pasa después**. Ubicación: `backend/tests/...` o repro
frontend. Pegar el nombre del test.)

- [ ] Test agregado y verde tras el fix.
- [ ] Si es patrón nuevo: entrada agregada a [`BUGS.md`](../../BUGS.md) (causa raíz + cómo evitarlo).

## Verificación

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build   # si tocó frontend
```
