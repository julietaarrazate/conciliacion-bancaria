# Cómo probar todo (web + celular) con datos reales

## ⚡ Setup en 5 minutos

### Paso 1: Levantar el backend

Doble clic en **`start_dev.bat`** en la raíz del proyecto.

Se abren 2 ventanas:
- **Backend** (puerto 8000)
- **Frontend Web** (puerto 3000)

La primera vez te muestra tus IPs disponibles, anotá la del WiFi (ej: `192.168.1.8`).

### Paso 2: Probar la web

Abrir http://localhost:3000

Login con:
- **Admin**: `admin@demo.com` / `admin123`
- **Operador**: `operador@demo.com` / `operador123`

### Paso 3: Probar el flujo de conciliación con datos reales

1. **Cargar Extracto Bancario**:
   - Click "Conciliar" en sidebar
   - Subí: `C:\Users\Tomas\Desktop\Extracto Macro\extracto macro abril.xlsx`

2. **Cliente**: escribir el nombre (ej: `Green`, `Alojando`)

3. **Cargar Planilla**:
   - Subí cualquier archivo de `C:\Users\Tomas\Desktop\INBOX\<cliente>\` o `INBOX\procesados\`
   - El sistema reconcilia automáticamente
   - Ves stats: acreditadas / no encontradas / duplicadas / sin datos

4. **Ver Historial**: click "Historial" en sidebar
5. **Ver Auditoría** (admin): click "Auditoría" → ves todas las acciones

---

## 📱 Probar en el celular (Android/iOS)

### Pre-requisitos

- Celular y PC en la **misma red WiFi**
- App **Expo Go** instalada en el celular (gratis):
  - Android: https://play.google.com/store/apps/details?id=host.exp.exponent
  - iOS: https://apps.apple.com/app/expo-go/id982107779

### Paso 1: Anotá tu IP

```
http://192.168.1.8:8000
```

(Es la IP que mostró `start_dev.bat`. Si no, corré `python backend/network_info.py`)

### Paso 2: Levantá Expo

Doble clic en **`start_mobile.bat`** en la raíz del proyecto.

Se abre una ventana con un **código QR**.

### Paso 3: Escaneá el QR

- **iOS**: abrí la **cámara nativa** y escaneá el QR
- **Android**: abrí **Expo Go** y tocá "Scan QR code"

La app se descarga y abre automáticamente.

### Paso 4: Configurar URL del backend (primera vez)

1. La primera vez, vas a ver "No se pudo conectar"
2. Tocá la pestaña **⚙️ Ajustes** abajo
3. En "URL del backend" pegá: `http://192.168.1.8:8000` (tu IP)
4. Tocá **Probar** → debe decir "✓ Conexión OK"
5. Tocá **Guardar**
6. Volvé al **Login**

### Paso 5: Probar la app

Login con `admin@demo.com` / `admin123`

**Pestaña Conciliar**:
- Tocá "Cargar extracto" → seleccioná un .xlsx desde el celular
- Ingresá nombre del cliente
- Tocá "Cargar y conciliar" → seleccioná planilla
- Ves los resultados

**Pestaña Historial**:
- Lista todas las reconciliaciones (de la web también)
- Pull-to-refresh para actualizar
- Filtro por nombre de cliente

**Pestaña Ajustes**:
- Cambiar URL del backend
- Cerrar sesión

---

## 🐛 Si algo no funciona

### "No se puede conectar al servidor" en el celular

- ✅ Verificá que estás en la misma WiFi
- ✅ Verificá la IP: `python backend/network_info.py`
- ✅ Verificá que el firewall de Windows permite conexiones al puerto 8000:
  - Panel de Control → Firewall de Windows → Permitir una app
  - O probá temporalmente desactivar el firewall

### El QR no aparece en `start_mobile.bat`

```bash
cd mobile
npm install
npx expo start --tunnel
```

`--tunnel` usa un servidor de Expo como puente (más lento pero funciona aunque las redes sean distintas).

### "Token inválido" después de tiempo

El JWT expira a los 30 minutos. Cerrar sesión y volver a entrar.

### Reset total del backend

```bash
cd backend
del test.db
python seed.py
```

Borra la BD y crea de cero los usuarios admin/operador.

---

## 🎯 Flujo de prueba recomendado

1. ✅ Levantar backend con `start_dev.bat`
2. ✅ Probar login en web (admin/operador)
3. ✅ Conciliar 1 planilla en web
4. ✅ Ver historial y auditoría
5. ✅ Cambiar rol de operador → revisor (página Usuarios, solo admin)
6. ✅ Levantar móvil con `start_mobile.bat`
7. ✅ Configurar URL en Settings
8. ✅ Login móvil
9. ✅ Conciliar 1 planilla desde el celular
10. ✅ Ver historial en celular (debe mostrar las 2 reconciliaciones)

---

## 📊 Datos reales que tenés

| Archivo | Ubicación |
|---|---|
| Extracto Abril | `C:\Users\Tomas\Desktop\Extracto Macro\extracto macro abril.xlsx` |
| Planilla Alojando | `C:\Users\Tomas\Desktop\INBOX\procesados\alojando.xlsx` |
| Planilla Green | `C:\Users\Tomas\Desktop\INBOX\procesados\Green 28.4.xlsx` |

Probalas con esos. Si tenés más planillas en otras carpetas, también las podés usar.
