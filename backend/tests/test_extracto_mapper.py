"""Lector de extractos Excel/CSV de cualquier banco (`services/extracto_mapper`).

Archivos sintéticos (ver `tests/extracto_sintetico.py`): nunca datos reales.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from decimal import Decimal as D

import pytest

from app.services.excel_parser import detectar_columnas, detectar_delimitador, parsear_extracto_bancario
from app.services.extracto_mapper import (
    Hoja,
    MapeoInvalido,
    analizar_extracto,
    analizar_hojas,
    controlar_saldos,
    firma_encabezado,
    leer_texto_delimitado,
    normalizar_mapeo,
    parse_fecha,
    parse_importe,
    serializar_analisis,
)
from tests.extracto_sintetico import (
    SALDO_INICIAL,
    movimientos_cronologicos,
    xlsx_desde_filas,
    xlsx_estilo_macro,
)


def _archivo(contenido: bytes | str, ext: str) -> str:
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
        f.write(contenido)
        return f.name


@pytest.fixture
def archivos():
    creados = []

    def crear(contenido, ext=".xlsx"):
        p = _archivo(contenido, ext)
        creados.append(p)
        return p

    yield crear
    for p in creados:
        os.remove(p)


# ── Fechas ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor,esperado", [
    ("19/05/2026", date(2026, 5, 19)),
    ("9/5/2026", date(2026, 5, 9)),
    ("19/05/26", date(2026, 5, 19)),
    ("19-05-2026", date(2026, 5, 19)),
    ("19.05.2026", date(2026, 5, 19)),
    ("2026-05-19", date(2026, 5, 19)),
    ("2026/05/19", date(2026, 5, 19)),
    ("20260519", date(2026, 5, 19)),
    ("19-may-26", date(2026, 5, 19)),
    ("19-May-2026", date(2026, 5, 19)),
    ("19 may 2026", date(2026, 5, 19)),
    ("19/05/2026 14:32", date(2026, 5, 19)),
    ("2026-05-19T10:00:00", date(2026, 5, 19)),
    (46161, date(2026, 5, 19)),           # número de serie de Excel
    ("46161", date(2026, 5, 19)),
    (date(2026, 5, 19), date(2026, 5, 19)),
])
def test_parse_fecha_formatos(valor, esperado):
    assert parse_fecha(valor) == esperado


@pytest.mark.parametrize("valor", [None, "", "TOTAL", "32/01/2026", "1234,56", 12.5, True])
def test_parse_fecha_invalidas(valor):
    assert parse_fecha(valor) is None


def test_parse_fecha_formato_mes_dia():
    assert parse_fecha("05/19/2026", "mdy") == date(2026, 5, 19)
    assert parse_fecha("05/19/2026") is None  # día/mes: mes 19 no existe


# ── Importes ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor,esperado", [
    ("1.234,56", D("1234.56")),
    ("-1.234,56", D("-1234.56")),
    ("1.234,56-", D("-1234.56")),
    ("(1.234,56)", D("-1234.56")),
    ("$ 1.234,56", D("1234.56")),
    ("-$ 1.234,56", D("-1234.56")),
    ("1,234.56", D("1234.56")),
    ("1234.56", D("1234.56")),
    (1234.56, D("1234.56")),
    (-200, D("-200.00")),
])
def test_parse_importe_formatos(valor, esperado):
    r = parse_importe(valor)
    assert r == esperado
    assert isinstance(r, D)


def test_parse_importe_separador_forzado():
    assert parse_importe("1,234", "punto") == D("1234.00")
    assert parse_importe("1,234", "coma") == D("1.23")
    assert parse_importe("1.234", "punto") == D("1.23")
    assert parse_importe("1.234,5", "coma") == D("1234.50")


@pytest.mark.parametrize("valor", [None, "", "-", "TOTAL", date(2026, 1, 1)])
def test_parse_importe_no_importes(valor):
    assert parse_importe(valor) is None


# ── Estilo Macro: título, encabezado fila 3, Orden con fórmulas, más nuevo primero, TOTAL ──

def test_estilo_macro_detecta_columnas_y_lee_todo(archivos):
    res = analizar_extracto(archivos(xlsx_estilo_macro(6)))
    assert res["origen"] == "heuristica"
    assert res["hoja"] == "Extracto conciliado"
    assert res["banco_clave"] == "macro"
    assert res["mapeo"]["fila_encabezado"] == 2
    cols = res["mapeo"]["columnas"]
    assert cols == {"orden": 0, "fecha": 1, "mes": 2, "titular": 3, "monto": 4, "saldo": 5,
                    "cliente_acreditado": 6, "fecha_acred": 7}
    assert res["mapeo"]["signo"] == "columna_unica"
    assert len(res["movimientos"]) == 6
    assert res["filas_resumen"] == 1             # la fila TOTAL no es un movimiento
    assert all(m["titular"] != "TOTAL" for m in res["movimientos"])


def test_estilo_macro_orden_con_formulas_trae_valor_calculado(archivos):
    movs = analizar_extracto(archivos(xlsx_estilo_macro(6)))["movimientos"]
    assert [m["orden"] for m in movs] == [105, 104, 103, 102, 101, 100]


def test_estilo_macro_mas_nuevo_primero_cuadra(archivos):
    res = analizar_extracto(archivos(xlsx_estilo_macro(6)))
    c = res["cuadre"]
    assert c["tiene_saldo"] is True
    assert c["orden"] == "desc"
    assert c["cuadra"] is True
    assert D(c["saldo_inicial"]) == SALDO_INICIAL
    assert c["primera_fila_con_error"] is None
    assert res["necesita_mapeo"] is False
    assert res["confianza"] >= 0.8


def test_montos_en_decimal(archivos):
    movs = analizar_extracto(archivos(xlsx_estilo_macro(6)))["movimientos"]
    esperado = list(reversed([m["monto"] for m in movimientos_cronologicos(6)]))
    assert [m["monto"] for m in movs] == esperado
    assert all(isinstance(m["monto"], D) and isinstance(m["saldo"], D) for m in movs)


def test_saldo_roto_marca_la_primera_fila(archivos):
    res = analizar_extracto(archivos(xlsx_estilo_macro(6, romper_fila=2)))
    c = res["cuadre"]
    assert c["cuadra"] is False
    # Datos desde la fila 4 de Excel: el índice 2 es la fila 6 (la fila 5, más
    # nueva, también "salta" pero porque arranca del saldo alterado).
    assert c["primera_fila_con_error"] == 6
    assert c["filas_con_error"] == 2
    assert "No cuadra en la fila 6" in c["mensaje"]
    assert res["necesita_mapeo"] is True


def test_mas_viejo_primero_cuadra():
    movs = movimientos_cronologicos(5)
    filas = [["Fecha", "Concepto", "Importe", "Saldo"]]
    for m in movs:
        filas.append([m["fecha"], m["titular"], float(m["monto"]), float(m["saldo"])])
    res = analizar_hojas([Hoja("h", filas)])
    assert res["cuadre"]["orden"] == "asc"
    assert res["cuadre"]["cuadra"] is True


def test_saldo_anterior_como_fila_aporta_apertura():
    movs = movimientos_cronologicos(3)
    filas = [["Fecha", "Descripción", "Importe", "Saldo"],
             [None, "Saldo anterior", None, float(SALDO_INICIAL)]]
    for m in movs:
        filas.append([m["fecha"].strftime("%d/%m/%Y"), m["titular"], float(m["monto"]), float(m["saldo"])])
    filas.append([None, "Saldo final", None, float(movs[-1]["saldo"])])
    res = analizar_hojas([Hoja("h", filas)])
    assert len(res["movimientos"]) == 3
    assert res["filas_resumen"] == 2
    assert D(res["cuadre"]["saldo_inicial"]) == SALDO_INICIAL
    assert D(res["cuadre"]["saldo_final"]) == movs[-1]["saldo"]
    assert res["cuadre"]["cuadra"] is True


def test_controlar_saldos_sin_columna_saldo():
    c = controlar_saldos([{"fila": 2, "fecha": date(2026, 1, 1), "monto": D("10"), "saldo": None}])
    assert c["tiene_saldo"] is False
    assert c["cuadra"] is None


def test_empresa_llamada_total_no_se_saltea():
    filas = [["Fecha", "Concepto", "Importe"],
             ["01/05/2026", "TOTAL ENERGIES SA", "1.000,00"],
             [None, "TOTAL", "1.000,00"]]
    res = analizar_hojas([Hoja("h", filas)])
    assert [m["titular"] for m in res["movimientos"]] == ["TOTAL ENERGIES SA"]
    assert res["filas_resumen"] == 1


# ── Débito / crédito e indicador ─────────────────────────────────────────────

def test_columnas_debito_credito():
    filas = [["Fecha", "Concepto", "Débitos", "Créditos", "Saldo"],
             ["01/05/2026", "Transferencia recibida", "", "1.500,00", "2.500,00"],
             ["02/05/2026", "Comisión", "45,25", "", "2.454,75"]]
    res = analizar_hojas([Hoja("h", filas)])
    assert res["mapeo"]["signo"] == "debito_credito"
    assert [m["monto"] for m in res["movimientos"]] == [D("1500.00"), D("-45.25")]
    assert res["cuadre"]["cuadra"] is True


def test_columna_indicador_debito_credito():
    filas = [["Fecha", "Detalle", "D/C", "Importe", "Saldo"],
             ["01/05/2026", "SIRCREB", "D", "90,00", "1.910,00"],
             ["02/05/2026", "Transferencia", "C", "900,00", "2.810,00"]]
    res = analizar_hojas([Hoja("h", filas)])
    assert res["mapeo"]["signo"] == "indicador"
    assert [m["monto"] for m in res["movimientos"]] == [D("-90.00"), D("900.00")]


def test_indicador_por_mapeo_manual():
    filas = [["Fecha", "Detalle", "Tipo", "Valor"],
             ["01/05/2026", "SIRCREB", "Débito", "90"],
             ["02/05/2026", "Transferencia", "Crédito", "900"]]
    mapeo = {"fila_encabezado": 0, "signo": "indicador",
             "columnas": {"fecha": 0, "titular": 1, "indicador": 2, "monto": 3}}
    res = analizar_hojas([Hoja("h", filas)], mapeo=mapeo)
    assert res["origen"] == "manual"
    assert [m["monto"] for m in res["movimientos"]] == [D("-90.00"), D("900.00")]


def test_columna_cuit_se_suma_al_titular():
    filas = [["Fecha", "Titular", "CUIT", "Importe"],
             ["01/05/2026", "ACME SA", "30-71234567-8", "100"]]
    res = analizar_hojas([Hoja("h", filas)])
    assert res["mapeo"]["columnas"]["cuit"] == 2
    assert res["movimientos"][0]["titular"] == "ACME SA 30712345678"


# ── CSV / TSV / TXT ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("delim,ext", [(";", ".csv"), (",", ".csv"), ("\t", ".tsv"),
                                       ("\t", ".txt"), (";", ".txt")])
def test_texto_delimitado(archivos, delim, ext):
    sep_dec = "." if delim == "," else ","
    filas = [["Fecha", "Concepto", "Importe", "Saldo"],
             ["19-may-26", "Cobro cliente", f"1500{sep_dec}50", f"2500{sep_dec}50"],
             ["20/05/2026", "Comision", f"-45{sep_dec}25", f"2455{sep_dec}25"]]
    if delim == ",":
        texto = "\n".join(",".join(f'"{c}"' for c in f) for f in filas)
    else:
        texto = "\n".join(delim.join(f) for f in filas)
    res = analizar_extracto(archivos(texto, ext))
    assert [m["monto"] for m in res["movimientos"]] == [D("1500.50"), D("-45.25")]
    assert res["movimientos"][0]["fecha"] == date(2026, 5, 19)
    assert res["cuadre"]["cuadra"] is True


def test_csv_con_montos_argentinos_y_signo_al_final(archivos):
    texto = ("Fecha;Concepto;Importe\n"
             "01/05/2026;Pago proveedor;1.234,56-\n"
             "02/05/2026;Cobro;(10,00)\n"
             "03/05/2026;Cobro;$ 2.000,00\n")
    movs = analizar_extracto(archivos(texto, ".csv"))["movimientos"]
    assert [m["monto"] for m in movs] == [D("-1234.56"), D("-10.00"), D("2000.00")]


def test_csv_latin1(archivos):
    texto = "Fecha;Descripción;Importe\n01/05/2026;Débito automático;-10,00\n"
    res = analizar_extracto(archivos(texto.encode("latin-1"), ".csv"))
    assert res["movimientos"][0]["titular"] == "Débito automático"


def test_detectar_delimitador():
    assert detectar_delimitador("a;b;c\n1;2,5;3\n") == ";"
    assert detectar_delimitador("a\tb\tc\n1\t2,5\t3\n") == "\t"
    assert detectar_delimitador("a,b,c\n1,2,3\n") == ","
    assert leer_texto_delimitado("a|b\n1|2\n") == [["a", "b"], ["1", "2"]]


# ── Sin detección → pedir el mapeo ───────────────────────────────────────────

def test_sin_encabezado_es_solo_sugerencia(archivos):
    movs = movimientos_cronologicos(4)
    filas = [[m["fecha"].strftime("%d/%m/%Y"), m["titular"], float(m["monto"]), float(m["saldo"])]
             for m in movs]
    p = archivos(xlsx_desde_filas(filas))
    res = analizar_extracto(p)
    assert res["origen"] == "sugerencia"
    assert res["necesita_mapeo"] is True
    assert res["mapeo"]["columnas"]["fecha"] == 0
    assert res["mapeo"]["columnas"]["monto"] == 2
    assert res["mapeo"]["columnas"]["saldo"] == 3
    assert res["mapeo"]["fila_encabezado"] == -1
    # El parser NO importa una sugerencia (antes asumía columnas de Macro en silencio).
    assert parsear_extracto_bancario(p)["total"] == 0


def test_nada_reconocible(archivos):
    p = archivos(xlsx_desde_filas([["hola", "chau"], ["foo", "bar"]]))
    res = analizar_extracto(p)
    assert res["origen"] == "ninguno"
    assert res["necesita_mapeo"] is True
    assert parsear_extracto_bancario(p)["total"] == 0


def test_detectar_columnas_ya_no_asume_macro():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append([1, 2])
    ws.append([3, 4])
    cols = detectar_columnas(ws)
    assert cols["monto"] is None and cols["fecha"] is None and cols["titular"] is None


def test_sin_fecha_baja_la_confianza():
    filas = [["Concepto", "Importe"], ["Cobro", "100"], ["Pago", "-50"]]
    res = analizar_hojas([Hoja("h", filas)])
    assert res["origen"] == "heuristica"
    assert res["necesita_mapeo"] is True
    assert "No encontramos la columna de fecha." in res["motivos"]


# ── Mapeo manual y validación ────────────────────────────────────────────────

def test_mapeo_manual_con_fila_de_encabezado_corrida():
    filas = [["Banco X"], ["col1", "col2", "col3"],
             ["2026-05-01", "Cobro", "100,00"], ["2026-05-02", "Pago", "-30,00"]]
    mapeo = {"fila_encabezado": 1, "columnas": {"fecha": 0, "titular": 1, "monto": 2}}
    res = analizar_hojas([Hoja("h", filas)], mapeo=mapeo)
    assert [m["fila"] for m in res["movimientos"]] == [3, 4]
    assert [m["monto"] for m in res["movimientos"]] == [D("100.00"), D("-30.00")]


@pytest.mark.parametrize("mapeo", [
    {"columnas": {"fecha": 0}},                                   # sin importe
    {"columnas": {"monto": 0, "inventado": 1}},                   # rol desconocido
    {"columnas": {"monto": 999}},                                 # fuera de rango
    {"columnas": {"monto": 0}, "signo": "indicador"},             # falta indicador
    {"columnas": {"monto": 0}, "formato_fecha": "xyz"},
    {"columnas": {"monto": 0}, "fila_encabezado": -5},
    "no es un dict",
])
def test_mapeo_invalido(mapeo):
    with pytest.raises(MapeoInvalido):
        normalizar_mapeo(mapeo)


def test_formato_fecha_mes_dia_por_contenido():
    filas = [["Date", "Description", "Amount"],
             ["05/19/2026", "Payment", "1,234.56"], ["05/20/2026", "Fee", "-10.00"]]
    res = analizar_hojas([Hoja("h", filas)])
    assert res["movimientos"][0]["fecha"] == date(2026, 5, 19)
    assert res["movimientos"][0]["monto"] == D("1234.56")


# ── Plantillas ───────────────────────────────────────────────────────────────

def test_firma_encabezado():
    a = firma_encabezado(["Fecha", "Concepto ", "IMPORTE"], "macro")
    b = firma_encabezado(["fecha", "concepto", "Importe", None], "macro")
    assert a and a == b
    assert firma_encabezado(["Fecha", "Concepto", "Importe"], "galicia") != a
    assert firma_encabezado(["Fecha", None], "macro") is None          # un solo texto
    assert firma_encabezado(["01/05/2026", "Cobro", 100], "macro") is None   # fila de datos


def test_plantilla_se_aplica_aunque_el_encabezado_se_corra():
    encabezado = ["F. Op", "Glosa x", "Valor x"]          # nada reconocible por palabras
    filas = [encabezado, ["01/05/2026", "Cobro", "100"], ["02/05/2026", "Pago", "-30"]]
    firma = firma_encabezado(encabezado, "generico")
    plantillas = {firma: {"id": 7, "mapeo": {"columnas": {"fecha": 0, "titular": 1, "monto": 2}}}}
    corridas = [["Resumen de cuenta"], []] + filas
    res = analizar_hojas([Hoja("h", corridas)], plantillas=plantillas)
    assert res["origen"] == "plantilla"
    assert res["plantilla_id"] == 7
    assert res["mapeo"]["fila_encabezado"] == 2
    assert [m["monto"] for m in res["movimientos"]] == [D("100.00"), D("-30.00")]
    assert res["necesita_mapeo"] is False


# ── Salida JSON ──────────────────────────────────────────────────────────────

def test_serializar_analisis(archivos):
    import json
    res = analizar_extracto(archivos(xlsx_estilo_macro(6)))
    out = serializar_analisis(res, muestra=3)
    json.dumps(out)   # todo serializable
    assert out["grilla"]["filas"][2][:3] == ["Orden", "Fecha", "Mes"]
    assert out["grilla"]["columnas"] == 8
    assert len(out["muestra"]) == 3
    assert out["muestra"][0]["monto"] == "-1234.56"
    assert out["total_movimientos"] == 6
    assert out["encabezados"][4] == "Importe"


def test_parsear_extracto_bancario_compatible(archivos):
    r = parsear_extracto_bancario(archivos(xlsx_estilo_macro(6)))
    assert r["total"] == 6
    assert r["banco_detectado"] == "macro"
    assert {"orden", "fecha", "mes", "titular", "monto", "saldo", "cliente_acreditado",
            "fecha_acred"} <= set(r["movimientos"][0])


# ── Sentido del archivo: el parser entrega siempre del más nuevo al más viejo ──

def test_parser_da_vuelta_un_archivo_ascendente(archivos):
    filas = [["Fecha", "Concepto", "Importe", "Saldo"]]
    for m in movimientos_cronologicos(4):
        filas.append([m["fecha"].strftime("%d/%m/%Y"), m["titular"], float(m["monto"]), float(m["saldo"])])
    movs = parsear_extracto_bancario(archivos(xlsx_desde_filas(filas)))["movimientos"]
    fechas = [m["fecha"] for m in movs]
    assert fechas == sorted(fechas, reverse=True)


def test_parser_deja_igual_un_archivo_descendente(archivos):
    movs = parsear_extracto_bancario(archivos(xlsx_estilo_macro(6)))["movimientos"]
    assert [m["orden"] for m in movs] == [105, 104, 103, 102, 101, 100]


def test_parser_sin_sentido_detectable_no_reordena(archivos):
    filas = [["Fecha", "Concepto", "Importe"],
             ["01/05/2026", "A", "10"], ["01/05/2026", "B", "20"], ["01/05/2026", "C", "30"]]
    assert analizar_hojas([Hoja("h", filas)])["cuadre"]["orden_detectado"] is False
    movs = parsear_extracto_bancario(archivos(xlsx_desde_filas(filas)))["movimientos"]
    assert [m["titular"] for m in movs] == ["A", "B", "C"]


def test_fechas_mandan_si_el_saldo_tampoco_encadena():
    """Archivo con huecos (como un extracto filtrado): el saldo no encadena en
    ningún sentido y deciden las fechas."""
    filas = [["Fecha", "Concepto", "Importe", "Saldo"],
             ["03/05/2026", "C", "10", "500"],
             ["02/05/2026", "B", "10", "300"],
             ["01/05/2026", "A", "10", "100"]]
    c = analizar_hojas([Hoja("h", filas)])["cuadre"]
    assert c["orden"] == "desc"
    assert c["orden_detectado"] is True
