# QUÉ INCLUIR EN EL EXPEDIENTE DNDA
## Identificación de carpetas y archivos a presentar

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12

---

## 1. ESTRUCTURA DEL PAQUETE A ENTREGAR

El expediente de registro debe organizarse en 3 carpetas principales:

```
EXPEDIENTE_DNDA_2026_06/
│
├── SOFTWARE/                          # Código fuente compilado y funcional
│   ├── backend/                       # API REST (FastAPI + Python 3.11)
│   ├── frontend/                      # Interfaz web (React 18 + TypeScript)
│   ├── mobile/                        # Aplicación móvil (React Native)
│   └── REGISTRO_OBRA_SOFTWARE/        # Documentación de registro
│
├── DOCUMENTACION/                     # PDFs principales
│   ├── MEMORIA_DESCRIPTIVA.pdf
│   ├── EVIDENCIA_AUTORIA.pdf
│   ├── INVENTARIO_TECNICO.pdf
│   ├── DOCUMENTACION_TECNICA.pdf
│   ├── MANUAL_FUNCIONAL.pdf
│   ├── ACTIVOS_PI.pdf
│   ├── RESUMEN_EJECUTIVO.pdf
│   └── CODIGO_FUENTE_EXTRACTO.pdf
│
├── CAPTURAS/                          # Screenshots del sistema funcionando
│   ├── 01_login.png
│   ├── 02_dashboard.png
│   ├── 03_conciliacion.png
│   ├── ...
│   └── (24 capturas total)
│
└── DIAGRAMAS/                         # Diagramas de arquitectura
    ├── arquitectura_3_capas.png
    ├── arquitectura_db.png
    └── flujo_conciliacion.png
```

---

## 2. CARPETA SOFTWARE/ — QUÉ INCLUIR

### 2.1 Backend (FastAPI + Python 3.11)

**Incluir:**
- `/backend/app/` — Código fuente completo de la API REST
  - `models/` — 18 modelos de datos (SQLAlchemy ORM)
  - `routers/` — 22 routers/endpoints
  - `services/` — 18 servicios de lógica de negocio
  - `schemas/` — 8 esquemas de validación Pydantic
  - `middleware/` — Autenticación JWT y permisos
  - `main.py` — Punto de entrada FastAPI con lifespan y safety nets
  - `config.py` — Configuración por entorno
  - `database.py` — Configuración SQLAlchemy

- `/backend/alembic/` — Sistema de migraciones de base de datos
  - `versions/` — 9 migraciones (001 a 009)
  - `env.py` — Configuración Alembic
  - `script.py.mako` — Template de migraciones

- `/backend/tests/` — Suite de 156 tests automatizados
  - `test_conciliacion.py`, `test_motor_contable.py`, `test_auth.py`, etc.
  - `conftest.py` — Configuración pytest

- `/backend/requirements.txt` — Dependencias de Python (con versiones)

- `/backend/.env.example` — Template de variables de entorno (sin valores reales)

**NO incluir:**
- `/backend/.venv/` — Entorno virtual (reinstalable)
- `/backend/__pycache__/` — Caché de Python (generado)
- `/backend/.env` — Variables de entorno reales (sensibles)
- `/backend/crear_datos_prueba.py` — Script generador de datos de prueba (testing local, no es parte del sistema)
- `/backend/node_modules/` — Si hubiera (no existe en este proyecto)

---

### 2.2 Frontend Web (React 18 + TypeScript + PWA)

**Incluir:**
- `/frontend/src/` — Código TypeScript/React completo
  - `pages/` — 31 páginas/vistas del sistema
  - `components/` — 18 componentes reutilizables
  - `store/` — 6 stores de estado global (Zustand)
  - `services/` — Cliente HTTP centralizado, servicios
  - `utils/` — Utilidades de fecha, formato, validación
  - `types/` — Definiciones TypeScript
  - `App.tsx`, `main.tsx` — Bootstrap de la aplicación

- `/frontend/public/` — Recursos públicos
  - `sw.js` — Service Worker para PWA
  - `manifest.json` — Manifiesto PWA
  - `favicon.ico` — Icono de la aplicación

- `/frontend/index.html` — HTML de entrada

- `/frontend/package.json` y `package-lock.json` — Dependencias NPM

- `/frontend/vite.config.ts` — Configuración del build (Vite)

- `/frontend/tsconfig.json` — Configuración TypeScript

- `/frontend/.env.example` — Template de variables de entorno (sin valores)

**NO incluir:**
- `/frontend/node_modules/` — Dependencias (reinstalables con `npm install`)
- `/frontend/dist/` — Build compilado (se genera con `npm run build`)
- `/frontend/.env`, `/frontend/.env.production` — Variables de entorno reales (sensibles)
- `/frontend/.env.local` — Configuración local del desarrollador

---

### 2.3 Aplicación Móvil (React Native + Expo)

**Incluir:**
- `/mobile/src/` — Código TypeScript/React Native
  - `screens/` — Pantallas de la aplicación móvil
  - `navigation/` — Navegación nativa (React Navigation)
  - `services/` — Cliente API
  - `store/` — Estado global

- `/mobile/app.json` — Configuración de Expo

- `/mobile/package.json` y `package-lock.json` — Dependencias

