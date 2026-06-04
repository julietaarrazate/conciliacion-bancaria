# CHECKLIST FINAL DE PRESENTACIÓN
## Pasos operativos para completar y presentar ante DNDA

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Obra:** Sistema Integral de Gestión Financiera, Contable y Empresarial  
**Versión:** v3.12

---

## 0. VERIFICACIÓN PREVIA

Antes de comenzar, verificar que tienes:

- [ ] ✓ Acceso al repositorio `/home/user/conciliacion-bancaria`
- [ ] ✓ Todos los archivos .md en `REGISTRO_OBRA_SOFTWARE/` (29 archivos)
- [ ] ✓ Las 8 PDFs de documentación generadas (MEMORIA, INVENTARIO, etc.)
- [ ] ✓ Acceso a screenshot del sistema funcionando
- [ ] ✓ Acceso a crear diagramas (Excalidraw, Draw.io, Figma, PowerPoint)
- [ ] ✓ Tiempo estimado: 3-4 horas

### 0.1 Tipo de trámite — información oficial

- **Trámite:** Inscripción de obra publicada — Software
- **Opción elegida:** Digital (el código se sube DESPUÉS de email de DNDA)
- **Pagos obligatorios previos al inicio:**
  - Arancel del trámite: **$3.800**
  - Tasa: **0,2% del valor declarado** de la obra (mínimo $4,11)
- **Silencio positivo:** 60 días hábiles desde acreditación de condiciones

### 0.2 Pagos previos (hacer antes del Paso 1)

- [ ] Pagar arancel del trámite: $3.800 (site.dnda.gov.ar o PagoMisCuentas)
- [ ] Guardar comprobante como PDF/JPG (`COMPROBANTE_PAGO_TRAMITE.pdf`)
- [ ] Pagar tasa: 0,2% del valor declarado de la obra (mínimo $4,11)
- [ ] Guardar comprobante como PDF/JPG (`COMPROBANTE_PAGO_TASA.pdf`)

---

## FASE 1: CAPTURAS DE PANTALLA — ✓ COMPLETADA

Se capturaron **27 pantallas** del sistema en producción real (organización
Caneland SA, usuario Superadmin Julieta Arrazate). El detalle completo, la
cobertura por módulo y el valor probatorio están en `DNDA_CAPTURAS.md`.

### 1.1 Capturas tomadas (27) — cobertura 18/18 módulos

- [x] 01_resumen_ejecutivo.png — Resumen ejecutivo
- [x] 02_resumen_dark.png — Resumen (modo oscuro)
- [x] 03_conciliar_dashboard.png — Conciliar transferencias (precisión 98%)
- [x] 04_extractos_archivo.png — Archivo de extractos
- [x] 05_movimientos_extracto.png — Movimientos del extracto (2.455 movs)
- [x] 06_conciliaciones.png — Conciliaciones ($211.689.798)
- [x] 07_historial.png — Historial (46 planillas, 96%)
- [x] 08_clientes.png — Clientes (cartera Caneland SA)
- [x] 09_cheques_listado.png — Cheques (stats + tabs)
- [x] 10_cheques_editar.png — Editar cheque (comisión auto + L/I)
- [x] 11_pagos_nuevo.png — Nuevo pago
- [x] 12_pagos_historial.png — Pagos (historial)
- [x] 13_caja_arqueo.png — Caja (arqueo diario)
- [x] 14_contabilidad_modulos.png — Contabilidad (libro diario 903 asientos)
- [x] 15_plan_cuentas_activo_pasivo.png — Plan de cuentas (Activo/Pasivo)
- [x] 16_plan_cuentas_resultado.png — Plan de cuentas (Resultado)
- [x] 17_cuentas_corrientes.png — Cuentas corrientes
- [x] 18_liquidaciones.png — Liquidaciones
- [x] 19_flujo_caja.png — Flujo de caja
- [x] 20_flujo_caja_detalle.png — Flujo de caja (detalle)
- [x] 21_flujo_caja_6meses.png — Flujo de caja (6 meses)
- [x] 22_auditoria_inteligencia.png — Auditoría/Inteligencia (95.9%)
- [x] 23_auditoria_log.png — Auditoría (log JSON)
- [x] 24_asistente_ia.png — Asistente IA Cuadra
- [x] 25_papelera.png — Papelera + backup automático
- [x] 26_perfil_datos.png — Perfil (datos de acceso)
- [x] 27_perfil_seguridad_ia.png — Perfil (PIN, push, Gemini IA)

**Total:** 27 capturas ✓

### 1.2 Verificar calidad de capturas

