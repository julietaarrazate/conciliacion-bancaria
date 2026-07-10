# Auditoría de Due Diligence (EKP): Cuadra — 2026-07-10

> Ejecutada con `generators/due-diligence.md` del repo de conocimiento EKP
> (julietaarrazate/ekp), por sesión T1 con gates corridos en vivo sobre este
> repo. Es una **re-auditoría**: diffea contra [`ENGINEERING_AUDIT.md`](../ENGINEERING_AUDIT.md)
> (junio 2026, v3.24). Versión auditada: **v3.28** (`dafc918`).

## 1. Resumen ejecutivo

Cuadra es un producto **maduro y en mejora continua**: desde la auditoría de
junio sumó +97 tests de backend (558, todos verdes, corridos en esta
auditoría), tests de frontend en CI (vitest, 40), y siguió puliendo UX. La
ingeniería no es el problema. El veredicto es **conditionally ready**: lista
para el uso actual, pero **tres bloqueadores operativos** — todos conocidos,
ninguno de código — la separan de venderse a clientes externos que pagan:
(1) infraestructura free-tier con cold start de ~30s, (2) restore de backup
nunca ensayado sobre datos financieros, (3) branch protection ausente con
auto-deploy a producción. Las 3 movidas de ahora: **pagar la infra (~USD
7–20/mes) + ensayar un restore completo + activar branch protection**. Todo
lo demás puede esperar a que eso esté. El detalle accionable está en §8.

## 2. Contexto y vara

- **Etapa declarada**: growth — multi-tenant en producción real, con
  organizaciones activas y objetivo de vender a estudios contables/financieras.
- **Decisión que esta auditoría alimenta**: qué mejorar primero para seguir
  puliendo con sesiones baratas (protocolo ultracode del propio repo).
- **Audiencia**: la propietaria (operadora técnica del repo vía IA).
- **Set crítico de etapa** (manda sobre el veredicto): seguridad, integridad
  de datos, operación — obligatorios con usuarios reales; acá además maneja
  **dinero de terceros**, lo que endurece integridad de datos.
- **Nivel de evidencia**: código y gates = **medido** (corridos acá: ruff
  limpio, pytest 558 ✅, tsc limpio, vitest 40 ✅, build ✅). Runtime
  (Render/Sentry/Neon) = **sin acceso desde esta sesión** → las bandas de
  performance, operación y costo quedan `provisional` (tope metodológico, no
  juicio negativo).

## 3. Mapa de sistema y producto

Backend FastAPI (39 routers — varios son agregadores delgados —, 27 modelos,
33+ servicios, 25 migraciones Alembic), frontend Vite SPA/PWA (~37 páginas,
code-splitting por ruta), Postgres Neon, deploy Render+Vercel con CI completo
(ruff+pytest+eslint+tsc+vitest+build). Módulos: conciliación multi-banco con
scoring + aprendizaje de patrones, cheques, pagos con OCR, caja,
liquidaciones, contabilidad de partida doble, 4 módulos de impuestos, ARCA
(construido, apagado a propósito), asistente IA (Gemini, opt-in), backups con
router de admin. Conspicuamente ausente: staging, E2E de flujos críticos,
branch protection, evidencia de restore ensayado. `ROADMAP.md` está
**desactualizado contra la realidad** (dice "solo Banco Macro" cuando el
multi-banco está hecho) — riesgo real en un repo operado por IA: una sesión
que lo lea planifica contra un estado falso.

## 4. Perfil de madurez

Bandas 0–4 con semántica de piso (se otorga la banda cuyos criterios se
cumplen TODOS). Nunca promedios. Δ = movimiento desde junio (escala distinta;
se reporta dirección, no número).

