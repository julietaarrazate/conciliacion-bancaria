# FORMATO DE PRESENTACIÓN EN EL PORTAL DNDA
## Adaptación del expediente a las restricciones del sistema de carga

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12  
**Tipo de trámite DNDA:** Inscripción de obra publicada — Software

---

## 0. PROCESO OFICIAL — OPCIÓN DIGITAL (DOS PASOS)

La opción **digital** seleccionada en el portal tiene **dos pasos distintos**:

### PASO 1 — Portal online (completar HOY)

Subir en el portal:
1. **Datos del trámite** (formulario online completo)
2. **Comprobante de pago del trámite** — $3.800 (obligatorio)
3. **Comprobante de pago de Tasa** — 0,2% del valor del ejemplar, mínimo $4,11 (obligatorio)
4. **Documentación técnica** — PDFs de memoria, inventario, capturas, etc.

Al finalizar el Paso 1, la DNDA genera automáticamente un **número de
Expediente Electrónico (carátula)**.

### PASO 2 — Carga digital del código (luego de recibir comunicación de DNDA)

Una vez iniciado el expediente, la DNDA envía una **comunicación por email**
detallando el procedimiento para la **carga digital de la obra** (el código
fuente).

> **La DNDA aceptó que el código fuente se suba de modo cifrado o encriptado**
> (Disposición 2-E/2016). El titular es responsable de proveer las herramientas
> de descifrado si una autoridad legitimada lo requiere.

El **ZIP de `DNDA_ESTRUCTURA_ZIP.md`** está preparado para este Paso 2. Puede
enviarse tal cual o cifrado con contraseña (`zip -e`).

---

| Paso | Cuándo | Qué se entrega | Formato |
|---|---|---|---|
| **1 — Portal** | Inmediatamente | Formulario + pagos + documentación | Archivos sueltos ≤ 20 MB, extensiones permitidas |
| **2 — Código** | Tras comunicación DNDA | Código fuente completo | Según instrucciones DNDA (ZIP / plataforma / etc.) |

---

## 0.1 PAGOS OBLIGATORIOS (previos al inicio)

| Pago | Monto | Cuándo |
|---|---|---|
| Arancel del trámite | **$3.800** | Antes de iniciar el expediente |
| Tasa sobre el ejemplar | **0,2% del valor de la obra** (mínimo $4,11) | Antes de iniciar el expediente |

> Guardar ambos comprobantes en PDF/JPG listos para subir al portal.

---

## 1. RESTRICCIONES DEL PORTAL ONLINE — PASO 1 (CONFIRMADAS)

El sistema de carga online de la DNDA acepta:

| Restricción | Valor |
|---|---|
| **Tamaño máximo** | 20 MB por archivo |
| **Extensiones permitidas** | pdf, doc, docx, xlsx, jpg, jpeg, png, bmp, gif, tiff, tif, html, dwf |

### Implicancias críticas

1. **NO se acepta ZIP** → el plan de "un único ZIP" queda descartado. Se suben
   archivos individuales.
2. **NO se aceptan archivos de código** (`.py`, `.ts`, `.tsx`, `.sql`) → el
   código fuente debe convertirse a **PDF** o **HTML** (ambos permitidos).
3. **NO se aceptan `.md` ni `.txt`** → toda la documentación de registro debe
   ir como **PDF** (ya estaba previsto: 8 PDFs).
4. **Límite de 20 MB por archivo** → cada PDF/imagen debe quedar por debajo de
   ese tamaño. Si el PDF de código supera 20 MB, se parte en varios.

> El cambio más importante respecto del plan anterior: el **código fuente se
> presenta como PDF/HTML**, no como archivos sueltos ni ZIP. Esto es lo habitual
> en la DNDA: se deposita el código impreso/PDF, no los archivos ejecutables.

---

## 2. LISTA FINAL DE ARCHIVOS A SUBIR — PASO 1 (portal)

Todos los archivos cumplen extensión permitida y < 20 MB.

