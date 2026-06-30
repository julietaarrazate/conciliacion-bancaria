# Playbook — Integrar un módulo nuevo con el motor contable

> Cómo hacer que un módulo registre **asientos de partida doble** en el motor contable.
> El detalle conceptual (plan de cuentas, idempotencia, inmutabilidad) está en
> [ACCOUNTING_ENGINE](../architecture/ACCOUNTING_ENGINE.md) — acá va el paso a paso. No dupliques
> ese contenido: referencialo.

Fuente: `backend/app/services/motor_contable.py`.

## Patrón

El módulo NO arma asientos a mano: llama a un helper de `motor_contable` que crea el `Asiento` +
sus `AsientoDetalle` (debe = haber) dentro de la misma transacción, de forma idempotente.

Helpers existentes que sirven de referencia:

| Acción | Helper |
|---|---|
| Importar lote de banco (UM) | `registrar_um_import` |
| Conciliar planilla | `registrar_reclasificacion_planilla` |
| Pago/gasto | `registrar_egreso` |
| Ingreso en efectivo | `registrar_ingreso_efectivo` |
| Cheque | `registrar_cheque` |
| Liquidación aprobada | `registrar_liquidacion_aprobacion` |
| Sueldos / F931 | `registrar_liquidacion_sueldos` |

Helpers de soporte: `_get_cuenta_por_codigo(db, codigo, org_id)`,
`_get_o_crear_cuenta_cliente(db, cliente_id, org_id)`, `_next_numero_asiento(db, org_id)`,
`_monto(v)` (convierte a `Decimal` con seguridad).

## Checklist

1. **Definir el asiento**: qué cuenta va al debe y cuál al haber (deben balancear). Usá códigos del
   plan vía `_get_cuenta_por_codigo`; si faltan cuentas, agregalas al seed idempotente
   (`services/seed_contable.py` / `PLAN_PATCH`) — **nunca** modifiques datos de Org A existentes.
2. **Crear un helper** `registrar_<tu_modulo>(db, org_id, ...)` en `motor_contable.py` siguiendo la
   forma de los existentes: asignar `numero_asiento` con `_next_numero_asiento`, montos con `_monto`
   (`Decimal`, ver [DATABASE_RULES](../database/DATABASE_RULES.md)).
3. **Idempotencia**: usá `referencia_id` + `modulo` para no duplicar el asiento si la acción se
   repite (mirá cómo lo hacen los helpers actuales).
4. **Llamarlo desde el router** del módulo, dentro de la transacción de la operación, antes del
   `db.commit()`.
5. **Invalidar cachés derivados** si tu asiento afecta reportes: el patrón está en
   `routers/ctb_libro.py::_invalidar_reportes` (cartera, sumas-saldo, balance).
6. **Tests**: agregá un test que verifique que la acción genera el asiento balanceado esperado
   (mirá `tests/test_motor_contable.py`).

## Reglas de oro

- Partida doble: la suma del debe debe igualar la del haber. Siempre.
- Inmutabilidad: un asiento de un período cerrado/presentado no se modifica.
- `Decimal` en todos los montos; nunca `float`.

Ver también: [NEW_MODULE](./NEW_MODULE.md) (estructura general del módulo) y
[ACCOUNTING_ENGINE](../architecture/ACCOUNTING_ENGINE.md).

## Pendiente de revisar

- La firma exacta de cada `registrar_*` varía; consultá la función concreta antes de llamarla.