| Dimensión | Banda | Δ | Evidencia (citada) | Qué exige la banda siguiente |
|---|:-:|:-:|---|---|
| Arquitectura | 3 | = | Capas limpias (`app/routers` delgados, p. ej. `contabilidad.py` agregador; servicios sin HTTP/SQL); multi-tenant centralizado (`CLAUDE.md` §Multi-tenant) | Estado fuera del proceso (cachés/cuotas/schedulers) y modelo de escalado documentado |
| Seguridad | 3 | = | Aislamiento por `organizacion_id` verificado por muestreo en routers; `backup_admin.py:21` exige `require_superadmin`; rate-limit en auth; SECURITY.md | Tests sistemáticos de autorización por endpoint + runbook de rotación de secretos |
| Performance | 2 (provisional) | = | Cold start Render ~30s + Neon dormido (ENGINEERING_AUDIT §3, sin refutar); cachés en memoria se pierden por redeploy | Infra paga + números reales de Sentry/logs SLOW decidiendo optimizaciones |
| UX (incl. a11y) | 3 | ↑ | v3.28: labels humanos + estados vacíos guiados (`dafc918`); PWA probada en celular (PROBAR_EN_CELULAR.md) | A11y sistematizada (lint/checklist) y tests de UI de los flujos core |
| Testing | 3 | ↑ | **558 backend verdes medidos acá** (+97 desde junio); vitest 40 en CI; sin E2E | E2E de los 3 flujos críticos (login, extracto→conciliación, pagos) |
| CI/CD | 2 | ↓ | `ci.yml` corre ruff+pytest+eslint+tsc+vitest+build en cada push/PR, **pero el job de backend estaba roto en `main`**: instala solo `requirements.txt` y pytest vive en `requirements-dev.txt` → "No module named pytest" (descubierto en vivo: el CI de este mismo PR falló; fix incluido acá). Sin branch protection, el rojo pasó inadvertido | Fix mergeado + branch protection en `main` + staging o canary + runbook de rollback |
| Infraestructura | 2 | = | Free tier Render+Neon; keep-alive UptimeRobot como mitigación (CLAUDE.md §producción) | Plan pago, sin dormidas, con SLA declarable a clientes |
| Documentación | 4 | = | `/docs` 10 áreas + BUGS.md con causa raíz + CLAUDE.md operativo + memoria de proyecto; honestidad explícita ("Pendiente de revisar") | Poco: mantener la regla "todo cambio actualiza su doc" (ya institucionalizada) |
| Escalabilidad | 2 | = | Schedulers APScheduler en proceso + cachés en memoria (ENGINEERING_AUDIT §3) — single instance by design | Estado compartido externalizable (Redis o equivalente) cuando el tráfico lo pida |
| Mantenibilidad | 3 | = | ruff+eslint en CI; cero `any` implícitos que rompan tsc; convenciones escritas (API_RULES); quedan `skip`/`offset` legacy y `.btn-ghost` duplicado | Cerrar la doble fuente de DDL (Alembic vs safety-nets) y las inconsistencias registradas |
| Deuda técnica | 3 | = | Registrada, priorizada y honesta (ENGINEERING_AUDIT §4 + PROJECT_MEMORY §3) | Que los 2 ítems estructurales (DDL dual, estado en memoria) tengan fecha o riesgo aceptado explícito |
| Producto | 3 | ↑ | Suite amplia en uso real; v3.2x mejora continua de UX; pero `ROADMAP.md` desactualizado y pricing/legal de venta externa sin definir (el propio ROADMAP Fase 1 lo lista) | Roadmap veraz + pricing y términos definidos para clientes piloto |
| Operación y observabilidad | 2 (provisional) | = | Sentry cableado + logs SLOW + request-id (ENGINEERING_AUDIT §2); backups con router admin (`backup_admin.py`); **restore jamás ensayado** (sin evidencia en repo); bus factor 1 | Restore ensayado y documentado + alertas activas + runbook de incidentes |
| Costo y unit economics | 3 (provisional) | = | COSTEO.md dedicado; free tier ≈ $0; cuotas de IA administradas | Números reales de costo por organización cuando haya clientes pagos |
| Datos y analítica | 3 | = | Integridad fuerte: `Decimal`/`Numeric` en todo el dinero, partida doble idempotente e inmutable, auditoría de operaciones, endpoints de backfill controlados (BUGS.md) | Analítica de producto (uso por módulo/tenant) para priorizar con datos |

## 5. Veredicto de preparación

Compuesto por **mínimo sobre el set crítico** (seguridad=3, integridad de
datos=3, operación=**2 provisional**):

