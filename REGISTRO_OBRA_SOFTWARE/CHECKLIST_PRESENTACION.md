# CHECKLIST DE PRESENTACIÓN
## Lista de verificación paso a paso

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## FASE 1 — PREPARACIÓN DEL EXPEDIENTE (hacer antes de salir de casa)

### 1.1 Completar campos obligatorios

- [ ] **DNI** — agregar en `EXPEDIENTE_FINAL.md` sección "Declaración de Presentación"
- [ ] **Contexto laboral/contractual** — completar en `EVIDENCIA_AUTORIA.md` sección 9, campo 3
  - Ejemplo: "La obra fue desarrollada con equipos propios, fuera de toda relación de dependencia laboral y sin acuerdo de confidencialidad ni cesión de derechos con terceros."
- [ ] **(Opcional)** Fecha exacta de inicio del desarrollo, si hay evidencia previa al repositorio git

### 1.2 Corrección menor detectada en auditoría

- [ ] En `MEMORIA_DESCRIPTIVA.md` línea 121: cambiar "5 roles" por "6 roles"

### 1.3 Verificar que el campo `[COMPLETAR]` quedó vacío en todos los demás documentos
```bash
grep -r "\[COMPLETAR\]" REGISTRO_OBRA_SOFTWARE/
```
Solo debe aparecer en `EVIDENCIA_AUTORIA.md` (los 3 que se completaron arriba).

---

## FASE 2 — DOCUMENTOS A EXPORTAR A PDF

Exportar los siguientes archivos de Markdown a PDF (con renderizado de tablas y headers):

| Documento | Prioridad | Herramienta sugerida |
|---|---|---|
| `MEMORIA_DESCRIPTIVA.md` | **IMPRESCINDIBLE** | Pandoc, Typora, VS Code + extensión |
| `EVIDENCIA_AUTORIA.md` | **IMPRESCINDIBLE** | Pandoc, Typora |
| `INVENTARIO_TECNICO.md` | **IMPRESCINDIBLE** | Pandoc, Typora |
| `ACTIVOS_PI.md` | Recomendado | Pandoc, Typora |
| `DOCUMENTACION_TECNICA.md` | Recomendado | Pandoc, Typora |
| `MANUAL_FUNCIONAL.md` | Recomendado | Pandoc, Typora |
| `EXPEDIENTE_FINAL.md` | Recomendado | Pandoc, Typora |
| `RESUMEN_EJECUTIVO.md` | Complementario | Pandoc, Typora |
| `MODULOS_DEL_SISTEMA.md` | Complementario | Pandoc, Typora |

**Comando rápido con Pandoc (si está instalado):**
```bash
cd REGISTRO_OBRA_SOFTWARE
for f in MEMORIA_DESCRIPTIVA EVIDENCIA_AUTORIA INVENTARIO_TECNICO ACTIVOS_PI; do
  pandoc ${f}.md -o ${f}.pdf --pdf-engine=wkhtmltopdf
done
```

---

## FASE 3 — EXTRACTO DE CÓDIGO FUENTE

- [ ] Imprimir o exportar a PDF el archivo `backend/app/services/conciliacion.py` (motor de conciliación — algoritmo central)
- [ ] Imprimir o exportar a PDF el archivo `backend/app/services/motor_contable.py` (asientos automáticos)
- [ ] *(Opcional)* Exportar `backend/app/services/aprendizaje.py`
- [ ] Los PDFs de código deben incluir: nombre del archivo, numeración de líneas

**Nota DNDA:** la mayoría de organismos requiere depositar una porción representativa del código, no el código completo. 20-50 páginas impresas es suficiente.

---

## FASE 4 — CAPTURAS DE PANTALLA

- [ ] Tomar las capturas listadas en `MATERIAL_COMPLEMENTARIO.md` (prioridad Alta primero)
- [ ] Nombrar los archivos según la nomenclatura indicada en ese documento
- [ ] Guardar en carpeta `CAPTURAS/`
- [ ] Resolución mínima: 1280×720 px
- [ ] Formato: PNG o JPG
- [ ] Impresión: si el organismo las requiere en papel, imprimir en color

