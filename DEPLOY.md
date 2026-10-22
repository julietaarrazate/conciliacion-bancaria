# Deploy a producción

Arquitectura en producción:
- **Backend → Render** (`render.yaml`)
- **Base de datos → Neon PostgreSQL** (`DATABASE_URL` cargada a mano en Render)
- **Frontend → Vercel** (deploy automático)

---

## 🔴 Backend en Render

1. https://dashboard.render.com → **New** → **Blueprint**
2. Seleccionar repo `conciliacion-bancaria` → detecta `render.yaml`
3. Clic **Apply** → esperar ~10 min
4. URL: `https://<tu-servicio>.onrender.com`

⚠️ **Free tier duerme tras 15 min de inactividad** (mitigado con UptimeRobot, ver CLAUDE.md)

---

## 🌐 Frontend en Vercel

### Primera vez:
1. https://vercel.com → **Add New** → **Project** → import `conciliacion-bancaria`
2. **Root Directory**: `frontend`
3. **Environment Variables**:
   - `VITE_API_URL` = URL del backend en Render (sin `/` al final)
4. Deploy

### Re-deploy (cuando hay cambios):
Vercel redeploya automáticamente en cada `git push` a `main`. Si el push no cambia nada dentro de
`frontend/`, el build se saltea (`ignoreCommand` en `frontend/vercel.json`) y queda publicado el
deploy anterior, que ya es el mismo front. Pasa igual en las ramas de los PR.

Después de cambiar una variable de entorno, hay que usar **Redeploy** a mano (un push que no toca
`frontend/` no la toma). El redeploy del mismo commit siempre arma el front: el `ignoreCommand`
solo saltea el build cuando hay un deploy anterior de OTRO commit y no cambió nada en `frontend/`.

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

### Backend (Render)
```
DATABASE_URL    = connection string de Neon (cargada a mano)
SECRET_KEY      = string aleatorio largo (>32 chars)
ALGORITHM       = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 480
```

### Frontend (Vercel)
```
VITE_API_URL = https://TU-BACKEND.onrender.com
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

Usuarios locales: `seed.py` crea el superadmin (contraseña desde `SUPERADMIN_PASSWORD`) y usuarios
demo solo para desarrollo (ver el docstring de `backend/seed.py`). Nunca usarlos en producción.
