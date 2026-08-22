# Business Rules — Cuadra

> **Documento más crítico del set**: las reglas de negocio **reales**, extraídas
> del código con cita a `archivo:línea`. Si una regla acá no cita código, es un
> error. La óptica de producto está en [`PRODUCT_BIBLE.md`](./PRODUCT_BIBLE.md);
> los flujos en [`WORKFLOWS.md`](./WORKFLOWS.md).
>
> Antes de tocar fechas, montos (`Decimal`) o detección de banco, consultá
> también [`../../BUGS.md`](../../BUGS.md).

---

## 1. Motor de conciliación

Archivo: `backend/app/services/conciliacion.py`.

### 1.1. Scoring por identidad

El score lo calcula `_score_identidad()`
(`conciliacion.py:138-232`). Cada señal otorga un **puntaje base**; encima se
suma el **bonus por fecha** (§1.2). Las señales son **excluyentes y ordenadas**
(la primera que matchea retorna; el titular es fallback que acumula):

| Señal de identidad | Puntos base | Cita |
|---|---|---|
| CUIT exacto (10-11 dígitos) | **12** | `conciliacion.py:174-176` |
| CUIT de planilla como substring de dígitos del movimiento | **12** | `conciliacion.py:180-184` |
| CBU/CVU exacto (22 dígitos) | **10** | `conciliacion.py:188-189` |
| Número en común de longitud ≥ 22 (CBU/CVU por longitud) | **10** | `conciliacion.py:198-199` |
| Número de cuenta largo (≥ 10 dígitos) en común | **8** | `conciliacion.py:200-201` |
| Número de referencia/operación (6-9 dígitos) en común | **6** | `conciliacion.py:202-203` |
| Titular: 2 palabras en orden exacto | **5** | `conciliacion.py:214-217` |
| Titular: 2 palabras presentes en distinto orden | **4** | `conciliacion.py:218-220` |
| Titular: solo primera palabra | **3** | `conciliacion.py:221-224` |
| Titular: única palabra presente | **3** | `conciliacion.py:225-227` |

Notas fieles al código:
- Solo se consideran "palabras" de titular las **alfabéticas de ≥ 3 caracteres**
  (`conciliacion.py:212`), para no filtrar nombres cortos (Ana, Leo, Sol).
- Los números significativos que se cruzan son los de **6 a 22 dígitos**
  (`extraer_todos_numeros`, `conciliacion.py:54`).
- El umbral base `UMBRAL_BASE = 3` está definido (`conciliacion.py:16`) pero la
  lógica vigente usa "monto único vs repetido" (§1.4), no este umbral.

> ⚠️ La tabla de [`../../CLAUDE.md`](../../CLAUDE.md) y la del
> [`../../README.md`](../../README.md) muestran "titular 2 palabras = 5 / 1
> palabra = 3". El código tiene **más granularidad**: 5 / 4 / 3 según orden y
> presencia. Ver "Pendiente de revisar".

### 1.2. Bonus por fecha cercana

`_bonus_fecha()` (`conciliacion.py:110-135`), progresivo, **solo desempata**
(nunca descarta un match por identidad fuerte):

| Distancia | Bonus | Cita |
|---|---|---|
| 0 días (mismo día) | **+5** | `conciliacion.py:127-128` |
| 1-2 días | **+4** | `conciliacion.py:129-130` |
| 3-4 días | **+3** | `conciliacion.py:131-132` |
| 5-7 días | **+2** | `conciliacion.py:133-134` |
| 8-10 días | **+1** | `conciliacion.py:135` |
| > `dias_tolerancia` | **0** | `conciliacion.py:125-126` |

El bonus se aplica **solo dentro de la tolerancia** (`delta > dias_tolerancia`
→ 0). La **tolerancia de fecha por defecto** es **5 días**
(`CONFIG_DEFAULT_ORG["dias_tolerancia_fecha"] = 5`, `conciliacion.py:364`),
configurable por organización vía `dias_tolerancia_fecha`
(`conciliacion.py:272`).

> El comentario del código (`conciliacion.py:118-119`) lista los tramos hasta
> "8-10 días → +1", pero el bonus solo se aplica si la distancia ≤
> `dias_tolerancia`. Con el default de 5 días, los tramos +1 (8-10) y parte de
> +2 (6-7) nunca se alcanzan. Ver "Pendiente de revisar".

### 1.3. Tolerancia de monto