- [x] Las 27 capturas tienen nombres correctos (01 a 27)
- [x] Todas están en PNG
- [ ] Renombrar archivos según la convención `NN_descripcion.png` (si aún no se hizo)
- [ ] (Opcional) Difuminar nombres de clientes / montos si se prefiere mayor reserva
- [x] Texto legible
- [x] Demuestran funcionalidad real con datos de producción

**Pendiente manual:** mover las 27 imágenes a la carpeta `CAPTURAS/` con los
nombres de la lista anterior.

---

## FASE 2: DIAGRAMAS DE ARQUITECTURA (0.5 horas)

### 2.1 Crear diagrama: Arquitectura 3 capas

**Archivo:** `arquitectura_3_capas.png`

**Contenido a dibujar:**
```
Frontend Web (React PWA)         Frontend Móvil (React Native)
         ↓                                  ↓
         └────────── API REST (FastAPI) ──────────┘
                          ↓
                  PostgreSQL (Neon)
```

**Herramientas:** Excalidraw, Draw.io, Figma, o PowerPoint

- [ ] Crear el diagrama
- [ ] Exportar como PNG (fondo blanco)
- [ ] Guardar en `/home/user/DIAGRAMAS/`

**Tiempo:** ~15 minutos

### 2.2 Crear diagrama: Modelo de datos (opcional pero recomendado)

**Archivo:** `arquitectura_base_datos.png`

**Contenido:**
- Tablas principales: users, organizaciones, clientes, extractos, planillas, cheques, egresos, asientos
- Relaciones FKs (flechas)

- [ ] Crear diagrama entidad-relación simplificado
- [ ] Incluir tabla AuditoriaLog (demostración de auditoría)
- [ ] Exportar PNG
- [ ] Guardar en `/home/user/DIAGRAMAS/`

**Tiempo:** ~10 minutos

### 2.3 Crear diagrama: Flujo de conciliación (opcional)

**Archivo:** `flujo_conciliacion.png`

**Contenido:**
```
Extracto Bancario → Parser → Tabla Movimientos → Scoring (12+ criterios)
↓
Planilla Cliente → Conciliación → Resultado (OK / PENDIENTE / ERROR)
↓
Asiento Contable (automático)
```

- [ ] Crear diagrama de flujo
- [ ] Mostrar los pasos del motor de conciliación
- [ ] Exportar PNG
- [ ] Guardar en `/home/user/DIAGRAMAS/`

**Tiempo:** ~15 minutos

---

## FASE 3: GENERACIÓN DE PDFs (0.5 horas)

### 3.1 Verificar los 8 PDFs principales

Los PDFs deben estar ya generados en `/home/user/DOCUMENTACION/`:

- [ ] MEMORIA_DESCRIPTIVA.pdf
- [ ] INVENTARIO_TECNICO.pdf
- [ ] DOCUMENTACION_TECNICA.pdf
- [ ] MANUAL_FUNCIONAL.pdf
- [ ] MODULOS_DEL_SISTEMA.pdf
- [ ] EVIDENCIA_AUTORIA.pdf
- [ ] ACTIVOS_PI.pdf
- [ ] RESUMEN_EJECUTIVO.pdf

**Verificar cada PDF:**
- [ ] Abre en Adobe Reader sin errores
- [ ] Texto está en español (Argentina)
- [ ] Acentos correctos (Á, É, Í, Ó, Ú, Ñ)
- [ ] Sin espacios en blanco excesivos
- [ ] Tablas bien formateadas
- [ ] Imágenes/diagramas visibles (si las hay)

**Tiempo:** ~10 minutos (lectura rápida)

### 3.2 PDF opcional: Extracto de código fuente

**Archivo:** `CODIGO_FUENTE_EXTRACTO.pdf` (OPCIONAL)

Si deseas incluir un extracto del código fuente como evidencia adicional:

- [ ] Exportar 50+ páginas de código representativo:
  - backend/app/services/conciliacion.py (Motor de conciliación)
  - backend/app/services/motor_contable.py (Motor contable)
  - backend/app/routers/cheques.py (Lógica de cheques)
  - frontend/src/pages/Conciliaciones.tsx (UI de conciliación)

**Cómo generar:**
```bash
# Opción 1: Usar enscript (Linux/Mac)
enscript -B -p /tmp/codigo.ps backend/app/services/*.py && ps2pdf /tmp/codigo.ps CODIGO_FUENTE_EXTRACTO.pdf

# Opción 2: Copiar código a Word/LibreOffice, formatear y exportar PDF

# Opción 3: Usar VS Code → Print to PDF (seleccionar archivos)
```

