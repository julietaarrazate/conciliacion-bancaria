# Changelog — Sistema de Conciliación Bancaria

Historial detallado de versiones. CLAUDE.md tiene la orientación general del proyecto y el estado
actual; este archivo es el changelog completo (no se carga automáticamente en cada sesión).

---

### v3.27 — Estandarización universal de planillas de clientes (jul 2026)

Cada cliente manda su planilla en un formato distinto (columnas, orden, headers en filas
distintas). Antes el parser buscaba "monto"/"importe" solo en las filas 1-5, tomaba el primer
match y caía a un fallback hardcodeado de Banco Macro → degradaba en silencio a "sin datos".
Ahora hay un **embudo de estandarización** que normaliza cualquier planilla al esquema canónico
`{monto, cuit, titular, referencia, fecha}` que ya consume el motor de conciliación (**el motor no
se tocó** — cero riesgo sobre el matcheo).

- **Pipeline de 3 capas** (`services/planilla_mapper.py`, `estandarizar_planilla`): 1) **perfil**
  por cliente (mapeo guardado + fingerprint de headers → si coincide, parsea directo sin preguntar);
  2) **heurística** mejorada (detecta la fila de headers escaneando 1..15, soporta offset de columna,
  diccionario de sinónimos normalizado, y **valida el contenido** de cada columna — monto numérico,
  CUIT 7-11 dígitos, titular no-constante para evitar la trampa "Cliente=constante", corta tras 3
  filas sin monto contra planillas con 1M de filas vacías); 3) **IA (Gemini)** solo si la heurística
  no llega al umbral (degradación total sin API key). Montos en Decimal.
- **Perfil aprendido**: nueva columna `Cliente.mapeo_planilla` (JSON) — la primera vez que se
  confirma/corrige el mapeo de un cliente se guarda; las próximas cargas del mismo formato parsean
  solas. Migración 022 + safety-net.
- **Endpoints**: `POST /planillas/preview` (detecta sin persistir → alimenta el modal) y
  `POST /planillas/upload` extendido con `mapeo` opcional (corrección manual, se guarda como perfil)
  + `deteccion` en la respuesta. Compatible: el upload sin `mapeo` sigue funcionando.
- **Frontend**: `ColumnMapperModal` — al cargar una planilla, si la detección es de alta confianza
  o de perfil, sube directo (sin fricción); si duda, muestra un modal con las primeras filas y un
  desplegable por columna ("Usar como: Monto/CUIT/Titular/Referencia/Fecha/Ignorar") para confirmar
  o corregir. Avisa cuántas filas detectó (no más filas desaparecidas en silencio).
- Probado contra **3 formatos reales** (Tucu/Green en Org A/Macro, Dani en Org Prueba/Comercio):
  los tres parsean con la heurística sola a confianza 1.00 (header en fila distinta, offset de
  columna, trampa del cliente-constante, 1M de filas vacías — todo resuelto). Multi-tenant: el
  perfil vive en `Cliente` (scopeado por org). **20 tests nuevos** (500 backend + 31 frontend).
- **Detección de fila de total/resumen**: algunos clientes agregan al final de la planilla una fila
  con el total (suma de los movimientos). Antes se contaba como un movimiento más (sin identidad →
  "sin datos"). Ahora `_detectar_totales` la reconoce (por etiqueta "total/suma/…" o porque su monto
  ≈ suma de los movimientos, y solo en filas trailing sin CUIT → no borra movimientos reales), la
  **excluye** de los movimientos, la guarda como `Planilla.total_declarado` y calcula el **cuadre**:
  la UI muestra "Total de la planilla" (suma de movimientos) vs. "Declarado por el cliente" con un
  badge ✓ Cuadra / ⚠ Difiere en $X. Verificado con Tucu real (8 mov + total 5.089.000 detectado
  correctamente). Migración 023 + safety-net. **+6 tests** (506 backend + 33 frontend).

- **Capa de diagnóstico de conciliación** (por qué las filas no matchean, sin tocar el matcher —
  Org A intacta): tras conciliar, `diagnostico_conciliacion` calcula y devuelve (aditivo, read-only)
  (a) **`banco_trae_identidad`**: si el extracto trae nombre/CUIT del que pagó (muchos bancos, ej.
  Comercio, solo dicen "CRÉDITO POR TRANSFERENCIA" → conciliación solo por monto); (b) **cobertura
  de montos**: cuántos montos de la planilla aparecen en el extracto ("12 de 33"); (c) **solape de
  fechas** planilla vs. período del extracto. El frontend (`DiagnosticoPanel`) lo muestra en el
  resultado: "este banco no trae identidad → solo por monto", "faltan N montos, ¿extracto correcto?",
  "las fechas no coinciden". Resuelve el falso "está roto" cuando en realidad el banco no da el dato.
  Verificado con datos reales de Dani/Comercio (banco sin identidad, 12/33). Además se persiste la
  **fecha de pago** de la planilla (`PlanillaRow.fecha`, antes se descartaba; migración 024) para el
  cálculo del período. **+10 tests** (536 backend + 37 frontend).

- **Archivar extractos (cierre de período)**: `archivado_at` en ExtractoBancario (migración 025;
  distinto de borrar) — un extracto archivado conserva TODO lo conciliado (consultable y exportable
  por id: movimientos, filtros por cliente/fecha y export siguen funcionando), pero sale del listado
  por defecto (`GET /extractos?incluir_archivados=true` los muestra con flag `archivado`) y rechaza
  nuevos UM (409 con mensaje claro). Endpoints `PATCH /extractos/{id}/archivar|desarchivar`
  (permiso `delete_records`, auditados, idempotentes). UI: botón "📦 Archivar / ↩️ Reabrir" + badge
  en Extractos. Resuelve "el extracto se pone pesado": cerrás el mes y subís uno nuevo del mismo
  banco. De paso: `ExtractoListItem` ahora declara `banco` (bug preexistente: el response_model lo
  filtraba y el frontend nunca lo recibía). **+4 tests** (558 backend).

- **UX para usuarios nuevos** (de una auditoría de fricciones como "usuario que entra por primera
  vez"): estados de conciliación con labels humanos en toda la UI vía `utils/status.ts::statusLabel`
  ("ok"→"Acreditado ✓", "no está"→"No encontrado ✕", "ambiguo (…)"→"Ambiguo — elegir a mano", etc.;
  los valores de API no cambian, solo lo que se muestra) + leyenda de estados en el panel de
  planilla; "UM" explicado inline (Últimos Movimientos, con tooltip); botón "🗑 UM"→"🗑 Limpiar UM";
  estado vacío del resultado con los 3 pasos en vez de "Esperando carga…"; filtros de monto
  "Desde $ / Hasta $". **+3 tests** (40 frontend).

---

### v3.26 — Liquidación REAL de IVA con "Mis Comprobantes" de ARCA (jul 2026)

Quinto módulo del plan de liquidación de impuestos. Complementa la *proyección* de IVA (v3.19,
que estima desde asientos internos): acá se liquida con los comprobantes oficiales que ARCA
entrega al contador (no hay API pública; el Excel "Mis Comprobantes" es la vía estándar).

- **Importación de comprobantes** (`mis_comprobantes_parser.py`): parser determinístico del Excel
  "Mis Comprobantes Emitidos/Recibidos" de ARCA (título fila 1, headers fila 2). Extrae fecha,
  tipo, PV, número, CUIT/denominación de la contraparte (receptor si emitido, emisor si recibido),
  neto gravado, Total IVA e Imp. Total + detalle por alícuota. Probado contra archivos reales.
- **Modelos** (`iva_liquidacion.py`): `ComprobanteIva` (staging re-importable, dedup por
  org+dirección+tipo+PV+número+CUIT, flag `incluido` para depurar) y `LiquidacionIva` (snapshot
  mensual, único por org+período). Ambos multi-tenant (`organizacion_id` NOT NULL).
- **Lógica fiscal** (`iva_liquidacion_service.py`): débito = Σ IVA emitidos incluidos, crédito =
  Σ IVA recibidos incluidos, las notas de crédito restan. Posición del período vs. **saldo técnico
  a favor arrastrado** (se auto-hereda del período anterior; solo compensa IVA). Retenciones +
  percepciones + **saldo de libre disponibilidad** (aplicable a otros impuestos) cancelan el saldo
  a pagar. Técnico y libre disponibilidad se llevan **separados** (art. 24). Todo en Decimal.
- **Router** (`/iva/comprobantes/*` + `/iva/liquidacion/*`): importar, listar+totales, toggle
  incluir/excluir, borrar, calcular (upsert), historial, presentar (inmutable). Permisos en 3
  capas: `view_accounting` (leer) / `manage_finance` (importar/depurar/calcular) / `admin_accounting`
  (presentar). Auditoría en cada acción.
- **Frontend** (`Iva.tsx`): tabs "Comprobantes" (importar ventas/compras por separado, tabla con
  toggle incluir/excluir, totales en vivo) y "Liquidación" (cascada débito→crédito→técnico→
  ret/perc→libre→a pagar) + historial. Retenciones/percepciones por carga manual (falta el
  formato de export de ARCA para automatizar).
- **14 tests** (parser sobre Excel real, dedup, toggle, herencia de saldo técnico entre períodos,
  NC que resta, libre disponibilidad, presentada→409, aislamiento multi-tenant). Total: 480 backend.

---

### v3.25 — Profesionalización de ingeniería + hardening (jun–jul 2026)

Sesión de calidad (no features de negocio): consolidar el sistema como producto mantenible.

- **Base de documentación `/docs`** (Fase 1): 21 docs + índice `README.md` cubriendo arquitectura,
  negocio, API, BD, seguridad, UX, playbooks (agregar módulo/endpoint/banco/parser/reporte) y ADR.
  Cada doc documenta el código tal como está y anota discrepancias en su sección "Pendiente de revisar".
- **Andamiaje `.claude/` + `.github/`** (Fase 2): comandos (`/analyze`, `/bug`, `/feature`,
  `/refactor`, `/review`, `/release`, `/deploy`, `/docs`), checklists, templates, memoria de deuda
  técnica (`PROJECT_MEMORY.md`); CI (backend ruff+pytest, frontend eslint+tsc+vitest+build),
  Dependabot, CODEOWNERS, plantillas de PR/issue, `SECURITY`/`CONTRIBUTING`/`SUPPORT`.
- **Ciclo de trabajo como Software Architect** (Fase 3): CLAUDE.md formaliza el ciclo obligatorio
  escalado por tamaño de cambio + ruteo por costo de modelo; `ENGINEERING_AUDIT.md` (madurez ~4/5).
- **Fixes de producción**: extractos al org correcto + aislamiento multi-tenant, re-subida tras
  borrar (índice único excluye soft-deleted, migración 020), número de orden por extracto/org,
  Decimal vs float en re-upload, selector de bancos, compartir foto de OP por WhatsApp.
- **Performance**: N+1 en historial/contabilidad (selectinload), exports paginados, cachés TTL,
  lazy-load Sentry, logging de requests lentas (`SLOW`, header `X-Process-Time`).
- **Deuda técnica saldada**: ruff, eslint (config sobria + react-hooks), `parseMonto`/`fecha`
  consolidados con tests, convención de paginación fijada en `offset`, `mobile/` eliminado.
- **Verde de marca mode-aware**: un token `--ml-green` (claro `#16A34A` / oscuro `#4ADE80` "Matrix").
- **Tests de frontend** (Testing Library + jsdom): smoke de `CuadraLogo`/`Skeleton`/`DonutChart`.
- **Guard de idempotencia del safety-net DDL**: lista extraída a `app/db_safety.py` + test que
  exige `IF NOT EXISTS`/`IF EXISTS` en toda sentencia (evita crash del 2º boot en Render).
- Estado de tests: **465 backend + 25 frontend**.

---

## Features implementadas (estado actual — v3.12.1)

- Conciliación bancaria multi-extracto con motor de scoring
- Carga masiva con auto-conciliar al subir planillas
- Export Excel contador + PDF cierre mensual + PDF estado de cuenta por cliente
- Búsqueda global ⌘K (clientes, planillas, movimientos, cheques)
- Token público de cliente — link sin auth por 7 días (`/p/:token`)
- Web push notifications — cron 10:00 ART
- Módulos: Cheques, Pagos/Gastos, Caja, Órdenes de Pago, Liquidaciones, Contabilidad
- Resumen ejecutivo mensual + Estado de cuenta por cliente + Flujo de caja
- Soft delete + papelera de reciclaje + reversión contable
- Backup diario por email + export JSON completo
- Recuperación de contraseña por email
- Bloqueo PIN + biometría (WebAuthn) + ConfirmDialog global
- Share target: recibir archivos desde WhatsApp/Galería
- **Aislamiento multi-org completo**: todos los reportes y módulos respetan org seleccionada
- **Aritmética exacta**: columnas financieras en `Numeric(12,2)` (migración 007); JSON encoder Decimal transparente
- **Validaciones Pydantic**: `monto > 0` en cheques y pagos/gastos; CUIT validado al crear cliente
- **Soft-delete hermético**: planillas eliminadas excluidas de stats, insights, liquidaciones y conciliaciones
- **Seguridad hardening**: `/auth/register` requiere superadmin; CORS con métodos/headers explícitos;
  `/contabilidad/stats` autenticado; libro mayor valida org; OP compartir valida org
- **Páginas legales**: `/privacidad` y `/terminos` públicas (Ley 25.326 Argentina)
- **Suite de tests**: 124 tests (29 nuevos en `test_audit_fixes.py`)
- **Storage S3/R2 con fallback**: `app/services/storage.py` sube fotos a S3-compatible si las env vars
  `S3_ENDPOINT/S3_BUCKET/S3_ACCESS_KEY/S3_SECRET_KEY/S3_PUBLIC_URL` están seteadas; si no, mantiene base64 en DB
- **Org isolation completa**: POST `/caja/op/registrar`, PUT `/caja/arqueo/hoy` y GET `/caja/op/exportar-eft`
  ahora aceptan `org_id` para que superadmin escriba/lea en la org seleccionada
- **Landing page pública** (`/`): hero, features, seguridad, FAQ, comparativa, pricing, contacto WhatsApp;
  Fraunces italic en títulos, menú hamburguesa mobile, secciones siempre visibles en mobile
- **Fix conciliación Decimal**: `parse_importe` y `montos_iguales` ahora soportan `Decimal` (SQLAlchemy
  Numeric); antes todas las filas salían "faltan datos" tras la migración 007
- **Plan de cuentas**: sub-cuenta `1-1-1-3-1 Banco Macro` bajo `1-1-1-3 Banco`; PLAN_PATCH idempotente
  agrega cuentas nuevas en cada deploy sin romper instalaciones existentes
- **Renumeración de movimientos**: al borrar un movimiento duplicado, el `orden` de los siguientes se
  decrementa automáticamente (-1 shift); `orden` es un contador secuencial global (NO es número del banco),
  el más alto = el más reciente. Import asigna `max_global + (n-i)`; UM merger continúa desde `max_orden`.
- **Boton Borrar UM**: en `/movimientos`, elimina el último lote UM y desvincula planillas afectadas
  (status queda "ok", `orden_movimiento_acreditado` queda NULL). Al re-subir el UM las planillas
  se re-concilian normalmente o el export usa fallback automático.
- **Export planilla robusto**: si una fila "ok" tiene el link al movimiento roto (FK NULL), el export
  busca el movimiento por monto + cliente en el extracto y rellena igual todas las columnas. Fallback
  a `row.fecha_acred` para la columna Fecha acred.
- **Comisión en liquidaciones**: al generar una liquidación se puede elegir 1.5% / 1.8% / 2% (presets)
  o ingresar un % manual. Si se deja vacío usa el default de la org (1.5%). Aplica a todos los clientes.
- **Comisión por cliente**: campo `porcentaje_comision` en modelo `Cliente` (migración 008, Numeric 5,4).
  Chip inline editable en `/clientes` — muestra `% —` (gris) o `2%` (ámbar). Prioridad al generar liq:
  override manual del form > % propio del cliente > default de la org.
- **Comisión por ítem (v3.5)**: `Planilla` y `Cheque` tienen su propio `porcentaje_comision` (Numeric 5,4).
  Safety net en `main.py` agrega ambas columnas con `ADD COLUMN IF NOT EXISTS`. Cadena de herencia:
  1. Al subir planilla → hereda `cliente.porcentaje_comision` automáticamente.
  2. Al conciliar → si la planilla no tiene %, hereda del cliente.
  3. Al crear cheque → selector de cliente pre-llena el % (editable antes de guardar).
  4. Liquidaciones calcula comisión ítem por ítem (pct propio → fallback del form → 0).
  5. Liquidaciones solo incluye TT (planillas). Cheques se gestionan en su módulo.
- **Renombrar y fusionar clientes**: `PUT /clientes/{id}/renombrar` cambia nombre y propaga a movimientos.
  `POST /clientes/{id}/fusionar` reasigna planillas+movimientos al cliente destino y elimina el origen.
  UI en `/clientes`: botones ✏️ y 🔀 visibles solo en desktop (`hidden md:inline-flex`).
- **Normalización nombres de clientes**: primera letra mayúscula; búsqueda `ilike` en crear cliente,
  subir planilla y caja — "green" y "Green" son el mismo cliente.
- **Fix botón ⬇️ Excel en Historial**: endpoint `/planillas/{id}/download` tenía NameError (`_` vs
  `current_user`) → 500 sin exportar. Corregido. Botón `📁 Exportar` en fila de planilla exporta el
  detalle completo (reemplazó el Excel global que era redundante).
- **Borrar liquidaciones borrador**: endpoint `DELETE /liquidaciones/{id}` + botón 🗑️ en `/liquidaciones`
  visible solo para estado "borrador". Permite re-generar con distinta comisión.
- **Fix liquidaciones período**: filtra por `PlanillaRow.fecha_acred` (no `fecha_carga`); fallback a
  `fecha_carga` cuando `fecha_acred` es NULL; maneja FK de movimiento roto o borrado.
- **Fix auditoria Decimal**: `registrar_log` fallaba con TypeError al guardar `Decimal` en JSON.
  `_serializable()` en `auditoria.py` convierte recursivamente Decimal→float antes de persistir.
- **Safety net startup**: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para `clientes.porcentaje_comision`,
  `planillas.porcentaje_comision` y `cheques.porcentaje_comision` — evita crashes si Alembic falla.
- **Responsive fixes**: Liquidaciones mobile — números usan `text-xs md:text-sm` + `truncate` + tabla
  con `overflow-x-auto`. Clientes mobile — botones ✏️/🔀 ocultos en mobile para que se vea el nombre.
- **Diseño unificado**: header/sidebar usan `bg-ml-blue` (Linear purple-blue #5E6AD2) en light mode
  en lugar del amarillo previo. `btn-yellow` también usa `bg-ml-blue` en light mode. Dark mode sin cambios.

### v3.6 — Contabilidad automática + Cuentas Corrientes (mayo 2026)

- **Asientos automáticos al importar UM**: Banco Macro (1-1-1-3-1) D / No identificado (2-1-1-1) H.
  Modo `agrupado` (un asiento por lote, default) o `individual` (uno por movimiento), elegible desde
  `/movimientos`. Config por org: `modo_asiento_um`. Al borrar lote UM → `reversar_asientos()` (deja
  asiento original + reverso, trazabilidad completa). En `services/motor_contable.py`.
- **Reclasificación al conciliar**: No identificado (2-1-1-1) D / Cliente X (2-1-2-X) H. Se dispara en
  `conciliar_planilla()` cuando `mov.source == "um"` y hay `cliente_id`. Modulo `um_reclass`.
- **Cuenta contable por cliente (1:1)**: `Cliente.cuenta_contable_id` (FK a `plan_cuentas`, safety net
  `ADD COLUMN IF NOT EXISTS`). `_get_o_crear_cuenta_cliente()` resuelve: cuenta vinculada → adopta por
  nombre bajo 2-1-2-0 → crea la próxima 2-1-2-X. NUNCA crea entidades Cliente desde movimientos.
- **Backfill de cuentas al arrancar**: vincula clientes existentes a cuentas por nombre normalizado
  (`unicodedata.normalize NFKD`); sin match claro → queda sin vincular (solo log). Idempotente. En `main.py`.
- **Módulo Contabilidad — tab 🔗 Clientes**: vinculación manual cliente↔cuenta. `GET /contabilidad/clientes-cuentas`,
  `PUT /contabilidad/clientes/{id}/cuenta` (409 si la cuenta ya está tomada — 1:1), `POST .../cuenta/crear`.
  Botón **"+ Crear cuentas faltantes"** → `POST /contabilidad/clientes/cuentas/crear-faltantes` crea/vincula
  la cuenta de todos los clientes sin cuenta (adopta por nombre, no duplica).
- **Cuentas Corrientes = MÓDULO PROPIO** (`/cuentas-corrientes`, permiso `manage_finance`, ícono banco en nav).
  Es el mismo componente `Contabilidad.tsx` con prop `modo="ctacte"`. Vista derivada de asientos (NO genera).
  Cartera global (`GET /contabilidad/cuentas-corrientes`: saldo, último mov, estado deudor/acreedor/equilibrado/
  sin_actividad) + detalle por cliente (`GET /contabilidad/cuenta-corriente`: timeline con filtros Banco/TT/
  Cheques/Ajustes, débito/crédito/saldo, links a planilla/movimiento). Botón "Cta. cte." en `/clientes`
  (ícono banco, deep-link `/cuentas-corrientes?cc=<id>`).
- **Backfill cuentas corrientes desde lo ya conciliado**: botón **"↻ Reconstruir desde conciliaciones"**
  en `/cuentas-corrientes` (solo `admin_accounting`). `POST /contabilidad/backfill-cuentas-corrientes`
  (soporta `?dry_run=true` para previsualizar conteo). Por cada fila de planilla conciliada (status ok)
  de un cliente con cuenta, genera asiento NETO **Banco Macro (D) / Cliente (H)** (modulo `cc_inicial`).
  Se eligió el neto Banco/Cliente para NO dejar "No identificado" en negativo. Idempotente: saltea filas
  con `um_reclass` (flujo normal) o `cc_inicial` previo. **ORDEN DE USO: 1) "+ Crear cuentas faltantes"
  → 2) "↻ Reconstruir desde conciliaciones".** El extracto solo dice que entró plata; la planilla
  conciliada identifica al cliente → por eso el backfill recorre conciliaciones, no el extracto crudo.