- `/mobile/tsconfig.json` — Configuración TypeScript

**NO incluir:**
- `/mobile/node_modules/` — Dependencias
- `/mobile/.env` — Variables sensibles

---

### 2.4 Documentación de Registro

**Incluir carpeta `/REGISTRO_OBRA_SOFTWARE/`** — Todos los 19 documentos .md:

Grupo A (imprescindibles):
- `MEMORIA_DESCRIPTIVA.md`
- `INVENTARIO_TECNICO.md`
- `DOCUMENTACION_TECNICA.md`
- `MANUAL_FUNCIONAL.md`
- `MODULOS_DEL_SISTEMA.md`
- `EVIDENCIA_AUTORIA.md`
- `ACTIVOS_PI.md`
- `RESUMEN_EJECUTIVO.md`

Grupo B (respaldo):
- `EXPEDIENTE_FINAL.md`
- `REVISION_EXPEDIENTE.md`
- `REVISION_AUTORIA_FINAL.md`
- `NOMBRE_DE_OBRA_RECOMENDADO.md`
- `VERSION_A_REGISTRAR.md`
- `MATERIAL_COMPLEMENTARIO.md`

Grupo C (guías operativas):
- `README_REGISTRO.md`
- `TAG_REGISTRO.md`
- `PAQUETE_FINAL.md`
- `CHECKLIST_PRESENTACION.md`
- `ESTADO_FINAL_REGISTRO.md`

---

## 3. ARCHIVOS RAÍZ A INCLUIR

**Incluir en la raíz del SOFTWARE/:**
- `README.md` — Descripción general del proyecto
- `CLAUDE.md` — Documentación técnica y arquitectura (v3.12, 15 KB)
- `.gitignore` — Archivo de control de Git (NO sensible, solo lista de patrones)
- `LICENSE` — Licencia de la obra (si existe)

**NO incluir:**
- `.git/` — Historial de Git (demasiado voluminoso, no requerido por DNDA)
- `.github/` — Configuración de GitHub Actions (no necesario para la DNDA)
- Archivos de configuración de deployment (`render.yaml`, `vercel.json`, `railway.json`) — Sensibles
- `ROADMAP.md`, `DEPLOY.md`, `COSTEO.md`, `PROBAR_EN_CELULAR.md` — Documentación interna (no oficial)

---

## 4. TAMAÑO ESTIMADO DEL PAQUETE

| Componente | Tamaño |
|---|---|
| Backend (código fuente) | ~1.1 MB |
| Frontend (código fuente) | ~1.5 MB |
| Mobile (código fuente) | ~836 KB |
| REGISTRO_OBRA_SOFTWARE/ (19 .md) | ~500 KB |
| DOCUMENTACION/ (8 PDFs) | ~8-10 MB |
| CAPTURAS/ (24 screenshots) | ~12-15 MB |
| DIAGRAMAS/ (3-4 diagramas) | ~500 KB |
| **TOTAL ESTIMADO** | **~24-26 MB** |

**CUMPLE REQUISITO DNDA:** < 2 GB ✓

---

## 5. REQUISITOS DE INCLUSIÓN VERIFICADOS

| Requisito DNDA | Cumple | Evidencia |
|---|---|---|
| Código fuente completo | ✓ | Backend (22 routers, 18 servicios), Frontend (31 páginas), Mobile (Expo) |
| Software compilado | ✓ | Backend puede ejecutarse con `python -m uvicorn`, Frontend con `npm run build` |
| Software terminado | ✓ | v3.12 en producción, 156 tests pasando, 121 commits históricos |
| Documentación de autoría | ✓ | EVIDENCIA_AUTORIA.md con 100% commits de Julieta Arrazate |
| Originalidad acreditada | ✓ | ACTIVOS_PI.md (5 algoritmos propios, 5 reglas de negocio) |
| Migraciones de BD | ✓ | 9 migraciones Alembic (001 a 009) |
| Tests automatizados | ✓ | 156 tests en `/backend/tests/` |
| Tecnologías documentadas | ✓ | INVENTARIO_TECNICO.md y DOCUMENTACION_TECNICA.md |
| Esquema de BD | ✓ | 18 modelos SQLAlchemy en `/backend/app/models/` |

---

## 6. ORDEN DE VERIFICACIÓN ANTES DE EMPAQUETAR

1. ✓ Carpeta SOFTWARE/ contiene backend, frontend, mobile sin node_modules ni __pycache__
2. ✓ Archivo REGISTRO_OBRA_SOFTWARE/DNDA_*.md existe (10 documentos)
3. ✓ Carpeta DOCUMENTACION/ contiene 8 PDFs en español
4. ✓ Carpeta CAPTURAS/ contiene 24 screenshots del sistema funcionando
5. ✓ Carpeta DIAGRAMAS/ contiene 3-4 diagramas de arquitectura
6. ✓ No hay archivos .env con credenciales reales
7. ✓ No hay archivos .pem, .key, o tokens
8. ✓ No hay paths con nombre de usuario personal (normalizados a ~/Desktop)
9. ✓ Tamaño total < 2 GB
10. ✓ README.md en SOFTWARE/ describe brevemente la instalación

---

*Documento de inclusión para expediente DNDA — Julieta Arrazate — Junio 2026*