- [ ] Verificar PDF generado (legible, acentos, numeración de líneas)
- [ ] Guardar en `/home/user/DOCUMENTACION/`

**Tiempo:** ~10 minutos

---

## FASE 4: CREAR ARCHIVO ZIP (0.5 horas)

### 4.1 Crear índice de contenido

Crear archivo de texto: `/home/user/INDICE_CONTENIDO.txt`

**Contenido mínimo:**
```
EXPEDIENTE DE REGISTRO DE OBRA DE SOFTWARE
DNDA 2026 — Julieta Arrazate

Sistema Integral de Gestión Financiera, Contable y Empresarial
Versión: v3.12 | Junio 2026

═════════════════════════════════════════
CONTENIDO:
1. SOFTWARE/ — Código fuente íntegro
2. DOCUMENTACION/ — 8-9 PDFs en español
3. CAPTURAS/ — 27 screenshots
4. DIAGRAMAS/ — Diagramas de arquitectura
═════════════════════════════════════════
```

- [ ] Crear el archivo

**Tiempo:** ~5 minutos

### 4.2 Crear el ZIP final

**Comando (Linux/Mac):**
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
  -x "*/node_modules/*" "*/__pycache__/*" "*/.venv/*" "*/dist/*" "*/.git/*" \
  -x "conciliacion-bancaria/backend/crear_datos_prueba.py"
```

**O desde Windows/Mac (GUI):**
1. Crear carpeta: `EXPEDIENTE_DNDA_ARRAZATE_2026_06/`
2. Copiar dentro:
   - Carpeta `SOFTWARE/` con backend, frontend, mobile, REGISTRO_OBRA_SOFTWARE
   - Carpeta `DOCUMENTACION/` con PDFs
   - Carpeta `CAPTURAS/` con 27 PNG
   - Carpeta `DIAGRAMAS/` con 3-4 PNG
   - Archivo `INDICE_CONTENIDO.txt`
3. Comprimir: Click derecho → Compress → `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip`

- [ ] ZIP creado exitosamente
- [ ] ZIP tiene tamaño esperado (~27-32 MB)

**Tiempo:** ~10 minutos

### 4.3 Verificar ZIP

```bash
# Verificar contenido
unzip -l EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip | head -50

# Verificar tamaño
du -sh EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip

# Verificar integridad
unzip -t EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip

