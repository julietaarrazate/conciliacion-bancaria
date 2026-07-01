# PROJECT_MEMORY — Memoria de ingeniería de Cuadra

Conocimiento **durable** del proyecto: principios, deuda técnica conocida, decisiones permanentes y
lecciones aprendidas. No duplica la documentación: apunta a la fuente de verdad.

- Orientación rápida: [`CLAUDE.md`](../../CLAUDE.md)
- Referencia profunda: [`docs/README.md`](../../docs/README.md)
- Historial de versiones: [`CHANGELOG.md`](../../CHANGELOG.md) · Bugs recurrentes: [`BUGS.md`](../../BUGS.md)
- Decisiones (ADR): [`docs/adr/DECISIONS.md`](../../docs/adr/DECISIONS.md)

---

## 1. Principios del proyecto

1. **Fidelidad financiera ante todo**: dinero en `Decimal`, nunca acreditar de más, inmutabilidad de
   lo presentado/cerrado. Un falso positivo en conciliación es peor que un faltante.
2. **Multi-tenant estricto**: una organización jamás ve datos de otra. El aislamiento se aplica en
   cada endpoint (`org_id` + `can_switch_org`).
3. **Degradación elegante**: cada integración externa es un feature flag; sin la env var, la feature
   se apaga sola, no rompe el sistema.
4. **Aditivo sobre Org A**: `organizacion_id=1` es producción real; solo cambios aditivos.
5. **La documentación describe el código tal como está**, no como debería ser. Si cambia el código,
   se actualiza el doc (y su sección `Pendiente de revisar`).
6. **Verificable**: nada se da por terminado sin `pytest` + `tsc --noEmit` + `build` en verde.

## 2. Convenciones (resumen — detalle en /docs)

| Tema | Regla | Fuente |
|---|---|---|
| Dinero | `Decimal`/`Numeric(12,2)`, nunca `float` | [DATABASE_RULES](../../docs/database/DATABASE_RULES.md), BUGS.md |
| Fechas de negocio | `hoy_art()`/`now_art()`, `localIsoDate()` (no UTC) | BUGS.md |
| API | `org_id` + permisos en 3 capas + paginación `{items,total}` | [API_RULES](../../docs/api/API_RULES.md) |
| Esquema | Migración Alembic + safety-net idempotente en `main.py` | [DATABASE_RULES](../../docs/database/DATABASE_RULES.md) |
| Contabilidad | Partida doble, asientos idempotentes e inmutables | [ACCOUNTING_ENGINE](../../docs/architecture/ACCOUNTING_ENGINE.md) |
| Commits | Autoría `Julieta Arrazate <julietaarrazate@gmail.com>` | CLAUDE.md |

## 3. Deuda técnica conocida

Registro vivo. Cada doc de `/docs` tiene además su propia sección `## Pendiente de revisar`.

| # | Deuda | Riesgo | Estado |
|---|---|---|---|
| D-1 | **Paginación inconsistente**: conviven `skip` y `offset` según el router | Bajo (confunde, no rompe) | **Convención fijada en `offset`** ([API_RULES §4](../../docs/api/API_RULES.md)); los `skip` legacy se migran oportunamente, no en masa |
| D-2 | **Design system**: `.btn-ghost` con dos definiciones y dos paletas de verde | Bajo (cosmético) | **Verde de la app unificado** en un token mode-aware (`--ml-green`: claro `#16A34A` / oscuro `#4ADE80`); quedan pendientes solo la colisión `.btn-ghost` y el verde propio de la landing |
| D-3 | **Doble fuente de DDL**: esquema en migraciones Alembic **y** en safety-nets (`app/db_safety.py`) | Medio (pueden divergir) | **Por diseño** (los safety-nets cubren si Render no corre Alembic). Extraídos a `db_safety.py` (importable) + guard en CI (`test_db_safety.py`) que exige que **toda** sentencia sea idempotente y sin índices duplicados; documentar al editar |
| D-4 | **Cachés/cuotas en memoria del proceso** (cartera, sumas-saldo, balance, cuota del agente IA) se reinician en cada redeploy/cold start | Bajo | Aceptado (TTL corto); revisar si se necesita persistencia |
| D-5 | **Free tier**: cold start de Render (~30s) y Neon que duerme | Alto (latencia percibida) | Mitigado (UptimeRobot + retry); se resuelve pasando Render a paid |
| D-6 | ~~`mobile/` scaffold React Native sin uso~~ | Bajo | **RESUELTO**: eliminado (la app mobile es la PWA). Si se retoma nativo, se arranca limpio. |
| D-7 | Cobertura de frontend acotada (utilidades + smoke de componentes; sin E2E) | Bajo-Medio | **Parcial**: vitest + Testing Library (jsdom) con smoke tests de componentes (`CuadraLogo`, `Skeleton`, `DonutChart`) + tests de utilidades (`monto`, `fecha`). Falta E2E de flujos críticos (Playwright) |
| D-8 | **Cadena Alembic desincronizada del esquema real** (jul 2026): `env.py` importaba clases inexistentes → `upgrade`/`stamp` fallaban → Alembic no corría en prod (el esquema lo sostienen `create_all` + safety-nets). `001` es stamp baseline (no construye desde cero); 007–009 referencian tablas ya dropeadas | Medio | **env.py corregido** (importa módulos, no clases). Camino real verificado sobre PG (sella 020, 44 tablas). **Resuelto (decisión jul 2026)**: `_run_alembic` ahora **solo hace `stamp head`** (no `upgrade`) → Alembic refleja la realidad sin correr la cadena derivada; `create_all`+safety-nets son la fuente de verdad. Re-baseline = mejora futura opcional |

