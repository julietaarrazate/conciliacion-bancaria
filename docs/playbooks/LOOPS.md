# LOOPS — Ciclos de trabajo permanentes

> Los flujos que Claude (y el equipo) sigue para mantener Cuadra con calidad a lo largo de los años.
> Son la versión detallada del **ciclo de trabajo obligatorio** de [`CLAUDE.md`](../../CLAUDE.md) y
> se operacionalizan en [`.claude/commands/`](../../.claude/commands/). Cada loop indica el
> **cerebro** (modelo) recomendado para no gastar tokens de más: lectura/análisis → Haiku;
> implementación estándar → Sonnet; lógica compleja/riesgosa → Opus; orquestación/diseño → Fable.

Plantilla de cada loop: **Objetivo · Cerebro · Entrada · Pasos · Salida · Docs afectada**.
Verificación común a casi todos: `cd backend && pytest -q` + `cd frontend && npx tsc --noEmit && npm run build`.

---

## 1. Feature Loop
- **Objetivo**: agregar una funcionalidad nueva sin romper lo existente.
- **Cerebro**: Fable diseña/descompone · Sonnet (CRUD/UI) · Opus (lógica financiera/compleja).
- **Entrada**: necesidad clara; idealmente un issue con criterios de aceptación.
- **Pasos**: leer PRODUCT_BIBLE + SYSTEM_MAP + DOMAIN_MODEL + DECISIONS → impacto → reutilización →
  diseño → modelo+service+router (permisos 3 capas) + migración+safety-net → página+nav → tests →
  docs → CHANGELOG → deuda técnica. Ver [`NEW_MODULE.md`](./NEW_MODULE.md), [`NEW_API_ENDPOINT.md`](./NEW_API_ENDPOINT.md).
- **Salida**: tests verdes, opt-in por org, docs y CHANGELOG actualizados, PR con checklist.
- **Docs afectada**: la del área + SYSTEM_MAP/DOMAIN_MODEL si cambian entidades; CHANGELOG.

## 2. Bug Loop
- **Objetivo**: corregir un defecto con regresión cubierta.
- **Cerebro**: Haiku (reproducir/leer) · Sonnet/Opus según complejidad de la causa.
- **Entrada**: síntoma reproducible o reporte con pasos.
- **Pasos**: **reproducir primero** (idealmente test que falle) → causa raíz (no enmascarar con
  `except` genérico) → fix → test de regresión → verificar → doc/`Pendiente de revisar` si aplica.
  Ver [`.claude/commands/bug.md`](../../.claude/commands/bug.md) y [`BUGS.md`](../../BUGS.md).
- **Salida**: bug reproducido y cubierto por un test que antes fallaba; BUGS.md si es recurrente.
- **Docs afectada**: BUGS.md (si es patrón recurrente); el doc del área si cambió comportamiento.

## 3. Refactor Loop
- **Objetivo**: mejorar el código sin cambiar comportamiento.
- **Cerebro**: Sonnet (mecánico) · Opus solo si toca lógica delicada.
- **Entrada**: tests verdes ANTES de empezar (red de seguridad).
- **Pasos**: confirmar verde → cambios mecánicos acotados → re-verificar verde (mismo resultado) →
  no tocar lógica de negocio ni contratos públicos.
- **Salida**: comportamiento idéntico, tests verdes, diff legible.
- **Docs afectada**: normalmente ninguna; actualizar si cambió una convención documentada.

## 4. Documentation Loop
- **Objetivo**: mantener `/docs` sincronizada con el código.
- **Cerebro**: Haiku (leer código + redactar).
- **Entrada**: un cambio de comportamiento ya mergeado, o una discrepancia detectada.
- **Pasos**: identificar el doc del área → actualizarlo describiendo el código **tal como está** →
  resolver/añadir su sección `## Pendiente de revisar` → cruzar referencias.
- **Salida**: doc fiel al código, sin links rotos.
- **Docs afectada**: la del área + `docs/README.md` si cambia la estructura.

## 5. Security Loop
- **Objetivo**: que ningún cambio abra un agujero (auth, permisos, multi-tenant, secretos).
- **Cerebro**: Opus/Fable (revisión) · Haiku (búsqueda de secretos/patrones).
- **Entrada**: cualquier cambio que toque auth, endpoints, datos de otra org, archivos subidos, o
  integraciones externas.
- **Pasos**: aplicar el [`security_checklist.md`](../../.claude/checklists/security_checklist.md):
  permisos en 3 capas, aislamiento `org_id`+`can_switch_org`, sin secretos en código, rate limiting,
  validación de inputs/magic bytes, Decimal, headers. Ver [`SECURITY_MODEL.md`](../security/SECURITY_MODEL.md).
