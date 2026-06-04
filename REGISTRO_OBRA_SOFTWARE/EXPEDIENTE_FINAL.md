# EXPEDIENTE DE REGISTRO DE OBRA INFORMÁTICA
## Presentación Formal

---

# PORTADA

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

           EXPEDIENTE DE REGISTRO DE OBRA DE SOFTWARE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  NOMBRE DE LA OBRA:
  Sistema Integral de Gestión Financiera,
  Contable y Empresarial

  DENOMINACIÓN DE TRABAJO:
  Cuadra (sin registro marcario vigente)

  AUTORA:
  Julieta Arrazate

  CORREO:
  julietaarrazate@gmail.com

  NACIONALIDAD:
  Argentina

  TIPO DE OBRA:
  Programa de computación
  (Ley 11.723, Art. 1 — Decreto 165/94)

  VERSIÓN REGISTRADA:
  v3.12

  FECHA DE LA OBRA:
  Mayo – Junio 2026

  FECHA DE PRESENTACIÓN:
  Junio 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

# ÍNDICE DEL EXPEDIENTE

## Sección A — Documentación Jurídica y de Autoría
1. Memoria Descriptiva de la Obra
2. Evidencia de Autoría
3. Declaración de Originalidad (incluida en Evidencia)

## Sección B — Documentación Técnica
4. Inventario Técnico
5. Documentación Técnica
6. Módulos del Sistema

## Sección C — Documentación Funcional
7. Manual Funcional
8. Activos de Propiedad Intelectual

## Sección D — Material Complementario
9. Capturas de Pantalla
10. Diagramas de Arquitectura

## Sección E — Identificación de Versión
11. Versión a Registrar (commit, tag, hash)
12. Historial Git (export)

## Sección F — Resumen y Presentación
13. Resumen Ejecutivo

---

# ORDEN RECOMENDADO DE PRESENTACIÓN

Para presentar ante la DNDA (Dirección Nacional del Derecho de Autor) u organismo equivalente:

| N° | Documento | Importancia |
|---|---|---|
| 1 | **Formulario del organismo** | Completar primero |
| 2 | **MEMORIA_DESCRIPTIVA.md** | Imprescindible — va primero en el cuerpo |
| 3 | **EVIDENCIA_AUTORIA.md** | Imprescindible — con campos [COMPLETAR] completados |
| 4 | **INVENTARIO_TECNICO.md** | Imprescindible — prueba del alcance técnico |
| 5 | Extracto de código fuente representativo | Imprescindible — mínimo 50 páginas del código |
| 6 | **ACTIVOS_PI.md** | Recomendado — refuerza la originalidad |
| 7 | **DOCUMENTACION_TECNICA.md** | Recomendado |
| 8 | **MANUAL_FUNCIONAL.md** | Recomendado |
| 9 | Capturas de pantalla | Recomendado — evidencia visual |
| 10 | **MODULOS_DEL_SISTEMA.md** | Complementario |
| 11 | **RESUMEN_EJECUTIVO.md** | Complementario — para evaluadores no técnicos |
| 12 | Historial git (export) | Complementario — evidencia de proceso creativo |

---

# ESTRUCTURA DEL EXPEDIENTE (versión PDF-ready)

## Sección A — DOCUMENTACIÓN JURÍDICA

### A.1 MEMORIA DESCRIPTIVA

Ver archivo: `MEMORIA_DESCRIPTIVA.md`

Puntos clave para el evaluador:
- Nombre oficial de la obra
- Objetivo y alcance
- Descripción técnica de tres capas
- 20 módulos funcionales
- Innovaciones funcionales (§7)
- Estado al momento del registro: v3.12, 156 tests, producción activa

### A.2 EVIDENCIA DE AUTORÍA

Ver archivo: `EVIDENCIA_AUTORIA.md`

Puntos clave:
- 100% de los 121 commits son de la autora
- Dos configuraciones de git del mismo autor (aclarado)
- Declaración de originalidad (§8)
- **Completar sección 9 antes de presentar**

---

## Sección B — DOCUMENTACIÓN TÉCNICA

### B.1 INVENTARIO TÉCNICO

Ver archivo: `INVENTARIO_TECNICO.md`