`montos_iguales()` compara con tolerancia **0.01** por defecto
(`conciliacion.py:100-101`); configurable por org vía `tolerancia_monto`
(`conciliacion.py:271`, default `0.01` en `conciliacion.py:362`).

### 1.4. Regla fundamental: monto duplicado → exigir identidad

En `buscar_match()` (`conciliacion.py:255-357`):

- **Monto único** en el extracto (1 solo candidato): se acredita directo, sin
  exigir identidad — no hay ambigüedad (`conciliacion.py:311-312`).
- **Monto repetido** (≥ 2 candidatos del mismo monto): **SIEMPRE** se exige
  identidad vía scoring (`conciliacion.py:314-350`). Razón documentada en el
  código: en un extracto real puede haber 30 movimientos de $50.000 el mismo día
  de clientes distintos (`conciliacion.py:305-310`).
- **Empate de score bajo** entre candidatos (dos con el mismo score y < 5): no
  se arriesga → estado `"ambiguo (N candidatos, mismo score)"`
  (`conciliacion.py:343-348`).

### 1.5. Estados de fila (resultado de la conciliación)

Estados base que produce el motor (`buscar_match` + `conciliar_planilla`):

| Estado | Significado | Cita |
|---|---|---|
| `ok` | Acreditado contra un movimiento | `conciliacion.py:278`, `312`, `350` |
| `no está` | Ningún movimiento con ese monto | `conciliacion.py:284` |
| `duplicado` | La misma fila aparece dos veces en esta corrida y todos los candidatos ya se usaron | `conciliacion.py:296-298` |
| `acreditado DD/MM` | El movimiento ya fue acreditado en una corrida anterior | `conciliacion.py:301-303` |
| `faltan datos` | El monto de la fila no se pudo parsear | `conciliacion.py:413-414` |
| `ambiguo (N candidatos, mismo score)` | Empate de score bajo | `conciliacion.py:348` |
| `sin datos (N mov. …)` | Monto repetido sin ningún identificador | `conciliacion.py:356` |
| `no coincide (N mov. …)` | Hay identificadores pero ninguno matchea | `conciliacion.py:357` |
| `ok` (vía aprendizaje) | Resuelto por patrón aprendido — internamente `"ok (aprendido)"` y luego se guarda como `ok` | `conciliacion.py:452-464` |

**Estados ricos** (opt-in por org, lista en `models/planilla.py:10`
`ESTADOS_RICOS = ["PAGO_PARCIAL", "CONCILIADO_CON_DIFERENCIA", "VENCIDO", "EN_REVISION"]`):

- `EN_REVISION`: si la org habilita el estado, los que serían "faltan datos"/no
  resueltos pasan a cola de revisión en lugar de fallar
  (`conciliacion.py:458-462`).
- `PAGO_PARCIAL`, `CONCILIADO_CON_DIFERENCIA`, `VENCIDO`: se asignan al
  **resolver manualmente** una fila `EN_REVISION` (`resolver_revision`,
  `routers/planillas.py:334-350`). Requiere que la org tenga
  `requiere_cierre_periodo=true` (`routers/planillas.py:315-319`).

> El monto duplicado y el monto ya acreditado se contabilizan ambos como
> `duplicadas` en el resumen (`conciliacion.py:485-486`).

### 1.6. Configuración por organización

`CONFIG_DEFAULT_ORG` (`conciliacion.py:361-367`) — comportamiento de la org base:
```python
{
  "match_rules": ["monto_cuit"],
  "tolerancia_monto": 0.01,
  "dias_tolerancia_fecha": 5,
  "estados_habilitados": ["pendiente","ok","no está","duplicado","faltan datos"],
  "requiere_cierre_periodo": False,
}
```
- `match_rules` con `"referencia"` habilita el match por referencia exacta antes
  del scoring (`conciliacion.py:275-278`, `buscar_match_referencia`
  `conciliacion.py:235-252`).
- Un movimiento solo es candidato si es **libre** (`es_libre()`:
  `cliente_acreditado` es None, vacío o "no identificado" —
  `conciliacion.py:104-107`) o ya pertenece al mismo cliente
  (`conciliacion.py:288-292`).

### 1.7. Bloqueo de planillas duplicadas (por cliente) — desde ago 2026

Archivo: `backend/app/routers/planillas.py` (`upload_planilla`), migración 026.

