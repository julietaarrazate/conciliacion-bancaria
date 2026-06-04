# TAG DE REGISTRO GIT
## Identificación permanente de la versión presentada ante la DNDA

**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## 1. EL TAG CREADO

```
Nombre:   dnda-software-2026-v1
Tipo:     Anotado (contiene autor, fecha y mensaje)
Commit:   358f589482db8df36bbec64aa825be6bf367f649
Mensaje:  Versión presentada ante la DNDA para registro de obra de
          software — Junio 2026 — Julieta Arrazate
```

---

## 2. POR QUÉ ESTE COMMIT Y NO EL PRIMERO

### El primer commit visible no es el inicio real del proyecto

El primer commit del repositorio (`6e57c09`) ya es un *fix* sobre una funcionalidad existente (2FA). El historial visible comienza el 2 de junio de 2026, pero el sistema fue desarrollado desde mayo. Tagear el primer commit visible implicaría marcar un punto arbitrario en el medio del desarrollo, no su inicio.

El tag no dice *"el proyecto empezó aquí"*. Dice *"en este punto exacto presenté el registro"*.

### El commit elegido representa el estado completo de la obra al momento del registro

El commit `358f589` es el último de la rama de registro. Contiene:

- Todo el código fuente del sistema (v3.12) — backend, frontend y móvil
- Los 9 documentos originales del expediente (`REGISTRO_OBRA_SOFTWARE/`)
- Los 8 documentos de revisión y preparación final
- La corrección de auditoría (nombre de cliente → ejemplo genérico)

Es el estado más completo y coherente: **el software que se registra + el expediente que lo describe**, todo junto en un único punto identificable.

---

## 3. QUÉ GARANTIZA UN TAG ANOTADO

A diferencia de una rama (que avanza con cada commit), un tag anotado es **inmutable**: una vez creado y publicado, siempre apuntará al mismo commit. Git garantiza la integridad del contenido mediante SHA-1: si alguien modifica un solo byte del repositorio, el hash cambia.

Esto significa que en cualquier fecha futura se puede verificar:

```bash
git show dnda-software-2026-v1 --stat
# → muestra exactamente qué archivos existían en el momento del registro
```

---

## 4. CÓMO PUBLICAR EL TAG

El tag fue creado localmente en este entorno. Para publicarlo en GitHub ejecutar **desde tu máquina** con el repo clonado:

```bash
# Opción A — si ya tenés el repo clonado y actualizado
git fetch origin
git tag -a dnda-software-2026-v1 358f589482db8df36bbec64aa825be6bf367f649 \
  -m "Versión presentada ante la DNDA para registro de obra de software — Junio 2026 — Julieta Arrazate"
git push origin dnda-software-2026-v1
```

```bash
# Opción B — desde GitHub web
# Ir a: github.com/julietaarrazate/conciliacion-bancaria/releases/new
# → "Choose a tag" → escribir: dnda-software-2026-v1
# → Target: claude/software-registration-docs-8aGy3 (o main si ya mergeaste)
# → Title: Registro DNDA — v1 — Junio 2026
# → Guardar como draft (no publicar como release público)
```

---

## 5. VERIFICACIÓN DESPUÉS DE PUBLICAR

```bash
# Verificar que el tag existe en el remoto
git ls-remote --tags origin | grep dnda

# Ver el contenido completo del tag
git show dnda-software-2026-v1

# Ver qué archivos incluye
git show dnda-software-2026-v1 --stat
```

---

## 6. CONSERVAR COMO EVIDENCIA

Guardar en el expediente físico:

| Dato | Valor |
|---|---|
| Nombre del tag | `dnda-software-2026-v1` |
| Hash del commit | `358f589482db8df36bbec64aa825be6bf367f649` |
| Fecha de creación del tag | 4 de junio de 2026 |
| Repositorio | `julietaarrazate/conciliacion-bancaria` (privado) |
| Rama base | `claude/software-registration-docs-8aGy3` |
| Versión del sistema | v3.12 |

Este hash es el identificador definitivo de la versión registrada. Es inmutable y verificable en cualquier momento.

---

*Documento elaborado para expediente de registro de obra de software — Julieta Arrazate — Junio 2026*
