# BUGS.md — Bitácora de bugs recurrentes

Registro de bugs que se repitieron (mismo patrón, distinto lugar) o que vale la pena recordar para
no reintroducirlos. Cada entrada: causa raíz + fix aplicado + cómo evitarlo en código nuevo.

CHANGELOG.md menciona este archivo desde v3.12 pero nunca se había creado — esta es la primera
versión real, reconstruida a partir del historial de fixes documentado ahí.

---

## Fechas en zona horaria Argentina (UTC-3) — el más recurrente

**Patrón:** cualquier código que use `new Date().toISOString()` (frontend) o `date.today()` /
`datetime.now()` (backend, Render corre en UTC) calcula la fecha en UTC. Entre las 21:00 y las
03:00 ART eso da la fecha de **mañana** (frontend) o deja fechas de negocio **un día adelantadas**
(backend) — el bug no aparece en testing diurno, solo entre esas horas.

- **Frontend (v3.11.2):** `new Date().toISOString().slice(0,10)` en formularios de Pagos/Caja/
  Clientes/EstadoCuenta/Resumen/Historial. Fix: helper compartido `localIsoDate()` que usa
  componentes locales (`getFullYear/getMonth/getDate`), no UTC.
- **Backend (v3.11.2):** `date.today()`/`datetime.now()` en el servidor (UTC). Fix:
  `app/services/tz.py` → `hoy_art()` / `now_art()` con `ZoneInfo("America/Argentina/Buenos_Aires")`.
  Excepción a propósito: timestamps de auditoría (`created_at`, expiración de tokens 2FA/reset)
  siguen en UTC — no usar `hoy_art()` ahí.
- **Backfill (v3.11.3):** filas ya guardadas con la fecha UTC corrida necesitaron un endpoint
  `POST /contabilidad/fix-fechas-utc` (dry_run + adelantar/atrasar por rango) para corregirlas
  retroactivamente.

**Cómo evitarlo:** nunca usar `new Date().toISOString()` para fecha de negocio en el frontend, ni
`date.today()`/`datetime.now()` sin tz en el backend. Usar siempre `localIsoDate()` /
`hoy_art()`/`now_art()`.

---

## Estado de cheque: filtrar por `"pendiente"` en vez de `"registrado"` → siempre 0

**Patrón:** el estado canónico de un cheque recién cargado es **`"registrado"`** (`"pendiente"` es un
sinónimo legacy — ver frontend `esRegistrado`). Un backfill de arranque (`main.py`) migra
`UPDATE cheques SET estado='registrado' WHERE estado='pendiente'`, así que en producción **no
existen** filas con `estado == "pendiente"`. Cualquier query que filtre cheques por
`estado == "pendiente"` devuelve **siempre 0/vacío**, silenciosamente.

- **Detectado (v3.29):** 5 lugares filtraban por `estado == "pendiente"` → todos devolvían vacío:
  `reportes_service.calcular_alertas` (alertas de cheques urgentes/vencidos del dashboard —
  nunca disparaban), `_cheques_proximos_vencimiento` (resumen), el saldo de cheques por cliente
  del estado de cuenta, el push de alertas de `backup_scheduler.py` (10:00 ART, nunca notificaba),
  y dos queries del asistente IA (`agente.py`).
- **Fix (v3.29):** constantes en `reportes_service.py` — `CHEQUE_EN_CARTERA = ("registrado",
  "pendiente")` (no depositado aún, para alertas por `fecha_deposito`) y `CHEQUE_PENDIENTE_COBRO =
  ("registrado", "pendiente", "depositado")` (importe aún no cobrado, para el saldo por cliente).
  Se reemplazó `estado == "pendiente"` por `estado.in_(...)` en los 5 lugares.

**Cómo evitarlo:** nunca filtrar cheques por `estado == "pendiente"`. Usar las constantes
`CHEQUE_EN_CARTERA` / `CHEQUE_PENDIENTE_COBRO` (backend) o el helper `esRegistrado` (frontend). El
único uso legítimo de `== estado` es cuando `estado` es un parámetro elegido por el usuario.

