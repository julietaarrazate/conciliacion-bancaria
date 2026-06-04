# ESTRUCTURA FINAL DEL PAQUETE ZIP
## Organización exacta de archivos para presentación ante DNDA

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12

---

> **⚠️ ÁMBITO DE ESTE DOCUMENTO — CANAL B (depósito de código fuente)**
>
> Este ZIP corresponde al **depósito del código fuente completo**, que la DNDA
> suele recibir por soporte físico (CD/DVD/USB) o por un canal de depósito
> aparte. **NO es para el portal de carga online**, que tiene un límite de 20 MB
> y no acepta ZIP ni archivos de código.
>
> Para la carga en el **portal online (Canal A)** ver
> **`DNDA_FORMATO_PRESENTACION.md`** (documentación y código como PDF, archivos
> sueltos ≤ 20 MB).
>
> **Antes de usar este ZIP, confirmar con la DNDA el medio del Canal B.**

---

## 1. ESTRUCTURA RECOMENDADA

```
EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip
│
├── SOFTWARE/
│   ├── backend/                           # Código FastAPI (1.1 MB)
│   │   ├── app/
│   │   │   ├── models/
│   │   │   ├── routers/
│   │   │   ├── services/
│   │   │   ├── schemas/
│   │   │   ├── middleware/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── alembic/
│   │   │   ├── versions/                  # 9 migraciones (001-009)
│   │   │   ├── env.py
│   │   │   └── script.py.mako
│   │   ├── tests/                         # 156 tests automatizados
│   │   │   ├── conftest.py
│   │   │   ├── test_*.py
│   │   │   └── ...
│   │   ├── requirements.txt               # Dependencias Python
│   │   ├── .env.example                   # Template env (sin valores)
│   │   ├── README.md
│   │   └── QUICKSTART.md
│   │
│   ├── frontend/                          # Código React PWA (1.5 MB)
│   │   ├── src/
│   │   │   ├── pages/                     # 31 páginas
│   │   │   ├── components/                # 18 componentes
│   │   │   ├── store/                     # 6 stores Zustand
│   │   │   ├── services/
│   │   │   ├── utils/
│   │   │   ├── types/
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── public/
│   │   │   ├── sw.js                      # Service Worker
│   │   │   ├── manifest.json              # PWA manifest
│   │   │   └── favicon.ico
│   │   ├── index.html
│   │   ├── package.json
│   │   ├── package-lock.json
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── .env.example
│   │   ├── .env.production.example
│   │   ├── README.md
│   │   └── (NO node_modules/, NO dist/)
│   │
│   ├── mobile/                            # Código React Native (836 KB)
│   │   ├── src/
│   │   │   ├── screens/
│   │   │   ├── navigation/
│   │   │   ├── services/
│   │   │   └── store/
│   │   ├── app.json
│   │   ├── package.json
│   │   ├── package-lock.json
│   │   ├── tsconfig.json
│   │   ├── README.md
│   │   └── (NO node_modules/)
│   │
│   ├── REGISTRO_OBRA_SOFTWARE/            # Documentación de registro
│   │   ├── MEMORIA_DESCRIPTIVA.md
│   │   ├── INVENTARIO_TECNICO.md
│   │   ├── DOCUMENTACION_TECNICA.md
│   │   ├── MANUAL_FUNCIONAL.md
│   │   ├── MODULOS_DEL_SISTEMA.md
│   │   ├── EVIDENCIA_AUTORIA.md
│   │   ├── ACTIVOS_PI.md
│   │   ├── RESUMEN_EJECUTIVO.md
│   │   ├── EXPEDIENTE_FINAL.md
│   │   ├── REVISION_EXPEDIENTE.md
│   │   ├── REVISION_AUTORIA_FINAL.md
│   │   ├── NOMBRE_DE_OBRA_RECOMENDADO.md
│   │   ├── VERSION_A_REGISTRAR.md
│   │   ├── MATERIAL_COMPLEMENTARIO.md
│   │   ├── README_REGISTRO.md
│   │   ├── TAG_REGISTRO.md
│   │   ├── PAQUETE_FINAL.md
│   │   ├── CHECKLIST_PRESENTACION.md
│   │   ├── ESTADO_FINAL_REGISTRO.md
│   │   ├── DNDA_OBRA_PRESENTABLE.md
│   │   ├── DNDA_INCLUIR.md
│   │   ├── DNDA_EXCLUSIONES.md
│   │   ├── DNDA_PRIVACIDAD.md
│   │   ├── DNDA_CAPTURAS.md
│   │   ├── DNDA_REVISION_EXPEDIENTE.md
│   │   ├── DNDA_VERSION_REGISTRADA.md
│   │   ├── DNDA_ESTRUCTURA_ZIP.md
│   │   ├── DNDA_VALIDACION_FINAL.md
│   │   └── DNDA_CHECKLIST_FINAL.md        # (a crear)
│   │
│   ├── README.md                          # Descripción general del sistema
│   ├── CLAUDE.md                          # Documentación técnica (opcional)
│   └── .gitignore                         # Archivo de control Git (informativo)
│
├── DOCUMENTACION/
│   ├── MEMORIA_DESCRIPTIVA.pdf
│   ├── INVENTARIO_TECNICO.pdf
│   ├── DOCUMENTACION_TECNICA.pdf
│   ├── MANUAL_FUNCIONAL.pdf
│   ├── MODULOS_DEL_SISTEMA.pdf
│   ├── EVIDENCIA_AUTORIA.pdf
│   ├── ACTIVOS_PI.pdf
│   ├── RESUMEN_EJECUTIVO.pdf
│   └── CODIGO_FUENTE_EXTRACTO.pdf         # (opcional: 50+ páginas código)
│
├── CAPTURAS/                         # 27 capturas reales del sistema
│   ├── 01_resumen_ejecutivo.png
│   ├── 02_resumen_dark.png
│   ├── 03_conciliar_dashboard.png
│   ├── 04_extractos_archivo.png
│   ├── 05_movimientos_extracto.png
│   ├── 06_conciliaciones.png
│   ├── 07_historial.png
│   ├── 08_clientes.png
│   ├── 09_cheques_listado.png
│   ├── 10_cheques_editar.png
│   ├── 11_pagos_nuevo.png
│   ├── 12_pagos_historial.png
│   ├── 13_caja_arqueo.png
│   ├── 14_contabilidad_modulos.png
│   ├── 15_plan_cuentas_activo_pasivo.png
│   ├── 16_plan_cuentas_resultado.png
│   ├── 17_cuentas_corrientes.png
│   ├── 18_liquidaciones.png
│   ├── 19_flujo_caja.png
│   ├── 20_flujo_caja_detalle.png
│   ├── 21_flujo_caja_6meses.png
│   ├── 22_auditoria_inteligencia.png
│   ├── 23_auditoria_log.png
│   ├── 24_asistente_ia.png
│   ├── 25_papelera.png
│   ├── 26_perfil_datos.png
│   └── 27_perfil_seguridad_ia.png
│
├── DIAGRAMAS/
│   ├── arquitectura_3_capas.png
│   ├── arquitectura_base_datos.png
│   └── flujo_conciliacion.png
│
└── INDICE_CONTENIDO.txt
```

