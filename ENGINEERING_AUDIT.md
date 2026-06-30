# ENGINEERING_AUDIT — Cuadra

> Auditoría de ingeniería del repositorio, pensada como foto de madurez + hoja de ruta para que
> Cuadra pueda ser mantenido por un equipo profesional y por asistentes de IA durante los próximos
> años. Basada en el estado real del código y en las Fases 1–3 de profesionalización.
>
> Fecha: junio 2026 · Versión de producto: v3.24 · Complementa a
> [`.claude/memory/PROJECT_MEMORY.md`](.claude/memory/PROJECT_MEMORY.md) y [`docs/`](docs/README.md).

## 1. Estado general

Cuadra es un SaaS financiero multi-tenant en producción real (Vercel + Render + Neon), con un
conjunto de funcionalidades amplio y maduro: conciliación bancaria multi-banco, cheques, pagos/gastos
(con OCR), caja, liquidaciones, contabilidad de partida doble, cuatro módulos de liquidación de
impuestos, ARCA (construido, desactivado a propósito) y un asistente IA. ~25 modelos, ~38 routers,
~33 servicios, 20 migraciones, ~37 páginas frontend y **461 tests de backend**.

Tras las Fases 1–3 el repo pasó de "código de producción sin andamiaje de ingeniería" a tener:
documentación arquitectónica (`/docs`), CI, plantillas y políticas (`.github/`), comandos/checklists/
templates y memoria de ingeniería (`.claude/`), y un ciclo de trabajo + loops formalizados.

## 2. Fortalezas

- **Multi-tenant bien implementado**: aislamiento por `organizacion_id` validado en los endpoints; el
  modelo de permisos por rol está centralizado.
- **Rigor financiero**: dinero en `Decimal`/`Numeric`, partida doble con asientos idempotentes e
  inmutables, auditoría de operaciones.
- **Degradación elegante**: cada integración externa es un feature flag; sin la env var, la feature
  se apaga sola sin romper el sistema.
- **Cobertura de tests de backend sólida** (461) y self-contained (SQLite en memoria) → ahora corren
  en CI.
- **Documentación profunda y honesta** (`/docs`), con secciones "Pendiente de revisar" que registran
  discrepancias en vez de taparlas.
- **Resiliencia operativa pragmática**: safety-nets idempotentes en `main.py`, retry/keep-alive para
  el cold start, observabilidad (log de requests lentas + Sentry cableado).

## 3. Debilidades

- **Infra free-tier**: cold start de Render (~30s) y Neon que duerme → mayor fuente de latencia
  percibida. Es la palanca #1 (pasar Render a paid).
- **Sin tests de frontend**: solo `tsc` + `build`; la UI se valida a mano. Riesgo creciente con 37
  páginas.
- **Bus factor = 1**: autora única. La doc y los procesos de estas fases mitigan, pero el conocimiento
  operativo (claves, deploy, decisiones) sigue concentrado.
- **Superficie grande y en crecimiento**: 38 routers / 33 servicios. Sin disciplina de loops, el
  costo marginal de cada feature sube.
- **Estado en memoria del proceso**: cachés (cartera, sumas-saldo, balance) y cuotas del asistente IA
  se reinician en cada redeploy/cold start.
- **Inconsistencias menores** que erosionan mantenibilidad: `skip`/`offset`, dos paletas de verde y
  `.btn-ghost` duplicado, doble fuente de DDL (Alembic + safety-nets).

## 4. Deuda técnica

Registro vivo en [`PROJECT_MEMORY.md §3`](.claude/memory/PROJECT_MEMORY.md). Resumen por prioridad:

| Prioridad | Deuda | Acción sugerida |
|---|---|---|
| Alta | Cold start free-tier (latencia) | Render paid |
| Media | Sin tests de frontend | Vitest/Playwright en CI (smoke de flujos críticos) |
| Media | Doble fuente de DDL (puede divergir) | Alembic como autoritativo; safety-nets documentados como red |
| Baja | `skip`/`offset` inconsistente | **Convención fijada en `offset`** (API_RULES §4); legacy se migra oportunamente, no en masa |
| Baja | Design tokens duplicados (verde, `.btn-ghost`) | Unificar paleta y clases |
| — | ~~`mobile/` scaffold sin uso~~ | **RESUELTO**: eliminado (la app mobile es la PWA) |
| Baja | Cachés/cuotas en memoria | Evaluar persistencia si crece el tráfico |

