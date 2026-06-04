# EXCLUSIONES POR SEGURIDAD Y PRIVACIDAD
## Archivos y carpetas que NO deben incluirse en el expediente

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12

---

## 1. ARCHIVOS DE CONFIGURACIÓN CON CREDENCIALES

**Estos archivos NO deben incluirse:**

| Archivo | Razón | Riesgo |
|---|---|---|
| `.env` (raíz backend) | Variables de entorno con credenciales reales | **CRÍTICO** — Expone API keys, contraseñas BD, tokens |
| `.env.production` (frontend) | URLs de API y configuración de producción | Contiene VITE_API_URL de servidor en producción |
| `.env.local` (frontend) | Configuración local del desarrollador | Puede contener tokens personales |
| `render.yaml` | Configuración de deployment en Render | Expone SERVICE_ID, env vars |
| `vercel.json` | Configuración de deployment en Vercel | Expone PROJECT_ID y settings |
| `railway.json` | Configuración de Railway | Sensible |

**Verificación realizada:**
- ✓ Backend tiene `.env.example` (seguro, sin valores)
- ✓ Frontend tiene `.env.example` y `.env.production.example` (seguros)
- ✓ Archivos `.env` reales NO están versionados (en `.gitignore`)
- ✓ Archivos deployment NO están en el repositorio

---

## 2. ARCHIVOS CON DATOS PERSONALES O RUTAS DE USUARIO

### 2.1 Crear datos de prueba (crear_datos_prueba.py)

**Archivo:** `/backend/crear_datos_prueba.py`

**Contenido sensible:**
```
C:/Users/Tomas/Desktop/INBOX/datos_prueba/
DESKTOP = "C:/Users/Tomas/Desktop"
```

**Razón de exclusión:**
- Contiene ruta local de desarrollador anterior (Tomas)
- Ruta hardcodeada expone estructura de directorios personales
- Script generador de datos de prueba NO es necesario para el registro

**Acción:** NO INCLUIR

---

### 2.2 Datos de seed (Usuarios de demo)

**Archivo:** `/backend/seed.py`

**Contenido seguro (OK incluir):**
- Crea usuarios de demo: `admin@demo.com`, `operador@demo.com`
- No contiene contraseñas hardcodeadas (lee de env `SUPERADMIN_PASSWORD`)
- Script es necesario para demostración del sistema

**Acción:** INCLUIR (es seguro)

---

## 3. DIRECTORIOS A EXCLUIR (NO son código fuente)

| Directorio | Razón | Acción |
|---|---|---|
| `node_modules/` (frontend y mobile) | Dependencias NPM reinstalables | EXCLUIR |
| `__pycache__/` (backend) | Caché compilado de Python | EXCLUIR |
| `.venv/` o `venv/` (backend) | Entorno virtual reinstalable | EXCLUIR |
| `.git/` | Historial Git (voluminoso, no requerido) | EXCLUIR |
| `.github/` | Configuración GitHub Actions | EXCLUIR |
| `dist/` (frontend) | Build compilado generado | EXCLUIR (se regenera con `npm run build`) |
| `.next/` (si hubiera) | Build Next.js | EXCLUIR |
| `build/` (si hubiera) | Artefactos de build | EXCLUIR |

**Tamaño ahorrado:**
- `node_modules/`: ~500 MB (frontend) + ~400 MB (mobile) = ~900 MB
- `__pycache__/`: ~50 MB
- `.git/`: ~100 MB
- **Total ahorrado:** ~1 GB

**Verificación:** Los archivos `.gitignore` existentes ya excluyen estos directorios.

---

## 4. ARCHIVOS DE DOCUMENTACIÓN INTERNA

**Estos archivos NO son necesarios para la DNDA:**

| Archivo | Propósito | Acción |
|---|---|---|
| `ROADMAP.md` | Planificación futura del proyecto | EXCLUIR |
| `DEPLOY.md` | Instrucciones de deployment | EXCLUIR |
| `COSTEO.md` | Análisis de costos | EXCLUIR |
| `PROBAR_EN_CELULAR.md` | Guía desarrollo local | EXCLUIR |
| `QUICKSTART.md` (backend) | Guía de inicio rápido | INCLUIR (documentación técnica útil) |
| `README.md` (backend) | Descripción del backend | INCLUIR |
| `README.md` (frontend) | Descripción del frontend | INCLUIR |
| `README.md` (mobile) | Descripción de la app móvil | INCLUIR |

---

## 5. ARCHIVOS Y CARPETAS SENSIBLES (DATOS)

### 5.1 Base de datos

**NO INCLUIR:**
- Archivos `.db`, `.sqlite`, `.sqlite3`
- Dumps de PostgreSQL (`.sql`, `.backup`)
- Archivos de configuración de BD con credenciales

**Acción:** No existen en el repositorio (BD está en Neon, no local). ✓

---

### 5.2 Logs y datos de diagnóstico

**NO INCLUIR:**
- Carpetas `logs/`, `tmp/`, `temp/`
- Archivos `.log`, `.pid`
- Reportes de errores con datos sensibles

**Acción:** No existen en el repositorio. ✓

---

### 5.3 Archivos de test con datos reales