---

## 2. TAMAÑO POR SECCIÓN

| Sección | Componentes | Tamaño estimado |
|---|---|---|
| SOFTWARE/backend | Código + tests + BD migrations | 1.1 MB |
| SOFTWARE/frontend | Código + PWA + service worker | 1.5 MB |
| SOFTWARE/mobile | Código React Native | 836 KB |
| SOFTWARE/REGISTRO_OBRA_SOFTWARE | 29 .md (documentación) | 600 KB |
| SOFTWARE/ (raíz) | README, CLAUDE, .gitignore | 50 KB |
| DOCUMENTACION | 8-9 PDFs en español | 10-12 MB |
| CAPTURAS | 27 screenshots PNG | 13-16 MB |
| DIAGRAMAS | 3-4 imágenes PNG | 500 KB |
| **TOTAL PAQUETE** | **~65 archivos + carpetas** | **~26-30 MB** |

**Cumple requisito DNDA:** < 2 GB ✓

---

## 3. ARCHIVOS POR CARPETA

### 3.1 SOFTWARE/backend

**Incluir:**
- `app/models/` — 18 archivos de modelos
- `app/routers/` — 22 archivos de routers
- `app/services/` — 18 archivos de servicios
- `app/schemas/` — 8 archivos de esquemas
- `app/middleware/` — 1 archivo de middleware
- `app/*.py` — main.py, config.py, database.py, etc.
- `alembic/versions/` — 9 migraciones (001_baseline.py hasta 009_drop_tablas_viejas.py)
- `alembic/env.py`, `alembic/script.py.mako`
- `tests/` — 10 archivos de tests (.py)
- `requirements.txt` — Todas las dependencias
- `.env.example` — Template sin valores reales
- `README.md`, `QUICKSTART.md`

**Tamaño:** ~1.1 MB (150+ archivos)

### 3.2 SOFTWARE/frontend

**Incluir:**
- `src/pages/` — 31 archivos .tsx (Login, Dashboard, etc.)
- `src/components/` — 18 archivos .tsx (Layout, FileUpload, etc.)
- `src/store/` — 6 archivos .ts (auth.ts, org.ts, theme.ts, etc.)
- `src/services/` — api.ts, ...
- `src/utils/` — fecha.ts, formateo.ts, ...
- `src/types/` — index.ts
- `src/App.tsx`, `src/main.tsx`
- `public/` — sw.js, manifest.json, favicon.ico
- `index.html`
- `package.json`, `package-lock.json`
- `vite.config.ts`, `tsconfig.json`
- `.env.example`, `.env.production.example`
- `README.md`

