# Deploy a producción (gratis)

Stack:
- **Backend + PostgreSQL**: Render.com (free tier)
- **Frontend Web**: Vercel (free tier)
- **App Móvil**: Expo Go (sin deploy necesario en dev) o EAS Build (APK)

---

## 🚀 Backend en Render (5 minutos)

### Paso 1: Crear cuenta
- Andá a https://render.com → "Sign up with GitHub"
- Autorizá Render a leer el repo `conciliacion-bancaria`

### Paso 2: Deploy con Blueprint
- En Render Dashboard → **New** → **Blueprint**
- Seleccionar repo `julietaarrazate/conciliacion-bancaria`
- Render detecta `render.yaml` automáticamente
- Click **Apply**

Render crea:
- ✅ Base de datos PostgreSQL (`conciliacion-db`)
- ✅ Web service `conciliacion-api`
- ✅ Conecta DB → API automático
- ✅ Genera `SECRET_KEY` random

**Esperá 5-10 min** (primer deploy). Cuando dice "Live":
- URL del backend: `https://conciliacion-api.onrender.com`
- Swagger: `https://conciliacion-api.onrender.com/docs`

⚠️ **Free tier de Render duerme tras 15 min sin tráfico**. La primera petición tras dormir tarda ~30 segundos.

### Paso 3: Verificar

```bash
curl https://conciliacion-api.onrender.com/health
# {"status":"healthy"}

curl -X POST https://conciliacion-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@caneland.com","password":"admin123"}'
```

El `seed.py` corre automático al deployar y crea admin + operador.

---

## 🌐 Frontend Web en Vercel (3 minutos)

### Paso 1: Cuenta + Import
- Andá a https://vercel.com → "Sign up with GitHub"
- Click **Add New** → **Project**
- Import `julietaarrazate/conciliacion-bancaria`

### Paso 2: Configurar
- **Root Directory**: `frontend` (importante!)
- **Framework**: Vite (autodetectado)
- **Environment Variables**: agregar:
  - `VITE_API_URL` = `https://conciliacion-api.onrender.com`

### Paso 3: Deploy
- Click **Deploy**
- En 2 minutos: `https://conciliacion-bancaria.vercel.app`

---

## 📱 App Móvil

### Opción A: Expo Go (rápido, para probar)
- Instalá Expo Go en el celular
- En la PC: `cd mobile && npx expo start --tunnel`
- Escaneá el QR
- En **Ajustes** dentro de la app, poner: `https://conciliacion-api.onrender.com`

### Opción B: APK Android (para usuarios)

```bash
cd mobile
npm install -g eas-cli
eas login                       # cuenta Expo gratis
eas build --platform android --profile preview
```

EAS te genera un APK descargable. Lo instalás en cualquier Android.

### Opción C: iOS
Requiere Apple Developer Account ($99/año). Para uso interno usar TestFlight.

---

## 🔄 CI/CD automático

Cada `git push` a `main` triggers:
- ✅ **Render**: redeploy del backend
- ✅ **Vercel**: redeploy del frontend
- ✅ **GitHub Actions**: corre tests del backend (`backend-tests.yml`)

Sin hacer nada extra.

---

## 🔐 Cambiar passwords default

⚠️ Después del primer deploy, los usuarios `admin@caneland.com` / `admin123` están vivos. Cambialos:

1. Login en la web con `admin@caneland.com / admin123`
2. (TODO: agregar pantalla de cambiar password)
3. **Por ahora**: borralos de Render Dashboard → Database → SQL Console:
   ```sql
   DELETE FROM users WHERE email IN ('admin@caneland.com', 'operador@caneland.com');
   ```
4. Registrate vos misma con `POST /auth/register` (Swagger)
5. Cambiate el rol con SQL: `UPDATE users SET role='admin' WHERE email='tu@email.com';`

---

## 💰 Costos

| Servicio | Plan | Costo | Limitación |
|---|---|---|---|
| Render Web | Free | $0 | Duerme tras 15 min sin uso |
| Render PostgreSQL | Free | $0 | 90 días, 1 GB, después borra |
| Vercel | Hobby | $0 | 100 GB bandwidth/mes |
| Expo Go | Free | $0 | Sólo dev, app pública |
| EAS Build APK | Free | $0 | 30 builds/mes |

**Para producción real (24/7 sin sleep)**: Render Starter $7/mes + PostgreSQL $7/mes = $14/mes total.

---

## 🆘 Troubleshooting

### "El backend no responde"
Render free duerme tras 15 min. Esperá 30-60 seg en la primera request.

### "CORS error en Vercel"
El backend tiene `allow_origins=["*"]`, debería funcionar. Si no:
- Verificá que `VITE_API_URL` en Vercel esté bien
- Verificá que el backend esté Live en Render

### "Database connection failed"
- En Render Dashboard, verificá que la DB esté linkeada al Web Service
- En "Environment" del Web Service: debe existir `DATABASE_URL`

### "Tests fallan en CI"
Ver logs en GitHub → Actions → último run.