- `POST /planillas/upload` calcula `fingerprint = sha1(contenido_del_archivo)` y
  rechaza con **409** si ya existe una planilla **activa** (no borrada) con el
  mismo `(cliente_id, fingerprint, organizacion_id)`. Mismo patrón que
  `ExtractoBancario.fingerprint` (§ arquitectura, índice único parcial
  `uq_extracto_fp_org`), acá `uq_planilla_fp_cliente_org` — `WHERE fingerprint
  IS NOT NULL AND deleted_at IS NULL`, así borrar la planilla existente libera
  el fingerprint para re-subir.
- El bloqueo es por **archivo idéntico para el mismo cliente**, no por cliente
  solo: dos clientes distintos pueden subir un archivo con bytes idénticos sin
  problema; el mismo cliente con datos distintos (mes siguiente) tampoco choca
  porque el contenido cambia.
- El mensaje de error incluye el id/fecha de la planilla existente y sugiere el
  camino correcto para el caso de uso real que motivó esto: si lo que cambió es
  el **% de comisión** (se tipea al conciliar, no viaja en el archivo — ver §4.1),
  no hace falta re-subir el archivo — hay que re-conciliar la planilla ya cargada
  con el % correcto.

---

## 2. Deduplicación de Últimos Movimientos (UM)

Archivo: `backend/app/services/extracto_merger.py`,
función `_match_existente()` (`extracto_merger.py:37-55`).

Un movimiento del UM se considera **duplicado** de uno existente si:

1. **(saldo, monto) coinciden** (ambos con tolerancia 0.01) —
   `extracto_merger.py:45-49`; **o**
2. **(fecha_iso, monto, titular_normalizado) coinciden** —
   `extracto_merger.py:50-54`.

`titular_normalizado` = quita CUITs (10-11 dígitos), pasa a minúsculas y toma las
**primeras 3 palabras de > 2 caracteres** (`_normalizar_titular`,
`extracto_merger.py:21-27`).

Estrategia de corte para saber dónde termina lo ya cargado (en orden de
prioridad, `extracto_merger.py:96-155`):
1. **Manual** (`corte_saldo`): busca ese saldo exacto en el UM.
2. **Ancla**: el movimiento de mayor `orden` del extracto; matchea por
   saldo + monto + fecha + titular (cuantos más campos coincidan, mejor score).
3. **Fallback**: primer movimiento del UM que ya exista.

Solo se agregan los movimientos **anteriores al corte** (`extracto_merger.py:158`)
y, como red de seguridad, se descartan los que ya existen
(`extracto_merger.py:161`). Los nuevos se marcan `source='um'` con un `um_lote`
incremental (`extracto_merger.py:184-188`).

---

## 3. IA Nivel 2 — aprendizaje de correcciones

Archivos: `backend/app/services/aprendizaje.py` + modelo
`backend/app/models/patron_aprendido.py` (`PatronAprendido`).

- **Registro** (`registrar_correccion`, `aprendizaje.py:38-92`): cuando el
  usuario corrige una fila a `ok`, se extrae el patrón (fragmento de titular del
  extracto + números clave) y se guarda/refuerza. Cada confirmación incrementa
  `veces_visto` y `veces_correcto` (`aprendizaje.py:73-75`).
- **Aplicación automática** (`buscar_por_patrones`, `aprendizaje.py:95-150`):
  antes de declarar fallo, se consultan los patrones del cliente/org que estén
  **activos y con `veces_correcto >= 2`** (`aprendizaje.py:116-121`). Es decir:
  **2+ confirmaciones → el patrón se aplica solo**. El match se da por fragmento
  de titular del extracto (`aprendizaje.py:139`) o por números en común
  (`aprendizaje.py:143-148`).
- Integración en el motor: se llama **después** del scoring, solo si el estado no
  es `ok`/`no está`/`duplicado`/`acreditado` (`conciliacion.py:434-456`).

> **Bug corregido (Fase 2)**: en `aprendizaje.py` la rama "match por números del
> plan" referenciaba `nums_plan` (indefinido) en vez de `numeros_plan` → `NameError`
> en runtime. Corregido + test de regresión en `tests/test_aprendizaje.py`.

---

## 4. Comisiones

### 4.1. Comisión por planilla / cliente (liquidaciones)

Archivo: `backend/app/routers/liquidaciones.py`.

