# CONTENIDO DEL PAQUETE FINAL
## Qué incluir y qué excluir del ZIP de registro

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## 1. QUÉ INCLUIR

### 1.1 Código fuente del backend

```
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── logging_config.py
│   ├── middleware/
│   │   └── auth.py
│   ├── models/          ← todos los archivos .py
│   ├── routers/         ← todos los archivos .py
│   ├── services/        ← todos los archivos .py
│   └── schemas/         ← todos los archivos .py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/        ← todos los archivos .py de migración
└── alembic.ini
```

### 1.2 Código fuente del frontend

```
frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── vite-env.d.ts
│   ├── pages/           ← todos los archivos .tsx
│   ├── components/      ← todos los archivos .tsx
│   ├── services/
│   │   └── api.ts
│   ├── store/           ← todos los archivos .ts
│   ├── utils/
│   │   └── fecha.ts
│   ├── types/           ← todos los archivos .ts
│   └── styles/
│       └── index.css
├── public/
│   ├── sw.js
│   ├── manifest.json
│   └── icons/           ← íconos de la PWA
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

### 1.3 Código fuente de la aplicación móvil

```
mobile/
├── src/
│   ├── screens/         ← todos los archivos .tsx
│   ├── components/      ← todos los archivos .tsx
│   ├── navigation/      ← todos los archivos .tsx
│   ├── services/        ← todos los archivos .ts
│   ├── store/           ← todos los archivos .ts
│   └── types/           ← todos los archivos .ts
├── app.json
├── package.json
└── tsconfig.json
```

### 1.4 Tests automatizados

```
backend/tests/
├── conftest.py
├── test_conciliacion.py
├── test_motor_contable.py
├── test_excel_parser.py
├── test_auth.py
├── test_audit_fixes.py
├── test_backup_service.py
├── test_fixes.py
├── test_soft_delete.py
├── test_tz.py
└── test_v34_features.py
```

### 1.5 Archivos de configuración de proyecto

```
backend/
├── requirements.txt
└── requirements-dev.txt

frontend/
├── package.json
└── vercel.json

(raíz)
├── render.yaml
└── railway.toml
```

### 1.6 Documentación de registro

```
REGISTRO_OBRA_SOFTWARE/
└── (todos los archivos .md)
```

### 1.7 Documentación técnica del repositorio

```
(raíz)
├── README.md
└── BUGS.md
```

---

## 2. QUÉ EXCLUIR

### 2.1 Dependencias instaladas (nunca incluir)

```
node_modules/          ← dependencias npm del frontend
mobile/node_modules/   ← dependencias npm del móvil
backend/.venv/         ← entorno virtual Python
backend/venv/          ← entorno virtual Python (variante)
__pycache__/           ← bytecode Python compilado
*.pyc                  ← archivos .pyc individuales
*.pyo
```

### 2.2 Build / distribución

```
frontend/dist/         ← build de producción del frontend
frontend/.vite/        ← caché de Vite
mobile/.expo/          ← caché de Expo
*.egg-info/
build/
```

### 2.3 Archivos de entorno y secretos — CRÍTICO

```
.env                   ← variables de entorno locales
.env.local
.env.production
.env.development
backend/.env
frontend/.env
*.pem                  ← certificados
*.key                  ← claves privadas
vapid_*.json           ← claves VAPID
```

### 2.4 Cobertura y reportes de test

```
.coverage
htmlcov/
coverage.xml
.pytest_cache/
```

### 2.5 Archivos de sistema

```
.DS_Store              ← macOS
Thumbs.db              ← Windows
*.swp                  ← Vim
.idea/                 ← JetBrains
.vscode/               ← VS Code (settings personales)
```

### 2.6 Archivos de git

```
.git/                  ← historial git completo
                         (salvo que el organismo lo solicite explícitamente)
```

**Excepción:** si el organismo solicita evidencia de historial, incluir un export del log:
```bash
git log --format="%H | %ad | %an | %s" --date=short > HISTORIAL_GIT.txt
```

### 2.7 Archivos internos de desarrollo

```
CLAUDE.md              ← documentación interna de desarrollo
COSTEO.md              ← información comercial interna
ROADMAP.md             ← planes futuros internos
instalar.bat
start.bat / start_dev.bat / start_local.bat / start_mobile.bat
watcher.py
importar_patrones.ps1
crear_datos_prueba.py
seed.py
```

---

## 3. ESTRUCTURA RECOMENDADA DEL ZIP

```
REGISTRO_OBRA_SOFTWARE_v3.12.zip
│
├── DOCUMENTACION/
│   ├── README_REGISTRO.md
│   ├── MEMORIA_DESCRIPTIVA.md
│   ├── INVENTARIO_TECNICO.md
│   ├── DOCUMENTACION_TECNICA.md
│   ├── MANUAL_FUNCIONAL.md
│   ├── MODULOS_DEL_SISTEMA.md
│   ├── EVIDENCIA_AUTORIA.md
│   ├── RESUMEN_EJECUTIVO.md
│   ├── ACTIVOS_PI.md
│   ├── VERSION_A_REGISTRAR.md
│   └── EXPEDIENTE_FINAL.md
│
├── SOFTWARE/
│   ├── backend/        ← código fuente Python (sin .venv, sin __pycache__)
│   ├── frontend/       ← código fuente React/TS (sin node_modules, sin dist)
│   └── mobile/         ← código fuente React Native (sin node_modules)
│
├── CAPTURAS/           ← capturas de pantalla del sistema en uso
│   └── (ver MATERIAL_COMPLEMENTARIO.md)
│
├── DIAGRAMAS/          ← diagramas de arquitectura, BD, módulos
│   └── (ver MATERIAL_COMPLEMENTARIO.md)
│
└── HISTORIAL_GIT.txt   ← export del log git (opcional pero recomendado)
```

---

## 4. COMANDO PARA GENERAR EL ZIP

```bash
# Desde la raíz del repositorio
cd /ruta/al/repositorio

# Generar el historial git
git log --format="%H | %ad | %an | %s" --date=short > HISTORIAL_GIT.txt

# Crear el ZIP excluyendo lo que no debe ir
zip -r REGISTRO_OBRA_SOFTWARE_v3.12.zip \
  backend/app \
  backend/alembic \
  backend/alembic.ini \
  backend/requirements.txt \
  backend/requirements-dev.txt \
  backend/tests \
  frontend/src \
  frontend/public \
  frontend/package.json \
  frontend/tsconfig.json \
  frontend/vite.config.ts \
  frontend/tailwind.config.js \
  frontend/vercel.json \
  mobile/src \
  mobile/app.json \
  mobile/package.json \
  mobile/tsconfig.json \
  REGISTRO_OBRA_SOFTWARE \
  README.md \
  HISTORIAL_GIT.txt
```

---

## 5. VERIFICACIÓN PREVIA AL ZIP

Antes de comprimir, verificar que NO existan en las carpetas incluidas:

- [ ] Ningún archivo `.env` o `.env.*`
- [ ] Ningún archivo `.key` o `.pem`
- [ ] Ningún directorio `node_modules/`
- [ ] Ningún directorio `.venv/` o `venv/`
- [ ] Ningún directorio `__pycache__/`
- [ ] Ningún directorio `dist/` o `build/`
- [ ] Ningún archivo con credenciales o tokens

---

*Documento elaborado para expediente de registro. Julieta Arrazate — Junio 2026*
