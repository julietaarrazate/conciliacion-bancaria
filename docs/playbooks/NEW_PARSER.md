# Playbook — Extender el parser de Excel

> Cómo trabajar sobre el parser de extractos y planillas sin reintroducir bugs conocidos.
> Para agregar un **banco** puntual ver [NEW_BANK](./NEW_BANK.md) (referencia, no dupliques).

Fuente: `backend/app/services/excel_parser.py`. Bugs históricos del área: ver
[`BUGS.md`](../../BUGS.md) (detección de banco, fin de tabla de planillas, montos argentinos).

## Anatomía del parser

| Función | Rol |
|---|---|
| `_convertir_xls_a_xlsx` / `_convertir_csv_a_xlsx` | Normalizan formatos de entrada a xlsx |
| `detectar_banco(ws)` | Identifica el banco por keywords (o `generico`) |
| `_kw_en_texto(keyword, texto)` | Match por **palabra completa** (`\b`), evita falsos positivos |
| `detectar_columnas(...)` | Ubica la fila de header real y mapea columnas |
| `parsear_generico(...)` | Parser por defecto cuando el banco no tiene formato propio |
| `parsear_planilla_cliente(...)` | Parsea la planilla de pagos del cliente |
| `_parse_fecha` / `_parse_monto` / `_normalizar` | Utilidades de tipos |

`parsear_extracto_bancario(path)` recorre las hojas y elige la que produce más movimientos
parseables (descarta hojas con `< 3` filas).

## Reglas para no romper nada (extraídas de BUGS.md)

1. **Detección por palabra completa**: usá `_kw_en_texto` / `\b`, nunca `substring` (no confundir
   "rio" dentro de "período"/"anterior").
2. **Validar el header candidato**: verificá que la fila siguiente tenga datos reales, para no
   tomar una fila de resumen ("Total débitos: $X") como encabezado.
3. **Montos en formato argentino**: parseá con `_parse_monto` (soporta `15.000,50` y `15,000.50`);
   nunca asumir `float(parseFloat)` directo.
4. **Fin de la tabla de planilla**: respetá la lógica de corte (bloques de resumen/notas separados
   por fila vacía, valores no numéricos en la columna de importe) para no descartar filas legítimas.
5. El `orden` lo asigna el backend al insertar (per-extracto, desde 1), **no** el parser — ver
   [BUSINESS_RULES](../business/BUSINESS_RULES.md) y `routers/extractos.py`.

## Cómo agregar/mejorar un patrón de columnas

1. Reproducí con un archivo real: `parsear_extracto_bancario('ruta.xlsx')` y revisá
   `movimientos` / `banco_detectado`.
2. Ajustá `detectar_columnas` / `parsear_generico` (o el parser específico del banco).
3. Agregá un test con un fixture mínimo en `tests/test_excel_parser.py`.
4. Verificá contra el archivo real que motivó el cambio antes de mergear.

## Pendiente de revisar

- El umbral `ws.max_row < 3` para descartar hojas es intencional pero poco documentado: tenerlo en
  cuenta al crear fixtures de test (incluir ≥2 filas de datos).
