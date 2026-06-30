# Playbook — Agregar soporte para un banco nuevo

> Cómo hacer que Cuadra reconozca y parsee el extracto de un banco que todavía no está soportado.
> La mecánica general del parser está en [NEW_PARSER](./NEW_PARSER.md) — referencialo, no lo
> dupliques.

Fuentes: `backend/app/services/excel_parser.py` (`detectar_banco`) y
`backend/app/routers/extractos.py` (`_BANCO_NOMBRE`, `_resolver_banco`).

## Primero: ¿hace falta?

El **parser genérico** ya cubre la mayoría de los extractos en Excel (detecta columnas de fecha,
titular/concepto, importe/débito-crédito y saldo). Antes de agregar un banco específico, probá
subir el archivo: si el genérico lo parsea bien, **no hace falta código** — el usuario solo escribe
el nombre del banco en el campo libre del Dashboard (se guarda y queda en sus sugerencias).

Agregá un banco específico solo si su layout confunde al genérico o querés que se **detecte solo**.

## Pasos

1. **Detección** — en `detectar_banco(ws)` (`excel_parser.py`): agregá las keywords que identifican
   al banco (texto que aparece en el encabezado del extracto). Usá match por **palabra completa**
   (`_kw_en_texto` / `\b`) para evitar falsos positivos (ver [`BUGS.md`](../../BUGS.md)).
2. **Nombre legible** — en `_BANCO_NOMBRE` (`routers/extractos.py`): mapeá la clave interna del
   parser (ej. `"comercio"`) a su nombre visible (`"Banco Comercio"`).
3. **Resolución** — `_resolver_banco(banco_param, banco_detectado)` ya usa el banco detectado cuando
   es más específico que el default; respeta lo que el usuario escribió a mano. Normalmente no hay
   que tocarlo.
4. **Columnas (si difiere)** — si el formato no encaja con `parsear_generico`, sumá el manejo de su
   layout en `detectar_columnas` / un parser propio (ver [NEW_PARSER](./NEW_PARSER.md)).
5. **Test** — agregá un fixture y un test en `tests/test_excel_parser.py` que verifique
   `banco_detectado` y la cantidad/signos de movimientos. Verificá contra un archivo real.

## Checklist

- [ ] `detectar_banco` reconoce el banco (palabra completa)
- [ ] `_BANCO_NOMBRE` tiene el nombre visible
- [ ] El parser produce movimientos con signo correcto (créditos +, débitos −)
- [ ] Test con fixture + verificación contra archivo real
- [ ] Sin tocar lógica de otros bancos

## Pendiente de revisar

- Confirmar la lista vigente de bancos detectados en `_BANCO_NOMBRE` al momento de editar (hoy:
  macro, bbva, santander, galicia, icbc, nacion, provincia, ciudad, hsbc + genérico).