- **Salida**: checklist de seguridad superado; vulnerabilidades reportadas según `SECURITY.md`.
- **Docs afectada**: SECURITY_MODEL.md si cambia el modelo de permisos/roles.

## 6. Database Loop
- **Objetivo**: cambios de esquema seguros y reproducibles.
- **Cerebro**: Opus (migraciones/lógica de datos).
- **Entrada**: necesidad de nueva tabla/columna/índice/constraint.
- **Pasos**: migración Alembic **+** safety-net idempotente en `main.py` → dinero en `Numeric(12,2)`
  → soft delete con `deleted_at` si aplica → índices únicos parciales que excluyan borrados →
  `organizacion_id` para multi-tenant → backfill cuidado (no tocar Org A) → tests.
  Ver [`DATABASE_RULES.md`](../database/DATABASE_RULES.md).
- **Salida**: esquema migrable y con red de respaldo; tests verdes.
- **Docs afectada**: DATABASE_RULES.md (índices/constraints), DOMAIN_MODEL.md (entidades).

## 7. AI Loop
- **Objetivo**: evolucionar el asistente IA (Gemini) o la IA Nivel 2 sin romper la degradación.
- **Cerebro**: Sonnet/Opus según el cambio.
- **Entrada**: nueva tool/endpoint del asistente, o ajuste del aprendizaje de patrones.
- **Pasos**: respetar el feature flag (`GEMINI_API_KEY` → 503 si falta) → tools scopeadas a la org →
  cuotas → OCR/voz por los endpoints existentes. Para IA Nivel 2 (aprendizaje), respetar el modelo
  `PatronAprendido` y la regla 2+ confirmaciones. Ver [`AI_GUIDE.md`](../ai/AI_GUIDE.md) y
  [`BUSINESS_RULES.md`](../business/BUSINESS_RULES.md).
- **Salida**: la IA degrada elegante sin la key; tools aisladas por org; tests.
- **Docs afectada**: AI_GUIDE.md (asistente) o BUSINESS_RULES.md (IA Nivel 2).

## 8. Release Loop
- **Objetivo**: publicar cambios a producción con seguridad.
- **Cerebro**: Fable (coordina) · Haiku (changelog/checks).
- **Entrada**: cambios mergeados y CI verde.
- **Pasos**: [`release_checklist.md`](../../.claude/checklists/release_checklist.md): pytest/tsc/build
  verdes, sin secretos, migraciones aplicadas, CHANGELOG actualizado → merge a `main` (squash) →
  Vercel (frontend) y Render (backend) deployan solos → smoke test (`/health`, logs `SLOW`, Sentry).
  Ver [`.claude/commands/deploy.md`](../../.claude/commands/deploy.md).
- **Salida**: producción estable; CHANGELOG y, si corresponde, tag/checkpoint.
- **Docs afectada**: CHANGELOG.md.

## 9. Architecture Loop
- **Objetivo**: revisar la arquitectura periódicamente y registrar decisiones.
- **Cerebro**: Fable/Opus.
- **Entrada**: una decisión estructural, deuda técnica acumulada, o cambio transversal.
- **Pasos**: evaluar impacto sistémico (SYSTEM_MAP) → registrar la decisión como ADR
  ([`adr_template.md`](../../.claude/templates/adr_template.md)) → actualizar
  [`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) y el registro de deuda en
  [`PROJECT_MEMORY.md`](../../.claude/memory/PROJECT_MEMORY.md).
- **Salida**: decisión documentada (ADR), deuda técnica registrada.
- **Docs afectada**: DECISIONS.md, ARCHITECTURE.md, PROJECT_MEMORY.md.

## 10. Product Loop
- **Objetivo**: alinear lo que se construye con el valor para el usuario.
- **Cerebro**: Fable (prioriza) · Haiku (leer roadmap/feedback).
- **Entrada**: una idea de feature, feedback real, o priorización del roadmap.
- **Pasos**: contrastar con [`PRODUCT_BIBLE.md`](../business/PRODUCT_BIBLE.md) y
  [`ROADMAP.md`](../../ROADMAP.md) → priorizar por valor/esfuerzo → definir alcance y criterios de
  aceptación ([`feature_template.md`](../../.claude/templates/feature_template.md)) → derivar al
  Feature Loop.
- **Salida**: feature priorizada y especificada, lista para el Feature Loop.
- **Docs afectada**: ROADMAP.md; PRODUCT_BIBLE.md si cambia el alcance del producto.

---

## Regla transversal

Todo loop respeta las **reglas de calidad permanentes** de `CLAUDE.md`: no duplicar lógica, no romper
compatibilidad, mantener multi-tenant, auditoría y trazabilidad contable, mantener tests y actualizar
la documentación afectada.