> Áreas históricamente frágiles (ver [`BUGS.md`](../../BUGS.md)): fechas UTC-3, Decimal vs float,
> compartir por WhatsApp (mobile), detección de banco, light mode, parseo de montos argentinos,
> `useEffect` con deps incompletas.

## 4. Módulos existentes

Mapa completo en [`docs/architecture/SYSTEM_MAP.md`](../../docs/architecture/SYSTEM_MAP.md). En una
línea: conciliación bancaria multi-banco, cheques, pagos/gastos (con OCR), caja, liquidaciones,
contabilidad de partida doble, 4 módulos de impuestos (IVA, Monotributo, IIBB, Sueldos/F931), ARCA
(facturación electrónica, construido y desactivado a propósito), asistente IA (Gemini).

## 5. Módulos / trabajo futuro

- **Intake Exportador de Servicios** — último módulo pendiente del plan de impuestos.
- **Activar R2** (storage de fotos) e **IA Nivel 3** (predicción con datos reales).
- **Activación de ARCA** cuando haya un cliente real (homologación → producción).
- Ver [`ROADMAP.md`](../../ROADMAP.md) y la sección "Pendiente para próximas sesiones" de CLAUDE.md.

## 6. Decisiones permanentes

Registradas como ADR en [`docs/adr/DECISIONS.md`](../../docs/adr/DECISIONS.md). Las más estructurales:
integración propia con ARCA (sin proveedor), `Decimal` para dinero, soft delete, config por
organización en JSON, multi-tenant vía `organizacion_id`, PWA en vez de app nativa, safety-nets
idempotentes además de Alembic.

## 7. Lecciones aprendidas

- **Medir, no auditar**: las auditorías estáticas se equivocaron varias veces (ej. "optimizar" algo
  ya optimizado, sugerir un índice sobre una columna inexistente). Por eso existe el log de requests
  lentas + Sentry: decidir performance con datos reales.
- **Reproducir antes de arreglar**: los bugs reales (Decimal/float al re-subir, fuga de extractos
  entre orgs, NameError en aprendizaje) se confirmaron reproduciendo con archivos/escenarios reales,
  no asumiendo.
- **El `except` genérico miente**: enmascarar errores como "verificá el formato" escondió bugs reales.
  Loguear la causa real (y no tragarse excepciones) ahorró horas.
- **Soft delete + índices únicos** interactúan mal: un registro borrado puede seguir ocupando un
  índice único; los índices parciales deben excluir `deleted_at`.
- **Mobile es su propio mundo**: compartir por WhatsApp, canvas, datalist y activación de usuario se
  comportan distinto; probar en celular real.

## Cómo mantener este archivo

Actualizalo cuando: se salde o detecte deuda técnica, se tome una decisión permanente, o se aprenda
una lección que valga para el futuro. Es la memoria que un equipo (humano o IA) hereda.