**Archivo:** `/backend/tests/` — Datos de prueba en fixtures

**Verificación realizada:**
- ✓ Los tests usan nombres ficticios: `LOZANO BEATRIZ`, `CABRERA OSCAR`, `TORRES MIGUEL`
- ✓ Los CUIT en fixtures son ficticios (20-XX-XXXXXX-X format, números válidos pero inventados)
- ✓ NO hay emails reales ni datos de clientes verdaderos
- ✓ OK INCLUIR la carpeta `/backend/tests/`

---

## 6. ARCHIVOS CON TOKENS O CLAVES SECRETAS

**Búsqueda realizada:**

```bash
grep -r "PRIVATE_KEY\|SECRET\|TOKEN\|password=" /backend \
  --include="*.py" --exclude-dir=node_modules
```

**Resultado:**
- ✓ NO hay tokens hardcodeados en el código
- ✓ Todos los secrets están en variables de entorno (`.env` — no versionado)
- ✓ Las claves se leen con `os.environ.get()` con valores por defecto seguros

**Acción:** OK INCLUIR el código fuente. ✓

---

## 7. ARCHIVOS DE TERCEROS O DEPENDENCIAS

**NO INCLUIR:**

| Tipo | Razón | Acción |
|---|---|---|
| `node_modules/` | Dependencias NPM | EXCLUIR (reinstalables) |
| Librerías de terceros | Código externo | Ya especificadas en `package.json` / `requirements.txt` |
| Fuentes de componentes UI | Bundles de terceros | EXCLUIR |
| Mapas, iconos de terceros | Assets externos | Ya linkados desde CDN |

**Verificación:**
- ✓ Dependencies correctas en `requirements.txt` (FastAPI, SQLAlchemy, Alembic, etc.)
- ✓ Dependencies correctas en `package.json` (React, Vite, TailwindCSS, etc.)
- ✓ Todas son open-source bajo licencias permisivas (MIT, Apache 2.0, BSD)

---

## 8. ARCHIVOS DE CONFIGURACIÓN DE IDE/EDITOR

**NO INCLUIR (aunque generalmente ya está en .gitignore):**

| Archivo | Herramienta | Acción |
|---|---|---|
| `.vscode/` | Visual Studio Code | EXCLUIR |
| `.idea/` | JetBrains IDEs | EXCLUIR |
| `*.swp`, `*.swo` | Vim | EXCLUIR |
| `.DS_Store` | macOS | EXCLUIR |
| `Thumbs.db` | Windows | EXCLUIR |

**Verificación:** ✓ Ya están en `.gitignore` del proyecto

---

## 9. CERTIFICADOS Y ASSETS DE PRODUCCIÓN

**NO INCLUIR:**

| Archivo | Razón | Acción |
|---|---|---|
| `.pem`, `.key`, `.crt` | Certificados SSL | EXCLUIR (en servidores de hosting) |
| `*.p8` | Claves de API | EXCLUIR |
| Imágenes/logos de marca | Potencial propiedad de terceros | EXCLUIR (si las hay) |

**Verificación:** ✓ No existen en el repositorio

---

## 10. CHECKLIST FINAL DE EXCLUSIONES

Antes de empaquetar, verificar:

- [ ] NO incluir `/backend/.env` (solo `.env.example`)
- [ ] NO incluir `/frontend/.env*` reales (solo `.env.example`)
- [ ] NO incluir `node_modules/` (frontend ni mobile)
- [ ] NO incluir `__pycache__/` (backend)
- [ ] NO incluir `.venv/` o `venv/`
- [ ] NO incluir `.git/` (historial Git)
- [ ] NO incluir `/backend/crear_datos_prueba.py` (contiene ruta C:/Users/Tomas)
- [ ] NO incluir `render.yaml`, `vercel.json`, `railway.json` (credentials)
- [ ] NO incluir `dist/` (build compilado frontend)
- [ ] NO incluir archivos `.pem`, `.key`, `.crt`, `*.p8`
- [ ] NO incluir ROADMAP.md, DEPLOY.md, COSTEO.md, PROBAR_EN_CELULAR.md
- [ ] INCLUIR seed.py (es seguro, crea datos de demo)
- [ ] INCLUIR `/backend/tests/` (tests con datos ficticios)
- [ ] INCLUIR `REGISTRO_OBRA_SOFTWARE/` completo (19 .md + 8 PDFs)
- [ ] INCLUIR README.md, CLAUDE.md raíz (documentación oficial)
- [ ] INCLUIR requirements.txt y package.json (dependencias)

---

## 11. RESUMEN DE IMPACTO

| Acción | Archivos | Espacio |
|---|---|---|
| Excluir node_modules | — | -1.3 GB |
| Excluir .venv, __pycache__, .git | — | -150 MB |
| Excluir crear_datos_prueba.py | 1 | -5 KB |
| Excluir archivos deployment sensibles | 3 | -10 KB |
| **Resultado** | **Código limpio y seguro** | **-1.45 GB de sensibles/bloat** |

**Tamaño final esperado:** ~24-26 MB (dentro del límite DNDA < 2 GB)

---

*Documento de exclusiones para expediente DNDA — Julieta Arrazate — Junio 2026*
