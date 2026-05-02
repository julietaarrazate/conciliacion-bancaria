# Deploy en Railway (RECOMENDADO sobre Render)

Railway es más simple y confiable. Free tier sin sleep.

## Backend en Railway (3 minutos)

1. Ir a https://railway.app → **Login with GitHub**
2. **New Project** → **Deploy from GitHub repo** → seleccionar `conciliacion-bancaria`
3. Railway detecta Python automáticamente
4. En el proyecto: **+ New** → **Database** → **PostgreSQL** → Railway agrega DATABASE_URL solo
5. En Settings → Variables, agregar:
   - `SECRET_KEY` = cualquier string largo (ej: `mi-clave-super-secreta-2026`)
   - `ROOT_DIR` = `backend`  ← IMPORTANTE
6. En Settings → **Root Directory** → poner `backend`
7. Clic **Deploy** → espera ~2 min

URL queda algo como: `https://conciliacion-api.up.railway.app`

## Frontend en Vercel (ya configurado)

1. https://vercel.com → tu proyecto
2. Settings → Environment Variables:
   - `VITE_API_URL` = URL de Railway (ej: `https://conciliacion-api.up.railway.app`)
3. Redeploy

## Variables Railway obligatorias

| Variable | Valor |
|---|---|
| `DATABASE_URL` | auto (PostgreSQL addon) |
| `SECRET_KEY` | string random largo |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
