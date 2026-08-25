# Playbook — Reset de datos operativos (arrancar limpio sin datos)

Cómo dejar el sistema listo para **empezar a cargar de cero** (extractos, planillas,
conciliaciones, cheques, contabilidad, liquidaciones…) **sin perder** los maestros ni la
configuración de cada organización.

> ⚠️ Es una operación **destructiva e irreversible** sobre la base apuntada por `DATABASE_URL`.
> Hacé un backup ANTES (ver más abajo). En producción esto sobrescribe la regla informal
> "Org A / `organizacion_id=1` = NUNCA modificar" — sólo hacerlo con pedido explícito de la operadora.

## Qué conserva y qué borra

**CONSERVA (maestros / config):**
`organizaciones`, `users`, `clientes` (con sus comisiones y `cuenta_contable_id`),
`plan_cuentas`, `reglas_contables`, `portadores`, `categorias_egreso`, `empleados`, y toda la
config impositiva/nómina (`categorias_monotributo`, `monotributo_config`, `jurisdicciones_iibb`,
`iibb_config`, `convenios_colectivos`, `categorias_convenio`, `config_sueldos`, `escala_ganancias`,
`arca_config`).

**BORRA (transaccional / operativo):**
`extractos_bancarios` + `movimientos_banco`, `planillas` + `planilla_rows`,
`asientos` + `asiento_detalle`, `cheques`, `egresos`, `arqueos_diarios`,
`liquidaciones` (+ `liquidacion_detalles` + `cierres_periodo`), `liquidaciones_sueldo`
(+ `detalles_liquidacion_sueldo`), `comprobantes_iva` + `liquidaciones_iva`, `comprobantes_arca`,
`liquidaciones_tarjeta`, `proyecciones_iva`, `proyecciones_iibb`, `controles_monotributo`,
`patrones_aprendidos`, y — opcionalmente — el log de `auditoria`. También limpia las tablas legacy
(`ordenes_de_pago`, `pagos`, `gastos`) si existen.

### Por qué los saldos de cuenta corriente vuelven a cero

Los saldos de cuenta corriente **no se guardan** en ninguna columna: se calculan al vuelo sumando
`debe − haber` de `asiento_detalle` (ver `routers/ctb_ctas_corrientes.py`). Al vaciar los asientos,
todos los saldos vuelven a cero **sin tocar la ESTRUCTURA** del plan de cuentas ni el vínculo
`clientes.cuenta_contable_id`. Es decir: el plan de cuentas queda "armado como tiene que ir",
sólo se resetean los movimientos.

## Cómo ejecutarlo

El código vive en `app/services/reset_operativo.py` (lógica) y `scripts/reset_operativo.py` (CLI).
El service borra en orden seguro de foreign keys (hijos antes que padres), scopeado por
organización, en una sola transacción. El caller decide el `commit()`.

### 1. Backup primero (obligatorio)

En Neon, crear un **branch** = snapshot instantáneo y restaurable de toda la base:

- MCP: `create_branch(projectId, branchName="backup-pre-reset-<fecha>")`
- o Neon Console → Branches → Create branch (desde `production`).

Si algo sale mal, se restaura desde ese branch (reset-from-parent o repointing).

### 2. Dry-run (ver qué caería, sin borrar)

```bash
python backend/scripts/reset_operativo.py --org 1 2 --dry-run
```

Imprime la cantidad de filas por tabla que se borrarían. No modifica nada.

### 3. Ejecución real

```bash
python backend/scripts/reset_operativo.py --org 1 2
# pide confirmación: escribir exactamente  BORRAR OPERATIVO
```

Flags:
- `--org N [M ...]` — id(s) de organización a limpiar (**requerido**).
- `--no-auditoria` — conservar el log de auditoría (por defecto se borra).
- `--dry-run` — no borra, sólo reporta.
- `--yes` — sin prompt interactivo (para automatización).

### Alternativa manual (una sola vez, sin script)

Como todas las orgs se limpiaban por completo, el reset inicial (ago 2026) se hizo con un
`TRUNCATE ... RESTART IDENTITY` de las tablas transaccionales (reinicia además los contadores de
ID en 1). El script org-scopeado es la vía **reutilizable** y segura para próximas veces
(p.ej. limpiar una sola organización dejando las demás intactas).

## Notas de implementación (para quien toque el service)

- `synchronize_session=False` + los deletes van dentro de `with db.no_autoflush:` y al final
  `db.expunge_all()`: sin eso, las relaciones de los maestros conservados (p.ej. `Cliente.planillas`)
  re-insertarían por cascade "save-update" las filas recién borradas en el `commit`.
- El chequeo de existencia de las tablas legacy usa `inspect(db.connection())` (la conexión de la
  sesión), **no** `inspect(db.bind)` (el engine): el segundo abre su propia transacción y dispara
  un `ROLLBACK` que revierte los borrados ya emitidos.
- Tests: `tests/test_reset_operativo.py` (aislamiento multi-tenant, saldo a cero, dry-run,
  flag de auditoría, múltiples orgs).

## Pendiente de revisar

- (nada por ahora)