**NO incluir:**
- `node_modules/` (gigantesco, reinstalable)
- `dist/` (generado al compilar)
- `.env`, `.env.local` (credenciales reales)

**Tamaño:** ~1.5 MB (200+ archivos fuente)

### 3.3 SOFTWARE/mobile

**Incluir:**
- `src/screens/` — Pantallas React Native
- `src/navigation/` — Configuración de navegación
- `src/services/` — Cliente API
- `src/store/` — Estado global
- `app.json` — Configuración Expo
- `package.json`, `package-lock.json`
- `tsconfig.json`
- `README.md`

**NO incluir:**
- `node_modules/` (reinstalable)

**Tamaño:** ~836 KB (80+ archivos)

### 3.4 SOFTWARE/REGISTRO_OBRA_SOFTWARE

**Incluir (29 archivos .md):**

Grupo A (8 documentos imprescindibles):
- MEMORIA_DESCRIPTIVA.md
- INVENTARIO_TECNICO.md
- DOCUMENTACION_TECNICA.md
- MANUAL_FUNCIONAL.md
- MODULOS_DEL_SISTEMA.md
- EVIDENCIA_AUTORIA.md
- ACTIVOS_PI.md
- RESUMEN_EJECUTIVO.md

Grupo B (11 documentos de respaldo):
- EXPEDIENTE_FINAL.md
- REVISION_EXPEDIENTE.md
- REVISION_AUTORIA_FINAL.md
- NOMBRE_DE_OBRA_RECOMENDADO.md
- VERSION_A_REGISTRAR.md
- MATERIAL_COMPLEMENTARIO.md
- README_REGISTRO.md
- TAG_REGISTRO.md
- PAQUETE_FINAL.md
- CHECKLIST_PRESENTACION.md
- ESTADO_FINAL_REGISTRO.md

Grupo C (10 nuevos documentos DNDA):
- DNDA_OBRA_PRESENTABLE.md
- DNDA_INCLUIR.md
- DNDA_EXCLUSIONES.md
- DNDA_PRIVACIDAD.md
- DNDA_CAPTURAS.md
- DNDA_REVISION_EXPEDIENTE.md
- DNDA_VERSION_REGISTRADA.md
- DNDA_ESTRUCTURA_ZIP.md
- DNDA_VALIDACION_FINAL.md
- DNDA_CHECKLIST_FINAL.md

**Tamaño:** ~600 KB (29 .md)

### 3.5 SOFTWARE/ (raíz)

**Incluir:**
- `README.md` — Descripción general del sistema (cómo compilar, cómo usar)
- `CLAUDE.md` — Documentación técnica completa v3.12 (OPCIONAL: puede ser sensible si contiene IDs de servicios)
- `.gitignore` — Informativo (qué archivos no versionan)

**Tamaño:** ~50 KB

### 3.6 DOCUMENTACION/ (PDFs)

**Incluir (8-9 archivos PDF):**
1. MEMORIA_DESCRIPTIVA.pdf
2. INVENTARIO_TECNICO.pdf
3. DOCUMENTACION_TECNICA.pdf
4. MANUAL_FUNCIONAL.pdf
5. MODULOS_DEL_SISTEMA.pdf
6. EVIDENCIA_AUTORIA.pdf
7. ACTIVOS_PI.pdf
8. RESUMEN_EJECUTIVO.pdf
9. CODIGO_FUENTE_EXTRACTO.pdf (opcional, extracto de código con 50+ páginas)

**Generación:**
- Exportar cada .md a PDF (pandoc + WeasyPrint)
- Verificar idioma: español (Argentina) ✓
- Verificar encoding: UTF-8 con acentos correctos ✓
- Verificar sans whitespace excesivo

**Tamaño:** ~10-12 MB (8 PDF × 1.2-1.5 MB cada uno)

### 3.7 CAPTURAS/ (Screenshots)

**Incluir (27 archivos PNG):**
- Nombrados `NN_descripcion.png` (01 a 27)
- Resolución 1280×720 o 1920×1080
- Con datos demo (NO datos reales)
- Legibles en pantalla pequeña

Ver DNDA_CAPTURAS.md para lista completa.

**Tamaño:** ~13-16 MB (27 × 500-600 KB)

### 3.8 DIAGRAMAS/ (Diagramas de arquitectura)

**Incluir (3-4 archivos PNG):**
1. `arquitectura_3_capas.png` — Diagrama de capas (Frontend web/mobile, API, BD)
2. `arquitectura_base_datos.png` — Esquema relacional simplificado (tablas principales)
3. `flujo_conciliacion.png` — Diagrama de flujo del motor de conciliación

