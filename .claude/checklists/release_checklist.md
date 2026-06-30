# Checklist — Release

Para usar con [`/release`](../commands/release.md) y [`/deploy`](../commands/deploy.md).

## Verde local

- [ ] `cd backend && python -m pytest -q` (suite completa pasando).
- [ ] `cd frontend && npx tsc --noEmit` sin errores de tipos.
- [ ] `cd frontend && npm run build` ok.

## Changelog y versión

- [ ] Entrada nueva al tope de [`CHANGELOG.md`](../../CHANGELOG.md) (feature/fix/PR), formato v3.x.
- [ ] "Versión actual" actualizada en [`CLAUDE.md`](../../CLAUDE.md) (encabezado y pie).

## Secretos

- [ ] Ningún key/token commiteado (van en Render/Vercel/GitHub, nunca en el repo).
- [ ] `.env`/credenciales no entraron en el diff.

## Migraciones / esquema

- [ ] Cada migración Alembic nueva tiene su safety-net idempotente en `main.py` (convergen).
- [ ] Sin migración destructiva sobre datos de Org A (`organizacion_id=1`).

## Deploy

- [ ] Merge a `main` vía PR squash; commits con autor `Julieta Arrazate
      <julietaarrazate@gmail.com>` (Vercel bloquea otros).
- [ ] Vercel (frontend) y Render (backend) dispararon deploy; o deploy manual de Render por API.
- [ ] Tag `vX.Y` creado y pusheado si la versión lleva tag físico (ver CHANGELOG → Checkpoints).

## Smoke test en producción

- [ ] `GET /health` responde ok.
- [ ] Logs de Render sin errores en el arranque; revisar líneas `SLOW` y `X-Process-Time`.
- [ ] Login + flujo tocado por el release funcionan en https://conciliacion-bancaria-ten.vercel.app.