---

## Deadlock de Postgres en deploy en caliente (DDL de arranque vs requests en vuelo)

**Patrón:** el DDL de arranque (`app/db_safety.py::SAFETY_NET_DDL` + los loops `indexes`/
`migrations` en `main.py::_init_db`) corre en un thread al bootear la instancia nueva, que **ya
está sirviendo requests**. Un `ALTER TABLE`/`DROP INDEX` toma `AccessExclusiveLock` sobre la tabla;
si un request en vuelo (p. ej. `GET /analisis/alertas` contando `cheques`) sostiene un
`AccessShareLock`, se forma un deadlock y Postgres mata una de las dos transacciones →
`OperationalError: deadlock detected` (500 al usuario, o arranque incompleto).

- **Causa raíz (v3.29):** las ~100 sentencias del safety-net corrían en **una sola transacción**
  (un `connect()`, un `commit()` al final). Esa transacción retenía el `AccessExclusiveLock` de
  ~15 tablas **hasta el commit final**, maximizando la ventana de deadlock. Sin `lock_timeout`, el
  DDL esperaba indefinidamente. Bonus bug: si una sentencia fallaba, el lote entero se abortaba y
  las siguientes no se aplicaban.
- **Fix (v3.29):** helper `main.py::_exec_startup_ddl(conn, sql)` — cada sentencia va en su propia
  transacción con `SET LOCAL lock_timeout = '4s'` (solo Postgres), commit por sentencia (libera el
  lock de la tabla al toque), reintento ante contención de lock/deadlock, y aislamiento de errores
  (una sentencia que falla no aborta las siguientes). Usado en los 3 loops de DDL de arranque.

**Cómo evitarlo:** cualquier DDL que corra en el arranque (o en caliente) debe ir por
`_exec_startup_ddl` (o replicar el patrón: `lock_timeout` + commit por sentencia). Nunca agrupar
muchos `ALTER TABLE`/`CREATE INDEX`/`DROP INDEX` en una transacción larga que sirva de barrera de
locks contra el tráfico de lectura.

---

## Decimal vs float en cálculos monetarios

**Patrón:** columnas `Numeric(12,2)` de SQLAlchemy llegan como `Decimal` a Python, pero código que
asume `float` (comparaciones, JSON, helpers de parseo) rompe con `TypeError` o pierde precisión.

- `parse_importe`/`montos_iguales` no soportaban `Decimal` → fix para aceptar ambos tipos.
- `registrar_log` (auditoría) fallaba con `TypeError` al serializar `Decimal` a JSON.
- `total_conciliado` (Decimal) se convertía a `float` en el camino y perdía precisión en estado de
  cuenta.

**Cómo evitarlo:** todo cálculo o comparación de montos debe asumir `Decimal`, no `float`. Si hace
falta serializar a JSON, convertir explícitamente con `str()` o un encoder custom, nunca confiar en
que el default funcione.

---

## Modo claro (light mode) — páginas dark-first sin variante `dark:`

**Patrón:** varias páginas se escribieron asumiendo dark mode como default, con colores hardcodeados
(`bg-white/3`, `border-white/8`, etc.) que no tienen contraparte en modo claro y quedan ilegibles o
con fondo gris heredado. Reaparece cada vez que se agrega una página nueva sin pensar en ambos modos
desde el inicio.

- Afectó: Cheques (página completa), Caja (historial de arqueos), Compartir, OCR/PDF scanner
  (canvas con fondo transparente que en WhatsApp se ve negro).
- Fix: revisar que todo color tenga su variante `dark:`, y que canvas/imágenes generadas para
  compartir fuercen fondo blanco explícito (no depender del fondo del documento).

**Cómo evitarlo:** al crear una página nueva, probarla en ambos modos antes de dar por terminada la
UI — no es algo que el linter detecte.