**Generación:**
- Usar Excalidraw, Draw.io, o Figma
- Exportar como PNG con fondo blanco
- Incluir leyenda/labels legibles

**Tamaño:** ~500 KB (3 × 150-200 KB)

---

## 4. ARCHIVO ÍNDICE

**Crear archivo `INDICE_CONTENIDO.txt` en raíz del ZIP:**

```
EXPEDIENTE DE REGISTRO DE OBRA DE SOFTWARE
DNDA 2026 — Julieta Arrazate

Sistema Integral de Gestión Financiera, Contable y Empresarial
Versión: v3.12 | Junio 2026

═══════════════════════════════════════════════════════

CONTENIDO DEL PAQUETE:

1. SOFTWARE/
   - Código fuente íntegro (backend, frontend, mobile)
   - Base de datos: 9 migraciones Alembic
   - Tests: 156 tests automatizados
   - Documentación de registro: 29 .md

2. DOCUMENTACION/
   - 8-9 PDFs en español (memoria, inventario, etc.)

3. CAPTURAS/
   - 27 screenshots del sistema funcionando

4. DIAGRAMAS/
   - 3-4 diagramas de arquitectura

═══════════════════════════════════════════════════════

INSTRUCCIONES:

1. Leer: SOFTWARE/REGISTRO_OBRA_SOFTWARE/DNDA_CHECKLIST_FINAL.md
2. Compilar backend: cd SOFTWARE/backend && pip install -r requirements.txt
3. Compilar frontend: cd SOFTWARE/frontend && npm install && npm run build
4. Presentar PDFs de DOCUMENTACION/ a la DNDA

═══════════════════════════════════════════════════════

AUTORA: Julieta Arrazate <julietaarrazate@gmail.com>
FECHA: Junio 2026
VERSIÓN: v3.12
```

---

## 5. CHECKLIST DE EMPAQUETAMIENTO

- [ ] SOFTWARE/backend/ contiene código completo (sin venv, __pycache__, .env real)
- [ ] SOFTWARE/frontend/ contiene código completo (sin node_modules, dist, .env real)
- [ ] SOFTWARE/mobile/ contiene código completo (sin node_modules)
- [ ] SOFTWARE/REGISTRO_OBRA_SOFTWARE/ contiene 29 .md
- [ ] SOFTWARE/ contiene README.md, CLAUDE.md (opcional), .gitignore
- [ ] DOCUMENTACION/ contiene 8-9 PDFs en español
- [ ] CAPTURAS/ contiene 27 PNG nombrados 01_*.png a 27_*.png
- [ ] DIAGRAMAS/ contiene 3-4 PNG de arquitectura
- [ ] INDICE_CONTENIDO.txt existe en raíz
- [ ] Tamaño total < 50 MB (recomendado < 100 MB)
- [ ] Ningún archivo .env con credenciales reales
- [ ] Ningún archivo .pem, .key, credenciales
- [ ] Ningún archivo crear_datos_prueba.py (contiene ruta personal)
- [ ] Todos los PDFs están en español
- [ ] Todos los PDFs tienen encoding UTF-8 correcto (acentos)

---

## 6. CREACIÓN DEL ZIP

**Desde línea de comandos (Linux/Mac):**
```bash
cd /home/user
zip -r EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip \
  conciliacion-bancaria/backend \
  conciliacion-bancaria/frontend \
  conciliacion-bancaria/mobile \
  conciliacion-bancaria/REGISTRO_OBRA_SOFTWARE \
  conciliacion-bancaria/README.md \
  conciliacion-bancaria/CLAUDE.md \
  conciliacion-bancaria/.gitignore \
  DOCUMENTACION/ \
  CAPTURAS/ \
  DIAGRAMAS/ \
  INDICE_CONTENIDO.txt \
  -x "*/node_modules/*" "*/__pycache__/*" "*/.venv/*" "*/dist/*" "*/.git/*"
```

**O desde Windows/Mac (GUI):**
1. Crear carpeta `EXPEDIENTE_DNDA_ARRAZATE_2026_06/`
2. Copiar carpetas: SOFTWARE/, DOCUMENTACION/, CAPTURAS/, DIAGRAMAS/
3. Copiar archivo: INDICE_CONTENIDO.txt
4. Click derecho → Comprimir/Zip → "EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip"

---

## 7. VALIDACIÓN FINAL DEL ZIP

**Verificar:**
```bash
unzip -l EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip | head -50
du -sh EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip
unzip -t EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip  # Test integridad
```

**Esperado:**
- Archivos: ~400-500 archivos
- Tamaño: ~26-30 MB
- Integridad: OK (sin errores)

---

*Documento de estructura ZIP para expediente DNDA — Julieta Arrazate — Junio 2026*