### Grupo 0 — Comprobantes de pago (OBLIGATORIOS)

| # | Archivo a subir | Descripción |
|---|---|---|
| 0a | `COMPROBANTE_PAGO_TRAMITE.pdf` o `.jpg` | Comprobante de pago del trámite ($3.800) |
| 0b | `COMPROBANTE_PAGO_TASA.pdf` o `.jpg` | Comprobante de pago de la tasa (0,2% valor ejemplar, mín. $4,11) |

> Sin estos dos comprobantes la DNDA no acepta el expediente.

### Grupo 1 — Documentación jurídica y técnica (PDF)

| # | Archivo a subir | Origen | Tamaño aprox. |
|---|---|---|---|
| 1 | `MEMORIA_DESCRIPTIVA.pdf` | REGISTRO_OBRA_SOFTWARE/MEMORIA_DESCRIPTIVA.md | < 1 MB |
| 2 | `EVIDENCIA_AUTORIA.pdf` | EVIDENCIA_AUTORIA.md | < 1 MB |
| 3 | `INVENTARIO_TECNICO.pdf` | INVENTARIO_TECNICO.md | < 1 MB |
| 4 | `DOCUMENTACION_TECNICA.pdf` | DOCUMENTACION_TECNICA.md | < 1 MB |
| 5 | `MANUAL_FUNCIONAL.pdf` | MANUAL_FUNCIONAL.md | < 1 MB |
| 6 | `ACTIVOS_PI.pdf` | ACTIVOS_PI.md | < 1 MB |
| 7 | `RESUMEN_EJECUTIVO.pdf` | RESUMEN_EJECUTIVO.md | < 1 MB |
| 8 | `MODULOS_DEL_SISTEMA.pdf` | MODULOS_DEL_SISTEMA.md | < 1 MB |

> Estos 8 PDFs ya fueron generados (en español, con acentos correctos) y se
> conservan en el repositorio separado de documentación.

### Grupo 2 — Código fuente (⚠️ va en el PASO 2, no en el portal inicial)

> El código fuente **NO se sube junto con la documentación del Paso 1**. La DNDA
> envía una comunicación separada indicando cómo cargarlo digitalmente. Ver
> `DNDA_ESTRUCTURA_ZIP.md` para la estructura del paquete de código.

**Para el Paso 2 (cuando DNDA lo solicite):**

| Archivo | Contenido | Tamaño aprox. |
|---|---|---|
| `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip` | Código completo (backend + frontend + mobile) | ~27-32 MB |

> La DNDA acepta el código cifrado/encriptado (Disposición 2-E/2016). Opción:
> `zip -e EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip [archivos]` (con contraseña).

**Si la DNDA pide código en PDF** (alternativa al ZIP):

| # | Archivo | Contenido | Tamaño aprox. |
|---|---|---|---|
| 9 | `CODIGO_FUENTE_BACKEND.pdf` | Todo `/backend/app` + migraciones | 5-12 MB |
| 10 | `CODIGO_FUENTE_FRONTEND.pdf` | Todo `/frontend/src` | 5-12 MB |
| 11 | `CODIGO_FUENTE_MOBILE.pdf` | Todo `/mobile/src` | 1-3 MB |

> Si alguno supera 20 MB, partirlo (ej. `CODIGO_FUENTE_BACKEND_1.pdf` y `_2.pdf`).
> Cada PDF lleva encabezado con el nombre del archivo y numeración de líneas.

### Grupo 3 — Evidencia visual (imágenes o PDF)

| # | Archivo a subir | Contenido | Tamaño aprox. |
|---|---|---|---|
| 12 | `CAPTURAS.pdf` | Las 27 capturas en un único PDF (1 por página, con epígrafe) | 8-15 MB |

> **Alternativa:** subir las 27 capturas como `.png` individuales (extensión
> permitida). Se recomienda consolidarlas en **un solo PDF** para reducir la
> cantidad de archivos y mantener el orden y los epígrafes.

### Grupo 4 — Comprobantes de pago + DNI (OBLIGATORIOS)

