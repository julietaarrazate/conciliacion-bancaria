# Deploy a producción

Arquitectura recomendada:
- **Backend + PostgreSQL → Railway** (más confiable que Render free tier, sin sleeping)
- **Frontend → Vercel** (ya configurado, deploy automático)

---

## 🚂 Backend en Railway (RECOMENDADO)

### Paso 1: Crear cuenta
- https://railway.app → **Login with GitHub** → autorizar acceso al repo

### Paso 2: Crear proyecto
1. **New Project** → **Deploy from GitHub repo** → seleccionar `conciliacion-bancaria`
2. Railway detecta el Dockerfile automáticamente

### Paso 3: Agregar PostgreSQL
1. En el proyecto → **+ New** → **Database** → **PostgreSQL**
2. Railway agrega `DATABASE_URL` automáticamente al servicio

### Paso 4: Configurar variables de entorno
En el servicio web → **Variables** → agregar:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | Cualquier string largo y aleatorio (ej: `abc123xyz789...`) |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` |
| `ROOT_DIRECTORY` | `backend` ← IMPORTANTE |

### Paso 5: Settings → Source
- **Root Directory**: `backend`
- Redeploy

### Paso 6: Obtener la URL
La URL queda como: `https://conciliacion-api-production.up.railway.app`

### Paso 7: Verificar
```
https://TU-URL.up.railway.app/health          → {"status":"healthy"}
https://TU-URL.up.railway.app/docs            → Swagger UI
```

---

## 🔴 Backend en Render (alternativa)

1. https://dashboard.render.com → **New** → **Blueprint**
2. Seleccionar repo `conciliacion-bancaria` → detecta `render.yaml`
3. Clic **Apply** → esperar ~10 min
4. URL: `https://conciliacion-api.onrender.com`

⚠️ **Free tier duerme tras 15 min de inactividad** (primera request tarda 60 seg)

---

## 🌐 Frontend en Vercel

### Primera vez:
1. https://vercel.com → **Add New** → **Project** → import `conciliacion-bancaria`
2. **Root Directory**: `frontend`
3. **Environment Variables**:
   - `VITE_API_URL` = URL del backend (Railway o Render, sin `/` al final)
4. Deploy

### Re-deploy (cuando hay cambios):
Vercel redeploya automáticamente en cada `git push` a `main`.

### Si cambia la URL del backend:
Vercel → tu proyecto → **Settings** → **Environment Variables** → editar `VITE_API_URL` → **Redeploy**

---

## ✅ Checklist de verificación

- [ ] `/health` del backend responde 200
- [ ] `/docs` del backend muestra Swagger
- [ ] Login desde frontend funciona (no errores CORS en consola)
- [ ] Red del browser muestra requests a la URL de producción (no localhost)
- [ ] Subir extracto funciona
- [ ] Conciliar planilla funciona

---

## 🔒 Variables de entorno (resumen)

### Backend (Railway o Render)
```
DATABASE_URL    = auto (del addon PostgreSQL)
SECRET_KEY      = string aleatorio largo (>32 chars)
ALGORITHM       = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 480
```

### Frontend (Vercel)
```
VITE_API_URL = https://TU-BACKEND.up.railway.app
```

---

## 💻 Desarrollo local

```bash
# Clonar
git clone https://github.com/julietaarrazate/conciliacion-bancaria.git
cd conciliacion-bancaria

# Doble click en:
start_local.bat    # Inicia backend + frontend

# O manual:
cd backend && pip install -r requirements.txt && python seed.py && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Credenciales locales:
- `admin@demo.com` / `admin123`
- `operador@demo.com` / `operador123`
