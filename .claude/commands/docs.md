# /docs — Mantener la documentación sincronizada con el código

Propósito: cuando el código cambia, actualizar `docs/` para que siga siendo la **fuente de verdad
arquitectónica**. La doc describe el código **tal como está**, no como debería ser.

## Pasos

1. **Identificar qué docs toca el cambio** desde [`docs/README.md`](../../docs/README.md):
   - Modelo/relaciones → `docs/architecture/DOMAIN_MODEL.md`, `SYSTEM_MAP.md`.
   - Endpoints/convenciones API → `docs/api/API_RULES.md`.
   - Esquema/migraciones → `docs/database/DATABASE_RULES.md` (tabla de migraciones, índices,
     constraints).
   - Permisos/auth → `docs/security/SECURITY_MODEL.md` (matriz de roles).
   - Reglas de negocio → `docs/business/BUSINESS_RULES.md`, `WORKFLOWS.md`.
   - UX → `docs/ux/UX_RULES.md`, `DESIGN_SYSTEM.md`.
   - Decisión arquitectónica nueva → ADR en `docs/adr/DECISIONS.md` (usar
     [`.claude/templates/adr_template.md`](../templates/adr_template.md)).
   - Paso a paso operativo → playbook en `docs/playbooks/`.
2. **Actualizar el contenido** para reflejar el estado real: si agregaste una migración, sumala a
   la tabla; si cambió la matriz de permisos, actualizala desde el código (no de memoria).
3. **Discrepancias que no podés resolver ahora**: NO las tapes. Agregalas a la sección
   `## Pendiente de revisar` del doc correspondiente (convención de `docs/README.md`).
4. **CHANGELOG / CLAUDE.md**: si el cambio es relevante para el historial, sumá la línea al
   [`CHANGELOG.md`](../../CHANGELOG.md); si cambia el contexto operativo, ajustá
   [`CLAUDE.md`](../../CLAUDE.md).
5. **BUGS.md**: si surgió un bug recurrente, dejá la entrada con causa raíz + cómo evitarlo.

## Verificación

Releer el doc tocado y confirmar que: (a) describe el código actual, (b) los links relativos
funcionan, (c) lo no resuelto quedó en "Pendiente de revisar". No hay build de docs; la
verificación es lectura.

## PR

Rama `claude/...` → PR squash, commits con
`git commit --author="Julieta Arrazate <julietaarrazate@gmail.com>"`.