> Áreas históricamente frágiles (regresiones repetidas): ver [`BUGS.md`](BUGS.md) —
> fechas UTC-3, Decimal vs float, compartir por WhatsApp, detección de banco, light mode.

## 5. Oportunidades de mejora

- **Branch protection** en `main` (exigir CI verde + PR) — cierra el loop que la Fase 2 dejó listo.
- **Observabilidad con datos reales**: una vez con Sentry + logs `SLOW` poblados unos días, priorizar
  performance con evidencia (no con auditorías estáticas, que en esta etapa fallaron varias veces).
- **Tests de frontend** sobre los flujos críticos (conciliación, pagos, compartir).
- **Resolver la doble fuente de DDL** y las inconsistencias de diseño para bajar carga cognitiva.
- **Linter/formatter en CI** (ruff/eslint) para consistencia automática.

## 6. Roadmap de ingeniería (no de producto)

1. **Inmediato**: activar branch protection; Render paid; mirar Sentry/SLOW con datos reales.
2. **Corto plazo**: tests de frontend (smoke), linter en CI, unificar paginación y design tokens.
3. **Mediano plazo**: decidir fuente única de esquema; evaluar cachés persistentes; eliminar o
   cobertura de tests sobre el motor de conciliación con fixtures reales anonimizados.
4. **Largo plazo**: si crece el equipo, CODEOWNERS por área + revisiones obligatorias; si crece el
   tráfico, mover cachés/cuotas fuera del proceso (Redis) y revisar el plan de Neon.

## 7. Nivel de madurez

Escala 1 (prototipo) – 5 (producto industrializado):

| Dimensión | Nivel | Comentario |
|---|---|---|
| Funcionalidad / producto | 4.5 | Amplio, en producción, con usuarios reales |
| Arquitectura backend | 4 | Capas claras, multi-tenant, partida doble |
| Calidad / tests | 3.5 | Backend fuerte; frontend con primeros tests de utils (fecha/monto) + vitest en CI |
| Documentación | 4.5 | Profunda y honesta tras Fase 1 |
| Procesos / tooling | 4 | CI con ruff + pytest + vitest + build, plantillas y loops; falta branch protection |
| Operación / infra | 3 | Funciona, pero free-tier y bus factor 1 |
| **Global** | **~4 / 5** | **Producto maduro; ingeniería recién profesionalizada — esta es la base para escalar** |

Lectura: Cuadra dejó de ser "prototipo veloz de autora única" y entró en territorio de proyecto
profesional. El cuello de botella para escalar ya no es el código, sino la **operación** (infra,
bus factor) y la **disciplina sostenida** (que estas fases instituyen).

## 8. Recomendaciones para escalar (próximos años)

1. **Institucionalizar el ciclo de trabajo y los loops** ([`docs/playbooks/LOOPS.md`](docs/playbooks/LOOPS.md))
   — orquestar por costo de modelo (leer con Haiku, razonar lo difícil con Opus) mantiene el costo
   bajo control a medida que crece la superficie.
2. **Medir antes de optimizar**: la lección recurrente de esta etapa es que las auditorías estáticas
   se equivocan; decidir con Sentry + logs.
3. **Reducir el bus factor**: la doc y los procesos ya ayudan; el siguiente paso es runbooks de
   operación (claves, deploy, recuperación) y, si entra gente, ownership por área.
4. **Subir el piso de calidad del frontend** (tests) antes de seguir sumando páginas.
5. **Mantener la documentación viva**: la regla "todo cambio actualiza su doc" es lo que evita que
   `/docs` se pudra y se vuelva ruido. El Documentation Loop existe para eso.

---

*Este documento es una foto. Reauditá cuando cambie algo estructural (infra, equipo, escala) y
actualizá el nivel de madurez y la deuda técnica.*