---

## FASE 5 — DIAGRAMAS

- [ ] Crear o exportar Diagrama de Arquitectura (ver especificación en `MATERIAL_COMPLEMENTARIO.md`)
- [ ] Crear o exportar Diagrama de Base de Datos (entidad-relación simplificado)
- [ ] Crear o exportar Diagrama de Módulos
- [ ] Guardar en carpeta `DIAGRAMAS/`
- [ ] Formato: PNG o PDF

---

## FASE 6 — HISTORIAL GIT

- [ ] Exportar el historial git a texto plano:
```bash
git log --format="%H | %ad | %an | %s" --date=short > HISTORIAL_GIT.txt
```
- [ ] Verificar que el archivo incluye el commit de documentación `b846c17`
- [ ] Guardar en la raíz del ZIP o en la carpeta `DOCUMENTACION/`

---

## FASE 7 — ARMADO DEL ZIP

- [ ] Crear el ZIP según estructura definida en `PAQUETE_FINAL.md`
- [ ] Verificar que NO hay `.env`, `.venv`, `node_modules`, `__pycache__`, `dist`, credenciales
- [ ] Calcular el hash SHA-256 del ZIP para registro posterior:
```bash
sha256sum REGISTRO_OBRA_SOFTWARE_v3.12.zip
```
- [ ] Guardar el hash en un archivo de texto separado como respaldo

---

## FASE 8 — CREAR EL TAG DE VERSIÓN EN GIT

- [ ] Mergear PR #111 a `main`
- [ ] Crear el tag anotado:
```bash
git checkout main && git pull origin main
git tag -a v3.12-registro -m "Registro de obra — Julieta Arrazate — Junio 2026"
git push origin v3.12-registro
```
- [ ] Verificar el tag: `git show v3.12-registro`
- [ ] Guardar el hash completo del tag (output de `git show`)

---

## FASE 9 — PRESENTACIÓN ANTE EL ORGANISMO

- [ ] Completar formulario del organismo (DNDA o equivalente)
- [ ] Abonar el arancel correspondiente
- [ ] Presentar:
  - Formulario completo
  - Documentos PDF del expediente (Memoria Descriptiva obligatoria)
  - Extracto de código fuente impreso o en soporte digital
  - ZIP con el código fuente completo (en CD/DVD o pendrive, según lo que acepte el organismo)
  - Capturas de pantalla (impresas o en soporte digital)
- [ ] Guardar el número de trámite / número de expediente
- [ ] Guardar el comprobante de presentación

---

## FASE 10 — RESPALDO Y CONSERVACIÓN

- [ ] Guardar copia del ZIP en al menos 2 ubicaciones (ej: disco externo + nube)
- [ ] Guardar los PDFs del expediente
- [ ] Guardar el hash SHA-256 del ZIP
- [ ] Guardar el hash del commit git (`b846c1753aac4363321311537f74a47fe96569c4`)
- [ ] Guardar el comprobante del organismo de registro
- [ ] Anotar el número de certificado cuando sea emitido

---

## RESUMEN RÁPIDO

| Estado | Acción |
|---|---|
| Completar manualmente | DNI + campo laboral en EVIDENCIA_AUTORIA |
| Corregir | "5 roles" → "6 roles" en MEMORIA_DESCRIPTIVA |
| Exportar a PDF | 9 documentos Markdown |
| Capturar | Pantallas según MATERIAL_COMPLEMENTARIO |
| Comprimir | ZIP según PAQUETE_FINAL |
| Git | Crear tag `v3.12-registro` post-merge |
| Presentar | Ante DNDA con formulario, PDF y código |

---

*Checklist elaborado para expediente de registro de obra de software — Julieta Arrazate — Junio 2026*