> **conditionally ready** — bloqueadores nombrados:
> 1. **Infra free-tier** (infraestructura=2): cold start ~30s es incompatible
>    con clientes que pagan; además Neon free duerme.
> 2. **Restore no ensayado** (operación=2): con datos financieros de
>    terceros, un backup sin restore probado es una hipótesis, no un backup.
> 3. **Branch protection ausente**: un commit directo con CI rojo
>    auto-deploya a producción (pendiente desde junio, sin evidencia de
>    cierre).

Para el uso actual (estudio propio + organizaciones que toleran la etapa), ya
opera y opera bien. Los bloqueadores gatean **venderla**, no usarla.

## 6. Fortalezas (prácticas a preservar)

- **Rigor financiero como práctica**, no accidente: dinero en `Decimal` punta
  a punta, asientos inmutables e idempotentes, correcciones vía endpoints de
  backfill auditados (no UPDATEs a mano).
- **Cultura de causa raíz**: BUGS.md registra patrón + fix + cómo no
  reincidir (fechas UTC-3, Decimal vs float) — es la práctica que evita pagar
  el mismo bug dos veces.
- **Degradación elegante por feature flag**: cada integración externa se
  apaga sola sin la env var. Mantenerla como regla para toda integración nueva.
- **Documentación honesta y viva** con discrepancias marcadas en vez de
  tapadas; +97 tests en un mes demuestra que la disciplina post-auditoría se
  sostuvo.
- **Protocolo de orquestación por costo de modelo** ya escrito en CLAUDE.md —
  esta auditoría lo usó y funciona.

## 7. Hallazgos (formato Review Engine: severidad S1–S4, esfuerzo E1–E3, escenario de falla)

Agrupados por causa raíz. Sin escenario de falla concreto no hay hallazgo.

**Causa raíz: operación por debajo de la madurez del código**
- **[S2·E1] Restore no ensayado.** Escenario: una migración destructiva o un
  borrado accidental sobre datos contables de un cliente; el backup existe
  pero el procedimiento de restore falla o tarda días por no estar probado →
  pérdida de datos financieros de terceros con responsabilidad legal (Ley
  25.326). Ruta: ensayo de restore completo documentado en
  BACKUP_Y_RECUPERACION.md (ítem de roadmap, requiere operadora).
- **[S2·E1] Free tier en producción.** Escenario: cliente pago abre la app a
  las 9:00, cold start de 30s+, percibe el producto como roto, churn. Ruta:
  Render Starter + plan Neon (decisión de gasto de la operadora — ya
  recomendado en junio, sigue abierto).
- **[S2·E1] Sin branch protection.** Escenario: push directo a `main` con
  tests rojos (humano o agente) → auto-deploy roto en producción con datos
  reales. Ruta: activar en GitHub Settings (5 minutos, operadora; los checks
  de CI ya existen y quedan como required). **El escenario ya ocurrió en
  versión leve**: ver el hallazgo siguiente.
- **[S2·E1, ✅ corregido en este PR] CI de backend roto en `main` sin que
  nadie lo note.** `ci.yml` instalaba solo `requirements.txt`; pytest vive en
  `requirements-dev.txt` → el paso "Tests" moría con "No module named
  pytest" en todo push/PR. Descubierto en vivo porque el CI de esta misma
  auditoría falló. Escenario materializado: el gate que debía proteger
  producción no corría ningún test, y sin branch protection el rojo no
  bloqueaba nada. Es la demostración empírica del bloqueador 3 del veredicto.

**Causa raíz: fuente de verdad divergente**
- **[S3·E2] Doble fuente de DDL** (Alembic + safety-nets idempotentes en
  `main.py`/`db_safety.py`). Escenario: un ambiente nuevo bootstrapeado por
  safety-nets difiere sutilmente del prod migrado → bug de integridad
  silencioso. Ruta: ya tiene acción sugerida en ENGINEERING_AUDIT §4
  (Alembic autoritativo + guard de idempotencia en CI); convertirla en tarea.
- **[S3·E1] ROADMAP.md desactualizado.** Escenario: una sesión IA (o un
  inversor) lee "solo Banco Macro" y planifica/valúa contra un producto que
  no es. En un repo operado por agentes, un doc falso es un bug operativo.
  Ruta: reescribirlo desde el estado real (tarea Haiku/Sonnet, 30 min).

