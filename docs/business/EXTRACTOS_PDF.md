# Extractos en PDF (lectura sin IA, cuadre de saldos y revisión)

Módulo aditivo (v3.31). Permite cargar el extracto bancario en PDF (el resumen que descarga el
home banking) además del Excel. El PDF se lee **sin IA** cuando se puede (lector propio +
formatos aprendidos por organización); la IA (Gemini) queda como último recurso. Nada se
guarda sin que una persona revise los movimientos con los totales a la vista.

No toca el motor de conciliación: el extracto que sale de un PDF es un `ExtractoBancario` con
`MovimientoBanco` igual al del Excel (se crea con el mismo código), y agregar a un extracto
existente usa el mismo merge que "Últimos movimientos".

Fuentes de verdad (código):
- `backend/app/services/extracto_pdf/` — el lector (paquete puro, sin DB):
  `texto.py` (texto con posiciones, pdfminer) · `tabla.py` (columnas, filas, saldos, signos) ·
  `fechas.py` · `bancos.py` · `saldos.py` (`validar_saldos`, única fuente del cuadre) ·
  `molde.py` (formatos aprendidos) · `ia.py` (fallback Gemini) · `lector.py` (el embudo).
- `backend/app/services/extracto_pdf_service.py` — borradores, duplicados, confirmación,
  aprendizaje.
- `backend/app/services/extracto_import.py` — creación del extracto y asiento de UM,
  compartidos con el upload de Excel (`routers/extractos.py`).
- `backend/app/routers/extractos_pdf.py` — endpoints (`/extractos-pdf`).
- `backend/app/models/extracto_pdf.py` — `BorradorExtractoPdf`, `MoldeExtractoPdf`
  (migración 028 + safety-net en `app/db_safety.py`).
- Frontend: `components/extractos/ImportarExtractoPdfModal.tsx`, `RevisionExtractoPdf.tsx`,
  `filasExtracto.ts`, `utils/saldoExtracto.ts` (el mismo cuadre en centavos enteros).
- Tests: `backend/tests/test_extracto_pdf_lector.py`, `test_extracto_pdf_casos_dificiles.py`,
  `test_extractos_pdf_api.py`; `frontend/src/components/__tests__/ImportarExtractoPdfModal.test.tsx`,
  `components/extractos/filasExtracto.test.ts`, `utils/saldoExtracto.test.ts`.

---

## 1. Flujo

1. **Subida** (`POST /extractos-pdf/importar`, permiso `upload_files`, 10 por minuto): desde
   Conciliar (al soltar un `.pdf`) o desde Extractos → "Importar PDF". Máximo `max_file_size`
   y 80 páginas. PDF con contraseña, dañado o que no es PDF → 400 con un mensaje que dice qué
   hacer. El mismo archivo dos veces (sha256) devuelve el mismo borrador.
2. **Lectura en embudo** (`leer_extracto_pdf`), de más barata a más cara:
   1. *Formato aprendido* de la organización para ese banco/encabezado (molde).
   2. *Lectura automática*: encabezado de columnas reconocido con los diccionarios del parser
      de Excel, o estructura (líneas que empiezan con fecha + importes alineados).
   3. *IA*: solo si el PDF es escaneado, si no se encontraron movimientos, si el saldo no
      cierra, si quedaron renglones ilegibles o si la persona tocó "Leer con IA". Va en segundo
      plano (`procesando`) y la pantalla consulta cada 2,5 s. Sin `GEMINI_API_KEY` se avisa y
      queda lo que se leyó.
3. **Revisión** (pantalla): método usado, banco, período, filas editables (fecha, descripción,
   débito, crédito, saldo), filas dudosas marcadas en amarillo con su motivo, alertas,
   duplicados y el **cuadre** recalculado en vivo. Se puede ver el PDF al lado.
