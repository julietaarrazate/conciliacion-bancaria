# ESTADO FINAL DEL EXPEDIENTE DE REGISTRO
## Sistema Integral de Gestión Financiera, Contable y Empresarial

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## 1. ¿ESTÁ LISTO PARA PRESENTAR?

**Respuesta: Casi. Faltan 2 acciones de 5 minutos y una decisión.**

El expediente está técnicamente completo. Los documentos son precisos, están basados exclusivamente en el código fuente, no contienen información sensible y están redactados a nivel profesional.

Lo que falta antes de presentar es completar información que solo la autora conoce y tomar capturas de pantalla del sistema.

---

## 2. QUÉ FALTA COMPLETAR (ordenado por importancia)

### Obligatorio

| Acción | Tiempo estimado | Impacto |
|---|---|---|
| Agregar DNI en `EXPEDIENTE_FINAL.md` | 1 minuto | Requerido por el formulario |
| Completar campo laboral/contractual en `EVIDENCIA_AUTORIA.md` §9 | 5 minutos | Importante para descartar cesión implícita |
| Tomar capturas de pantalla del sistema | 30–60 minutos | Fuerte evidencia visual de la obra |
| Exportar documentos a PDF | 15 minutos | Requerido para presentación |
| Crear tag git `v3.12-registro` | 2 minutos | Identifica la versión de forma permanente |

### Recomendado

| Acción | Tiempo estimado | Impacto |
|---|---|---|
| Corregir "5 roles" → "6 roles" en `MEMORIA_DESCRIPTIVA.md` | 1 minuto | Precisión del expediente |
| Crear diagramas de arquitectura y BD | 1–2 horas | Refuerza la comprensión técnica |
| Exportar historial git | 1 minuto | Evidencia adicional del proceso creativo |

---

## 3. DOCUMENTOS IMPRESCINDIBLES

Estos 4 documentos son los que, como mínimo, deben presentarse ante el organismo:

| # | Documento | Por qué es imprescindible |
|---|---|---|
| 1 | `MEMORIA_DESCRIPTIVA.md` | Describe la obra — es el documento central del registro |
| 2 | `EVIDENCIA_AUTORIA.md` | Acredita la autoría exclusiva |
| 3 | `INVENTARIO_TECNICO.md` | Prueba el alcance y la existencia técnica de la obra |
| 4 | Extracto de código fuente | La ley requiere depositar parte del código |

Sin estos 4, el registro no puede completarse.

---

## 4. DOCUMENTACIÓN OPCIONAL (pero recomendada)

| Documento | Valor que agrega |
|---|---|
| `ACTIVOS_PI.md` | Refuerza la originalidad de los algoritmos — útil ante impugnaciones |
| `DOCUMENTACION_TECNICA.md` | Demmuestra profundidad técnica — útil para licenciamientos futuros |
| `MANUAL_FUNCIONAL.md` | Demuestra utilidad práctica de la obra |
| `MODULOS_DEL_SISTEMA.md` | Muestra la escala del sistema |
| `RESUMEN_EJECUTIVO.md` | Para evaluadores no técnicos o negociaciones comerciales |
| Capturas de pantalla | Evidencia visual directa del sistema funcionando |
| Diagramas | Comprensión rápida de la arquitectura |
| Historial git | Prueba del proceso creativo y la autoría progresiva |

---

## 5. RIESGOS A GESTIONAR ANTES DE PRESENTAR

### Riesgo 1 — Campo laboral sin completar (MEDIO)
**Descripción:** Si la autora tiene o tuvo relación de dependencia laboral al momento del desarrollo, el empleador podría reclamar derechos sobre la obra.
**Mitigación:** Completar en `EVIDENCIA_AUTORIA.md` que la obra fue desarrollada con equipos propios, fuera de toda relación laboral y sin contrato de cesión. Si hubo relación laboral, consultar con un abogado especialista antes de registrar.

### Riesgo 2 — Nombre "Cuadra" sin registro marcario (BAJO)
**Descripción:** El nombre de trabajo "Cuadra" es mencionado en el expediente pero no está registrado como marca.
**Mitigación:** El expediente ya aclara en todos los documentos que "Cuadra constituye una denominación de trabajo sin registro marcario". El registro del software no requiere que la marca esté registrada. El riesgo es que un tercero registre la marca "Cuadra" antes que la autora.
**Acción recomendada:** Iniciar el trámite de registro marcario ante el INPI (Instituto Nacional de la Propiedad Industrial) en paralelo.

