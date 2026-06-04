# VERSIÓN A REGISTRAR
## Identificación inequívoca de la obra para el expediente

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## 1. COMMIT RECOMENDADO

### Commit del paquete de documentación (rama de registro)

| Campo | Valor |
|---|---|
| **Hash completo** | `b846c1753aac4363321311537f74a47fe96569c4` |
| **Hash corto** | `b846c17` |
| **Fecha** | 4 de Junio de 2026 |
| **Mensaje** | `docs: paquete completo de registro de obra de software` |
| **Rama** | `claude/software-registration-docs-8aGy3` |
| **Autor** | Julieta Arrazate \<julietaarrazate@gmail.com\> |

Este commit es el que incorpora la carpeta `REGISTRO_OBRA_SOFTWARE/` con todos los documentos de este expediente. Es el punto de referencia ideal para el registro.

### Último commit de código funcional (estado del sistema)

| Campo | Valor |
|---|---|
| **Hash** | `ed1f4b8` |
| **Mensaje** | `docs: CLAUDE.md v3.12` |
| **Versión del sistema** | v3.12 |
| **Fecha** | 3 de Junio de 2026 |

---

## 2. RAMA RECOMENDADA

**Para el registro, la rama de referencia es `main`.**

Motivo: `main` contiene la versión estable de producción. La rama `claude/software-registration-docs-8aGy3` fue creada para el proceso de documentación y eventualmente se incorporará a `main` mediante merge.

**Orden de acción recomendado:**
1. Mergear la rama de documentación a `main` (merge squash del PR #111)
2. Crear el tag de registro **después** del merge
3. El tag queda sobre `main`

---

## 3. TAG RECOMENDADO

### Crear el tag de registro

```bash
git tag -a v3.12-registro \
  -m "Versión registrada ante organismo de propiedad intelectual — Junio 2026" \
  HEAD

git push origin v3.12-registro
```

### Alternativa con fecha explícita

```bash
git tag -a v3.12-registro-2026-06 \
  -m "Registro de obra — Sistema Integral de Gestion Financiera, Contable y Empresarial — Junio 2026" \
  HEAD

git push origin v3.12-registro-2026-06
```

### Parámetros del tag

| Parámetro | Valor recomendado |
|---|---|
| **Nombre del tag** | `v3.12-registro` |
| **Tipo** | Anotado (`-a`) — incluye autor, fecha y mensaje |
| **Mensaje** | "Versión registrada ante organismo de propiedad intelectual — Junio 2026" |
| **Rama base** | `main` (después del merge) |

---

## 4. IDENTIFICACIÓN INEQUÍVOCA DE LA VERSIÓN

Para identificar la versión registrada en cualquier momento futuro, se debe conservar:

| Identificador | Valor | Inmutable |
|---|---|---|
| Hash SHA-1 del commit de registro | `b846c1753aac4363321311537f74a47fe96569c4` | Sí (git garantiza integridad) |
| Tag anotado | `v3.12-registro` | Sí (una vez pusheado) |
| Nombre de la versión | v3.12 | Sí (documentado) |
| Fecha | Junio 2026 | Sí |
| Rama | `main` (post-merge) | Sí |

---

## 5. QUÉ INCLUYE ESTA VERSIÓN

La versión `v3.12` (commit `b846c17`) incluye:

- Todos los módulos funcionales del sistema (v3.12 completo)
- Carpeta `REGISTRO_OBRA_SOFTWARE/` con documentación de registro
- 121 commits de historial de desarrollo
- 156 tests automatizados pasando
- 9 migraciones de base de datos
- Código fuente completo: backend (Python/FastAPI) + frontend (React/TypeScript) + móvil (React Native)

---

## 6. INSTRUCCIÓN FINAL

Una vez mergeado el PR #111 a `main`, ejecutar:

```bash
# Verificar que estás en main con el merge aplicado
git checkout main
git pull origin main

# Crear el tag anotado
git tag -a v3.12-registro -m "Registro de obra — Julieta Arrazate — Junio 2026"

# Pushear el tag al repositorio remoto
git push origin v3.12-registro

# Verificar
git show v3.12-registro
```

El hash que devuelva `git show v3.12-registro` es el identificador definitivo de la versión registrada.

---

*Documento elaborado para expediente de registro. Julieta Arrazate — Junio 2026*