4. **Confirmación** (`POST /extractos-pdf/borradores/{id}/confirmar`): el servidor vuelve a
   validar todo con la misma función de cuadre y guarda (ver §3). Transición atómica
   `listo → confirmando → confirmado`: dos clics no duplican.
5. **Aprendizaje**: si cerró y se corrigió como mucho el 10 % de las filas, se guarda (o
   refuerza) el formato de ese PDF para la organización: el próximo mes se lee sin IA.

## 2. Cuadre de saldos (Decimal punta a punta)

`saldo inicial + créditos − débitos = saldo final`, tolerancia $0,01, y además el control
fila por fila del saldo corrido (`saldo[i] = saldo[i−1] + monto[i]` en orden cronológico).

- **Cierra** solo si la diferencia es ≤ $0,01 **y no hay saltos** en el saldo corrido: dos
  errores que se compensan no cierran (la pantalla dice "los totales dan, pero el saldo no
  sigue en N filas").
- El **saldo inicial** sale del PDF ("Saldo anterior", "Saldo al 31/08"…); si no figura, se
  deduce de la primera fila con saldo (se muestra como "deducido").
- El **saldo final** sale del PDF; si no figura, solo se toma el saldo de la **última** fila.
  Si la última fila no trae saldo, queda sin verificar: deducirlo de importes que no se pueden
  controlar sería darlos por buenos.
- Si los movimientos cierran entre sí pero el saldo inicial o final impreso en el PDF no
  coincide con el que sale de las filas (pasa en resúmenes de home banking con el cuadro de
  arriba de otra fecha), el aviso lo dice con los dos importes y propone revisar que estén
  todas las hojas o borrar ese saldo en la revisión. Solo cuando la lectura lo sabe: todas las
  páginas y renglones leídos, ningún signo supuesto y la fila del extremo con su saldo; del
  lado del inicial, además, el signo lo tiene que decir el PDF (deducido, se eligió para llegar
  a ese saldo). Si no, queda el aviso de la diferencia. En la pantalla, "El saldo no sigue" se
  recalcula al editar los saldos (no queda la marca de la lectura).
- Si no cierra, se puede guardar igual con confirmación explícita (`confirmar_sin_cuadre`).
- El frontend (`saldoExtracto.ts`) espeja `validar_saldos` en centavos enteros; el servidor es
  la autoridad al confirmar.

## 3. Duplicados y extractos que se pisan

Antes de guardar se busca si ya hay un extracto con esos movimientos (`buscar_duplicado`):

- `mismo_archivo`: el mismo PDF ya se confirmó → se ofrece abrir el extracto.
- `mismos_movimientos`: misma huella que un extracto (la del Excel: cantidad + suma) **con las
  mismas fechas e importes**, o todas las filas iguales en fecha e importe → al confirmar se
  **vincula** (no se crea nada).
- `solapado`: otro extracto tiene parte de las filas → se ofrece "agregar solo los nuevos"
  (merge de UM: deduplica y agrega solo lo más nuevo que el último movimiento, `source='um'`,
  `um_lote`, asiento automático) o crear un extracto nuevo.

Reglas:
- Se comparan los extractos (activos **o archivados**, hasta 30) cuyas fechas se pisan con las
  del PDF, más los 10 activos más recientes. Un mes viejo o archivado por un cierre no se duplica.
- La coincidencia que decide es **por fecha e importe**: una cuenta que repite los mismos
  importes y saldos todos los meses no hace pasar octubre por septiembre.
- A un extracto **archivado** no se le agregan filas (409): la pantalla lo dice y guarda como
  extracto nuevo.
- Si el PDF trae filas **más viejas** que el último movimiento del extracto y que no están en
  él, el merge no las agrega: la pantalla lo avisa antes (`anteriores`) y la respuesta lo dice
  (`no_agregados`), con la sugerencia de guardar el PDF como extracto nuevo.
- Agregar a un existente: si algo se corta después del merge (que commitea solo), el reintento
  genera el asiento que haya faltado (el asiento de UM es idempotente). La auditoría va aparte:
  si falla, el extracto queda guardado y se loguea el error.

## 4. Qué entiende el lector

- Importes AR y US, signo adelante/atrás, paréntesis, moneda (`parse_importe_ar`). Un número
  absurdo (más dígitos que la precisión de Decimal) no es un importe: nunca lanza.
- Columnas Débito/Crédito, Importe con signo o sin signo (el signo se deduce del saldo; con
  varios movimientos sin saldo, la única combinación de signos que llega al saldo siguiente).
- Columna con la palabra "Débito"/"Crédito" (o D/C) y el importe sin signo en otra columna:
  la columna da el signo (campo `signo` del layout). Se reconoce por el título ("Débito/Crédito"
  junto a "Monto", también partido en dos renglones, o "D/C") o por el contenido: debajo de un
  título de importe solo marcas y ningún importe, o debajo de un título desconocido ("Tipo") las
  palabras enteras en casi todas las filas. Una marca pegada a la descripción ("COMPRA TARJETA
  DE DEBITO") no cuenta. Sin títulos reconocibles no se busca: la última palabra de muchas
  descripciones es "debito" o "credito". Un "-" impreso manda sobre la palabra (la fila queda
  para revisar); una fila sin palabra saca el signo del saldo, descontando los que ya se
  conocen. Una marca D/C pegada al importe ("1.500,00 D") también da el signo de esa fila.
- Entre lecturas automáticas que no cierran gana la que menos signos tuvo que suponer: un
  signo deducido contra un saldo inicial mal impreso puede dar una diferencia más chica.
- Orden ascendente o descendente; fechas sin año (con el período del PDF o el año más reciente).
- Saldo por fila o por día, "Saldo anterior" como transporte arriba de cada hoja, subtotales,
  descripciones de varios renglones, filas de dos renglones con el importe abajo, cuadros de
  resumen con dos rótulos por renglón, descripciones que invaden la columna vecina.
- No suma como movimiento: pies legales con importes, cuadros de retenciones al pie, totales
  ("Débitos del período"), saldo promedio. Si el PDF sigue con otra cuenta, lee solo la primera.
- Banco: el membrete (arriba de la página 1 y líneas repetidas en todas las hojas) gana a las
  descripciones que nombran otros bancos.
- Renglones con fecha e importes ilegibles (columnas pegadas): alerta y la lectura no cuenta
  como buena.

## 5. IA y costos

- Gemini se usa solo como fallback (ver §1). Para PDF con texto se manda el texto en tandas de
  4 páginas (más barato que el PDF); escaneados, el PDF (hasta 15 MB).
- `EXTRACTOS_PDF_IA_DAILY_LIMIT` (default 100) limita las lecturas con IA por día en el
  servidor. Sin `GEMINI_API_KEY` todo funciona sin IA.

## Pendiente de revisar

- Probar con PDFs reales de cada banco soportado (los tests usan PDFs generados que imitan los
  formatos). Lo que falle con un PDF real se agrega como test en
  `test_extracto_pdf_casos_dificiles.py`, con datos inventados que copian el formato (el PDF
  real nunca entra al repo). Probado hasta ahora con un resumen de movimientos de home banking
  real (columna Débito/Crédito, cuadro de saldos de otra fecha).
- Un PDF de home banking que no nombra al banco en ninguna parte queda como genérico (se lee
  igual; el banco no se puede deducir solo del CBU sin una tabla de códigos de entidad).
- Listados monoespaciados con columnas a menos de un espacio entre sí (fecha pegada al número
  de comprobante): la fecha no se reconoce y la fila queda "Sin fecha" (cierra igual, se ve).
- Columnas de importes que se superponen físicamente no se pueden separar: la lectura no cierra
  y pasa a la IA.
- El merge de "agregar solo los nuevos" compara por (saldo, importe) sin fecha, como el de UM.
