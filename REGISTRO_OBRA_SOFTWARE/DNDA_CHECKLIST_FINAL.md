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

---

## FASE 1: CAPTURAS DE PANTALLA (1.5 horas)

### 1.1 Preparar el sistema para capturar

- [ ] Loguearse en el sistema con `admin@demo.com / admin123`
- [ ] Navegar a cada módulo y crear datos demo si falta:
  - [ ] Extracto bancario demo (Excel)
  - [ ] Planilla de conciliación demo (con filas en distintos estados)
  - [ ] 10-15 cheques registrados
  - [ ] 5-10 pagos/gastos
  - [ ] Arqueos de caja (últimos 5 días)
  
**Tiempo:** ~30 minutos

### 1.2 Capturar 24 screenshots

**Grupo 1: Autenticación (2 capturas)**

- [ ] 01_login.png — Página de login (formulario email/password)
- [ ] 02_dashboard_overview.png — Dashboard vista general (light mode)

**Grupo 2: Dashboard y tema (2 capturas)**

- [ ] 03_dashboard_dark.png — Dashboard dark mode (tema oscuro)
- [ ] (opcional: algún módulo en dark mode)

**Grupo 3: Módulo Extractos (2 capturas)**

- [ ] 04_extractos_archivo.png — Lista de extractos cargados
- [ ] (opcional: preview de movimientos del extracto)

**Grupo 4: Módulo Conciliación (3 capturas)**

- [ ] 05_movimientos_tabla.png — Tabla de movimientos bancarios
- [ ] 06_conciliacion_panel.png — Panel de conciliación de planilla (filas PEND/OK/ERROR)
- [ ] 07_conciliacion_scoring.png — Modal de scoring (desglose de puntos)

**Grupo 5: Módulo Cheques (3 capturas)**

- [ ] 08_cheques_registro.png — Tabla de cheques (tab "Todos")
- [ ] 09_cheques_deposito.png — Tab "Por depósito" (acreditación masiva)
- [ ] 10_cheques_ocr.png — Formulario nuevo cheque con foto cargada + OCR (campos pre-llenados)

**Grupo 6: Módulo Pagos (2 capturas)**

- [ ] 11_pagos_listado.png — Tabla de egresos (pagos/gastos)
- [ ] 12_pagos_nuevo.png — Formulario nuevo pago (con campos y botón cámara)

**Grupo 7: Módulo Caja (1 captura)**

- [ ] 13_caja_arqueo.png — Panel de arqueología diaria (denominaciones, total)

**Grupo 8: Módulo Contabilidad (4 capturas)**

- [ ] 14_libro_diario.png — Libro Diario (tabla de asientos)
- [ ] 15_libro_mayor.png — Libro Mayor (movimientos por cuenta)
- [ ] 16_plan_cuentas.png — Plan de Cuentas (árbol jerárquico)
- [ ] 17_cuentas_corrientes.png — Cartera de clientes (saldos de cuentas corrientes)

**Grupo 9: Análisis y reportería (3 capturas)**

- [ ] 18_resumen_mensual.png — Resumen ejecutivo (ingresos por cliente)
- [ ] 19_flujo_caja.png — Flujo de Caja (proyección gráfica)
- [ ] 20_estado_cuenta_cliente.png — Estado de Cuenta de cliente (desglose de movimientos)

**Grupo 10: Auditoría y administración (3 capturas)**

- [ ] 21_auditoria_log.png — Log de Auditoría (historial de acciones)
- [ ] 22_usuarios_rol.png — Gestión de Usuarios (tabla con roles)
- [ ] 23_papelera_reciclaje.png — Papelera (registros borrados)

**Grupo 11: Configuración y seguridad (1 captura)**

- [ ] 24_perfil_usuario.png — Perfil de usuario (datos, 2FA, PIN, tema)

**Total:** 24 capturas

**Instrucciones para capturar:**
1. Resolución: 1280×720 o 1920×1080 (landscape)
2. Formato: PNG
3. Guardar en carpeta: `/home/user/CAPTURAS/`
4. Nombrar: `NN_descripcion.png` (ej: `01_login.png`)

**Tiempo:** ~1 hora

### 1.3 Verificar calidad de capturas

- [ ] Todas las 24 capturas tienen nombres correctos (01 a 24)
- [ ] Todas están en PNG (formato verificado)
- [ ] Tamaño individual: 400-600 KB (legible)
- [ ] Ninguna captura tiene datos reales de clientes
- [ ] Texto es legible (no pixelado)
- [ ] Contienen datos demo claramente ficticios

**Tiempo:** ~15 minutos

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
3. CAPTURAS/ — 24 screenshots
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
   - Carpeta `CAPTURAS/` con 24 PNG
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

## FASE 5: COMPLETAR FORMULARIO DNDA (0.5 horas)

### 5.1 Descargar formulario DNDA