- El porcentaje se toma con esta **prioridad** (`_calcular_monto_y_comision`,
  `liquidaciones.py:47-111`): **% propio de la planilla** (`Planilla.porcentaje_comision`)
  → si es None, **% fallback del formulario** → si no hay, **0%**
  (`liquidaciones.py:100-104`). Comentario explícito: el % del cliente **no se
  hereda**; cada planilla debe tener el suyo (`liquidaciones.py:144-147`).
- `_comision_cliente()` (`liquidaciones.py:38-44`) lee de la config de org
  `comisiones.por_cliente[cliente]` y, si no está, `comisiones.porcentaje_default`
  (default **1.5**). *(Helper presente; el cálculo principal usa la prioridad de
  arriba.)*
- Solo entran filas con **`status == "ok"`** y `fecha_acred` (o, si es None, la
  fecha de carga de la planilla) **dentro del período**
  (`liquidaciones.py:69-82`).
- El monto de cada fila se toma del **movimiento bancario acreditado** si existe;
  si no, del monto de la fila (`liquidaciones.py:93-98`).
- `comision = monto_fila * pct / 100`; `neto = monto - comisión`
  (`liquidaciones.py:106`, `167`).
- Solo cubre planillas (TT). **Los cheques se liquidan por separado** en su
  módulo (`liquidaciones.py:55`).

> **No hay doble cobro posible entre el % de la planilla y el % del cliente** —
> son dos números que ni siquiera se suman: son **campos independientes que
> alimentan pantallas distintas** y pueden mostrar valores diferentes para el
> mismo cliente/período si no coinciden:
> - **Liquidaciones** (arriba) usa exclusivamente `Planilla.porcentaje_comision`
>   (el % tipeado al conciliar esa planilla puntual). Nunca lee `Cliente.porcentaje_comision`.
> - **Estado de Cuenta** (`reportes_service.calcular_estado_cuenta_cliente`,
>   `reportes_service.py:737-745`) — incluida la página pública compartida
>   (`/p/:token`) — usa `Cliente.porcentaje_comision` si está seteado, si no el
>   default de la org (`comisiones.porcentaje_default`, 1.5%). Nunca lee
>   `Planilla.porcentaje_comision`.
>
> Si el % "de siempre" de un cliente está en su ficha (`Clientes.porcentaje_comision`,
> ej. 2%) y además se tipea un % al conciliar cada planilla, mantenerlos iguales es
> responsabilidad manual — el sistema no los sincroniza ni los valida entre sí.

### 4.1bis. Asiento contable al conciliar una planilla (cuenta corriente del cliente)

Archivos: `backend/app/services/conciliacion.py` (`conciliar_planilla`) +
`backend/app/services/motor_contable.py` (`registrar_reclasificacion_planilla`).
Tratamiento acordado con el contador (ago 2026).

Al conciliar filas de una planilla contra el banco, además de actualizar el
`status` de cada fila, se postea un asiento que reclasifica la plata del banco
a la cuenta corriente del cliente:

- **Cliente (Haber) = NETO** (total conciliado **menos** la comisión de esa
  planilla) — es lo que se ve como "Total Crédito" en Cuentas Corrientes.
- **Pagos al cliente** (efectivo/transferencia, eventos `pago_cliente_banco` /
  `pago_cliente_efectivo`) siguen siendo lo único que entra en "Total Débito".
  La comisión **no** pasa por el débito del cliente — se separa a un asiento
  distinto, no ensucia su cuenta corriente.
- **Comisión** → asiento aparte: **Comisiones ganadas** (3-1-1-0) al Haber, se
  reconoce como ingreso nuestro independiente de la cuenta del cliente.

**Contrapartida (Debe) según el ORIGEN del movimiento** — de dónde salió la
plata realmente, no es intercambiable:
| Origen del movimiento (`MovimientoBanco.source`) | Cuenta de origen (Debe) | Por qué |
|---|---|---|
| `"extracto"` (extracto bancario principal) | **Pasivo Corriente** (2-1-0-0) | Ahí quedó la plata al importar el extracto (`registrar_extracto`: Banco D / Pasivo Corriente H). |
| `"um"` (Últimos Movimientos) | **No identificado** (2-1-1-1) | Ahí quedó la plata al importar el UM (`registrar_um_import`: Banco D / No identificado H). |

Una planilla con filas conciliadas contra **ambos** orígenes genera **dos
asientos principales independientes** (uno por origen, módulos
`reclass_planilla_extracto` / `um_reclass_planilla`) — cada uno neteando su
propia comisión proporcional — para no dejar ninguna de las dos cuentas de
origen mal (una nunca se cancelaría, la otra quedaría negativa).