| # | Archivo a subir | Contenido |
|---|---|---|
| 13 | `COMPROBANTE_PAGO_TRAMITE.pdf`/`.jpg` | Pago del trámite ($3.800) |
| 14 | `COMPROBANTE_PAGO_TASA.pdf`/`.jpg` | Pago de tasa (0,2%, mín. $4,11) |
| 15 | `DNI_ARRAZATE.pdf` o `.jpg` | Copia/foto del DNI |

> Los datos del formulario se completan directamente en el portal (no es un
> archivo adjunto); la carátula/índice del expediente la genera el portal al
> asignar el número de expediente electrónico.

**Total de archivos a subir en Paso 1:** ~15 (todos < 20 MB, extensiones permitidas).

---

## 3. CÓMO GENERAR LOS PDF DE CÓDIGO FUENTE

El código fuente debe quedar legible, con nombre de archivo y numeración de
líneas. Tres opciones:

### Opción A — `enscript` + `ps2pdf` (Linux/Mac, recomendada)

```bash
cd /home/user/conciliacion-bancaria

# Backend (Python)
find backend/app backend/alembic/versions -name "*.py" | sort > /tmp/lista_back.txt
enscript --line-numbers --header='$n|Cuadra v3.12|Pagina $% de $=' \
  -p /tmp/backend.ps $(cat /tmp/lista_back.txt)
ps2pdf /tmp/backend.ps CODIGO_FUENTE_BACKEND.pdf

# Frontend (TypeScript/TSX)
find frontend/src -name "*.ts" -o -name "*.tsx" | sort > /tmp/lista_front.txt
enscript --line-numbers --header='$n|Cuadra v3.12|Pagina $% de $=' \
  -p /tmp/frontend.ps $(cat /tmp/lista_front.txt)
ps2pdf /tmp/frontend.ps CODIGO_FUENTE_FRONTEND.pdf

# Mobile
find mobile/src -name "*.ts" -o -name "*.tsx" | sort > /tmp/lista_mobile.txt
enscript --line-numbers --header='$n|Cuadra v3.12|Pagina $% de $=' \
  -p /tmp/mobile.ps $(cat /tmp/lista_mobile.txt)
ps2pdf /tmp/mobile.ps CODIGO_FUENTE_MOBILE.pdf
```

### Opción B — HTML (extensión permitida, sin instalar nada)

Generar un `.html` por componente con todo el código embebido y subirlo
directamente (el portal acepta `html`). Útil si no hay `enscript`/`ps2pdf`.

### Opción C — VS Code

Extensión "PDF" o "Print" → abrir cada carpeta, "Print to PDF" con números de
línea activados. Más manual pero sin dependencias.

> **Verificar tras generar:** que el PDF abra bien, que el texto sea legible,
> que aparezca el nombre de cada archivo y que el tamaño sea < 20 MB.

---

## 4. CÓMO CONSOLIDAR LAS 27 CAPTURAS EN UN PDF

### Opción A — desde las imágenes (Linux/Mac con ImageMagick)

```bash
cd /home/user/CAPTURAS
# Asegurar orden por nombre (01_, 02_, ... 27_)
convert $(ls -1 *.png | sort) CAPTURAS.pdf
# Verificar tamaño; si supera 20 MB, bajar calidad:
convert $(ls -1 *.png | sort) -resize 1600x -quality 85 CAPTURAS.pdf
```

### Opción B — Word/LibreOffice/Google Docs

Insertar las 27 imágenes en orden, una por página, con un epígrafe debajo
(usar la columna "Contenido evidenciado" de `DNDA_CAPTURAS.md`), exportar a PDF.

---

## 5. GESTIÓN DEL LÍMITE DE 20 MB

| Si un archivo supera 20 MB | Solución |
|---|---|
| PDF de código muy grande | Partir por capa o por carpeta (backend_1, backend_2) |
| PDF de capturas pesado | Reducir resolución a 1600 px y calidad 85% |
| Imágenes PNG individuales grandes | Convertir a JPG (también permitido) calidad 85% |