Visitar sitio oficial de la DNDA:
- [ ] Ir a www.cultura.gob.ar/dnda/ (o dirección actual)
- [ ] Descargar formulario de registro de obra de software
- [ ] Guardar en `/home/user/formulario_dnda.pdf`

**Alternativa:** Si no hay formulario digital, preparar documento Word con los campos:

- [ ] Nombre de la obra: "Sistema Integral de Gestión Financiera, Contable y Empresarial"
- [ ] Tipo de obra: "Programa de computación"
- [ ] Autora: "Julieta Arrazate"
- [ ] Email: "julietaarrazate@gmail.com"
- [ ] DNI: 36316081
- [ ] Nacionalidad: Argentina
- [ ] Domicilio: [completar]
- [ ] Teléfono: [completar]
- [ ] Versión: v3.12
- [ ] Fecha: Junio 2026

### 5.2 Completar campos del formulario

- [ ] Nombre completo de la obra
- [ ] Tipo de obra: Programa de computación
- [ ] Autora: Julieta Arrazate
- [ ] Datos de contacto: Email, teléfono, domicilio
- [ ] DNI: 36316081
- [ ] Declaración: "Autorizo la presentación de esta obra para registro"
- [ ] Firma: Julieta Arrazate
- [ ] Fecha: Junio de 2026

- [ ] Formulario completado y guardado

**Tiempo:** ~30 minutos

---

## FASE 6: CHECKLIST FINAL PRE-PRESENTACIÓN (0.5 horas)

### 6.1 Verificación de completitud

- [ ] ZIP `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip` existe y es accesible
- [ ] Contiene 24 screenshots en CAPTURAS/
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
- [ ] 24 screenshots PNG (01_login.png a 24_perfil_usuario.png)

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

## FASE 7: PRESENTACIÓN ANTE DNDA

### 7.1 Preparar presentación

**Paquete a entregar:**
- ZIP: `EXPEDIENTE_DNDA_ARRAZATE_2026_06.zip` (~27-32 MB)
- Formulario DNDA firmado (copia impresa + digital)
- Copia del DNI (fotocopia legible)
- Carta de presentación (opcional, 1-2 páginas)

### 7.2 Opciones de entrega

**Opción A: Presentación presencial**
- [ ] Contactar con la DNDA para agendar cita
- [ ] Presentar personalmente con documentos impresos y copia digital en USB/CD
- [ ] Obtener recibo de presentación

**Opción B: Presentación por correo electrónico**
- [ ] Verificar dirección de email de DNDA (registro@dnda.gov.ar u otra)
- [ ] Enviar ZIP, formulario PDF y DNI en correo
- [ ] Solicitar confirmación de recepción
- [ ] Guardar confirmación como comprobante

**Opción C: Portal DNDA (si existe)**
- [ ] Verificar si hay portal de presentaciones en línea
- [ ] Crear cuenta con datos de autora
- [ ] Subir ZIP y documentos
- [ ] Obtener número de expediente

### 7.3 Seguimiento

- [ ] Guardar número de expediente DNDA
- [ ] Anotar fecha de presentación
- [ ] Guardar confirmación de recepción
- [ ] Verificar plazo de respuesta (típicamente 30-60 días)

---

## TIMELINE RECOMENDADO

| Fase | Duración | Día |
|---|---|---|
| Fase 1: Capturas | 1.5 horas | Día 1 (mañana) |
| Fase 2: Diagramas | 0.5 horas | Día 1 (tarde) |
| Fase 3: PDFs | 0.5 horas | Día 1 (tarde) |
| Fase 4: ZIP | 0.5 horas | Día 2 (mañana) |
| Fase 5: Formulario | 0.5 horas | Día 2 (mañana) |
| Fase 6: Checklist | 0.5 horas | Día 2 (tarde) |
| Fase 7: Presentación | Variable | Día 3-5 |
| **TOTAL** | **~4 horas** | **1-5 días según opción** |

---

## CONTACTO DNDA

**Dirección Nacional del Derecho de Autor (Argentina)**

- **Sitio:** www.cultura.gob.ar/dnda/ (o actualizado)
- **Email:** Verificar en sitio oficial
- **Teléfono:** Verificar en sitio oficial
- **Domicilio:** Av. Córdoba 1515, CABA (verificar)

**Documentación requerida (verificar en sitio):**
1. Formulario de registro completo y firmado
2. Copia del DNI del autor
3. Expediente técnico (código fuente + documentación)
4. Certificado de originalidad (si aplica)
5. Constancia de pago de aranceles (si aplica)

---

## NOTAS FINALES

- **Tiempo total:** ~4 horas (fases 1-6) + tiempo de presentación
- **Costo:** Verificar arancel actual en DNDA (típicamente $500-1500 ARS)
- **Plazo de respuesta:** 30-60 días hábiles desde presentación
- **Próximos pasos:** Una vez aprobado, registrar el número de expediente en la carpeta del proyecto

---

*Checklist final de presentación para expediente DNDA — Julieta Arrazate — Junio 2026*

**¡LISTO PARA PRESENTAR! 🎉**
