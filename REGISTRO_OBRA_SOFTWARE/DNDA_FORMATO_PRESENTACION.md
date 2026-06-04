# FORMATO DE PRESENTACIÓN EN EL PORTAL DNDA
## Adaptación del expediente a las restricciones del sistema de carga

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12

---

## 0. DOS CANALES DE PRESENTACIÓN (IMPORTANTE)

El trámite de registro de software ante la DNDA suele tener **dos vías
distintas**, y conviene no mezclarlas:

| Canal | Para qué sirve | Formato | Documento de referencia |
|---|---|---|---|
| **A. Portal online** | Formulario + documentación + carátula + (opcional) código en PDF | Archivos sueltos ≤ 20 MB, extensiones permitidas (pdf, doc, xlsx, png, jpg, html…) | **Este documento** |
| **B. Depósito del código fuente** | Entrega del código fuente completo de la obra | Suele admitir **ZIP** (en soporte físico CD/DVD/USB, o canal de depósito separado) | `DNDA_ESTRUCTURA_ZIP.md` |

> La restricción de 20 MB y "sin ZIP" aplica al **Canal A (portal online)**. El
> **ZIP del Canal B** sigue siendo válido para el depósito del código fuente por
> el medio que indique la DNDA (a menudo soporte físico o un formulario de
> depósito aparte). **Confirmar con la DNDA cuál es el medio del Canal B.**

Por eso se conservan ambos documentos:
- `DNDA_ESTRUCTURA_ZIP.md` → arma el ZIP del código (Canal B).
- `DNDA_FORMATO_PRESENTACION.md` (este) → arma los archivos del portal (Canal A).

Si finalmente la DNDA pidiera **todo por el portal** (Canal A únicamente),
entonces el código fuente se sube como PDF según la sección 2/3 de este
documento, y el ZIP queda como respaldo interno.

---

## 1. RESTRICCIONES DEL PORTAL ONLINE — CANAL A (CONFIRMADAS)

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

## 2. LISTA FINAL DE ARCHIVOS A SUBIR

Todos los archivos cumplen extensión permitida y < 20 MB.

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

### Grupo 2 — Código fuente como PDF (lo que reemplaza al ZIP)

| # | Archivo a subir | Contenido | Tamaño aprox. |
|---|---|---|---|
| 9 | `CODIGO_FUENTE_BACKEND.pdf` | Todo `/backend/app` (modelos, routers, servicios) + migraciones | 5-12 MB |
| 10 | `CODIGO_FUENTE_FRONTEND.pdf` | Todo `/frontend/src` (páginas, componentes, stores) | 5-12 MB |
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

### Grupo 4 — Formulario y carátula (PDF/DOC)

| # | Archivo a subir | Contenido |
|---|---|---|
| 13 | `FORMULARIO_DNDA.pdf` | Formulario oficial completado y firmado |
| 14 | `EXPEDIENTE_FINAL.pdf` (carátula) | Portada e índice del expediente (EXPEDIENTE_FINAL.md → PDF) |
| 15 | `DNI_ARRAZATE.pdf` o `.jpg` | Copia/foto del DNI |

**Total de archivos a subir:** ~15 (todos < 20 MB, extensiones permitidas).

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

## 6. ORDEN SUGERIDO DE CARGA EN EL PORTAL

1. `FORMULARIO_DNDA.pdf` (formulario oficial)
2. `EXPEDIENTE_FINAL.pdf` (carátula/índice)
3. `MEMORIA_DESCRIPTIVA.pdf`
4. `EVIDENCIA_AUTORIA.pdf`
5. `INVENTARIO_TECNICO.pdf`
6. `DOCUMENTACION_TECNICA.pdf`
7. `MANUAL_FUNCIONAL.pdf`
8. `MODULOS_DEL_SISTEMA.pdf`
9. `ACTIVOS_PI.pdf`
10. `RESUMEN_EJECUTIVO.pdf`
11. `CODIGO_FUENTE_BACKEND.pdf`
12. `CODIGO_FUENTE_FRONTEND.pdf`
13. `CODIGO_FUENTE_MOBILE.pdf`
14. `CAPTURAS.pdf`
15. `DNI_ARRAZATE.pdf`

---

## 7. RELACIÓN CON DNDA_ESTRUCTURA_ZIP.md

`DNDA_ESTRUCTURA_ZIP.md` describe el **ZIP del Canal B** (depósito del código
fuente completo). Ese ZIP **sigue siendo válido** para entregar el código por el
medio que indique la DNDA (soporte físico CD/DVD/USB o canal de depósito
aparte).

- **Canal A (portal online, ≤ 20 MB):** usar los archivos individuales de la
  sección 2 de este documento. Aquí el código va como **PDF**, no como ZIP.
- **Canal B (depósito de código):** usar el **ZIP** de `DNDA_ESTRUCTURA_ZIP.md`.

Ambos describen el mismo expediente; cambia el envoltorio según el canal.
**Acción previa:** confirmar con la DNDA si el código se deposita por soporte
físico (ZIP) o si debe ir todo por el portal (entonces, código en PDF).

---

## 8. CHECKLIST DE FORMATO

- [ ] Los 8 PDFs de documentación están generados y en español
- [ ] Generado `CODIGO_FUENTE_BACKEND.pdf` (< 20 MB, legible, con nombres de archivo)
- [ ] Generado `CODIGO_FUENTE_FRONTEND.pdf` (< 20 MB)
- [ ] Generado `CODIGO_FUENTE_MOBILE.pdf` (< 20 MB)
- [ ] Consolidado `CAPTURAS.pdf` con las 27 capturas (< 20 MB) — o 27 PNG sueltos
- [ ] `EXPEDIENTE_FINAL.pdf` (carátula) generado
- [ ] `FORMULARIO_DNDA.pdf` completado y firmado
- [ ] `DNI_ARRAZATE.pdf`/`.jpg` listo
- [ ] Cada archivo verificado < 20 MB
- [ ] Cada archivo con extensión permitida (pdf/png/jpg/html)
- [ ] Ningún archivo `.zip`, `.py`, `.ts`, `.md`, `.txt` en la carga

---

*Documento de formato de presentación para portal DNDA — Julieta Arrazate — Junio 2026*