- **Permisos en 3 capas** (reemplaza el `view_accounting` monolítico):
  - `view_accounting` — lectura contable formal: Libro diario, Mayor, Sumas y saldo, Balance.
  - `manage_finance` — operación financiera diaria: Cuentas Corrientes.
  - `admin_accounting` — config estructural: Plan de cuentas, Reglas, vinculación cliente↔cuenta, backfill.
  - Mapeo: ADMIN = las 3 · OPERADOR = manage_finance + view_accounting · REVISOR = view_accounting ·
    AUDITOR = view_accounting + manage_finance. Definido en `store/auth.ts` y `middleware/auth.py`.
    Tabs de `/contabilidad` filtradas por permiso; guards `require_permission` en backend.
- **Borrar OP en Caja**: `DELETE /caja/op/{op_id}` (ícono 🗑️ por OP del día, deshabilitado si arqueo
  cerrado). Reversa el asiento `caja_op`, repone denominaciones físicas al arqueo y registra la baja.
- **Fix estado de cuenta Decimal×float**: `total_conciliado` (Numeric 12,2 = Decimal) se convertía a float
  antes de multiplicar por % comisión; sin eso lanzaba TypeError → 500 en clientes con filas conciliadas.
- **Mobile clientes**: se ocultó la flecha gris ▼ de desplegar (tocar el cliente ya despliega).
- **Landing**: FAQ dice "ARCA" en vez de "AFIP".
- **Modulos de asiento (referencia para cta.cte.)**: `um_lote`/`um_mov` (import UM), `um_reclass` (reclasif.),
  `cc_inicial` (backfill histórico Banco/Cliente), `planilla`/`planilla_comision` (TT), `cheque_carga`/
  `cheque_rechazo`, `pago`, `caja_op`/`caja_efectivo`, `*_reverso` (reversos). La cta.cte. del cliente lee
  los `AsientoDetalle` que tocan su `cuenta_contable_id`.

### v3.7 — Rol contador de prueba + login por aprobación (mayo 2026)

- **Rol `CONTADOR`** (RoleEnum backend + UserRole frontend): opera (sube, concilia, finanzas,
  liquidaciones) y ve contabilidad + auditoría en solo lectura. Permisos:
  `upload_files, reconcile, manage_finance, view_accounting, view_audit`. NO ve Usuarios/Orgs/
  Papelera/Actividad. El panel Actividad es cross-org de superadmin → queda fuera.
- **Permiso `delete_records`** (nuevo): solo ADMIN (+ superadmin) lo tienen — el Operador lo tuvo originalmente pero se quitó en v3.11 por principio de menor privilegio. Todos los
  DELETE destructivos pasaron a `require_permission("delete_records")`: cheques (+foto), caja OP,
  clientes, planillas/filas, extractos, movimientos, mov-UM, liquidaciones. pagos/gastos y purgar
  papelera ya eran admin/superadmin-only. El contador NO puede borrar nada (devuelve 403).
- **Liquidaciones**: nav/route pasó de `manage_users` a `reconcile` (el contador genera borradores;
  aprobar/pagar siguen siendo `manage_users`).
- **Login por aprobación en vivo (solo contador)**: el login NO devuelve token; crea un
  `LoginApproval` (tabla `login_approvals`, vía `create_all`) en estado `pending` (caduca a 10 min),
  notifica a los superadmins por push y devuelve 202 con `{approval_id, poll_secret}`. El cliente del
  contador hace polling a `GET /auth/login-approval/{id}?secret=` hasta recibir el token (1 sola vez).
  El superadmin aprueba/rechaza en `/aprobaciones` (`GET /auth/pending-approvals`, `POST
  .../decide`). Al aprobar se genera el JWT con **expiración de 4h** (`CONTADOR_SESSION_MINUTES`);
  pasadas las 4h expira y se repite la aprobación. `push_service.send_push_to_user()` nuevo.
  Robusto sin push: el panel `/aprobaciones` y el login del contador pollean igual.
- **Asignar organización al crear usuario** (superadmin): `PATCH /admin/users/{id}` acepta
  `organizacion_id`; selector de org en el alta de `/usuarios`. Para que los contadores de prueba
  operen en la **org de prueba** y NO en la Organización A (datos reales).
- **Perfil**: la card de setup VAPID ya estaba gateada por `is_superadmin` → el contador no ve datos
  de superadmin en `/perfil` (ve solo su propia cuenta + PIN/push).
- **Switch de org para contadores (`allowed_org_ids`)**: campo JSON en `User` con la lista de orgs
  extra a las que puede cambiar. `can_switch_org(user, org_id)` (en `middleware/auth.py`) reemplaza
  los chequeos `is_superadmin and org_id` en 9 routers (extractos, historial, clientes_dir, caja,
  auditoria, cheques, pagos_gastos, contabilidad, liquidaciones). `get_current_user` lee `?org_id=`
  del request y hace **override en memoria** (`db.expunge(user)` para NO persistir) si el ID está en
  la whitelist o es superadmin. `GET /me/allowed-orgs` lista las orgs disponibles; selector en el
  sidebar visible para contadores; multi-select de orgs al crear un CONTADOR en `/usuarios`.
  Safety net: `ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_org_ids JSONB DEFAULT '[]'`.
- **Fix email dominios reservados**: `UserRegister`/`UserLogin` dejaron de usar `EmailStr` (rechazaba
  `.test`, `.local`) y usan validación de formato básica → permite crear cuentas de prueba con mails
  inventados (`contador1@cuadra.test`). `ForgotPasswordRequest` mantiene `EmailStr` (manda mail real).
- **Fix crash React #31**: el interceptor de respuesta de axios (`services/api.ts`) normaliza el
  `detail` de errores 422 de Pydantic (array de objetos `{type, loc, msg, ...}`) a un string legible
  antes de llegar a los componentes. Evita "Objects are not valid as a React child" al renderizar
  `err.response.data.detail` (afectaba los 25 sitios con ese patrón).
- **Botones de borrar ocultos**: todas las páginas con delete buttons usan `canDelete = hasPermission('delete_records')`.
  Usuarios.tsx y Liquidaciones.tsx usaban chequeos de rol — alineados en v3.11.4.

### v3.8 — Reset Libro Diario + filtros Excel + orden de fechas (mayo 2026 — PRs #63-#68)

- **Reset y rebuild del Libro Diario**: `POST /contabilidad/reset-y-rebuild` (solo superadmin).
  `dry_run=true` (default) devuelve conteos sin tocar nada (`a_borrar`, `a_crear`); `dry_run=false`
  borra TODOS los asientos+detalles de la org y los reconstruye limpio desde los datos reales:
  `um_lote` (un asiento por lote UM importado) + `cc_inicial` (un asiento por PlanillaRow conciliada
  con cliente vinculado a cuenta). Renumera correlativo cronológico (`numero_asiento = 1,2,3…`,
  asiento #1 = el más viejo). Sirve para limpiar basura de operaciones de recuperación previas.
  Botón **"⚠️ Reset Libro Diario"** en `/contabilidad` → tab Cuentas Corrientes (visible solo
  superadmin); muestra el dry_run en `window.confirm` antes de ejecutar. Al terminar llama
  `recargarTodo()` + `cargarCartera()` para refrescar plan/sumas/balance/mayor sin F5.
- **Campo `numero_asiento`** (Integer nullable) en modelo `Asiento`. Safety net en `main.py`
  (`ALTER TABLE asientos ADD COLUMN IF NOT EXISTS numero_asiento INTEGER`). Además el propio endpoint
  de reset ejecuta el ALTER con commit aislado al arrancar (auto-reparable si el safety net de startup
  falló — corre todos los ALTER en una transacción y un fallo previo aborta el commit del lote).
- **Filtros tipo Excel en el Libro Diario**: componente `ExcelFilterCtb` (desplegable en headers,
  igual patrón que `/movimientos`). Columnas filtrables: **Fecha** (rango desde/hasta), **Concepto**
  (selector de módulo: um_lote, um_mov, um_reclass, cc_inicial, planilla…), **Cuenta** (buscador del
  plan). Chips de filtros activos + "✕ Limpiar". Backend `/contabilidad/asientos` acepta `?cuenta_id=`
  (subquery sobre `asiento_detalle`) y devuelve `numero_asiento`.
- **Orden de fechas — más reciente arriba**: tanto el Libro Diario (`/contabilidad/asientos`) como las
  Conciliaciones (`/conciliaciones` + export) muestran lo más reciente arriba (`fecha DESC`). Las
  conciliaciones ya estaban así (se revirtió un cambio intermedio). El `numero_asiento` se asigna
  ascendente (cronológico) y el Libro Mayor/saldos mantienen orden ascendente para el saldo acumulado;
  solo cambia el orden de **visualización** del listado.
- **Columna "Módulo" → "Concepto"**: en el header del Libro Diario solo cambió la etiqueta visible;
  el filtro interno sigue usando el campo `modulo`.
- **Fix tipos TS preexistentes**: `App.tsx` — `lazyPage` ahora es genérico sobre módulo+key (antes
  propagaba `any` y `<Contabilidad modo="ctacte" />` no validaba el prop). `Login.tsx` — el type guard
  `'pending_approval' in response && response.pending_approval` no estrechaba el tipo (la 2ª condición
  es expresión, no predicate); simplificado a `'pending_approval' in response`.
- **ORDEN DE USO del reset**: 1) "+ Crear cuentas faltantes" (vincula clientes sin cuenta) →
  2) "⚠️ Reset Libro Diario" (limpia y reconstruye numerado desde 1). El reset NO borra plan de
  cuentas, reglas, sumas ni balance — solo asientos+detalles.

### v3.9 — Módulo unificado Pagos + Libro Diario limpio + Asistente IA (mayo 2026 — PRs #74-#77)