### Riesgo 3 — Versión del sistema evoluciona después del registro (BAJO)
**Descripción:** El sistema seguirá desarrollándose. Las versiones futuras no quedarán cubiertas por este registro.
**Mitigación:** El registro protege la versión v3.12. Para versiones futuras con cambios sustanciales, puede presentarse una nueva solicitud. Las mejoras menores quedan protegidas por el derecho moral del autor sobre la obra.

### Riesgo 4 — Historial git comprimido (MUY BAJO)
**Descripción:** El repositorio git muestra commits a partir del 2 de junio de 2026, aunque el sistema se desarrolló desde mayo 2026. La cronología del CLAUDE.md describe versiones desde mayo pero los commits visibles corresponden a junio.
**Mitigación:** La DNDA no requiere historial git; el registro protege la obra tal como existe al momento de presentarla. El campo [COMPLETAR] de fecha de inicio en EVIDENCIA_AUTORIA sirve para complementar este punto.
**Acción recomendada:** En el campo de fecha de inicio del desarrollo, indicar "Mayo 2026" si hay evidencia local (archivos, capturas) de ese período.

---

## 6. MEJORAS OPCIONALES ANTES DE PRESENTAR

| Mejora | Esfuerzo | Beneficio |
|---|---|---|
| Registrar marca "Cuadra" en INPI | Medio (trámite separado) | Protección del nombre comercial |
| Agregar firma digital a los PDFs | Bajo (5 min) | Certifica la fecha de los documentos |
| Enviar el ZIP a uno mismo por email (con timestamp del servidor) | Mínimo (1 min) | Evidencia de fecha adicional |
| Notaría: acta de depósito del código fuente | Medio (costo y tiempo) | Evidencia con fecha fehaciente |

---

## 7. ESTADO DOCUMENTO POR DOCUMENTO

| Documento | Estado | Observación |
|---|---|---|
| `README_REGISTRO.md` | ✅ Listo | |
| `MEMORIA_DESCRIPTIVA.md` | ⚠️ Casi | Corregir "5 roles" → "6 roles" |
| `INVENTARIO_TECNICO.md` | ✅ Listo | |
| `DOCUMENTACION_TECNICA.md` | ✅ Listo | |
| `MANUAL_FUNCIONAL.md` | ✅ Listo | |
| `MODULOS_DEL_SISTEMA.md` | ✅ Listo | |
| `EVIDENCIA_AUTORIA.md` | ⚠️ Completar | Agregar DNI y contexto laboral |
| `RESUMEN_EJECUTIVO.md` | ✅ Listo | |
| `ACTIVOS_PI.md` | ✅ Listo | Corregido (nombre de cliente → ejemplo genérico) |
| `REVISION_EXPEDIENTE.md` | ✅ Listo | |
| `NOMBRE_DE_OBRA_RECOMENDADO.md` | ✅ Listo | |
| `VERSION_A_REGISTRAR.md` | ✅ Listo | Crear tag git post-merge |
| `PAQUETE_FINAL.md` | ✅ Listo | |
| `EXPEDIENTE_FINAL.md` | ⚠️ Completar | Agregar DNI |
| `CHECKLIST_PRESENTACION.md` | ✅ Listo | |
| `MATERIAL_COMPLEMENTARIO.md` | ✅ Listo | Tomar capturas según guía |
| `ESTADO_FINAL_REGISTRO.md` | ✅ Listo | Este archivo |

---

## 8. PRÓXIMOS PASOS (en orden)

```
1. Completar DNI y campo laboral (5 minutos)
2. Corregir "5 roles" en MEMORIA_DESCRIPTIVA (1 minuto)
3. Tomar capturas de pantalla del sistema (30-60 minutos)
4. Exportar 4 documentos clave a PDF (15 minutos)
5. Exportar extracto de código a PDF (10 minutos)
6. Mergear PR #111 y crear tag git v3.12-registro (5 minutos)
7. Armar el ZIP según PAQUETE_FINAL (10 minutos)
8. Presentar ante la DNDA o iniciar trámite online
9. (Paralelo) Iniciar trámite de registro marcario de "Cuadra" en INPI
```

---

*Estado final del expediente preparado para registro de obra de software — Julieta Arrazate — Junio 2026*
