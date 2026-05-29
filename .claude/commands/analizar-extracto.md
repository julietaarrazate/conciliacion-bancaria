# Analizar extracto o planilla Excel — Julieta Arrazate

Pre-valida un archivo Excel (extracto bancario o planilla de cliente) **antes** de
subirlo al sistema, usando el mismo parser de producción. Detecta problemas de
formato que harían fallar la conciliación.

## Cuándo usar
- Llega un extracto de un banco nuevo (no Macro) y querés ver si el sistema lo lee bien.
- Una planilla de cliente dio muchos "sin datos" al conciliar y querés entender por qué.
- Antes de subir un archivo grande, para confirmar que las columnas mapean OK.

## Cómo ejecutarlo

Pediste analizar un archivo. Pasos:

1. Identificá la ruta del archivo `.xlsx`/`.xls`/`.csv` que el usuario quiere revisar.
   Si lo adjuntó o lo subió, usá esa ruta. Si no la dio, preguntale dónde está.
2. Corré el analizador (reutiliza `app/services/excel_parser.py`, el parser real):

   ```bash
   cd /home/user/conciliacion-bancaria && python backend/scripts/analizar_excel.py "<ruta_del_archivo>"
   ```

3. Leé la salida y explicásela al usuario en español claro, sin jerga técnica.

## Cómo interpretar el reporte

El script reporta:
- **Banco detectado** + **mapeo de columnas** → si dice "genérico" o hay columnas
  "no reconocidas", puede que el formato sea nuevo y haya que ajustar el parser.
- **Movimientos válidos + suma** → si son 0, el formato no se está leyendo.
- **Montos duplicados** → CLAVE: el sistema exige identidad (CUIT/CBU/nº cuenta)
  cuando un monto se repite. Si hay duplicados sin CUIT/CBU en el texto, esas filas
  van a quedar en "sin datos" al conciliar → avisar al usuario que pida esos datos al cliente.
- **Identidad detectada** → cuántas filas muestran CUIT/CBU.
- **Rango de fechas** → fechas futuras o muy viejas suelen indicar un error de formato.
- **Veredicto final** → "LISTO PARA SUBIR" o "REVISAR ANTES DE SUBIR" con la lista de problemas.

## Recordá (lógica del motor de conciliación)
- Scoring: CUIT 12 pts · CBU 10 pts · nº cuenta 8 pts · referencia 6 pts · titular 2 palabras 5 pts.
- Regla fundamental: **monto duplicado en extracto → SIEMPRE exige identidad.**
- Tolerancia de fecha: 5 días.
- Bancos soportados: Macro, BBVA, Santander, Galicia, ICBC y genérico.

## Si el formato es nuevo / no soportado
Si el banco no se detecta o hay muchas columnas sin reconocer, ofrecé al usuario
agregar el banco a `INDICADORES_BANCO` y los keywords de columnas en
`backend/app/services/excel_parser.py` (KEYWORDS_MONTO, KEYWORDS_FECHA, etc.).
NO modifiques el parser sin confirmar con el usuario primero.