**Estimación total del expediente:** ~30-45 MB repartidos en ~15 archivos
individuales, ninguno por encima de 20 MB. Como la carga es por archivo, el
total no es un problema mientras cada archivo cumpla el límite.

---

## 6. ORDEN SUGERIDO DE CARGA EN EL PORTAL — PASO 1

**Primero completar el formulario online, luego adjuntar:**

1. `COMPROBANTE_PAGO_TRAMITE.pdf` (obligatorio)
2. `COMPROBANTE_PAGO_TASA.pdf` (obligatorio)
3. `DNI_ARRAZATE.pdf` o `.jpg`
4. `MEMORIA_DESCRIPTIVA.pdf`
5. `EVIDENCIA_AUTORIA.pdf`
6. `INVENTARIO_TECNICO.pdf`
7. `DOCUMENTACION_TECNICA.pdf`
8. `MANUAL_FUNCIONAL.pdf`
9. `MODULOS_DEL_SISTEMA.pdf`
10. `ACTIVOS_PI.pdf`
11. `RESUMEN_EJECUTIVO.pdf`
12. `CAPTURAS.pdf`

> El código (Paso 2) se carga **después** de recibir la comunicación de la DNDA.
> Ver `DNDA_ESTRUCTURA_ZIP.md` para el paquete de código.

---

## 7. RELACIÓN CON DNDA_ESTRUCTURA_ZIP.md — PASO 2

`DNDA_ESTRUCTURA_ZIP.md` describe el **ZIP del código fuente completo**. Este
ZIP **no se sube en el Paso 1** (portal de documentación). Se usa en el
**Paso 2** cuando la DNDA comunica el procedimiento de carga digital.

Resumen del flujo completo:

```
HOY                             LUEGO (tras email DNDA)
─────────────────────────────   ──────────────────────────────────
Portal online                   Plataforma / canal indicado por DNDA
  └── Formulario (datos obra)     └── ZIP con código fuente completo
  └── Comprobante pago $3800           (puede ir cifrado si se prefiere)
  └── Comprobante pago tasa
  └── DNI
  └── 8 PDFs documentación
  └── CAPTURAS.pdf (27 pantallas)
         ↓
  Expediente electrónico generado
         ↓
  Email de DNDA con instrucciones
```

**Silencio positivo:** transcurridos 60 días hábiles desde que se acreditó el
cumplimiento de todas las condiciones, sin respuesta de la DNDA, el registro
se considera otorgado (Art. 10 inciso b, Ley 19.549).

---

## 8. CHECKLIST DE FORMATO

### Paso 1 — Portal (hacer primero)
- [ ] Pagar arancel del trámite ($3.800) y guardar comprobante
- [ ] Pagar tasa (0,2% del valor declarado de la obra) y guardar comprobante
- [ ] Comprobante de pago tramite en PDF/JPG listo
- [ ] Comprobante de pago tasa en PDF/JPG listo
- [ ] DNI en PDF/JPG listo
- [ ] Los 8 PDFs de documentación están generados y en español
- [ ] Consolidado `CAPTURAS.pdf` con las 27 capturas (< 20 MB) — o 27 PNG sueltos
- [ ] Cada archivo verificado < 20 MB
- [ ] Cada archivo con extensión permitida (pdf/png/jpg/html)
- [ ] Ningún archivo `.zip`, `.py`, `.ts`, `.md`, `.txt` en el Paso 1

### Paso 2 — Código (esperar email de DNDA)
- [ ] ZIP `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip` preparado (ver `DNDA_ESTRUCTURA_ZIP.md`)
- [ ] ZIP verificado sin archivos sensibles (`.env`, `node_modules`, `__pycache__`)
- [ ] (Opcional) ZIP cifrado con contraseña si se prefiere privacidad del código
- [ ] Clave de cifrado guardada de forma segura si se optó por cifrar

---

*Documento de formato de presentación para portal DNDA — Julieta Arrazate — Junio 2026*