---

## Compartir por WhatsApp (mobile) — race conditions y transient activation

**Patrón:** el flujo de compartir imagen/PDF por WhatsApp en mobile tiene dos fallas que volvieron a
aparecer en módulos distintos (Pagos, Cheques):

1. **Race condition de canvas:** leer `img.src` antes de que `img.onload` dispare deja la imagen en
   blanco o corta. Fix: `await` explícito sobre la carga antes de generar el canvas.
2. **Transient activation:** Android/Chrome exige que `navigator.share()` se llame dentro de la
   "ventana" de interacción del usuario (~5s) — un `await` a una request HTTP antes de compartir
   consume esa ventana y el share falla en silencio. Fix: hacer la llamada de compartir
   fire-and-forget (sin `await` bloqueante antes del share).

**Cómo evitarlo:** cualquier función nueva de "compartir" debe llamar a `navigator.share()` lo antes
posible en el handler del click, no después de un `await` a backend.

---

## Borrar usuario sin romper integridad referencial (FK)

**Patrón:** `DELETE` en endpoints con relaciones FK (usuarios, pagos) puede tirar error de
constraint si no se nulifican o reasignan las referencias primero.

- `DELETE /admin/users`: requirió nulificar referencias FK con savepoints antes de borrar.
- `DELETE /pagos/{id}`: faltaba directamente el decorador del router (`@router.delete`), error
  distinto pero mismo área de riesgo (operaciones de borrado mal cubiertas por tests).

**Cómo evitarlo:** todo endpoint `DELETE` sobre una entidad con FKs entrantes necesita test
explícito de borrado con datos relacionados, no solo el caso feliz sin relaciones.

---

## Parseo de montos en formato argentino ("15.000,50")

**Patrón:** inputs `type="number"` del HTML rechazan en silencio el separador de miles argentino
(`.`) y el decimal con coma (`,`) — el usuario escribe un monto válido y el campo queda vacío sin
ningún error visible. Apareció en OCR de montos (Pagos) más de una vez.

- Fix: el input/OCR guarda en formato estándar (`"15000.5"`) y se parsea con un helper
  `parseMonto()` dedicado a formato argentino antes de convertir a número.

**Cómo evitarlo:** nunca asumir que `type="number"` + `parseFloat` alcanza para montos ingresados
por el usuario en Argentina — siempre pasar por `parseMonto()`.

---

## `useEffect` con dependencias incompletas

**Patrón:** efectos que dependen de datos que cargan async (`activeOrgId`, resultado de un
`load()`) pero tienen el array de dependencias vacío o incompleto — corren antes de que el dato
esté listo, o nunca se re-disparan cuando cambia.

- `Dashboard.tsx`: `refreshExtractos()` se llamaba sin esperar `activeOrgId`.
- `Historial.tsx`: `useEffect(() => { load() }, [])` no incluía las dependencias reales del fetch.
- Onboarding checklist: bug cuando `activeOrgId` carga después del primer render.

**Cómo evitarlo:** revisar el lint de `react-hooks/exhaustive-deps` en vez de silenciarlo — si un
`useEffect` necesita un dato async, modelarlo explícitamente en el array de dependencias.

---

## Confusión de keywords al detectar banco por texto ("rio" → Santander vs Banco Rioja/La Pampa)

**Patrón:** detección de banco por substring en el nombre (`"rio" in nombre`) sin límites de
palabra captura falsos positivos cuando se agregan bancos nuevos con nombres parecidos (Banco
Rioja, La Pampa contienen "rio"/similar a substrings ya usados).

**Cómo evitarlo:** al agregar un banco nuevo al detector multi-banco, revisar que ningún substring
nuevo colisione con los existentes — usar coincidencia de palabra completa o lista explícita de
alias, no `in` sobre substrings cortos.

---

Última actualización: junio 2026 (reconstrucción inicial desde CHANGELOG.md, v3.6-v3.24).
