# REVISIÓN DE AUTORÍA FINAL
## Verificación de referencias a terceros en el expediente

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026  
**Alcance:** Todos los documentos de `REGISTRO_OBRA_SOFTWARE/`

---

## 1. METODOLOGÍA

Se realizó una búsqueda exhaustiva en todos los documentos del expediente buscando:

- Nombres de personas físicas distintas a la autora
- Nombres de empresas o estudios contables
- Referencias a asesores, consultores o validadores funcionales
- Referencias a potenciales socios comerciales
- Nombres de clientes reales del sistema
- Atribución de autoría creativa a terceros
- Menciones de revisores funcionales o testers externos

---

## 2. RESULTADOS

### 2.1 Personas físicas

| Persona mencionada | Rol en el documento | ¿Problema? |
|---|---|---|
| Julieta Arrazate | Autora de la obra | No — es la autora |

**Ninguna otra persona física aparece en el expediente.**

### 2.2 Empresas o estudios

No se encontraron referencias a empresas, estudios contables, consultoras ni organizaciones comerciales identificadas por nombre.

Los servicios técnicos de terceros mencionados (Google, Vercel, Render, Sentry, etc.) son **proveedores de infraestructura y herramientas de desarrollo** — su mención es técnicamente necesaria para describir la arquitectura del sistema y no implica participación en la autoría.

### 2.3 Asesores, consultores o validadores funcionales

No se encontraron referencias a personas que hayan asesorado, validado o aprobado funcionalidades del sistema.

### 2.4 Socios comerciales

No se encontraron referencias a socios comerciales, inversores, co-fundadores ni participantes en la explotación de la obra.

### 2.5 Clientes reales

**Un hallazgo fue detectado y corregido:**

| Documento | Hallazgo original | Corrección aplicada |
|---|---|---|
| `ACTIVOS_PI.md` línea 163 | Ejemplo de normalización usaba `"green"` — nombre de cliente real del sistema | Reemplazado por `"empresa abc"` |

No quedan referencias a clientes reales en ningún documento.

### 2.6 Rol "contador" en los documentos

La palabra "contador" aparece múltiples veces. En todos los casos sin excepción se refiere al rol técnico `CONTADOR` (enum en el código fuente del sistema), no a ninguna persona física. Contextos verificados:

- "rol contador" → enum `RoleEnum.CONTADOR` en `models/user.py`
- "el contador ingresa credenciales" → caso de uso del rol técnico (CU-02)
- "exportación para el contador" → formato de archivo Excel generado por el sistema
- "sesión de contador" → flujo de autenticación del rol

**Todos son referencias técnicas al funcionamiento del sistema. Ninguno identifica a una persona.**

### 2.7 Rol "usuario" en los documentos

La palabra "usuario" aparece como término técnico genérico (usuario del sistema, usuario autenticado, gestión de usuarios). No identifica a ninguna persona física.

### 2.8 "Terceros" en los documentos

La palabra "terceros" aparece en dos contextos:

1. **"Cheques de terceros"** → término bancario estándar para cheques emitidos por alguien distinto al tenedor. No identifica personas.
2. **"Librerías de terceros"** → dependencias de código abierto. No identifica personas.
3. **"Cesión de derechos en favor de terceros"** → declaración negativa de la autora. Correcto.

---

## 3. PALABRAS CLAVE AUDITADAS

| Término buscado | Apariciones encontradas | Todas legítimas |
|---|---|---|
| nombres propios de personas | 0 (salvo autora) | ✅ |
| asesores / consultores | 0 | ✅ |
| estudios / firmas | 0 | ✅ |
| socios / inversores | 0 | ✅ |
| clientes reales | 1 → corregido | ✅ |
| validadores / testers externos | 0 | ✅ |
| "contador" como persona | 0 (solo rol técnico) | ✅ |
| "usuario" como persona identificada | 0 (solo término técnico) | ✅ |

---

## 4. CONCLUSIÓN

**El expediente está libre de referencias a terceros que puedan:**

- Generar ambigüedad sobre la autoría exclusiva de la obra
- Atribuir participación creativa a personas que no desarrollaron software
- Exponer relaciones comerciales o contractuales
- Identificar clientes, asesores o validadores funcionales

La documentación describe únicamente la obra informática, su arquitectura, sus funcionalidades, su evidencia técnica y la autoría acreditada mediante el historial de control de versiones.

**La autoría de la obra corresponde exclusivamente a Julieta Arrazate.**

---

*Auditoría realizada sobre el material del expediente. Julieta Arrazate — Junio 2026*