Incluye:
- Árbol de directorios completo
- Stack: FastAPI + React 18 + PostgreSQL + React Native
- 22 routers, 18 servicios, 18 modelos, 9 migraciones
- 31 páginas frontend, 18 componentes, 156 tests

### B.2 DOCUMENTACIÓN TÉCNICA

Ver archivo: `DOCUMENTACION_TECNICA.md`

Incluye:
- Arquitectura de 3 capas
- Seguridad: JWT, 2FA, PIN, WebAuthn, rate limiting
- Modelo de permisos en 3 capas
- APIs y endpoints
- Integraciones externas
- Auditoría y scheduler
- Motor OCR

### B.3 MÓDULOS DEL SISTEMA

Ver archivo: `MODULOS_DEL_SISTEMA.md`

Incluye:
- Tabla maestra de 23 módulos
- Objetivos, funcionalidades y dependencias de cada módulo

---

## Sección C — DOCUMENTACIÓN FUNCIONAL

### C.1 MANUAL FUNCIONAL

Ver archivo: `MANUAL_FUNCIONAL.md`

Incluye:
- Flujo operativo general (8 pasos)
- 40 casos de uso (CU-01 a CU-40)
- Procesos contables: partida doble, plan de cuentas
- Gestión documental: formatos de entrada y salida

### C.2 ACTIVOS DE PROPIEDAD INTELECTUAL

Ver archivo: `ACTIVOS_PI.md`

Incluye:
- 5 algoritmos propios
- 5 reglas de negocio originales
- 4 procesos diferenciales
- 6 componentes innovadores
- Tabla de elementos potencialmente registrables

---

## Sección D — MATERIAL COMPLEMENTARIO

### D.1 Capturas de pantalla

Ver `CAPTURAS/` en el ZIP de registro.
Ver lista detallada en: `MATERIAL_COMPLEMENTARIO.md`

### D.2 Diagramas

Ver `DIAGRAMAS/` en el ZIP de registro.
Ver especificaciones en: `MATERIAL_COMPLEMENTARIO.md`

---

## Sección E — IDENTIFICACIÓN DE VERSIÓN

### E.1 Versión registrada

Ver archivo: `VERSION_A_REGISTRAR.md`

- Hash del commit: `b846c1753aac4363321311537f74a47fe96569c4`
- Tag recomendado: `v3.12-registro`
- Fecha: Junio 2026

---

## Sección F — RESUMEN

### F.1 Resumen Ejecutivo

Ver archivo: `RESUMEN_EJECUTIVO.md`

Para presentar a evaluadores sin perfil técnico o como documento introductorio.

---

# EXTRACTO DE CÓDIGO FUENTE PARA PRESENTACIÓN

Para el expediente, incluir al menos un extracto representativo del código. Opciones recomendadas (en orden de importancia para acreditar originalidad):

1. **`backend/app/services/conciliacion.py`** — Motor de conciliación (algoritmo propio)
2. **`backend/app/services/motor_contable.py`** — Motor de asientos automáticos
3. **`backend/app/services/aprendizaje.py`** — Motor de aprendizaje por patrones
4. **`backend/app/main.py`** — Startup con safety nets, plan de cuentas, scheduler
5. **`frontend/src/services/api.ts`** — Cliente HTTP centralizado (~25 KB)

Exportar como PDF con numeración de líneas y encabezado con nombre de archivo.

---

# DECLARACIÓN DE PRESENTACIÓN

Yo, **Julieta Arrazate**, con correo electrónico julietaarrazate@gmail.com, declaro que soy la autora exclusiva de la obra denominada **Sistema Integral de Gestión Financiera, Contable y Empresarial** (denominación de trabajo: Cuadra), que la misma es una creación intelectual original, y que no he cedido los derechos de la misma a ningún tercero.

Asimismo, declaro que las librerías de código abierto utilizadas son de uso libre bajo licencias permisivas que no restringen la comercialización ni el registro de la obra que las integra.

**Fecha:** Junio 2026  
**Firma:** ___________________________  
**Aclaración:** Julieta Arrazate  
**DNI:** [COMPLETAR]

---

*Expediente preparado para registro de obra informática — Todos los derechos reservados — Julieta Arrazate — 2026*
