# /release — Preparar un release

Propósito: cortar una versión nueva de Cuadra de forma reproducible: verde local, changelog,
tag y deploy a Render (backend) + Vercel (frontend).

## Pasos

1. **Recorrer** [`.claude/checklists/release_checklist.md`](../checklists/release_checklist.md)
   entero. No avanzar con ítems en rojo.
2. **Verde local**:

   ```bash
   cd backend && python -m pytest -q
   cd frontend && npx tsc --noEmit && npm run build
   ```
3. **Changelog**: agregar la entrada de la versión nueva al tope de
   [`CHANGELOG.md`](../../CHANGELOG.md) (feature/fix/PR), siguiendo el formato de las entradas
   v3.x existentes. Actualizar la "Versión actual" en [`CLAUDE.md`](../../CLAUDE.md) y en el pie.
4. **Sin secretos**: confirmar que no se commitearon keys/tokens (van en Render/Vercel/GitHub,
   nunca en el repo). Ver [`.claude/checklists/security_checklist.md`](../checklists/security_checklist.md).
5. **Migraciones**: si la versión trae cambios de esquema, verificar que cada migración Alembic
   tiene su safety-net idempotente en `main.py` (convergen en el arranque de Render).
6. **Tag** (si aplica — varios "checkpoints" son documentales, no tags físicos; ver CHANGELOG
   → "Checkpoints / releases"):

   ```bash
   git tag vX.Y && git push origin vX.Y
   ```
7. **Deploy**: seguir [`/deploy`](./deploy.md). Push a `main` dispara Vercel + Render; deploy
   manual de Render por API si hace falta.
8. **Smoke test en prod**: ver paso de verificación de [`/deploy`](./deploy.md).

## PR

Merge a `main` vía PR squash desde `claude/...`, commits con
`git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>"`.