- El **% de comisión efectivo** es el que se manda en el request de conciliar
  si es `> 0`, o si no vino, el que ya tenía guardado `Planilla.porcentaje_comision`
  (re-conciliar sin re-tipear el % no lo pierde) — resuelto en el router
  (`planillas.py::conciliar`), no en `conciliar_planilla`.
- **Upsert por `(modulo, planilla_id, organizacion_id)`**: re-conciliar
  recalcula sobre TODAS las filas `ok` (no solo las de esa pasada) y actualiza
  los asientos existentes — idempotente. Si el % de comisión baja a 0, el
  asiento de comisión se borra (no queda huérfano con un monto que ya no
  corresponde).
- La cuenta del cliente se resuelve/crea/vincula vía `_get_o_crear_cuenta_cliente`
  — **nunca** la cuenta madre genérica "Cliente" (2-1-2-0). Ese fue el bug de un
  backfill de arranque ya eliminado (ver CHANGELOG ago 2026): usaba la cuenta
  genérica y el monto bruto, dejando las cuentas corrientes por cliente vacías.

### 4.2. Comisión de cheques (local / interior)

Archivos: `backend/app/routers/cheques_common.py` y `cheques_crud.py`,
modelo `backend/app/models/cliente.py`.

- Clasificación por código postal: **CP < 2000 → "local"**, **CP ≥ 2000 →
  "interior"** (`_local_interior`, `cheques_common.py:100-104`).
- El % de comisión del cheque sale del cliente según la clasificación:
  `porcentaje_comision_local` (local) o `porcentaje_comision_interior` (interior)
  (`cheques_crud.py:195-198`). El cliente también tiene `porcentaje_comision`
  general (`models/cliente.py:12-14`).

---

## 5. Módulos de impuestos

Criterio común de **ingreso gravado** en los tres servicios de proyección:
cuentas de tipo `resultado` cuyo código empieza con **`3-1`**, sumando
`haber - debe` de sus líneas en el período
(IVA: `iva_service.py:105`; Monotributo: `monotributo_service.py:96-97`;
IIBB: `iibb_service.py:77-78`). Todos calculan con **`Decimal`**.

### 5.1. IVA — proyección y DDJJ

Archivo: `backend/app/services/iva_service.py`.

- **Es una proyección**, no un dato real: Cuadra no emite facturas, así que el
  débito fiscal se proyecta sobre los ingresos reconocidos
  (`iva_service.py:1-16`).
- **Débito fiscal**: ingresos (`HABER`) × `tasa_iva` de la cuenta
  (`iva_service.py:107-110`).
- **Crédito fiscal** = crédito **proyectado** (gastos gravados que reciben
  `DEBE` × tasa, `iva_service.py:111-114`) + crédito **real** ya contabilizado en
  la cuenta `1-1-2-4` (`iva_service.py:129-153`).
- **Saldo** = débito − crédito. Positivo = a pagar a ARCA; negativo = saldo a
  favor (`iva_service.py:158`).
- Se **excluyen** los asientos de módulo `tarjeta_liq` para no contar dos veces
  el crédito fiscal (`iva_service.py:89`).
- **Período**: `YYYY-MM` (mes calendario completo, `_rango_periodo`,
  `iva_service.py:46-56`).

### 5.2. Monotributo — control semestral

Archivo: `backend/app/services/monotributo_service.py`.

- **Herramienta interna de alerta**, no presenta DDJJ (`monotributo_service.py:1-8`).
- **Ventanas de cálculo** (últimos 12 meses al corte, `_rango_periodo`,
  `monotributo_service.py:47-73`):
  - `YYYY-S1` → corte **30/jun**, ventana `[1/jul/(YYYY-1), 30/jun/YYYY]`.
  - `YYYY-S2` → corte **31/dic**, ventana `[1/ene/YYYY, 31/dic/YYYY]`.
- **Categoría sugerida**: la de menor `orden` cuyo `limite_anual >=` ingresos 12m;
  si superan **todas**, devuelve la más alta y `excede=True`
  (`evaluar_categoria`, `monotributo_service.py:118-152`).
- Requiere `MonotributoConfig.activo = True`, si no lanza error
  (`monotributo_service.py:186-190`).
- Escala sembrada `_LIMITES_VIGENTES` (categorías A-K, vigente desde 1/feb/2026)
  — **editable, no hardcodeada en lógica** (`monotributo_service.py:305-319`).
  Recordatorio de actualización semestral en
  [`../../CLAUDE.md`](../../CLAUDE.md).

