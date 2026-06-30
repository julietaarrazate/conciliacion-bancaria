# ADR-NNN — <Título de la decisión>

Plantilla para registrar una decisión arquitectónica. Alineada con
[`docs/adr/DECISIONS.md`](../../docs/adr/DECISIONS.md) (formato:
**Título · Contexto · Decisión · Consecuencias · Estado**). Al completarla, copiá la entrada
a `docs/adr/DECISIONS.md` con el próximo número `ADR-NNN` correlativo. Solo decisiones con
evidencia en el código/changelog — no decisiones aspiracionales.

## ADR-NNN — <Título>

- **Contexto:** (qué problema o fuerza motivó la decisión. Citar evidencia: archivo de código,
  migración Alembic, entrada de CHANGELOG/BUGS.)
- **Decisión:** (qué se decidió, en concreto. Dónde vive en el código — modelos, services,
  routers, migración.)
- **Consecuencias:** (qué implica para el código nuevo: invariantes a respetar, trade-offs,
  efectos en otras áreas. Ej.: "toda query debe filtrar X", "los índices deben excluir Y".)
- **Estado:** (Propuesta / Aceptada y vigente / Reemplazada por ADR-MMM / Obsoleta.)

## Notas

- Cross-ref a los docs relevantes (`docs/architecture/`, `docs/database/DATABASE_RULES.md`,
  `docs/security/SECURITY_MODEL.md`) con rutas relativas.
- Si reemplaza a un ADR anterior, dejarlo explícito en ambos (el viejo pasa a "Reemplazada por...").
