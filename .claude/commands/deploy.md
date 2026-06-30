# /deploy — Runbook de deploy (Render + Vercel)

Propósito: llevar a producción de forma segura. Arquitectura: frontend en Vercel, backend en
Render, DB en Neon. Detalle de infraestructura en [`CLAUDE.md`](../../CLAUDE.md).

## Pasos

1. **Pre-deploy — verde local**:

   ```bash
   cd backend && python -m pytest -q
   cd frontend && npx tsc --noEmit && npm run build
   ```
2. **Merge a `main`** vía PR squash desde `claude/...`. El push a `main` dispara automáticamente:
   - **Vercel** → build + deploy del frontend. Recordá: Vercel **bloquea builds con autor de commit
     distinto** de `Julieta Arrazate <julietaarrazate@gmail.com>`.
   - **Render** → build + deploy del backend (`srv-d7pqt81j2pic73c0c6fg`).
3. **Deploy manual de Render** (si el auto-deploy no disparó o querés forzarlo):

   ```bash
   curl -X POST https://api.render.com/v1/services/srv-d7pqt81j2pic73c0c6fg/deploys \
     -H "Authorization: Bearer <RENDER_API_KEY>"
   ```
   El `RENDER_API_KEY` vive en el entorno de Julieta, no en el repo.
4. **Esperar el arranque** (Render free tier: cold start ~30s). En el boot, `main.py` corre Alembic
   + safety-nets idempotentes + seed por org — el esquema converge solo aunque Alembic falle.

## Verificación (smoke test en prod)

1. **Health**:

   ```bash
   curl -s https://conciliacion-api.onrender.com/health
   ```
2. **Logs de Render**: sin errores en el arranque; revisar líneas `SLOW <método> <path>` (requests
   > `SLOW_REQUEST_MS`, default 1500ms) y el header `X-Process-Time` para detectar regresiones de
   latencia.
3. **Frontend**: abrir https://conciliacion-bancaria-ten.vercel.app, login, y verificar el flujo
   tocado por el release (cargar dashboard / la página de la feature).
4. Si algo falla: revisar logs de Render/Vercel; el frontend ya tiene retry para el cold start.

## Notas

- Feature flags por env var en Render degradan solas si faltan (no rompen): `RESEND_API_KEY`,
  `VAPID_*`, `GEMINI_API_KEY`, `SENTRY_DSN`, `S3_*`, etc. (ver [`CLAUDE.md`](../../CLAUDE.md)).
- Org A (`organizacion_id=1`): ningún deploy debe correr migraciones destructivas sobre sus datos.