### 5.3. Ingresos Brutos (IIBB) y Convenio Multilateral

Archivo: `backend/app/services/iibb_service.py`.

- **Proyección interna**, no DDJJ oficial (`iibb_service.py:1-9`).
- **Modo `simple`**: ingreso total × alícuota de la jurisdicción única
  (`iibb_service.py:120-149`).
- **Modo `convenio_multilateral`**: el ingreso se reparte por el
  `coeficiente_distribucion` de cada jurisdicción activa y a cada porción se le
  aplica su propia alícuota (`iibb_service.py:151-180`). Si los coeficientes **no
  suman 100%** (tolerancia `0.0001`), **no se bloquea** pero devuelve un
  `warning` (`iibb_service.py:182-187`).
- Requiere `IIBBConfig.activo = True` (`iibb_service.py:105-109`).
- **Período**: `YYYY-MM` (`iibb_service.py:52-62`).

### 5.4. Inmutabilidad de snapshots presentados / revisados

Patrón compartido por los tres módulos en su `guardar_o_actualizar_*`:

| Módulo | Estado mutable (recalcula/pisa) | Estado inmutable (no se pisa) | Cita |
|---|---|---|---|
| IVA | `proyectado` | `presentado` | `iva_service.py:202-203` |
| IIBB | `proyectado` | `presentado` | `iibb_service.py:220-221` |
| Monotributo | `pendiente` | `revisado` | `monotributo_service.py:239-240` |

Una vez `presentado`/`revisado`, el upsert **devuelve el snapshot existente
intacto** (no recalcula ni sobreescribe). `marcar_presentada` / `marcar_revisado`
sellan el estado y registran la fecha (`iva_service.py:222-243`,
`iibb_service.py:239-262`, `monotributo_service.py:263-286`); exigen que el
snapshot ya exista (se calcula primero).

---

## 6. Cierre de período (inmutabilidad financiera)

Archivo: `backend/app/services/cierre_periodo.py`.

- Aplica solo si la org tiene `requiere_cierre_periodo=true` en su configuración
  (`_org_requiere_cierre`, `cierre_periodo.py:17-22`).
- `periodo_esta_cerrado()` devuelve True si la fecha cae dentro de un
  `CierrePeriodo` de la org (`cierre_periodo.py:24-46`). Los registros con fecha
  dentro de un período cerrado quedan **inmutables** (p. ej. `patch_row_status`
  valida el cierre antes de editar, `routers/planillas.py:387-389`).
- Al **generar una liquidación** no puede existir un cierre previo para ese
  período (`liquidaciones.py:135-142`).

---

## 7. Multi-tenant (regla transversal)

- **Organización A (`organizacion_id=1`)**: solo cambios aditivos, nunca se
  modifican sus datos existentes ([`../../CLAUDE.md`](../../CLAUDE.md)).
- Aislamiento por org en cada lectura/escritura. Detalle del modelo de permisos
  y roles en [`../security/SECURITY_MODEL.md`](../security/SECURITY_MODEL.md).

---

## Pendiente de revisar

1. **Granularidad del scoring de titular**: [`../../CLAUDE.md`](../../CLAUDE.md) y
   [`../../README.md`](../../README.md) documentan "2 palabras = 5 / 1 palabra =
   3". El código (`conciliacion.py:214-227`) distingue además **4 puntos** (2
   palabras presentes en distinto orden). La doc de alto nivel está incompleta,
   no incorrecta.
2. **Tramos de bonus de fecha vs. tolerancia**: con el default de 5 días, los
   tramos +1 (8-10 días) y +2 parcial (6-7 días) descritos en el comentario
   (`conciliacion.py:118-119`) son inalcanzables porque `_bonus_fecha` corta en
   `dias_tolerancia` (`conciliacion.py:125-126`). El comportamiento real depende
   del `dias_tolerancia_fecha` de cada org.
3. ~~**Bug en `aprendizaje.py:147`**: `nums_plan` indefinido~~ → **CORREGIDO** (Fase 2):
   ahora usa `numeros_plan`, con test en `tests/test_aprendizaje.py`.
4. **Conteo de bancos soportados**: discrepancia entre landing ("10+"),
   README (lista 9) y CLAUDE.md ("16 bancos"). Verificar contra
   `backend/app/services/excel_parser.py`.
