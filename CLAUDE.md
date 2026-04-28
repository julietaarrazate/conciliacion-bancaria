# Sistema de Conciliación Bancaria — Caneland SA

## Qué hace este sistema

Concilia transferencias bancarias recibidas (extraídas del banco como "Últimos Movimientos") contra planillas de clientes. Para cada pago de cliente, busca la fila correspondiente en el extracto del banco y la "acredita" (marca con nombre del cliente y fecha).

---

## Archivos principales

| Archivo | Descripción |
|---|---|
| `watcher.py` | Script principal. Monitorea INBOX, concilia automáticamente al arrastrar archivos |
| `bot.py` | Bot de Telegram para procesar desde el celular |
| `config.json` | Rutas y configuración |
| `start.bat` | Doble clic para arrancar el watcher |
| `instalar.bat` | Instala dependencias (correr una sola vez) |

---

## Rutas del sistema

```
Desktop/
├── INBOX/                          ← arrastrar planillas de clientes acá
│   ├── green/  tucu/  david/  smt/  gwinn/  innova/  camparo/  alojando/  pinares/  paraguay/
│   └── procesados/                 ← archivos ya procesados (movidos automáticamente)
├── Extracto Macro/
│   └── extracto macro abril.xlsx   ← extracto bancario acumulado
└── clientes/tt/
    ├── Green/26-4 ABR/
    ├── Tucu/26-4 ABR/
    ├── Alojando/26-4 Abr/
    └── ...
```

---

## Extracto bancario — estructura interna

Archivo: `extracto macro abril.xlsx`

- Fila 2: headers → `[None, Orden, Fecha, Mes, titular, Importe Pesos, Saldo, cliente, fecha acred]`
- Fila 3+: datos en orden descendente (más reciente primero)

Columnas:
- **Col 2** `Orden`: número secuencial. Las filas nuevas (UM) usan fórmula `=+B{r-1}+1` — openpyxl lo guarda así. Al leer con `data_only=True` se obtiene el número evaluado.
- **Col 5** `titular`: concepto de la transferencia. Suele incluir CUIT/CUIL del ordenante (11 dígitos).
- **Col 6** `Importe Pesos`: monto, int/float
- **Col 7** `Saldo`: saldo acumulado
- **Col 8** `cliente`: `None` = libre, `"No identificado"` = también libre, cualquier otro valor = tomado
- **Col 9** `fecha acred`: fecha en que se acreditó

**⚠ CRÍTICO:** siempre cargar el extracto con `data_only=True`:
```python
wb = openpyxl.load_workbook(EXTRACTO, data_only=True)
```
Sin esto, col 2 devuelve strings `=+B562+1` en lugar de enteros, y la Hoja2 de los archivos de cliente queda con `(1)` en vez del número de orden real.

**⚠ CRÍTICO:** NO filtrar filas por tipo de col 2. Solo filtrar por importe válido en col 6.

---

## Función es_libre()

```python
def es_libre(cli):
    if cli is None: return True
    if isinstance(cli, str) and cli.strip().lower() in ('no identificado', ''): return True
    return False
```

Tanto `None` como `"No identificado"` significan fila disponible para acreditar.

---

## parse_importe — manejo de formatos

```python
def parse_importe(v):
    if isinstance(v, (int, float)): return round(float(v), 2)
    if isinstance(v, str):
        s = v.strip().replace('$','').replace('\xa0','').replace(' ','')
        if not s: return None
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'): s = s.replace('.','').replace(',','.')
            else: s = s.replace(',','')
        elif ',' in s: s = s.replace(',','.')
        try: return round(float(s), 2)
        except ValueError: pass
    return None
```

Acepta: int, float, strings con `$`, espacios, `\xa0`, formato europeo `78.827,20` y anglosajón `78,827.20`.

---

## Lógica de conciliación con CUIT

### Extracción de CUIT del extracto

```python
def extraer_cuit_titular(titular):
    """Extrae CUIT del campo titular del extracto (busca 10-11 dígitos consecutivos)."""
    if not titular: return ''
    nums = re.findall(r'\d{10,11}', str(titular))
    return nums[0] if nums else ''
```

Cada fila del extracto carga su `cuit_ex` desde el campo titular.

### Normalización de CUIT

```python
def norm_cuit(v):
    if v is None: return ''
    return re.sub(r'\D', '', str(v))
```

### UMBRAL_COMUN — cuando exigir CUIT

```python
UMBRAL_COMUN = 3
```

Si un monto aparece ≥ 3 veces en el extracto (es "común", ej: $500.000), **no se puede acreditar sin validar CUIT o titular**. Retorna `"faltan datos"` si no hay match de CUIT/titular.

Si el monto aparece < 3 veces (es poco frecuente), se acredita directamente al primer libre.

### buscar_match() — flujo completo

```
candidatos  = filas extracto con ese importe
no_usados   = candidatos no usados en esta sesión
libres      = no_usados donde es_libre(cliente)

si no hay candidatos             → "no está"          (rojo)
si hay libres:
    si len(candidatos) < UMBRAL  → acreditar primera  → "ok"
    si monto común (≥ UMBRAL):
        buscar por CUIT exacto   → ok si encuentra
        buscar por titular parcial (primeras 2 palabras) → ok si encuentra
        si no hay match          → "faltan datos"      (rojo)
si no hay libres:
    si no hay no_usados          → "duplicado"         (rojo)
    si hay no_usados (tomado)    → "acreditado DD/MM"  (verde oscuro)
```

---

## Detección automática de header en planillas de clientes

`detectar_header(ws)` busca "monto" o "importe" en filas 1–5. Verifica que la columna detectada **o col+1** tenga valores numéricos reales en las primeras filas de datos. Esto resuelve el caso donde el header está corrido (el label "Importe" está en col 6 pero los datos están en col 7).

`detectar_cuit_col(ws, hdr_row)` busca "cuit" en el header.
`detectar_titular_col(ws, hdr_row)` busca "titular" o "nombre" en el header.

---

## Formatos de planillas por cliente

### Mayoría de clientes (alojando, tucu, green, etc.)
- Hoja activa única
- Header en fila 1 o 2 con "Importe" o "Monto"
- Puede tener columna CUIT y/o titular

### SMT
- 60+ hojas, una por día hábil
- Formato: `FECHA | IMPORTE | BANCO EMISOR | TITULAR CTA | CUIT/CUIL | CLIENTE | status`
- **Solo se procesa la hoja activa** (la más reciente que el usuario dejó activa)
- El watcher usa `wb.active` únicamente

---

## Archivo de salida por planilla

Nombre: `{Cliente} acreditado DD.MM.xlsx` (si hay más de una planilla del mismo cliente/día: agrega ` (2)`, ` (3)`, etc.)

**Hoja1** = la planilla original del cliente con columna de status agregada (ok/no está/duplicado/faltan datos/acreditado DD/MM)

**Hoja2** — solo las filas acreditadas en esa planilla:

| A Orden | B Fecha | C Mes | D titular | E Importe Pesos | F Saldo | G clien