- **Módulo unificado Pagos** (PR #74): reemplaza OrdenDePago + Pago + Gasto con un único módulo
  `Egreso`. Nuevo modelo `Egreso` (tabla `egresos`) + `CategoriaEgreso` (tabla `categorias_egreso`).
  Campos: `tipo` (proveedor|gasto|pago_cliente), `forma_pago` (banco|efectivo), `foto_comprobante`,
  `denominaciones_usadas`, `arqueo_id`. Router `/pagos` con CRUD completo, foto, compartir WhatsApp.
  Motor contable: `registrar_egreso()` usa cuenta hoja `1-1-1-3-1` (banco) o `1-1-1-2` (efectivo),
  cuenta cliente dinámica `2-1-2-X` para `pago_cliente`, `3-2-0-0` para gasto/proveedor.
  Categorías editables por usuario. UI en `/pagos` con filtros, foto, compartir. Nav unificada.
  Redirects `/op` → `/pagos` y `/pagos-gastos` → `/pagos`. Archivos viejos eliminados:
  `pago.py`, `pagos_gastos.py`, `OrdenDePago.tsx`, `PagosGastos.tsx`.
- **Libro Diario limpio** (PR #75): eliminados asientos `extracto` y `planilla` que usaban cuentas
  madre incorrectas y duplicaban con `um_lote`/`um_reclass`. `registrar_extracto()` y
  `registrar_planilla()` desactivados. Startup limpia esos módulos legacy automáticamente.
  `numero_asiento` se auto-asigna correlativamente en `_crear_asiento()`, `_crear_asiento_directo()`
  y `reversar_asientos()`. Startup también corrige NULLs existentes sin reset manual.
  Migración 009: drop tablas huérfanas `ordenes_de_pago`, `pagos`, `gastos`.
- **Flujo contable correcto** (post v3.9): solo 4 módulos generan asientos automáticos:
  `um_lote` (Banco Macro D / No identificado H al importar UM) · `um_reclass` (No identificado D /
  Cliente X H al conciliar) · `egreso` (gasto o pago con cuenta hoja correcta) · `cc_inicial`
  (backfill histórico). Los módulos `extracto` y `planilla` ya NO se crean.
- **Compartir cheque por WhatsApp** (PR #76): botón 📤 en tabla y modal de foto. Si el cheque
  tiene foto la adjunta vía Web Share API nativa (gratis). Fallback a `whatsapp://send?text=`.
- **Asistente IA Gemini Flash** (PR #77): botón ✨ flotante en todas las páginas. Consultas en
  lenguaje natural sobre datos reales de la DB vía function calling. Funciones disponibles:
  `consultar_pagos_cliente`, `consultar_cheques`, `consultar_saldo_caja`, `buscar_cliente`,
  `resumen_financiero`. Dictado por voz: SpeechRecognition (Chrome/Android, instantáneo) con fallback a
  MediaRecorder + `POST /agente/transcribir` (Gemini) en iOS — ver v3.17.
  Backend: `routers/agente.py` + `google-generativeai==0.8.3`. Activado con `GEMINI_API_KEY` en
  Render (AI Studio — capa gratuita). Modelo: `gemini-2.5-flash` (configurable via `GEMINI_MODEL`).

### v3.9.1 — OCR de fotos con Gemini Flash (mayo 2026)

- **OCR cheques**: al adjuntar foto en el formulario de cheque, `POST /agente/ocr-cheque` llama a
  Gemini con la imagen (inline_data) y extrae número, banco, titular, monto, fecha_emision y
  fecha_deposito. Pre-completa solo campos vacíos. Endpoint en `routers/agente.py`.
- **OCR transferencias**: al adjuntar foto en `/pagos`, `POST /agente/ocr-transferencia` extrae
  monto, fecha, beneficiario y referencia del comprobante. Solo pre-completa campos vacíos.
- Ambos usan el mismo `GEMINI_API_KEY` (capa gratuita AI Studio, sin costo extra). El fallback
  silencioso ante error permite al usuario cargar datos manualmente sin interrupciones.

### v3.9.2 — Módulo cheques mejorado + Loco de Cuadra (mayo 2026)

- **Portadores**: nueva tabla `portadores` (id, organizacion_id, nombre). Selector con botón "+"
  inline para agregar desde el form sin salir. GET/POST `/cheques/portadores`.
- **librador reemplaza titular**: campo `librador` en `Cheque`; `titular` se mantiene para compat.
  `_cheque_dict()` hace fallback `c.librador or c.titular`. Safety net backfill en startup.
- **Campos nuevos en Cheque**: `portador_id`, `librador`, `codigo_postal`, `local_interior`,
  `fecha_rechazo`, `fisico` (bool), `fecha_devolucion`. Todos con `ADD COLUMN IF NOT EXISTS`.
- **Auto-clasificación Local/Interior**: CP < 2000 → "local", CP ≥ 2000 → "interior".
  Calculado al tipear el CP en el form (frontend: `computeLI(cp)`) y también al importar Excel.
- **3 tabs en `/cheques`**: Todos | Por depósito | Rechazados.
- **Tab "Por depósito"**: selector de fechas disponibles (`GET /cheques/deposito` sin param devuelve
  `{fechas: [...]}`; con `?fecha=` devuelve `{fecha, items, resumen}`). Tabla con detalle, cards de
  resumen por L/I. Botón "↓ Excel" → `GET /cheques/deposito/exportar?fecha=` devuelve xlsx (openpyxl)
  con detalle + resumen por cliente + resumen L/I + total en una sola hoja.
- **Tab "Rechazados"**: carga independiente `GET /cheques?estado=rechazado&limit=500` al activar la
  tab. Columnas: F.Depósito, F.Rechazo, Cliente, F.Cheque, N°Banco, Banco, Librador, N°Cheque,
  CP, L/I, Importe, Físico, F.Devolución.
- **Modal "Rechazar" mejorado**: `RechazarIn` con `fecha_rechazo`, `fisico` (checkbox), `fecha_devolucion`
  (aparece solo si físico=true). Endpoint actualizado para setear los 3 campos.
- **Ícono "Loco de Cuadra"**: reemplaza el ícono Gemini en el asistente IA flotante. SVG custom con
  5 líneas de pelo revuelto, cabeza circular, ojos puntito, sonrisa curva. Subtítulo → "IA Cuadra".
- **OCR actualizado**: prompt retorna `librador` (no `titular`).
- Safety nets en `main.py`: `CREATE TABLE IF NOT EXISTS portadores` + 7x `ALTER TABLE cheques ADD
  COLUMN IF NOT EXISTS` + `UPDATE cheques SET librador = titular WHERE librador IS NULL`.
- Route ordering: `/portadores`, `/deposito`, `/deposito/exportar` definidos ANTES de `/{cheque_id}`.

### v3.9.3 — Asistente IA: modelo 2.5 + manejo de errores + botón flotante (mayo 2026 — PRs #82-#84)

- **Logo Cuadra en el asistente** (PR #82): el botón flotante usa el componente `CuadraLogo`
  (mismo logo que el header/sidebar), NO un ícono custom. `w-10 h-10 rounded-full overflow-hidden`
  → círculo perfecto, levemente más chico. Auto-hide al scrollear hacia abajo (fade + slide),
  reaparece al subir o tras 1.2s parado; siempre visible si el chat está abierto. Burbujas con
  `break-words` para no desbordar horizontalmente.
- **Manejo de errores Gemini** (PR #83): `_classify_gemini_error(ex)` mapea la excepción a
  (status, mensaje amigable): API key inválida/sin permisos (503), modelo no disponible (503),
  cuota diaria agotada vs límite por minuto (429 con mensaje distinto). `_gemini_send()` reintenta
  1 vez con `time.sleep(5)` ante 429 transitorio (límite por minuto). `api_key.strip()` en los 3
  endpoints (chat + 2 OCR) para tolerar espacios/comillas en la env var de Render. Los OCR también
  usan `_classify_gemini_error` (antes devolvían el error crudo de Python).
- **Modelo configurable + actualizado** (PR #84): `_GEMINI_MODEL = os.environ.get("GEMINI_MODEL",
  "gemini-2.5-flash")`. Default pasó de `gemini-2.0-flash` (se depreca 1/6/2026, free tier ya en
  `limit: 0`) a **`gemini-2.5-flash`** (free tier vigente: 250 req/día, mejor precisión OCR).
  Override-able en Render con `GEMINI_MODEL` (ej: `gemini-2.5-flash-lite` = 1.000 req/día, menos
  preciso). El mismo `_GEMINI_MODEL` se usa para chat, OCR de cheques y OCR de transferencias.
- **IMPORTANTE Gemini free tier (mayo 2026)**: la familia 2.0 (`gemini-2.0-flash`/`flash-lite`) se
  depreca el 1/6/2026; los modelos Pro pasaron a pago en abril 2026. Solo Flash y Flash-Lite de la
  versión 2.5 mantienen capa gratuita. NUNCA volver a `gemini-2.0-flash`.

### v3.9.4 — Usuarios por org + CONTADOR en contabilidad + mejoras varias (mayo 2026)

- **Gestión de usuarios filtrada por org activa** del sidebar + columna **Org** en la tabla de `/usuarios`.
- **CONTADOR ve todas las tabs de Contabilidad en solo lectura** (Plan, Reglas, Clientes) — antes algunas
  quedaban ocultas.
- **Cheques — agregar cliente inline**: botón **+** en el formulario de cheque crea el cliente sin salir.
- **Extractos — renombrar inline**: ✏️ al hacer hover sobre el nombre del archivo en `/extractos`.
- **Pagos**: campo **"A favor de"** en el pago a cliente + label **"Nro. OP"** (antes "Referencia").
- **Fix borrar usuario sin error FK**: `DELETE /admin/users` nulifica referencias FK con savepoints antes
  de borrar; `historial.py` usa `usuario_nombre` con fallback "—" si el dueño fue borrado; export de
  extractos tolera nombres sin extensión `.xlsx`.

### v3.10 — Ciclo contable completo de cheques (junio 2026 — PR #88)

- **Plan de cuentas — cuentas nuevas** (PLAN_PATCH idempotente en `main.py`):
  `1-1-1-4 Banco 2` (para pruebas de cheques) · `1-1-2-1 Cheques en cartera` (tránsito activo) ·
  `2-1-3-0 Cheques` / `2-1-3-1 Cheques depositados` / `2-1-3-2 Cheques a depositar` (tránsito pasivo) ·
  `3-1-3-0 Comisiones cheques` · `3-2-2-1 Gastos de rechazos`.
- **Regla de negocio**: el cliente DEBE tener `cuenta_contable_id` vinculada **antes** de registrar un
  cheque. Si no la tiene, `POST /cheques` devuelve **HTTP 400**. Orden de uso: crear cliente en
  `/clientes` → Contabilidad → tab Clientes → **"+ Crear cuentas faltantes"** → recién ahí cargar el cheque.
- **3 fases contables** (en `services/motor_contable.py`, helper `_crear_asiento_multilinea` para N líneas):
  1. **Registro** (`registrar_cheque`, modulo `cheque_registro`): Cheques en cartera (1-1-2-1) **D** /
     Cliente X (2-1-2-X) **H** por el neto / Comisiones cheques (3-1-3-0) **H** (si hay comisión).
  2. **Acreditación** (`acreditar_cheque`, 2 asientos): `cheque_acred_banco` = Banco elegido (1-1-1-3-1 o
     1-1-1-4) **D** / Cheques depositados (2-1-3-1) **H**; `cheque_acred_cliente` = reversa el tránsito.
     Se elige el banco al acreditar y se guarda en `Cheque.banco_cuenta_id` (se necesita para el rechazo).
  3. **Rechazo** (`rechazar_cheque`, 3 asientos): `cheque_rechazo_banco` revierte la acreditación bancaria;
     `cheque_rechazo_cliente` reabre la deuda del cliente; `cheque_rechazo_gasto` = Gastos de rechazos
     (3-2-2-1) **D** / Banco **H** por los gastos bancarios. Solo desde estado `acreditado`.
- **Las cuentas de tránsito netean a cero** tras el ciclo completo (cartera 1-1-2-1 y depositados 2-1-3-1).
  Test de integración `test_cheque_ciclo_completo_transitorias_netean_cero` lo verifica.
- **Estados del cheque**: `registrado | depositado | acreditado | rechazado | anulado`. Safety-net migra
  los viejos `pendiente → registrado` en startup (`UPDATE cheques SET estado='registrado' WHERE
  estado='pendiente'`). `Cheque.banco_cuenta_id` (FK plan_cuentas) con `ADD COLUMN IF NOT EXISTS`.
- **Acreditación masiva**: `POST /cheques/acreditar` recibe lista de IDs + `banco_cuenta_id`; valida banco
  y cuenta de cliente por cada cheque. UI en tab **"Por depósito"**: checkboxes + selector de banco +
  botón **"✓ Acreditar (N)"**.
- **Frontend** (`Cheques.tsx`): selector de banco (cuentas hoja cuyo nombre empieza con "Banco", resueltas
  vía `GET /contabilidad/plan-cuentas` + Set de `parentIds`), modal Acreditar con banco requerido, modal
  Rechazar con campo `gastos_bancarios`. Botón Acreditar para registrado/pendiente; Rechazar solo para
  acreditado.
- **Eliminar cheque**: reversa `cheque_registro` (con fallback a los legacy `cheque_carga`/`cheque_comision`).
- **Tests**: 152 pasando — 7 tests nuevos del ciclo de cheques reemplazan los 3 viejos.

### v3.10.1 — Cold-start fix + comisión L/I cheques + fix WhatsApp share (junio 2026 — PRs #90-#92)

- **Fix cold-start Render** (PR #90): reintento automático en el interceptor de axios (`api.ts`).
  `_shouldRetry()` + `_MAX_RETRIES = 3`: 502/503/504 → retries en cualquier método (Render proxy
  responde antes que el handler, es seguro); errores de red/timeout → solo GET (POST/DELETE pueden
  haber ejecutado). Backoff lineal 1.5s / 3s / 4.5s. `App.tsx` bootstrap: solo cierra sesión en 401
  real, en errores transitorios hace un segundo intento silencioso y conserva la sesión. Elimina los
  "errores flash" al ingresar con el backend dormido (free tier Render).
- **Comisión de cheque por local/interior** (PR #91): campos `porcentaje_comision_local` y
  `porcentaje_comision_interior` (Numeric 5,4) en el modelo `Cliente`. Safety nets en `main.py`.
  `PUT /clientes/{id}/comision` hace update parcial de los 3 campos (general, local, interior).
  Al crear un cheque, el backend auto-deriva el % según el campo `local_interior` del cheque:
  interior→`porcentaje_comision_interior`, local→`porcentaje_comision_local`, fallback al general.
  Si el form envía `porcentaje_comision` explícito, ese tiene prioridad (override manual).
  **UI en `/clientes`**: chip simple con % general (opción C) — el L/I se configura en DB directamente
  o se editará en el form de cheque. Los campos existen en la API y el frontend los leerá al elegir
  cliente en el form de cheque (`pctParaCliente()` en `Cheques.tsx`).
- **Fix compartir por WhatsApp** (PR #92):
  - `suppressLockForShare()` llamado antes de cada `navigator.share()` en `Pagos.tsx` y `Cheques.tsx`
    — evita que el bloqueo PIN interrumpa la hoja de compartir del sistema.
  - Canvas JPEG sin fondo negro: `ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h)` antes de
    `drawImage()` en `compressScanner` (Cheques) y en la captura de foto (Pagos). Soluciona foto negra.
  - `sharePagoPdf` en Pagos: re-renderiza la foto sobre fondo blanco; usa `naturalWidth/naturalHeight`
    desde `img.onload` para respetar el aspect ratio correcto en el PDF compartido.
  - `AbortError` (usuario cancela el share sheet) tratado como éxito — no muestra fallback de texto.

### v3.10.2 — Landing rediseñada (junio 2026 — PRs #94-#95)

- **Rediseño completo de la landing** (`/`): reemplaza la versión estática anterior por una experiencia
  interactiva orientada a conversión.
  - **Mockups animados**: `ConciliacionMockup` (filas pasando PEND.→OK en loop), `OCRMockup` (idle→scan→
    campos apareciendo), `AlertaMockup` (push + chat IA en 3 pasos). Todos con `IntersectionObserver`.
  - **Spotlights 01/02/03**: grid 2 columnas desktop (texto + mockup), stack mobile. Secciones:
    Conciliación, Cheques con OCR, Asistente IA.
  - **Calculadora interactiva**: 2 sliders (planillas/mes 1–300, horas/planilla 1–8) → muestra horas
    ahorradas con Cuadra vs hoy.
  - **Contadores animados** en stats (easing cúbico, activan al hacer scroll en desktop).
  - **`StatCounter`** y componentes sub-hero: comparativa Excel vs Cuadra, testimoniales, pricing,
    FAQ acordeón, closing CTA card verde, contacto directo WhatsApp (sin formulario).
  - **Cormorant Garamond** 600 italic para `.em-serif` (titulos en verde), reemplaza Fraunces/Playfair.
  - **`--bg: #FFFFFF`** en modo claro — fix definitivo del fondo gris heredado.
  - **Sin barra sticky mobile** (se eliminó el bar fijo WhatsApp + Contacto del pie en mobile).
  - **Steps contacto en línea** (`flexWrap: nowrap`): ya no se rompen en triángulo en mobile.
  - **Botón WhatsApp en spotlight Conciliación** (visible alto en la página sin hacer scroll hasta el final).
  - **Script tema síncrono** en `<head>` de `index.html` (previene flash blanco→gris antes de React).
  - Sin nombres de clientes reales, sin branding Gemini, FAQ con ARCA en vez de AFIP.

### v3.10.3 — Dashboard: onboarding checklist + alertas (junio 2026 — PR #100)

- **`OnboardingChecklist`** en el Dashboard: guía de 3 pasos para usuarios nuevos (subir extracto →
  subir planilla → conciliar). Barra de progreso verde, botón "Omitir" que persiste la decisión en
  `localStorage` por org (`onboarding-dismissed-<orgId>`). Desaparece automáticamente al completar
  los 3 pasos. Scroll a `#upload-planilla-section` desde el botón del paso 2.
- **`AlertasWidget`** en el Dashboard: chips clickeables por tipo de alerta encima del onboarding.
  Llama a `GET /analisis/alertas` al montar. 4 tipos: `cheques_urgentes` (⏰ rojo), `cheques_vencidos`
  (🔴 rojo), `filas_atrasadas` (📋 ámbar), `movimientos_sin_asignar` (🔍 azul). Variantes light/dark
  mode. Retorna `null` si no hay alertas (sin ruido en orgs limpias). Cada chip navega al módulo.
- `isDark` derivado de `useThemeStore` para pasar a `AlertasWidget`.
- `useEffect` reactivo para el estado del onboarding (evita bug cuando `activeOrgId` carga después
  del mount inicial y cambia el `localStorage` key).

### v3.11 — Ajuste manual Libro Diario + 2FA + permisos hardening + fix onboarding (junio 2026 — PR #102)

- **Ajuste manual del Libro Diario**: modal en `/contabilidad` → tab Libro Diario, visible solo para
  `admin_accounting`. Selector de cuenta Debe/Haber con búsqueda (solo cuentas hoja, sin hijos).
  Monto, fecha, descripción libres. Endpoint `POST /contabilidad/asiento-manual` valida partida doble
  y que ambas cuentas sean hoja. Botón 🗑️ por fila `ajuste_manual` → `DELETE /contabilidad/asientos/{id}`
  crea asiento reverso (`ajuste_manual_reverso`), nunca borra físicamente. `registrar_ajuste_manual()`
  en `motor_contable.py` asigna `numero_asiento` correlativo.
- **2FA por email para Superadmin y Admin**: al loguearse, si `RESEND_API_KEY` está seteada en Render, se
  genera un código de 6 dígitos (SHA256 hasheado, TTL 10 min), se envía por email (asunto "Código de
  verificación Cuadra") y se retorna `202 {requires_2fa: true, email}`. Nuevo modelo `TwofaCode` (tabla
  `twofa_codes`, safety net `CREATE TABLE IF NOT EXISTS` en `main.py`). Endpoint `POST /auth/verify-2fa`
  valida hash, marca `used=True` y entrega JWT. Sin `RESEND_API_KEY` el login sigue sin 2FA (degradación
  elegante). Aplica a roles `is_superadmin` o `role == "admin"`. El Contador ya tiene protección mejor
  (aprobación en vivo). Frontend: pantalla 2FA con input 6 dígitos, tipo `TwofaChallenge` en `types/index.ts`.
- **`delete_records` solo para Admin y Superadmin**: se quitó el permiso al rol Operador (principio de
  menor privilegio). El Operador sigue haciendo toda la operatoria diaria (subir, conciliar, caja,
  cheques, pagos, liquidaciones) pero no puede borrar datos. Si algo se subió mal, lo reporta y un Admin
  lo corrige. Cambio en `middleware/auth.py` y `store/auth.ts`.
- **Fix onboarding checklist**: `dataLoaded` + `Promise.all` para carga paralela de extractos y planillas.
  El checklist solo renderiza después de que los datos cargaron (evita flash de 1-2 s). Auto-dismiss
  inmediato cuando los 3 pasos ya están completos al cargar (orgs con datos existentes nunca ven el widget).

### v3.11.1 — Fix compartir WhatsApp + contraste de mensajes en dark/light (junio 2026)

- **Fix imagen negra al compartir por WhatsApp** (`Pagos.tsx`): el fallback de compartir como imagen
  re-renderiza la foto sobre un canvas con fondo blanco (`ctx.fillStyle = '#ffffff'; fillRect`) antes de
  exportar a JPEG. Antes pasaba el blob original (PNG con alpha) etiquetado como `image/jpeg` → WhatsApp
  mostraba los píxeles transparentes en negro. Mismo patrón que ya usaba `sharePagoPdf`.
- **Fix mensajes con mal contraste en dark/light**: cuadros de estado (`setMsg`/`error`/`success`) que
  tenían solo variante de un modo quedaban ilegibles en el otro. Estandarizados con variantes light **y**
  dark:
  - Faltaba variante dark (fondo claro en dark mode): `Dashboard.tsx` (error+success), `Caja.tsx` (error),
    `Perfil.tsx` (2 cuadros error), `Historial.tsx` (error).
  - Faltaba variante light (texto claro invisible en light mode): `Cheques.tsx` (mensaje de form),
    `Resumen.tsx` (error de carga).
  - El resto de páginas (Organizaciones, Revision, Liquidaciones, Clientes, Login, Papelera, password reset)
    ya tenían ambas variantes. El Toaster global ya estaba correcto.
  - Nota: el CSS global (`index.css`) ya sobreescribe `text-gray-400/500/700/800/900` en dark mode, por eso
    esos grises no requieren `dark:` por instancia.
- **Fix Cheques light mode completo**: toda la página `Cheques.tsx` era dark-first (colores sin `dark:`
  prefijo). Convertido a dual-mode: ESTADO_BADGE con pastel light, `inputClass` con hex fallback para
  evitar replace_all collisions, LiBadge, acreditación masiva panel, botones de acción, modales,
  alternación de filas, tab activa, stat cards de importe, fechas rechazadas.
- **Fix PDF scanner en Cheques** (`shareChequePdf`): canvas con fondo blanco + aspect ratio preservado
  (`ratio = Math.min(maxW/w, maxH/h)`), centrado horizontal. Mismo patrón que `sharePagoPdf` en Pagos.
- **Fix OCR monto en Pagos**: helper `parseMonto()` para parsear formatos argentinos ("15.000,00"),
  US y planos. OCR canvas sin filtros grayscale (Gemini lee mejor color). Error visible en lugar de
  silencioso cuando OCR falla (`.catch(() => {})` → mensaje "OCR no disponible").
- **Fix compartir imagen en Pagos y Cheques**: race condition `img.src` antes de `img.onload` → await
  explícito con Promise + `canvas.toBlob()` null-safe.
- **Lazy loading en Pagos**: clientes/categorías se cargan solo cuando `vista === 'nuevo'`.

### v3.11.2 — Fecha local (timezone UTC-3) + light mode Caja/Compartir/Cheques (junio 2026)

- **Fix fecha local en formularios (FRONTEND)**: `new Date().toISOString().slice(0,10)` devuelve fecha
  UTC — antes de las 3 AM en Argentina (UTC-3) generaba la fecha de ayer. Nuevo helper compartido
  `src/utils/fecha.ts` (`localIsoDate()/hoyIso()/isoHaceNDias()`) = `getFullYear()/getMonth()+1/getDate()`,
  usado en: `Pagos.tsx` (fecha default del pago → afectaba Libro Diario), `Caja.tsx` (`toISO`/`today` →
  selector de arqueo), `Clientes.tsx` (modal Acreditar), `EstadoCuenta.tsx`, `Resumen.tsx`, `Historial.tsx`
  (modal re-conciliar + botones Hoy/Ayer), `Dashboard.tsx` (fechaAcred/bulkFecha/hoyStr), `Bulk.tsx`,
  `Movimientos.tsx` (acreditar), `Contabilidad.tsx` (ajuste manual).
- **Fix hora de Argentina (BACKEND)**: el servidor Render corre en UTC; `date.today()` y `datetime.now()`
  devolvían la fecha UTC → fechas de negocio quedaban 1 día adelantadas entre 21:00–00:00 ART. Nuevo
  helper `app/services/tz.py` (`hoy_art()/now_art()` con `ZoneInfo("America/Argentina/Buenos_Aires")`).
  Reemplazado en TODAS las fechas de negocio: `models/egreso.py` (default `Egreso.fecha`), `routers/pagos.py`,
  `routers/cheques.py` (depósito/acreditación/rechazo/import — 7 casos), `routers/caja.py` (arqueo),
  `routers/agente.py` (consultas IA caja/resumen — 5 casos), `routers/contabilidad.py` (asientos
  cc_inicial/reset/ajuste — 5 casos), `routers/planillas.py` (ref liquidación), `routers/clientes_dir.py`
  (acreditar mov), `services/motor_contable.py` (TODOS los asientos automáticos — 6 casos),
  `services/backup_scheduler.py` (alertas cheques por vencer), `main.py` (backfill). Las marcas de
  AUDITORÍA (`created_at`, expiración de tokens 2FA/reset/aprobación) siguen en UTC a propósito —
  eso es correcto y consistente. Tests: `test_tz.py` (4 tests). Suite total: **156 passing**.
- **Fix light mode Caja — historial de arqueos**: panel `bg-white/3 border-white/8` → `bg-gray-50
  dark:bg-white/3 border-gray-200 dark:border-white/8`. Texto `text-gray-300/200` → dual-mode.
  Dividers y hover también duales. Date pickers EFT: `bg-white/5 text-gray-300` → variantes light.
- **Fix light mode Compartir**: toda la página era dark-only. Error box, panel de titulo/texto,
  tarjetas de archivos, botones Cheque/Pago — todos con variantes light/dark.
- **Fix Cheques colores residuales**: stats (importe pendientes/acreditados/rechazados) usaban
  `text-yellow/green/red-400` (tenues en light) → `*-600 dark:*-400`. Botón Excel depósito y
  compartir WhatsApp: `bg-green-*/*` → `bg-green-100 dark:bg-green-*/...`. Quitar foto: dual-mode.

### v3.11.3 — Editar cheque + Export Excel + Comisión auto + Fix fechas bidireccional (junio 2026)

- **Editar cheque** (`✏️` en tabla): botón inline en la columna de acciones de cheques en estado
  `registrado`. `handleOpenEdit(c)` pre-llena el form (sin foto — ocultada en modo edición).
  `PATCH /cheques/{id}` acepta todos los campos del cheque. `handleSave()` unificado (POST si nuevo,
  PATCH si editId ≠ null). Modal muestra "Editar cheque" / "Nuevo cheque" según estado. Cancelar
  limpia `editId`.
- **Export Excel todos los cheques** (`↓ Excel` en toolbar): `GET /cheques/exportar` con filtros
  opcionales `org_id, estado, cliente_id, desde, hasta`. Devuelve xlsx con columnas: Estado,
  F.Depósito, F.Acred., Cliente, Portador, Librador, Banco, Número, CP, L/I, Monto, Comisión,
  Notas + fila de total. Ruta registrada ANTES de `/deposito/exportar` para evitar conflictos.
  `exportandoTodos` state para feedback del botón.
- **Comisión auto-calculada en cheques**: se eliminó el campo "Comisión $" (monto plano) del form.
  Queda solo `% Comisión (cuenta 3-1-3-0)` con preview `= $X.XX` calculado en tiempo real
  (`monto × pct / 100`). Al guardar, `comisionCalc = Math.round(monto * pct) / 100` se envía
  como `comision` en el payload (no viene del form). `emptyForm()` sin `comision`. Label claro
  referencia la cuenta 3-1-3-0 para no confundir con gastos bancarios (3-2-2-1).
- **Stats cards overflow**: `overflow-hidden` en card container + `text-sm` + `truncate` en el
  valor monetario → montos grandes ($6,972,528.75) no desbordan en mobile de 3 columnas.
- **Fix fechas bidireccional** (`🕐 Fix fechas UTC` en `/contabilidad` → tab Cuentas Corrientes,
  solo superadmin): `POST /contabilidad/fix-fechas-utc` acepta `desde`, `hasta`, `modulo`,
  `direccion` (adelantar = +1 día · atrasar = −1 día), `dry_run`. Corrige tanto `Asiento.fecha`
  como `Egreso.fecha` en el rango dado. UI con `window.prompt` para ingresar rango+dirección,
  `window.confirm` con preview (dry_run) antes de ejecutar. Uso: egresos cargados antes de las
  3 AM ART quedaban con fecha UTC del día anterior → `adelantar` los corrige.

### v3.11.4 — Botones de borrar + Sentry + Validación extracto (junio 2026)

- **Botones de borrar por permiso**: `Usuarios.tsx` y `Liquidaciones.tsx` migrados a
  `canDelete = hasPermission('delete_records')` (antes usaban chequeos de rol ad-hoc).
  Todas las páginas con delete buttons usan el permiso estándar.
- **Sentry — monitoreo de errores (opt-in)**: backend `sentry-sdk[fastapi]` en `requirements.txt`;
  `sentry_dsn: str = ""` en `config.py`; inicialización en `main.py` solo si `SENTRY_DSN` env var
  está seteada (`traces_sample_rate=0.05`, `send_default_pii=False`). Frontend `@sentry/react`;
  `VITE_SENTRY_DSN` declarado en `vite-env.d.ts`; `Sentry.init()` en `main.tsx` solo si la var existe;
  `Sentry.captureException(err)` en el ErrorBoundary global. Sin DSN → sin overhead, sin errores.
  Activar: setear `SENTRY_DSN` en Render y `VITE_SENTRY_DSN` en Vercel (Environment Variables).
- **Validación post-parse del extracto**: `POST /extractos` ahora rechaza con HTTP 400 si el parser
  devuelve 0 movimientos (formato no reconocido) o si la suma absoluta de montos es cero (columna
  de monto mal detectada). Protege contra cambios de formato bancario silenciosos.

### v3.12 — Editar pago + SVG icons + fix suppress lock (junio 2026 — PRs #106-#108)

- **Editar pago** (`✏️` en historial): modal inline con campos monto, fecha, beneficiario/proveedor,
  referencia, concepto. `PATCH /pagos/{id}` edita campos básicos, reversa el asiento contable y
  genera uno nuevo con los valores corregidos. Permite corregir montos con ceros de más sin borrar.
- **Fix DELETE /pagos/{id}**: el decorador `@router.delete("/{egreso_id}")` faltaba en `pagos.py`,
  dejando el endpoint sin registrar (devolvía 404). Corregido.
- **Fix registrar_egreso en edición**: la llamada a `registrar_egreso()` usaba `egreso=e` (parámetro
  inexistente); corregido para pasar todos los campos individualmente.
- **Fix selector de clientes en Pagos**: `r.data.clientes` solo incluye clientes con planillas.
  Cambiado a `r.data.organizaciones[].clientes` que incluye TODOS los clientes de la org (incluso
  los recién creados sin planillas).
- **OCR monto (BUG-03 resuelto)**: `type="number"` rechazaba silenciosamente el formato argentino
  `"15.000,50"`. Fix: OCR guarda en formato estándar `"15000.5"` y `montoNum = parseFloat(form.monto)`.
- **Compartir PDF por WhatsApp (BUG-02 resuelto)**: `await apiClient.client.post('/compartir')`
  consumía la ventana de transient activation (~5s). Fix: fire-and-forget (sin await).
- **SVG icons en Pagos y Cheques**: emojis 📷/🏦/💵/📤/✅ reemplazados con Heroicons SVG en botones,
  badges y pantalla de éxito. Pantalla de éxito → círculo verde con checkmark SVG.
- **Fix suppress lock cámara**: `suppressLockForCamera()` (8s) separado de `suppressLockForShare()`
  (20s). Antes el botón de cámara suprimía el lock por 20s → el PIN no se pedía al minimizar la app
  dentro de los 20s de tomar una foto. Aplicado en Pagos.tsx y Cheques.tsx.
- **BUGS.md**: registro permanente de bugs recurrentes con causa raíz y solución. Ver `/BUGS.md`.

### v3.12.1 — Auditoría de performance (junio 2026 — PR #114)

- **N+1 eliminado en Papelera** (`routers/papelera.py`): `listar_papelera()` hacía un `COUNT` por
  item en loop. Reemplazado por 2 queries `GROUP BY` que cubren todos los items de una vez.
- **N+1 eliminado en Liquidaciones** (`routers/liquidaciones.py`): `_calcular_monto_y_comision()`
  hacía un query al `MovimientoBanco` por cada fila de planilla. Ahora pre-fetcha todos los IDs con
  un único `WHERE id IN (...)` antes del loop.
- **Migración 010** — índices faltantes: `clientes(organizacion_id)` (usado en 10+ queries sin
  índice), `plan_cuentas(parent_id)` (queries recursivas del árbol), `plan_cuentas(organizacion_id)`,
  `users(organizacion_id)`. Todos con `IF NOT EXISTS`. Los índices de `movimientos_banco`,
  `planillas`, `planilla_rows`, `cheques` y `extractos` ya existían desde migración 004.
- **Cache TTL 60s server-side** (`routers/analisis.py`): dict module-level `_cache` con
  `time.monotonic()`. Cubre `/analisis/alertas` (key: `alertas:{org_id}`) y `/analisis/dashboard`
  (key: `dashboard:{org_id}:{periodo}:{anio}:{mes}:{desde}:{hasta}`). Sin dependencias externas.
  Reduce ~19 queries/request a 0 durante el TTL — el endpoint de alertas se llama en cada carga
  de página. Por proceso: en Render free (1 worker) el hit rate es ~100%.
- **Limit conciliaciones 500→50** (`routers/extractos.py`): el endpoint `GET /conciliaciones`
  tenía `limit: int = 500` por defecto — devolvía 500 movimientos completos sin pedirlo.
- **`useMemo` en Dashboard**: `bulkPendingCount/bulkOkCount/bulkTotalAcred/bulkTotalFilas` +
  `totalMovimientos/totalAcreditadas/totalProcesadas/accuracy/montoConciliadoHoy` — 9 valores
  derivados que se recalculaban en cada render del componente.
- **`useMemo` en Cheques**: `totalPend/totalAcred/totalRech` — 3 filter+reduce sobre el array
  completo que corrían en cada render, incluyendo al tipear en los filtros.
- **Bug fix `refreshExtractos` sin `activeOrgId`** (`Dashboard.tsx:307`): `listExtractos()` se
  llamaba sin pasar la org activa → podía mostrar extractos de otra organización tras borrar.
- **`cargarAsientos()` en paralelo** (`Contabilidad.tsx`): antes se llamaba al final del `.then()`
  del `Promise.all` de 4 requests. Ahora se dispara al inicio de `recargarTodo()` en paralelo.
- **Fix dep array Historial** (`Historial.tsx`): `useEffect(() => { load() }, [])` no incluía
  `activeOrgId` → el historial no se actualizaba al cambiar de organización en el sidebar.
- **Pendiente deliberado**: paginación de rows en `GET /planillas/{id}` (retorna todas las filas
  sin paginar). No implementado porque `PlanillaPanel` asume todas las filas juntas — requiere
  refactor coordinado de frontend+backend+componente. Tarea para próxima sesión si el volumen crece.

### v3.13 — Asientos agrupados por planilla + liquidación con asientos + arranque limpio (junio 2026 — PR #119)

- **Asientos agrupados por planilla**: al conciliar, en vez de un asiento `um_reclass` por cada fila,
  se crea **un solo asiento `um_reclass_planilla` por planilla** (No identificado 2-1-1-1 D / Cliente
  2-1-2-X H, con el total conciliado). `registrar_reclasificacion_planilla()` en `motor_contable.py`
  hace **upsert**: re-conciliaciones que acreditan filas adicionales actualizan el monto del mismo
  asiento (no duplican). `conciliacion.py` acumula el total UM durante el loop y llama una vez al final.
- **Asiento al aprobar liquidación**: `registrar_liquidacion_aprobacion()` — por cada detalle de la
  liquidación genera Cliente (2-1-2-X) **D** monto bruto / Banco Macro (1-1-1-3-1) **H** neto +
  Comisiones ganadas (3-1-1-0) **H** comisión (si > 0). Módulo `liquidacion_aprobacion`. Se dispara en
  `aprobar_liquidacion()`. Cancela la deuda del cliente y reconoce la comisión como ingreso. Idempotente.
- **Arranque limpio (un solo botón)**: el flujo de reparación contable se consolidó en **"🧹 Empezar
  limpio"** (`/contabilidad` → tab Cuentas Corrientes, solo superadmin). Es el `reset-y-rebuild`
  mejorado: borra TODOS los asientos y reconstruye desde cero usando solo las 2 fuentes confiables —
  `um_lote` (importaciones del banco) + `um_reclass_planilla` (conciliaciones agrupadas), numerado
  desde 1, fechado cronológicamente. **Ahora es one-shot**: ya no exige correr "crear cuentas faltantes"
  antes — el loop crea/vincula la cuenta de cada cliente automáticamente (`_get_o_crear_cuenta_cliente`).
  Se **eliminó el botón "↻ Reconstruir desde conciliaciones"** (generaba `cc_inicial` por fila = los
  asientos erróneos/duplicados). El endpoint `backfill-cuentas-corrientes` queda en el backend pero sin
  UI. Quedan como diagnósticos secundarios (superadmin): "🕐 Fix fechas UTC" y "🔍 Ver gaps".
- **Cta. cte. — chips y PDF**: chip "Banco (UM)" renombrado a **"TT"**; chip "TT" (vacío desde v3.9)
  eliminado. `_MODULO_TIPO` mapea `um_reclass_planilla` → (banco, "Transferencia (TT)") y
  `liquidacion_aprobacion` → (ajustes, "Liquidación aprobada"). `get_cuenta_corriente` maneja
  `um_reclass_planilla` con `referencia_id` = planilla_id directo. Nuevo **export PDF** de la cuenta
  corriente del cliente: `GET /contabilidad/cuenta-corriente/exportar-pdf` + botón "PDF" en la toolbar +
  `cuenta_corriente_pdf()` en `pdf_export.py` + `apiClient.downloadCtaCtePdf()`.
- **ORDEN DE USO (actualizado)**: ya NO hay ritual de 2 pasos. Para dejar el Libro Diario prolijo:
  un solo click en **"🧹 Empezar limpio"** (muestra dry_run en el confirm antes de ejecutar).
- Tests: 212 passing (6 nuevos en `test_motor_contable.py` — reclasif. agrupada + liquidación).

### v3.14 — Legales actualizadas (junio 2026 — PR #120)

- **Política de Privacidad**: Art. 12 Ley 25.326 reemplaza Privacy Shield (obsoleto 2020); tabla de
  subprocesadores (Neon, Render, Vercel, Gemini, Resend); sección IA (Gemini API externa, sin
  entrenamiento con datos de usuarios); derechos de oposición y portabilidad; cláusulas datos de
  terceros y datos sensibles; retención granular (backups 30d, logs 90d, auditoría 2 años).
- **Términos**: cláusula de indemnidad; datos de terceros (usuario responsable de la base legal de
  los datos de sus clientes); PI menciona registro DNDA. Identidad: "Cuadra, desarrollado y operado
  por Julieta Arrazate" (marca primero, respaldo legal después; cambiar a razón social cuando exista).

### v3.15 — Expansión: 16 bancos + export contable + tarjetas + split frontend (junio 2026 — PRs #121-#124)

- **Parsers 9 → 16 bancos** (PR #121): Mercado Pago (CSV liberaciones con headers en inglés
  `TRANSACTION_AMOUNT`/`RELEASE_DATE`/etc. y "Detalle de movimientos"; detección por estructura vía
  `_es_mercadopago_por_headers()` cuando no dice "Mercado Pago"), Credicoop, Supervielle, Patagonia,
  Bancor, Banco Rioja, La Pampa. **Fix bug preexistente**: keyword `"rio"` (Santander) capturaba
  "Banco de La Rioja" — ahora las keywords se ordenan por longitud desc (la más específica gana) +
  guard `rio`/`rioja`. `detectar_banco` escanea filas 1-9 / cols 1-11 con normalización de acentos.
- **Export contable configurable** (PR #122): `services/export_contable.py` — formatos `csv`
  (separador/encoding/fecha configurables), `tango` (tab + coma decimal + latin-1), `holistor`
  (punto-y-coma + coma decimal), `regisoft` (CSV con headers). Mapeo de cuentas por org en
  `Organizacion.config["mapeo_cuentas_export"]` ({"1-1-1-3-1": "11030001"}); cuentas sin mapeo →
  header `X-Cuentas-Sin-Mapeo` + warning amarillo en UI. Endpoints: `GET /contabilidad/asientos/
  exportar-contable?formato=&desde=&hasta=` (view_accounting), `GET/PUT /contabilidad/export-config`
  (PUT requiere admin_accounting). Botón "Exportar contable" + modal en tab Libro Diario.
- **Módulo Tarjetas** (PR #123): `/tarjetas` (nav con permiso manage_finance). Modelo
  `LiquidacionTarjeta` (tabla `liquidaciones_tarjeta`, Numeric 12,2, soft delete, FK movimiento+asiento).
  Parser best-effort `tarjeta_parser.py` (Excel/CSV por keywords por marca; PDF vía pdfminer si está,
  degrada con `parse_warnings`; el usuario confirma/corrige en UI). **Asiento mensual agrupado**
  (módulo `tarjeta_liq`, 6 líneas): Banco D neto / Aranceles 3-2-3-X D / IVA CF 1-1-2-4 D /
  Percepciones IIBB 1-1-2-5 D / Retenciones 1-1-2-6 D / Ingresos por tarjetas 3-1-4-0 H bruto.
  **Invariante**: neto+aranceles+iva+percepciones+retenciones == bruto (tolerancia 0.01) → 422 si no.
  9 cuentas nuevas en PLAN_PATCH. Flujo: upload (preview) → crear (asiento) → conciliar (vincula
  mov del extracto) → soft delete (reverso). UI 3 tabs: Resumen (cards por marca), Cargar, Historial.
- **Split frontend** (PR #124): `Cheques.tsx` 1747→189 líneas, `Contabilidad.tsx` 1590→85.
  Patrón: hook con todo el estado (`useCheques.ts` / `useContabilidad.ts` con tipo `ContabilidadCtx`)
  + subcomponentes que reciben el bag (`components/cheques/` 9 archivos, `components/contabilidad/`
  10 archivos). Comportamiento idéntico verificado (tsc sin errores nuevos). El modal de export
  contable vive en `ContabilidadModales.tsx` (porteado en la resolución del merge con #122).
- Tests: **266 passing** (220 base + 11 parsers + 27 export + 8 tarjetas).
- Pendientes del plan de expansión (tareas 5-8): split router contabilidad.py, tipar `any` en TS,
  paginación en 5 endpoints (plan-cuentas, reglas, clientes-cuentas, clientes-aging, papelera),
  tests para cheques/contabilidad/planillas.
- Deuda anotada por auditoría de agentes: `_parse_monto` devuelve float por contrato (conversión
  Decimal la hace SQLAlchemy en DB — mover al parser requiere tocar el merger); `_convertir_csv_a_xlsx`
  frágil con montos "1.234,56" (separador de miles); pdfminer no está en requirements (parser de
  tarjetas degrada a manual para PDFs).

### v3.16 — Deuda técnica v3.15 + UI comisión L/I + tsc limpio + paginación (junio 2026 — PRs #126-#133)

- **Split router `contabilidad.py`** (PR #127): monolito 1628 líneas → agregador delgado 38 líneas +
  4 sub-módulos: `ctb_common.py` (helpers compartidos), `ctb_plan.py` (/stats, /plan-cuentas, /reglas),
  `ctb_libro.py` (/asientos, /libro-mayor, /sumas-saldo, /balance, /export-config, /asiento-manual,
  /fix-fechas-utc, /reset-y-rebuild), `ctb_clientes.py` (/clientes-cuentas, vincular, crear-faltantes),
  `ctb_ctas_corrientes.py` (/cuentas-corrientes, /cuenta-corriente, exportar-pdf, backfill). Sin cambios
  funcionales, `main.py` sin tocar. Comportamiento idéntico verificado con tsc + pytest.
- **Deuda técnica v3.15** (PR #128): `pdfminer.six>=20221105` agregado a `requirements.txt` (antes el
  tarjeta parser degradaba silenciosamente en PDFs). `_normalizar_numero()` en `excel_parser.py`
  detecta formato argentino `"1.234,56"` antes de `float()`. Doc de `_parse_monto` sobre contrato float.
- **50 tests de integración** (PR #130): `test_cheques_integration.py` (13 tests), `test_contabilidad_integration.py`
  (15 tests), `test_planillas_integration.py` (22 tests). Suite total: 316 tests pasando.
- **Tipado `any` eliminado — frontend** (PR #131): `api.ts`, componentes de contabilidad, cheques y páginas.
  Tipos nuevos: `ConciliacionItem`, `TarjetaUploadPreview`, `TarjetaCreatePayload`, `LiquidacionTarjeta` en
  `types/index.ts`. `AxiosResponse` en métodos de descarga.
- **UI comisión L/I por cliente** (PR #129): chip expandible en `/clientes` con 3 inputs inline:
  `% General`, `% Local (CP < 2000)`, `% Interior (CP ≥ 2000)`. Llama a `PUT /clientes/{id}/comision`
  con los 3 campos (null si vacío). Click-outside cierra; chip ámbar si algún campo tiene valor.
- **Fix tsc TS6133** (PR #129 + #132): eliminados imports y variables no usadas en 7 archivos:
  `AgenteChat.tsx` (React import), `Layout.tsx` (useCallback + ThemeToggle), `Actividad.tsx` (fmt + totalFilas),
  `Caja.tsx` (useRef), `Dashboard.tsx` (extractoNombre, loading, handleBulkFiles), `Historial.tsx`
  (downloadingId, handleDownload), `Movimientos.tsx` (editingId, editValues, _startEdit, _saveEdit).
  `tsc --noEmit` → 0 errores.
- **Paginación limit/offset en 5 endpoints** (PR #133): `GET /contabilidad/plan-cuentas`, `GET /contabilidad/reglas`,
  `GET /contabilidad/clientes-cuentas`, `GET /admin/papelera`, `GET /analisis/clientes-aging` — todos agregan
  `limit`/`offset` query params y retornan `{"items": [...], "total": N}`. Backward-compat: `clientes`/
  `cuentas_disponibles`/`extractos`/`planillas` se mantienen como aliases. Frontend (`useContabilidad.ts`,
  `useCheques.ts`) usa `r.data?.items ?? r.data` para tolerar ambos shapes. 316 tests pasando.

### v3.17 — Audit pre-lanzamiento + audio real en el asistente IA (junio 2026 — PRs #135-#138)

- **Audit de seguridad/performance** (PR #135): índice `idx_asientos_numero ON asientos(numero_asiento
  DESC)` (migración 011 + safety net en `main.py`) para acelerar el orden del Libro Diario; validación de
  **magic bytes** en upload de extractos (`POST /extractos/upload` y `/{id}/agregar-um` verifican firma ZIP
  `PK\x03\x04` para .xlsx, OLE2 `\xD0\xCF\x11\xE0` para .xls antes de parsear). El audit confirmó que 2FA
  brute-force (3 intentos → bloqueo) y `/conciliaciones` paginado (`{items, total}`) **ya estaban**
  implementados. Sin hallazgos CRÍTICOS — sistema listo para producción.
- **Copy de posicionamiento** (PR #136): landing badge → "Software financiero con IA para estudios
  argentinos", hero sub agrega "contabilidad" + "con IA integrada", Login y página pública → "Gestión
  financiera con IA" (antes "Conciliación bancaria" — ya no describía el alcance del sistema).
- **Transcripción de audio con Gemini** (PR #137 backend): nuevo `POST /agente/transcribir` —
  `multipart/form-data` campo `audio` (UploadFile), pasa el `content_type` real a Gemini via
  `inline_data` (mismo patrón que los OCR), retorna `{"texto": "..."}`. 503 si falta `GEMINI_API_KEY`,
  400 si audio vacío, `_classify_gemini_error` para formatos no soportados. Sin transcodificación ffmpeg.
- **Audio recording en el asistente** (PR #138 frontend): `AgenteChat.tsx` — el botón de micrófono ahora
  es **siempre visible**. Si el browser tiene `SpeechRecognition` (Chrome/Android) usa ese flujo rápido;
  si no (iOS Safari/Chrome iOS, que NO soporta SpeechRecognition) graba con **MediaRecorder**
  (`audio/webm → mp4 → ogg → default`) y sube a `/agente/transcribir`, poniendo el texto en el input para
  revisar antes de enviar. **Fix feedback**: el `onerror` de SpeechRecognition ahora muestra toasts
  diferenciados (permiso denegado, sin voz, sin micrófono) en vez de fallar en silencio. Estados visuales:
  rojo pulsante grabando, azul tenue transcribiendo.

### v3.18 — Paginación planillas + Google OAuth + índices DB + fix campana (junio 2026 — PRs #140-#146)

- **Paginación server-side en planillas**: `GET /planillas/{id}/detalle` acepta `limit/offset` +
  filtros (`status`, `cuit`, `titular`, `importe`, `mov_titular`, `mov_fecha`, `mov_fecha_acred`).
  Stats (ok, no está, etc.) se calculan desde TODAS las filas con `GROUP BY` (no solo la página
  actual); `total_filtered` en la respuesta para paginar bien con filtros activos. `PlanillaPanel`
  hace fetch por página + debounce 350ms en filtros; "Seleccionar todo" = solo la página actual
  (ya no carga 1000+ filas en memoria). Resuelve el pendiente de v3.12.1.
- **Google OAuth — login con cuenta de Google** (opt-in, link-only): `POST /auth/google` verifica
  el token de Google (`useGoogleLogin` con popup + `access_token`, NO el iframe `GoogleLogin` que
  queda invisible si el origen no está en la whitelist de Google) vía `tokeninfo` y valida
  `azp == GOOGLE_CLIENT_ID`. Solo permite usuarios YA registrados en el sistema (no crea cuentas
  nuevas). Activar seteando `GOOGLE_CLIENT_ID` en Render y `VITE_GOOGLE_CLIENT_ID` en Vercel (mismo
  valor) + agregar el origin en Google Console. Sin esas env vars el botón no aparece.
- **Índices DB críticos en contabilidad** (migración 012): `asientos(organizacion_id)`,
  `asientos(organizacion_id, fecha)`, `asientos(modulo)`, `asiento_detalle(asiento_id)`,
  `asiento_detalle(cuenta_id)`, `asiento_detalle(cuenta_id, asiento_id)`. Cache TTL 60s en
  `GET /contabilidad/cuentas-corrientes` (se invalida con "Empezar limpio").
- **Fix campana de alertas**: navegaba a `/resumen` pero el `AlertasWidget` vive en el Dashboard
  (`/`) — el usuario veía el badge pero al clickear no encontraba las alertas. Corregido a `/`.
- **Fix badge de campana inflado sin alertas reales**: `filas_atrasadas` contaba como urgencia
  `"media"` en el total del badge aunque fuera informativo — bajado a `"baja"` (sigue visible en
  `AlertasWidget`, ya no infla el número de la campana).
- **Fix micrófono/cámara bloqueados en la PWA**: `Permissions-Policy` en `vercel.json` y `main.py`
  tenía `microphone=(), camera=()` — paréntesis vacíos bloquean TODOS los orígenes, incluido el
  propio sitio. Cambiado a `microphone=(self), camera=(self)`. Afectaba dictado por voz en el
  asistente IA y OCR de fotos (cheques/comprobantes).
- SVG icons (reemplaza emojis 👁️/🙈) en Login, landing (secciones Seguridad/El Problema);
  `CuadraLogo` centrado; layout mobile de Organizaciones.

### v3.19 — Módulo IVA Proyección y DDJJ (junio 2026 — PR #147)

- **Qué hace**: proyecta el IVA de un período (mes) a partir de los asientos contables ya
  registrados, cruzados con una `tasa_iva` configurable por cuenta. Cuadra no emite facturas, así
  que el **Débito Fiscal es una proyección** (no un dato legal real) calculada sobre las cuentas de
  ingreso que el admin marca como gravadas. El **Crédito Fiscal** combina una proyección similar
  sobre gastos gravados + el crédito fiscal REAL ya contabilizado en `1-1-2-4 IVA Crédito Fiscal`
  (p. ej. de liquidaciones de Tarjetas). La UI deja explícito en todo momento que es una
  herramienta de estimación interna, no una liquidación oficial ante ARCA.
- **`PlanCuenta.tasa_iva`** (Numeric 5,4 nullable) — % de IVA por cuenta, configurable en
  `/iva` → tab Config (`admin_accounting`). **No se restringe a cuentas hoja**: algunos módulos
  (Pagos → `registrar_egreso`) postean directo contra cuentas cabecera como `3-2-0-0 Gastos`, así
  que esa cuenta también debe poder marcarse como gravada — la agregación es por `cuenta_id` exacto
  de cada línea de asiento, así que no hay riesgo de doble conteo entre una cuenta y sus subcuentas.
- **Cuentas nuevas en el plan**: `2-2-0-0 Impuestos a pagar` / `2-2-1-0 IVA Débito Fiscal`
  (idempotente vía PLAN_PATCH, no toca Org A).
- **Modelo `ProyeccionIva`** (tabla `proyecciones_iva`, unique por org+período): snapshot
  débito/crédito/saldo + estado `proyectado`/`presentado` + detalle JSON por cuenta. Marcar como
  `presentado` (DDJJ ya enviada a ARCA) la deja **inmutable** — recalcular no la pisa.
- **Excluye `tarjeta_liq` del crédito proyectado**: ese asiento ya postea el IVA REAL del arancel
  contra `1-1-2-4` en la misma operación — si además se marca como gravada la cuenta de aranceles
  (Visa/Mastercard/Amex), el sistema NO suma proyectado ahí también (evita doble conteo, hallazgo
  de code review corregido antes de mergear).
- **`services/iva_service.py`**: `calcular_proyeccion_iva` (preview, no persiste),
  `guardar_o_actualizar_proyeccion` (upsert idempotente), `marcar_presentada`. Todo en `Decimal`,
  fechas con `tz.now_art()`.
- **`routers/iva.py`** (prefix `/iva`) — permisos en 3 capas: `GET/PUT /iva/config` (tasa por
  cuenta) → `admin_accounting`; `GET /iva/proyeccion` (preview) → `view_accounting`;
  `POST /iva/proyeccion/calcular` (persiste) → `manage_finance`;
  `POST /iva/proyeccion/{id}/marcar-presentada` → `admin_accounting`;
  `GET /iva/historial` (paginado) → `view_accounting`.
- **Frontend `/iva`**: 3 tabs — Proyección (período, preview en vivo, calcular y guardar, marcar
  presentada con confirm), Historial (paginado, saldo color-coded), Config (tasa por cuenta,
  ingresos vs gastos). Nav item gated `view_accounting`; acciones de escritura gated dentro de la
  página. Migración 013 + safety nets en `main.py`. 14 tests nuevos (`test_iva.py`). 333 tests
  pasando en total.

### v3.20 — Módulo Control Semestral Monotributo (junio 2026 — PR #148)

- **Qué hace**: herramienta de **control/alerta interna** (NO una declaración oficial) que proyecta
  los ingresos de los ÚLTIMOS 12 MESES de la organización (a partir de los asientos ya registrados)
  y los compara contra las escalas de categoría del Monotributo de ARCA, para anticipar si
  corresponde recategorizarse o si se excedió el régimen antes del corte semestral (30/jun, 31/dic).
- **Ventana de 12 meses por corte**: S1 → corte 30/jun/YYYY → ventana [1/jul/(YYYY-1), 30/jun/YYYY];
  S2 → corte 31/dic/YYYY → ventana [1/ene/YYYY, 31/dic/YYYY]. Criterio de ingreso idéntico a
  `iva_service.py` (cuentas `resultado` que empiezan con `3-1`, haber − debe).
- **Modelos nuevos** (`app/models/monotributo.py`): `CategoriaMonotributo` (escala editable por
  org+tipo_actividad+categoría), `MonotributoConfig` (opt-in por org, `activo=False` por default,
  `categoria_actual`, `tipo_actividad` servicios/bienes), `ControlMonotributo` (snapshot por
  período, **inmutable una vez `estado="revisado"`** — mismo patrón que `ProyeccionIva`).
- **`services/monotributo_service.py`**: `evaluar_categoria()` sugiere la categoría de menor `orden`
  cuyo `limite_anual >= ingresos_12m`, o la más alta con `excede=True` si supera el tope de todas.
  `guardar_o_actualizar_control()` hace upsert pero no pisa un control ya revisado.
- **Escala sembrada con valores REALES vigentes de ARCA** (no placeholders) — `_LIMITES_VIGENTES` en
  `monotributo_service.py`, corroborados vía prensa especializada (afip.gob.ar bloquea fetch directo
  con 403 anti-bot). El límite anual por categoría es el MISMO para servicios (A-H) y bienes (A-K) —
  lo que difiere entre actividades es la cuota mensual a pagar, no la escala de ingresos (este módulo
  no calcula esa cuota). **Vence con la próxima actualización semestral de ARCA (jul/ago 2026)** —
  ver recordatorio en "Pendiente para próximas sesiones" más arriba. Completamente editable vía
  `PUT /monotributo/categorias/{id}`, sin valores hardcodeados en la lógica.
- **Router `/monotributo`** — permisos en 3 capas: `GET/PUT /monotributo/config` → `admin_accounting`;
  `GET /monotributo/categorias`/`GET /monotributo/control` (preview)/`GET /monotributo/historial`
  (paginado) → `view_accounting`; `PUT /monotributo/categorias/{id}` → `admin_accounting`;
  `POST /monotributo/control/calcular` (persiste) → `manage_finance`;
  `POST /monotributo/control/{id}/marcar-revisado` → `admin_accounting`.
- **Frontend `/monotributo`**: 3 tabs — Control Semestral (selector de período, preview en vivo,
  barra de progreso color-coded, alertas de recategorización/exceso de régimen), Historial
  (paginado), Config (activo, tipo_actividad, categoría actual, tabla editable de límites por
  categoría con disclaimer de verificar contra ARCA). Mismo estilo que `/iva`. Nav gateada
  `view_accounting`. Migración `014_monotributo` + safety nets idempotentes en `main.py` (seed al
  crear org nueva + backfill para orgs existentes). 19 tests nuevos (`test_monotributo.py`). 352
  tests pasando en total.

### v3.21 — Módulo Ingresos Brutos y Convenio Multilateral (junio 2026 — PR #154)

- **Qué hace**: herramienta de **proyección interna** (NO una DDJJ oficial) que estima el impuesto a
  los Ingresos Brutos de un período (mes) a partir de los ingresos contables ya reconocidos, aplicando
  alícuotas que la organización configura por jurisdicción. Sirve para que el estudio anticipe cuánto
  va a pagar de IIBB antes de armar la declaración real ante AGIP/ARBA o el organismo provincial.
- **Dos modos de cálculo** (`IIBBConfig.modo`, opt-in por org, `activo=False` por default):
  - `simple`: la org opera en UNA jurisdicción → `ingreso_total × alícuota` de la jurisdicción única
    (`IIBBConfig.jurisdiccion_unica_id`).
  - `convenio_multilateral`: la org opera en VARIAS jurisdicciones → el ingreso total se distribuye
    según el `coeficiente_distribucion` de cada jurisdicción activa y a cada porción se le aplica SU
    PROPIA alícuota. El coeficiente es un **% editable por la org** (no se recalcula desde
    ingresos/gastos del ejercicio anterior — es proyección interna, no la DDJJ del Convenio).
- **Criterio de ingreso idéntico a `iva_service.py`/`monotributo_service.py`**: cuentas `resultado`
  cuyo código empieza con `3-1`, sumando (haber − debe) de los `AsientoDetalle` del mes filtrando por
  `Asiento.fecha` y `organizacion_id`.
- **NO se siembran alícuotas reales** (a diferencia de Monotributo): las 24 jurisdicciones argentinas
  (CABA + 23 provincias) tienen su propio régimen, alícuotas que varían por actividad y cambian con
  frecuencia. `seed_iibb_jurisdiccion()` crea UNA jurisdicción ILUSTRATIVA ("CABA (ejemplo — completar)",
  alícuota 0) y el admin DEBE completar/verificar todo contra AGIP/ARBA/organismo provincial. Todo
  100% editable vía API/UI. Disclaimer visible en la página (mismo tono que Monotributo).
- **Validación de coeficientes (no bloqueante)**: en `convenio_multilateral`, si la suma de
  `coeficiente_distribucion` de las jurisdicciones activas ≠ 100% (tolerancia 0.0001), el cálculo
  SIGUE funcionando (es interno) pero la respuesta incluye `suma_coeficientes` + un `warning` explícito
  para que el usuario lo corrija en Config. La UI muestra una alerta ámbar.
- **Modelos nuevos** (`app/models/iibb.py`): `JurisdiccionIIBB` (nombre, alícuota Numeric 5,4,
  coeficiente Numeric 5,4, activa, orden, unique org+nombre), `IIBBConfig` (1 por org, opt-in, modo,
  FK `jurisdiccion_unica_id`), `ProyeccionIIBB` (snapshot por período, unique org+período, detalle JSON
  por jurisdicción, **inmutable una vez `estado="presentado"`** — mismo patrón que `ProyeccionIva`).
- **`services/iibb_service.py`** (puro, sin FastAPI, Decimal + `tz.now_art()`):
  `calcular_ingreso_periodo`, `calcular_proyeccion_iibb` (preview, no persiste, devuelve detalle +
  warning), `guardar_o_actualizar_proyeccion` (upsert idempotente, no pisa presentada),
  `marcar_presentada`, `seed_iibb_jurisdiccion`.
- **Router `/iibb`** — permisos en 3 capas: `GET/PUT /iibb/config` → `admin_accounting`;
  `GET/POST /iibb/jurisdicciones`, `PUT /iibb/jurisdicciones/{id}` → `admin_accounting` (409 si nombre
  duplicado, 422 si alícuota/coef fuera de [0,1]); `GET /iibb/proyeccion` (preview) → `view_accounting`;
  `POST /iibb/proyeccion/calcular` (persiste) → `manage_finance`;
  `POST /iibb/proyeccion/{id}/marcar-presentada` → `admin_accounting`;
  `GET /iibb/historial` (paginado) → `view_accounting`.
- **Frontend `/ingresos-brutos`** (`pages/IngresosBrutos.tsx`): 3 tabs — Proyección (selector de mes,
  preview en vivo, calcular y guardar, alerta si coeficientes ≠ 100%, desglose por jurisdicción,
  marcar presentada con confirm), Historial (paginado), Config (activo, modo, selector de jurisdicción
  única en modo simple, tabla editable de jurisdicciones con alta inline + toggle activa + columna
  coeficiente solo visible en convenio_multilateral, disclaimer AGIP/ARBA). Mismo estilo que `/iva` e
  `/monotributo`. Nav gateada `view_accounting`. Las tasas se ingresan como % (5 = 5%) y se guardan
  como fracción.
- **Migración `015_iibb`** + safety nets idempotentes en `main.py` (3x `CREATE TABLE IF NOT EXISTS` +
  índices + seed de jurisdicción ilustrativa al crear org nueva / backfill para orgs existentes).
  Org A intacta (solo aditivo). 23 tests nuevos (`test_iibb.py`: simple, convenio, warning de
  coeficientes, inmutabilidad post-presentado, permisos por capa, aislamiento multi-org). 375 tests
  pasando en total.

### v3.22 — Módulo Liquidador de Sueldos y F931 (junio 2026 — PR #155)

- **Qué hace**: herramienta de **liquidación interna de sueldos + proyección del F931** (la DDJJ
  mensual de AFIP/ARCA de aportes y contribuciones de la seguridad social). Por cada empleado activo
  de la org calcula sueldo bruto (+ SAC proporcional), aportes del empleado, contribuciones del
  empleador y sueldo neto; los totales agregados son la base del F931 (total remuneraciones, total
  aportes, total contribuciones). La UI deja explícito que **NO sustituye un sistema de liquidación
  de sueldos homologado ni reemplaza el SUSS/AFIP** — es gestión interna del estudio.
- **Dominio de datos nuevo (empleados)** — primer módulo del plan que agrega un dominio, no solo
  proyección sobre asientos. Modelos en `app/models/sueldos.py`:
  - `ConvenioColectivo` (org-scoped, unique org+nombre) — varios convenios por org.
  - `CategoriaConvenio` (FK convenio, unique convenio+nombre, `sueldo_basico` Numeric 12,2).
  - `Empleado` (org-scoped, `cuil` 11 dígitos validado igual que CUIT de clientes, FK convenio/
    categoría nullable, `sueldo_basico` override del de la categoría, `cargas_familia`, `activo`,
    **soft delete `deleted_at`** — mismo patrón que Planilla).
  - `ConfigSueldos` (1 por org, opt-in `activo=False` por default, igual patrón que IIBBConfig) con
    las alícuotas de aportes (jubilación/INSSJP/obra social) y contribuciones (jubilación/INSSJP ley
    19032/obra social/asignaciones familiares/fondo desempleo/ART). **Sembradas como DEFAULT EDITABLE**
    con valores de referencia 2024 (esquema nacional ley 27.541: aportes 11%+3%+3%; contribuciones
    ~18%) y nota "verificar vigencia con tu contador/AFIP". **ART queda en 0 obligatoriamente**
    editable (varía 100% por póliza). A diferencia de IIBB sí se siembran defaults porque el esquema
    de seguridad social es nacional y estable; igual de explícito que el disclaimer de Monotributo.
  - `LiquidacionSueldoPeriodo` (snapshot por org+período unique, estados borrador/aprobado/presentado,
    **inmutable una vez `presentado`** — mismo patrón ProyeccionIva/IIBB/ControlMonotributo).
  - `DetalleLiquidacionEmpleado` (FK liquidación+empleado, bruto/sac/aportes/contribuciones/neto +
    `detalle_json` con el desglose de cada concepto).
- **`services/sueldos_service.py`** (puro, sin FastAPI, Decimal + `tz.now_art()`):
  `calcular_liquidacion_periodo` (preview, no persiste), `guardar_o_actualizar_liquidacion` (upsert
  idempotente, reemplaza detalles, no pisa presentado), `aprobar_liquidacion` (genera asiento),
  `marcar_presentada` (inmutable), `get_o_crear_config`, `seed_config_sueldos`.
  - **Básico**: override del empleado → básico de su categoría → 0.
  - **SAC proporcional — SIMPLIFICACIÓN DOCUMENTADA**: el SAC legal se devenga semestralmente; aquí
    se usa la provisión mensual `sac = básico / 12` (práctica contable habitual de costeo laboral
    mensual). NO es el cálculo legal del recibo de junio/diciembre. El SAC integra la base imponible
    (bruto = básico + sac). Documentado en el docstring del service.
  - aportes = bruto × Σ alícuotas de aporte ; contribuciones = bruto × Σ alícuotas de contribución
    (incluye ART) ; neto = bruto − aportes.
- **Asiento contable agrupado** al aprobar (`registrar_liquidacion_sueldos` en `motor_contable.py`,
  módulo `sueldos_liquidacion`, 3 líneas vía `_crear_asiento_multilinea`):
  Sueldos y cargas sociales (3-2-4-0, gasto) **D** por bruto+contribuciones / Sueldos a pagar
  (2-1-4-0) **H** por el neto / Cargas sociales a pagar (2-1-5-0) **H** por aportes+contribuciones.
  Partida doble: D = bruto+contrib ; H = neto + aportes + contrib = bruto+contrib ✓. Idempotente por
  (modulo, referencia_id=liquidacion_id, org). 3 cuentas nuevas en PLAN_PATCH (no toca Org A).
- **Router `/sueldos`** — permisos en 3 capas: CRUD de Convenios/Categorías/Empleados +
  GET/PUT `/sueldos/config` → escritura `admin_accounting`, lectura `view_accounting`; DELETE
  (convenios/categorías/empleados) → `delete_records`; `GET /sueldos/liquidacion` (preview) →
  `view_accounting`; `POST /sueldos/liquidacion/calcular` y `.../{id}/aprobar` → `manage_finance`;
  `POST .../{id}/marcar-presentada` → `admin_accounting`; `GET /sueldos/historial` (paginado) →
  `view_accounting`. Empleados con soft delete (DELETE setea `deleted_at` + `activo=False`).
- **Frontend `pages/Sueldos.tsx`**: 4 tabs — **Empleados** (alta/edición + convenios/categorías
  inline), **Liquidación** (selector de período, preview en vivo, calcular/guardar borrador, aprobar
  con asiento, marcar presentada, card "Base del F931", desglose por empleado), **Historial**
  (paginado), **Config** (activo + alícuotas de aportes/contribuciones editables con disclaimer
  "valores de referencia — verificar vigencia"). Mismo estilo que `/iva` e `/ingresos-brutos`. Nav
  gateada `view_accounting` (ícono Users). Las tasas se ingresan como % (11 = 11%) y se guardan como
  fracción.
- **Migración `016_sueldos`** + safety nets idempotentes en `main.py` (6x `CREATE TABLE IF NOT EXISTS`
  + índices + seed de ConfigSueldos apagada al crear org nueva / backfill para orgs existentes).
  Org A intacta (solo aditivo). 23 tests nuevos (`test_sueldos.py`: cálculo, aportes/contribuciones,
  SAC, básico de categoría, inmutabilidad, permisos por capa, aislamiento multi-org, asiento con
  partida doble, validación CUIL, soft delete, end-to-end API). **398 tests pasando en total.**

- **Extensión — Retención de Ganancias 4ta categoría (opt-in)**: `ConfigSueldos` agrega
  `ganancias_activo` (default False), `minimo_no_imponible` y `deduccion_especial` (Numeric 12,2).
  Nueva tabla `EscalaGanancias` (org-scoped, tramos `tramo_desde`/`tramo_hasta` nullable/`alicuota`/
  `monto_fijo`) — **arranca VACÍA a propósito** (los valores de la escala de AFIP/ARCA cambian
  periódicamente; no se siembran placeholders que aparenten ser reales). `calcular_ganancias_4ta()`
  en `sueldos_service.py`: si `ganancias_activo=False` o la escala está vacía devuelve 0 sin romper
  nada; si está activo, **anualiza el bruto mensual ×12** (misma simplificación documentada que el
  SAC proporcional — no reproduce el cálculo legal exacto acumulativo mes a mes) y aplica la fórmula
  AFIP `monto_fijo + alícuota × (excedente sobre tramo_desde)`, devolviendo la retención mensual
  (anual / 12). Nuevo campo `retencion_ganancias` en `DetalleLiquidacionEmpleado`, restado del neto.
  CRUD de la escala (`GET/POST/PUT/DELETE /sueldos/escala-ganancias`) → `admin_accounting`; lectura
  vía `GET /sueldos/escala-ganancias` → `view_accounting`. UI: card en tab Config con checkbox de
  activación, disclaimer de cargar la escala vigente antes de activar, tabla editable de tramos.
  Migración `017_ganancias` + safety nets idempotentes. **Bug real detectado y corregido durante la
  extensión siguiente**: `guardar_o_actualizar_liquidacion` no persistía `retencion_ganancias` en
  `DetalleLiquidacionEmpleado` (quedaba en 0 al recalcular y guardar, aunque el preview sí lo
  calculaba bien) — corregido junto con el recibo en PDF.
- **Extensión — Recibo de sueldo en PDF**: `recibo_sueldo_pdf()` en `services/pdf_export.py`, mismo
  patrón reportlab que `estado_cuenta_pdf`/`cuenta_corriente_pdf` (header de marca, columnas
  Haberes/Descuentos, contribuciones del empleador como informativo, neto a pagar destacado).
  Footer aclara explícitamente: *"Liquidación interna de gestión — no reemplaza el recibo oficial de
  sueldo según la Ley de Contrato de Trabajo (Ley 20.744)"*. Endpoint
  `GET /sueldos/liquidacion/{id}/empleado/{empleado_id}/recibo-pdf` → `view_accounting`, resuelve
  nombre de convenio/categoría inline (el helper compartido `_empleado_dict` solo devuelve IDs, no se
  tocó para no afectar otros endpoints). `StreamingResponse` + `Content-Disposition`, mismo patrón
  que el PDF de cuenta corriente. Botón **"PDF"** por fila de empleado en la tabla de la tab
  Liquidación (visible solo si la liquidación ya fue calculada/guardada — necesita el `id` persistido,
  no solo el preview). 5 tests nuevos (PDF válido, permisos, 404 liquidación/empleado inexistente,
  retención de Ganancias incluida en el cálculo). 411 tests pasando en total.
- **Extensión — Export SICOSS (formato de referencia)**: `services/sicoss_export.py` —
  `generar_archivo_sicoss()` construye un archivo de texto de ancho fijo (106 bytes por registro,
  un registro por `DetalleLiquidacionEmpleado`) a partir de una liquidación ya aprobada/presentada.
  **El docstring del módulo documenta explícitamente, columna por columna, qué es confiable y qué es
  placeholder** — ver detalle completo en el archivo. Resumen: CUIL, nombre, remuneración bruta,
  remuneración imponible jubilatoria (≈ bruto, sin topes SIPA), aporte jubilatorio, contribución
  patronal, retención de Ganancias y fecha de ingreso vienen de datos reales de Cuadra; situación de
  revista, condición, código de actividad y código de zona son **placeholders fijos documentados**
  porque Cuadra no captura esos datos hoy. Se eligió un archivo honestamente incompleto (con
  placeholders explícitos) en vez de uno que aparente estar completo con datos inventados. Endpoint
  `GET /sueldos/liquidacion/{id}/exportar-sicoss` → `manage_finance`; HTTP 400 si la liquidación está
  en `borrador` (debe estar aprobada o presentada). Botón **"Exportar SICOSS"** + disclaimer ámbar en
  la tab Liquidación: *"formato de referencia — verificá contra la última especificación de AFIP/Mis
  Aplicaciones Web antes de importarlo, puede requerir ajustes"*. 8 tests nuevos (ancho de línea, un
  registro por empleado activo, 400 en borrador, 403 sin permiso, 404 liquidación inexistente,
  helpers de centavos/CUIL). **419 tests pasando en total.**
- **Fix asiento Ganancias (auditoría post-merge)**: la retención de 4ta categoría ahora tiene
  contrapartida en `2-1-6-0 Retención de Ganancias a depositar` (nueva cuenta en PLAN_PATCH); sin ella
  el asiento descuadraba (el neto ya viene con la retención restada) y la red de partida doble lo dejaba
  sin postear en silencio al activar Ganancias, dejando la liquidación aprobada sin asiento. Se agregó la
  columna `total_retencion_ganancias` en `LiquidacionSueldoPeriodo` (migración 018 + safety net) que se
  persiste y se pasa a `registrar_liquidacion_sueldos` como 4ta línea al Haber. SICOSS: `assert` de ancho
  de registro → `ValueError` (los assert se desactivan con `python -O`). 421 tests pasando.

### v3.23 — Asistente IA proactivo y explicativo (junio 2026 — PR #159)

- **Qué hace**: primer paso del plan de mejora del asistente acordado con Julieta — que deje de ser
  "solo respuestas a lo que se le pregunta" y empiece a (a) avisar proactivamente lo importante del
  día sin que se le pregunte, y (b) explicar en lenguaje claro POR QUÉ algo no concilió, en vez de
  devolver solo números.
- **Tool `consultar_alertas`** (`agente.py`): reusa `reportes_service.calcular_alertas()` (mismo dato
  que `/analisis/alertas` y el `AlertasWidget` del Dashboard) — cheques urgentes/vencidos, filas
  atrasadas, movimientos sin asignar. El asistente lo usa proactivamente ante saludos genéricos o
  preguntas tipo "qué necesito ver hoy".
- **Tool `explicar_filas_pendientes`**: query nueva sobre `PlanillaRow` + `Planilla` + `Cliente`
  (`status != "ok"`, filtro opcional por nombre de cliente) que devuelve el detalle de cada fila
  pendiente (monto, cuit, titular, status, `comentario_revision`). Le permite al asistente traducir
  los status internos del motor de conciliación (`no está`, `duplicado`, `faltan datos`,
  `EN_REVISION`) a una explicación concreta por cliente, en vez de un código interno.
- **Prompt del sistema reescrito**: pide explícitamente comportamiento proactivo (no esperar a que
  pregunten, chequear alertas/resumen ante saludos genéricos) y explicativo (nunca devolver un número
  sin contexto).
- **Refactor `_run_chat_message()`**: la lógica de chat (config Gemini, tools, loop de 3 rondas de
  function-calling) se extrajo a una función compartida entre `/agente/chat` y el nuevo endpoint de
  saludo proactivo — sin duplicar código.
- **Nuevo `GET /agente/saludo-proactivo`**: usa un prompt interno fijo (no escrito por el usuario)
  para generar un saludo de 2-4 oraciones con lo importante del día. Comparte la cuota diaria
  (`_CHAT_DAILY_LIMIT`) con `/chat` — no es un endpoint nuevo de cuota separada.
- **Frontend (`AgenteChat.tsx`)**: al abrir el chat se llama una vez (`useRef` guard, no en cada
  render) a `/agente/saludo-proactivo`; el resultado se inserta como primer mensaje del asistente.
  Las sugerencias rápidas estáticas siguen visibles como fallback/quick-replies hasta que el usuario
  envía su primer mensaje real — no se pierden si Gemini falla o no está configurado.
- **Mejora de transcripción por audio**: el prompt de `/agente/transcribir` (usado por el flujo
  MediaRecorder de iOS, ver v3.17) era genérico ("transcribí este audio en español") y por eso
  Gemini transcribía mal jerga financiera y nombres propios de clientes. Se agregó un glosario de
  dominio fijo (CUIT, CBU, cheque, planilla, conciliación, extracto, liquidación, comisión, IIBB,
  IVA, monotributo, sueldo) + la lista de nombres de clientes de la organización del usuario
  (`_glosario_transcripcion()`, hasta 200 nombres) como contexto del prompt antes de transcribir.
  No cambia el flujo de SpeechRecognition nativo (Android/Chrome) que ya usaba `lang = 'es-AR'`
  correctamente — solo mejora el fallback de Gemini para iOS.
- 421 tests pasando (sin tests nuevos de `agente.py` — el módulo no tiene suite propia todavía,
  queda anotado como deuda pendiente si se vuelve a tocar este router).

### v3.24 — ARCA (ex-AFIP): facturación electrónica con integración propia WSFEv1 (junio 2026)

- **Qué hace**: emisión de comprobantes electrónicos (Factura A/B/C) con CAE real de ARCA, integrando
  Cuadra DIRECTAMENTE contra los web services SOAP de ARCA (WSAA + WSFEv1) — sin tercerizar en un
  proveedor intermediario. Decisión explícita de Julieta: "Integración propia con WSFEv1".
- **Seguridad del certificado — la parte más sensible del sistema**: el certificado y clave privada
  de cada org se cifran con Fernet (`services/arca_crypto.py`, clave `ARCA_ENCRYPTION_KEY` — env var
  SOLO en Render, nunca en el repo) antes de persistir en `arca_config.certificado_enc` /
  `clave_privada_enc`. El token/sign de WSAA (cacheados ~12h para no reloguear en cada factura)
  también se guardan cifrados (`ultimo_token_enc`/`ultimo_sign_enc`). **Ningún endpoint devuelve estos
  campos** — `_config_dict()` solo expone `tiene_certificado: bool`. Nunca se loguean.
- **`services/arca_wsaa.py`**: login WSAA — genera el TRA (XML con `uniqueId`/`generationTime`/
  `expirationTime`), lo firma CMS/PKCS#7 con la clave privada de la org (vía `cryptography`/`openssl`),
  lo manda al WSAA (homologación o producción según `ArcaConfig.ambiente`) y parsea el `token`+`sign`
  de la respuesta. Cachea en DB cifrado; solo relogea si el token cacheado venció.
- **`services/arca_wsfe.py`**: WSFEv1 — `FECompUltimoAutorizado` (consulta el último número autorizado
  para no pisar numeración) + `FECAESolicitar` (pide el CAE armando el XML del comprobante: tipo,
  punto de venta, concepto, doc tipo/nro del receptor, importes neto/IVA/total, fecha). Parsea CAE +
  vencimiento de la respuesta SOAP o el detalle de rechazo de ARCA si lo hay.
- **Asiento contable** (`registrar_factura_arca()` en `motor_contable.py`): Cliente (2-1-2-X) **D** /
  Ventas facturadas — ARCA (3-1-5-0, cuenta nueva en PLAN_PATCH) **H** neto / IVA Débito Fiscal
  (2-2-1-0, ya existía desde v3.19) **H** IVA. Idempotente por `(modulo="factura_arca",
  referencia_id=comprobante_id, org_id)`. Se dispara solo si la emisión devuelve CAE (nunca para
  comprobantes rechazados o en error).
- **Modelos** (`app/models/arca.py`): `ArcaConfig` (1 por org, opt-in `activo=False` por default,
  `cuit`, `ambiente` homologación/producción, `punto_venta`, certificado/clave/token cifrados) y
  `ComprobanteArca` (tipo de comprobante, cliente, importes, `cae`/`cae_vencimiento`, estado
  `borrador|emitido|rechazado|error`, `error_detalle`). **Inmutable una vez `emitido`** — re-emitir
  devuelve 409 (mismo patrón que `ProyeccionIva`/`ControlMonotributo` al marcar presentado).
- **Router `/arca`** — permisos en 3 capas: `GET/PUT /arca/config` y `POST/DELETE /arca/certificado`
  → `admin_accounting`; `GET /arca/comprobantes` (paginado) y `GET /arca/comprobantes/{id}` →
  `view_accounting`; `POST /arca/comprobantes` (crea borrador) y `POST /arca/comprobantes/{id}/emitir`
  (llama WSAA+WSFEv1, genera el asiento) → `manage_finance`. El router bloquea activar `ArcaConfig`
  sin certificado cargado.
- **Frontend `/arca`** (`pages/Arca.tsx`, mismo patrón que `Iva.tsx`): tab **Comprobantes** (alta de
  borrador con selector de cliente vía `organizaciones[].clientes` — no `clientes`, que excluye
  clientes sin planillas —, botón "Emitir" con confirm, badges de estado) y tab **Config** (activar
  módulo, CUIT, ambiente, punto de venta, subir/borrar certificado por textarea PEM — gateado
  `admin_accounting`). Nav `/arca` gateada `view_accounting`, ícono nuevo en `Layout.tsx`.
- **Migración `019_arca`** + safety nets idempotentes en `main.py` (`CREATE TABLE IF NOT EXISTS` ×2 +
  índices). Org A intacta (solo aditivo — `3-1-5-0` es una cuenta nueva, no toca el plan existente).
  16 tests nuevos (`test_arca.py`: cifrado, permisos por capa, inmutabilidad post-emisión, aislamiento
  multi-org, asiento con partida doble, bloqueo sin certificado). **437 tests pasando en total.**
- **Setup en producción**: generar `ARCA_ENCRYPTION_KEY` (Fernet, 32 bytes urlsafe-base64) y pegarla en
  Render. Sin esa env var el módulo no cifra/descifra y la activación queda bloqueada — degradación
  segura, nunca cae a texto plano.
- **Revisión de correctitud pre-merge** (mismo PR, antes de salir de draft): se evaluó AfipSDK
  (afip.php/js/py/rb) como posible referencia y se descartó — sus repos públicos son clientes
  delgados contra `app.afipsdk.com` (su backend propio con Bearer token), no implementaciones
  abiertas de WSAA/WSFEv1; no firman CMS ni hablan SOAP directo con ARCA. Se usó en cambio
  `PyAr/pyafipws` (implementación abierta y activamente mantenida) como criterio de comparación:
  confirmó que las URLs de WSAA/WSFEv1 (`afip.gov.ar`, no `arca.gov.ar`) y el `SOAPAction` vacío de
  `loginCms` ya estaban correctos en `arca_wsaa.py`/`arca_wsfe.py`. Encontró y corrigió dos problemas
  reales: (1) **bug de datos faltantes** — `FchServDesde`/`FchServHasta`/`FchVtoPago` son obligatorios
  ante ARCA cuando `Concepto` es 2 (servicios) o 3 (ambos), y no existían en `DatosComprobante` ni en
  el XML de `FECAEDetRequest`; cualquier factura de servicios habría sido rechazada por ARCA. Se
  agregaron las 3 fechas a `ComprobanteArca` (3 columnas nuevas), `ComprobanteIn`, `DatosComprobante`
  y al XML (solo cuando concepto≠1, con validación tanto en el router como en `arca_wsfe.solicitar_cae`
  como segunda red de seguridad); UI en `Arca.tsx` con selector de Concepto + 3 campos de fecha
  condicionales. (2) **comentario engañoso** — el docstring de `arca_wsaa.py` decía que la firma
  CMS/PKCS#7 era "detached" cuando en realidad (correctamente) es NO detached/attached — corregido
  para que un futuro mantenimiento no "arregle" agregando `PKCS7Options.DetachedSignature`, lo que
  rompería la integración en producción. 3 tests nuevos. **440 tests pasando en total.**

---

## Checkpoints / releases

Nota: son referencias documentales del changelog, no siempre tags físicos de git — antes de un
`git checkout vX.Y` correr `git tag` y confirmar que existe; tags reales hoy: `v2.1`, `v2.2`,
`v3.14-stable`, `v3.22`, `dnda-software-2026-v1`.

- `v3.1-stable-checkpoint` — antes de las 5 features de mayo 2026
- `v3.2-stable-checkpoint` — después de seguridad hardening + Numeric migration + legal pages (mayo 2026)
- `v3.3-stable-checkpoint` — después de export robusto, comisiones, landing page, Borrar UM
- `v3.4-stable-checkpoint` — después de comisión por ítem, fusionar clientes, responsive fixes (mayo 2026)
- `v3.6` — contabilidad automática UM, cuentas corrientes como módulo propio, permisos en 3 capas,
  backfill de cuentas corrientes, borrar OP (mayo 2026 — PRs #36–#39 mergeados a main)
- `v3.7-stable-checkpoint` — rol CONTADOR + login por aprobación + PDF Cuadra + switch de org para
  contadores (allowed_org_ids) + fix email .test + fix crash React #31 (mayo 2026 — PRs #56-#58
  mergeados a main)
- `v3.8` — reset Libro Diario (reconstruye asientos limpio + numero_asiento), filtros Excel en el
  diario (fecha/concepto/cuenta), orden de fechas más reciente arriba, columna "Concepto", fix tipos
  TS (lazyPage, Login) (mayo 2026 — PRs #63-#68 mergeados a main)
- `v3.9` — módulo unificado Pagos (reemplaza OP+Pagos+Gastos), libro diario limpio (asientos
  correctos con cuentas hoja, drop tablas viejas, numeración correlativa automática), compartir
  cheques por WhatsApp, asistente IA Gemini Flash con function calling + dictado por voz
  (mayo 2026 — PRs #74-#77 mergeados a main)
- `v3.9.1` — OCR de fotos con Gemini Flash: cheques (número, banco, titular, monto, fechas) y
  comprobantes de transferencia (monto, fecha, beneficiario, referencia). Mismo GEMINI_API_KEY.
  Endpoints: POST /agente/ocr-cheque, POST /agente/ocr-transferencia (mayo 2026)
- `v3.9.3` — Asistente IA: logo Cuadra + botón circular con auto-hide, manejo de errores Gemini
  (retry 429, clasificación API key/cuota/modelo, key strip), modelo default `gemini-2.5-flash`
  (2.0-flash deprecado 1/6/2026), `GEMINI_MODEL` configurable (mayo 2026 — PRs #82-#84)
- `v3.9.2` — Cheques mejorado: portadores (selector + inline add), librador reemplaza titular,
  CP + local/interior auto, 3 tabs (Todos/Por depósito/Rechazados), Excel por fecha de depósito,
  modal rechazo con físico + fecha devolución, ícono Loco de Cuadra en asistente IA (mayo 2026)
- `v3.9.4` — usuarios filtrados por org activa + columna Org, CONTADOR ve contabilidad completa en
  solo lectura, cliente inline en cheques, renombrar extractos inline, "A favor de"/"Nro. OP" en pagos,
  fix borrar usuario sin error FK (mayo 2026)
- `v3.10` — ciclo contable completo de cheques (registro 3 líneas / acreditación 2 asientos con selector
  de banco / rechazo 3 asientos con gastos bancarios), cuentas tránsito que netean a cero, acreditación
  masiva, cuentas nuevas del plan (Banco 2, Cheques en cartera, Cheques depositados, Comisiones cheques,
  Gastos de rechazos), cliente requiere cuenta antes de cargar cheque, 152 tests (junio 2026 — PR #88)
- `v3.10.1` — cold-start fix (retry interceptor axios 3 intentos, backoff 1.5s/3s/4.5s, bootstrap
  conserva sesión en errores transitorios), comisión L/I de cheque por cliente (`porcentaje_comision_local`
  + `porcentaje_comision_interior`, auto-deriva al crear cheque, UI chip simple % general),
  fix WhatsApp share (suppressLockForShare, fondo blanco canvas, AbortError como éxito)
  (junio 2026 — PRs #90-#92)
- `v3.10.2` — landing rediseñada: mockups animados (conciliación/OCR/asistente IA), calculadora
  interactiva, spotlights, comparativa, testimoniales; fondo blanco (#FFFFFF), sin sticky bar mobile,
  steps contacto en línea, WA en spotlight, script tema síncrono en head (junio 2026 — PRs #94-#95)
- `v3.10.3` — dashboard onboarding checklist (3 pasos, barra progreso, dismiss por org) + alertas
  widget (chips cheques/planillas/movimientos, light+dark mode, navega al módulo) (junio 2026 — PR #100)
- `v3.11` — ajuste manual Libro Diario (modal con cuentas hoja, reverso no destructivo), 2FA por email
  para Superadmin y Admin (código 6 dígitos SHA256, TTL 10 min, modelo TwofaCode, degradación elegante
  sin RESEND_API_KEY), delete_records quitado del Operador (principio de menor privilegio),
  fix onboarding checklist (dataLoaded + Promise.all, auto-dismiss inmediato en orgs con datos)
  (junio 2026 — PR #102)
- `v3.11.1` — fix imagen negra WhatsApp (canvas fondo blanco), contraste mensajes dark/light en
  Dashboard/Caja/Perfil/Historial/Cheques/Resumen, Cheques light mode completo (dual-mode),
  PDF scanner Cheques (aspect ratio + canvas blanco), OCR monto Pagos (parseMonto + error visible),
  lazy loading clientes/categorias en Pagos.
- `v3.11.2` — fix fecha local UTC-3 en Pagos/Caja/Clientes/EstadoCuenta/Resumen/Historial
  (localIsoDate vs toISOString que daba ayer antes de las 3 AM ART), light mode Caja historial +
  EFT inputs, Compartir page dual-mode completo, Cheques stats colores light mode (junio 2026).
- `v3.11.3` — editar cheque inline (✏️, PATCH /cheques/{id}, form reutilizado), export Excel
  todos los cheques (GET /cheques/exportar con filtros), comisión auto-calculada desde % (sin campo
  monto plano), stats cards overflow fixed (truncate), fix fechas bidireccional Libro Diario
  (POST /contabilidad/fix-fechas-utc: adelantar/atrasar por rango, dry_run, afecta Asiento+Egreso)
  (junio 2026 — PR #103).
- `v3.11.4` — botones de borrar ocultos por permiso delete_records (Usuarios, Liquidaciones),
  Sentry opt-in (SENTRY_DSN en Render / VITE_SENTRY_DSN en Vercel, sin overhead si no configurado),
  validación post-parse extracto (400 si 0 movimientos o montos todos cero) (junio 2026 — PR #104).
- `v3.12` — editar pago (PATCH /pagos/{id}, modal inline, reverso contable), fix DELETE /pagos
  (decorador faltante), fix selector clientes en Pagos (todos los clientes, no solo con planillas),
  OCR monto (BUG-03: type=number + formato argentino), compartir PDF (BUG-02: fire-and-forget),
  SVG icons en Pagos/Cheques (reemplaza emojis), fix suppress lock cámara 8s vs share 20s,
  BUGS.md (registro de bugs recurrentes) (junio 2026 — PRs #106-#108).
- `v3.12.1` — auditoría de performance completa: N+1 eliminados (papelera GROUP BY, liquidaciones
  IN batch), migración 010 con 4 índices faltantes (clientes/plan_cuentas/users.organizacion_id,
  plan_cuentas.parent_id), cache TTL 60s server-side para /alertas y /dashboard, limit 500→50 en
  conciliaciones, useMemo en Dashboard (9 derivados) y Cheques (3 totales), bug fix refreshExtractos
  sin activeOrgId, cargarAsientos en paralelo en Contabilidad, fix dep array Historial
  (junio 2026 — PR #114).

- `v3.12-dnda-docs` — expediente DNDA completo en `REGISTRO_OBRA_SOFTWARE/`, rutas locales
  normalizadas (sin usuario de PC), privacidad auditada (junio 2026 — PR #112 mergeado a main)
- `v3.12.1-performance` — auditoría performance completa (N+1, índices, cache TTL, payload,
  rendering). Ver sección v3.12.1 arriba. (junio 2026 — PR #114 mergeado a main)
- `v3.14-stable-checkpoint` — RAMA de checkpoint pre-expansión: legales v3.14 + contabilidad v3.13.
  Punto de retorno si la expansión v3.15 falla en producción (junio 2026 — commit 44ed85d)
- `v3.15` — expansión mayor: 16 bancos (Mercado Pago + 6 regionales), export contable
  (Tango/Holistor/Regisoft/CSV con mapeo por org), módulo Tarjetas (asiento mensual agrupado
  6 líneas + invariante 422), split frontend (Cheques 189L / Contabilidad 85L). 266 tests.
  (junio 2026 — PRs #121-#124 mergeados a main)
- `v3.16` — deuda técnica v3.15 completada: split contabilidad.py (5 sub-módulos), pdfminer.six,
  CSV "1.234,56", 316 tests (+50 integración), tipado `any` eliminado en frontend, UI comisión
  L/I chip expandible en /clientes, tsc TS6133 limpio (0 errores), paginación limit/offset en
  5 endpoints (plan-cuentas, reglas, clientes-cuentas, papelera, clientes-aging).
  (junio 2026 — PRs #126-#133 mergeados a main)
- `v3.17` — audit pre-lanzamiento (índice asientos.numero_asiento, magic bytes en upload de extractos)
  + copy de posicionamiento (software financiero con IA) + audio real en el asistente IA: endpoint
  `POST /agente/transcribir` (Gemini) y MediaRecorder en `AgenteChat.tsx` para que el dictado funcione
  en iPhone, con feedback de errores de micrófono. (junio 2026 — PRs #135-#138 mergeados a main)
- `v3.19` — primer módulo del plan de liquidación de impuestos: IVA Proyección y DDJJ (débito fiscal
  proyectado sobre cuentas de ingreso gravadas, crédito proyectado + crédito real de Tarjetas,
  inmutable al marcar presentada). 333 tests. (junio 2026 — PR #147 mergeado a main)
- `v3.20` — segundo módulo del plan: Control Semestral Monotributo (ventana de ingresos de últimos
  12 meses por corte semestral, sugerencia de categoría/exceso de régimen, escala sembrada con
  valores reales vigentes de ARCA — no placeholders). 352 tests. (junio 2026 — PR #148 mergeado a main)
- `v3.21` — tercer módulo del plan: Ingresos Brutos y Convenio Multilateral (proyección por jurisdicción,
  modo simple vs convenio multilateral con distribución por coeficientes + alícuota propia, warning si
  los coeficientes no suman 100%, sin sembrar alícuotas reales, inmutable al marcar presentada). 375 tests.
  (junio 2026 — PR #154)
- `v3.22` — cuarto módulo del plan: Liquidador de Sueldos y F931 (dominio nuevo de empleados con
  convenios/categorías + soft delete, ConfigSueldos opt-in con alícuotas de aportes/contribuciones
  sembradas como default editable de referencia 2024 / ART en 0, liquidación por período con SAC
  proporcional, asiento contable agrupado de partida doble al aprobar, inmutable al marcar presentada,
  base del F931). 398 tests. Extendido con: retención de Ganancias 4ta categoría opt-in (escala vacía
  por diseño, anualización documentada igual que el SAC), recibo de sueldo en PDF por empleado/período
  (reportlab, disclaimer Ley 20.744), export SICOSS de referencia (ancho fijo, columnas confiables vs.
  placeholder documentadas explícitamente en el código). 419 tests. (junio 2026 — PR #155)
- `v3.23` — asistente IA proactivo (saluda con alertas/resumen del día al abrir el chat, sin esperar
  pregunta) y explicativo (traduce el status interno de conciliación — no está/duplicado/faltan
  datos/EN_REVISION — a lenguaje claro por cliente); mejora de transcripción de audio en iOS con
  glosario de dominio + nombres de clientes de la org en el prompt de Gemini. 421 tests.
  (junio 2026 — PR #159 mergeado a main)
- `v3.24` — ARCA (ex-AFIP): facturación electrónica con integración propia WSFEv1/WSAA (sin
  intermediarios) — certificado y clave privada cifrados con Fernet, nunca expuestos en API ni logs;
  emisión de CAE real contra ARCA homologación/producción; asiento contable automático al emitir
  (Cliente D / Ventas facturadas ARCA H / IVA Débito Fiscal H); inmutable una vez emitido. 437 tests.
  (junio 2026)