**Causa raíz: cobertura desigual frontend vs backend**
- **[S3·E2] Sin E2E de flujos críticos.** Escenario: regresión de UI en
  extracto→conciliación (el corazón del producto) pasa CI (tsc/vitest no la
  ven) y llega a producción; se descubre a mano. Ruta: 3 specs Playwright con
  API mockeada (patrón ya probado en staffing-gastro PR #58 — reutilizable).

**Riesgo aceptado (explícito, revisar si cambia la escala)**
- **[S4·E2] Cachés/cuotas en memoria de proceso** — se resetean por
  redeploy/cold start; hoy autocurativo y proporcional al tráfico. Aceptado
  hasta señal real de carga (regla anti-R4 del propio repo). Igual criterio
  para PostGIS/Redis/outbox.

## 8. Roadmap de evolución (por etapas; cada ítem nombra la banda que sube)

**Desbloquear (esta semana — las 3 movidas del veredicto, todas E1):**
1. Infra paga (Render Starter + revisar plan Neon) → infraestructura 2→3,
   performance sale de provisional. *Operadora: decisión de gasto ~USD 7–20/mes.*
2. Ensayo de restore completo + documentar tiempos en
   BACKUP_Y_RECUPERACION.md → operación 2→3. *Operadora + una sesión guiada.*
3. Branch protection en `main` con los checks de CI required → CI/CD 3→4
   (junto con el ítem 5). *Operadora: 5 min en GitHub Settings.*

**Estabilizar (próximas 2–4 semanas, sesiones baratas):**
4. Reescribir ROADMAP.md desde la realidad v3.28 → producto 3→camino a 4. *Sonnet.*
5. E2E Playwright de login, extracto→conciliación y pagos (API mockeada) →
   testing 3→4. *Sonnet, patrón de staffing-gastro.*
6. DDL: Alembic autoritativo + guard de idempotencia de safety-nets en CI →
   mantenibilidad 3→4. *Opus (toca migraciones = lógica riesgosa, según el
   ruteo del propio repo).*

**Profesionalizar (cuando haya cliente piloto a la vista):**
7. Pricing + términos de servicio + AAIP (ROADMAP Fase 1 "Legal y comercial",
   sigue vigente) → producto 3→4. *Operadora + abogado; la IA prepara borradores.*
8. Runbook de incidentes + alertas de Sentry activas con datos reales →
   operación 3→4.

**Diferenciar (solo con señal real de carga):**
9. Estado fuera de proceso (Redis o equivalente) → escalabilidad 2→3.
10. Analítica de uso por módulo/tenant para priorizar features con datos →
    datos y analítica 3→4.

Camino crítico al próximo veredicto (`production-ready` para clientes pagos):
**1 → 2 → 3** — nada de código, todo operación. El resto acompaña.

## 9. Ruteo de artefactos

| Hallazgo | Artefacto | Estado |
|---|---|---|
| Restore no ensayado (S2) | Ítem 2 del roadmap + procedimiento en BACKUP_Y_RECUPERACION.md | ruteado (requiere operadora) |
| Free tier (S2) | Ítem 1 del roadmap (decisión de gasto) | ruteado (requiere operadora) |
| Branch protection (S2) | Ítem 3 del roadmap | ruteado (requiere operadora) |
| DDL dual (S3) | Ítem 6 — tarea para sesión Opus | ruteado |
| ROADMAP desactualizado (S3) | Ítem 4 — tarea para sesión Sonnet | ruteado |
| Sin E2E (S3) | Ítem 5 — tarea para sesión Sonnet | ruteado |
| Cachés en memoria (S4) | Riesgo aceptado explícito (§7) | aceptado |
| Lección para EKP | Intake en el repo EKP (evidencia runtime inaccesible desde sesiones remotas → bandas provisional; considerar paso de interrogación pidiendo acceso de solo lectura a paneles) | ruteado |

---

*Regenerable: otra sesión que corra `generators/due-diligence.md` sobre la
misma evidencia debe llegar a las mismas bandas. Próxima re-auditoría: al
cerrar los ítems 1–3, o en 3 meses, lo que ocurra primero.*