# Verificar sin archivos sensibles
unzip -l EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip | grep -E "\.env|node_modules|__pycache__|\.git"
# Esperado: vacío (0 líneas)
```

- [ ] Contenido verificado (> 400 archivos)
- [ ] Tamaño OK (~27-32 MB)
- [ ] Integridad OK (0 errores)
- [ ] Sin archivos sensibles (0 líneas grep)

**Tiempo:** ~5 minutos

---

## FASE 5: INICIAR TRÁMITE ONLINE EN PORTAL DNDA (1 hora)

### 5.1 Ir al portal y completar formulario

- [ ] Ir a **tramites.argentina.gob.ar** → buscar "Inscripción de obra publicada - Software"
- [ ] (Alternativa directa) **argentina.gob.ar/dnda** → trámites
- [ ] Iniciar sesión con CUIL/CUIT en Mi Argentina (o crear cuenta si no tenés)
- [ ] Seleccionar: "Inscripción de obra publicada — Software"
- [ ] Seleccionar opción: **Digital** (ya elegida)

### 5.2 Completar los Datos del Trámite en el portal

- [ ] **Nombre de la obra:** "Sistema Integral de Gestión Financiera, Contable y Empresarial"
- [ ] **Tipo de obra:** Programa de computación
- [ ] **Autora:** Julieta Arrazate
- [ ] **Email:** julietaarrazate@gmail.com
- [ ] **DNI:** 36316081
- [ ] **Nacionalidad:** Argentina
- [ ] **Domicilio:** [completar con domicilio real]
- [ ] **Teléfono:** [completar]
- [ ] **Versión:** v3.12
- [ ] **Año de publicación:** 2026
- [ ] **Declarar** información de origen de la obra según Disposición 2-E/2016

### 5.3 Subir documentación obligatoria

Subir en el portal (todos < 20 MB, extensiones permitidas):

- [ ] `COMPROBANTE_PAGO_TRAMITE.pdf` (obligatorio)
- [ ] `COMPROBANTE_PAGO_TASA.pdf` (obligatorio)
- [ ] `DNI_ARRAZATE.pdf` o `.jpg`
- [ ] `MEMORIA_DESCRIPTIVA.pdf`
- [ ] `EVIDENCIA_AUTORIA.pdf`
- [ ] `INVENTARIO_TECNICO.pdf`
- [ ] `DOCUMENTACION_TECNICA.pdf`
- [ ] `MANUAL_FUNCIONAL.pdf`
- [ ] `MODULOS_DEL_SISTEMA.pdf`
- [ ] `ACTIVOS_PI.pdf`
- [ ] `RESUMEN_EJECUTIVO.pdf`
- [ ] `CAPTURAS.pdf` (las 27 capturas consolidadas)

### 5.4 Confirmar y guardar número de expediente

- [ ] Confirmar presentación → el sistema genera **Expediente Electrónico**
- [ ] Anotar número de expediente: ___________________________
- [ ] Guardar carátula del expediente (PDF generado por DNDA)
- [ ] Verificar que llegó email de confirmación

### 5.5 Esperar comunicación de DNDA (código digital — Paso 2)

- [ ] Aguardar email de DNDA con instrucciones para **carga digital del código**
- [ ] Al recibirlo, subir el ZIP preparado en Fase 4 según las instrucciones
- [ ] (Opcional) Si se prefiere privacidad: subir ZIP cifrado con contraseña

**Tiempo:** ~60 minutos (formulario + subida de archivos)

---

## FASE 6: CHECKLIST FINAL PRE-PRESENTACIÓN (0.5 horas)

### 6.1 Verificación de completitud

- [ ] ZIP `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip` existe y es accesible
- [x] Contiene 27 screenshots en CAPTURAS/
- [ ] Contiene 3-4 diagramas en DIAGRAMAS/
- [ ] Contiene 8-9 PDFs en DOCUMENTACION/
- [ ] Contiene código fuente íntegro en SOFTWARE/
- [ ] Contiene 29 .md de documentación en SOFTWARE/REGISTRO_OBRA_SOFTWARE/
- [ ] Contiene INDICE_CONTENIDO.txt
- [ ] Tamaño: ~27-32 MB
- [ ] Sin archivos .env reales, .pem, .key, node_modules, __pycache__
- [ ] Formulario DNDA completado y firmado
- [ ] Copia de DNI (fotocopia legible)

### 6.2 Checklist de contenidos

**Código fuente:**
- [ ] backend/ — 1.1 MB (22 routers, 18 servicios, 18 modelos, 9 migraciones, 156 tests)
- [ ] frontend/ — 1.5 MB (31 páginas, 18 componentes, PWA)
- [ ] mobile/ — 836 KB (React Native)

**Documentación:**
- [ ] MEMORIA_DESCRIPTIVA.md ✓
- [ ] INVENTARIO_TECNICO.md ✓
- [ ] DOCUMENTACION_TECNICA.md ✓
- [ ] MANUAL_FUNCIONAL.md ✓
- [ ] MODULOS_DEL_SISTEMA.md ✓
- [ ] EVIDENCIA_AUTORIA.md ✓
- [ ] ACTIVOS_PI.md ✓
- [ ] RESUMEN_EJECUTIVO.md ✓

**Documentación DNDA (nuevos análisis):**
- [ ] DNDA_OBRA_PRESENTABLE.md ✓
- [ ] DNDA_INCLUIR.md ✓
- [ ] DNDA_EXCLUSIONES.md ✓
- [ ] DNDA_PRIVACIDAD.md ✓
- [ ] DNDA_CAPTURAS.md ✓
- [ ] DNDA_REVISION_EXPEDIENTE.md ✓
- [ ] DNDA_VERSION_REGISTRADA.md ✓
- [ ] DNDA_ESTRUCTURA_ZIP.md ✓
- [ ] DNDA_VALIDACION_FINAL.md ✓
- [ ] DNDA_CHECKLIST_FINAL.md ✓ (este documento)

**PDFs:**
- [ ] MEMORIA_DESCRIPTIVA.pdf ✓
- [ ] INVENTARIO_TECNICO.pdf ✓
- [ ] DOCUMENTACION_TECNICA.pdf ✓
- [ ] MANUAL_FUNCIONAL.pdf ✓
- [ ] MODULOS_DEL_SISTEMA.pdf ✓
- [ ] EVIDENCIA_AUTORIA.pdf ✓
- [ ] ACTIVOS_PI.pdf ✓
- [ ] RESUMEN_EJECUTIVO.pdf ✓

**Capturas:**
- [x] 27 screenshots PNG (01_resumen_ejecutivo.png a 27_perfil_seguridad_ia.png)

**Diagramas:**
- [ ] arquitectura_3_capas.png ✓
- [ ] arquitectura_base_datos.png ✓
- [ ] flujo_conciliacion.png ✓

**Formulario:**
- [ ] Formulario DNDA completado y firmado ✓
- [ ] Copia DNI incluida ✓

### 6.3 Verificación de calidad

- [ ] Todos los PDFs están en español ✓
- [ ] Acentos correctos en PDFs (Gestión, Descripción, etc.) ✓
- [ ] Sin errores ortográficos ✓
- [ ] Tablas bien formateadas ✓
- [ ] Formato profesional ✓
- [ ] Sin información sensible ✓
- [ ] Coherencia entre documentos ✓

---

## FASE 7: CARGA DIGITAL DEL CÓDIGO (Paso 2 — tras email DNDA)

### 7.1 Esperar comunicación oficial de la DNDA

La DNDA envía por email las instrucciones de carga digital del código fuente
después de recibir el expediente del Paso 1. Puede demorar algunos días hábiles.

- [ ] Verificar bandeja de entrada (y carpeta Spam/No deseado)
- [ ] Email confirmado: ___________________________

### 7.2 Subir el código según instrucciones recibidas

- [ ] Seguir exactamente las instrucciones del email de DNDA
- [ ] Subir ZIP: `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip` (~27-32 MB) por el canal indicado
- [ ] (Opcional) Si se prefiere privacidad del código: cifrar el ZIP con contraseña
  ```bash
  zip -e EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip [archivos]
  # (ingresar contraseña cuando pida; guardarla en lugar seguro)
  ```
- [ ] Guardar confirmación de recepción del Paso 2

### 7.3 Seguimiento del expediente

- [ ] Número de expediente DNDA: ___________________________
- [ ] Fecha de inicio (Paso 1): ___________________________
- [ ] Fecha carga código (Paso 2): ___________________________
- [ ] **Silencio positivo:** 60 días hábiles a partir de acreditación de condiciones
  → Si no hay respuesta en ese plazo, el registro se considera otorgado (Ley 19.549 Art. 10 inc. b)
- [ ] Guardar todos los comprobantes en carpeta segura

---

## TIMELINE RECOMENDADO

| Fase | Duración | Día |
|---|---|---|
| Pagos previos (0.1 y 0.2) | 0.5 horas | Día 1 (antes de empezar) |
| Fase 1: Capturas | ✓ Completada | — |
| Fase 2: Diagramas | 0.5 horas | Día 1 (tarde) |
| Fase 3: PDFs | 0.5 horas | Día 1 (tarde) |
| Fase 4: ZIP | 0.5 horas | Día 2 (mañana) |
| Fase 5: Iniciar trámite online | 1 hora | Día 2 (tarde) |
| Fase 6: Checklist pre-carga | 0.5 horas | Día 2 (tarde) |
| Fase 7: Carga código (Paso 2) | Variable | Cuando llegue email DNDA |
| **TOTAL activo** | **~3,5 horas** | **2 días + espera DNDA** |

---

## CONTACTO DNDA

**Dirección Nacional del Derecho de Autor (Argentina)**

- **Portal de trámites:** tramites.argentina.gob.ar (buscar "Inscripción obra Software")
- **Sitio institucional:** argentina.gob.ar/dnda
- **Domicilio (solo opción física):** **Moreno 1230**, Ciudad Autónoma de Buenos Aires
  Horario: 9:30 a 14:30 hs (opción física NO elegida — optó por digital)

**Documentación obligatoria (opción digital):**
1. Datos del trámite completados en el portal
2. **Comprobante de pago del trámite** ($3.800) — obligatorio
3. **Comprobante de pago de tasa** (0,2% del valor del ejemplar, mín. $4,11) — obligatorio
4. Documentación técnica (PDFs: memoria, inventario, manual, capturas, etc.)
5. DNI del autor
6. Código fuente (Paso 2, canal digital indicado por DNDA después del expediente)

---

## NOTAS FINALES

- **Tiempo total activo:** ~3,5 horas (preparación + portal) + espera email DNDA (días)
- **Costo confirmado:** $3.800 (trámite) + 0,2% del valor de la obra (tasa)
- **Plazo de respuesta:** 60 días hábiles (silencio positivo — si no responden en ese plazo, el registro es otorgado)
- **Código cifrado:** Opción válida (Disposición 2-E/2016). El titular debe poder proveer la clave si una autoridad lo requiere.
- **Próximos pasos:** Guardar número de expediente y esperar email de DNDA para subir el código (Paso 2)

---

*Checklist final de presentación para expediente DNDA — Julieta Arrazate — Junio 2026*

**¡LISTO PARA PRESENTAR! 🎉**
