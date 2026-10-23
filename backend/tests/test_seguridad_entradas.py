"""Entradas de terceros (revisión de seguridad oct/2026).

- Inyección de fórmulas: un titular/concepto que empieza con `=`, `+`, `-` o `@` se
  exporta como texto (con apóstrofo), no como fórmula viva. Números/fechas no cambian.
"""
import csv
import io
from datetime import date
from decimal import Decimal

import openpyxl

from app.services.excel_export import export_movimientos
from app.services.excel_safe import safe_cell, sanear_workbook
from app.services.export_contable import _export_csv, _export_regisoft


# ── 1. Inyección de fórmulas en Excel/CSV ────────────────────────────────────

def test_safe_cell_neutraliza_prefijos_de_formula():
    for v in ("=HYPERLINK(\"http://x\",\"y\")", "+1+cmd|' /C calc'!A0", "-2+3", "@SUM(A1)",
              "\t=1", "\r=1"):
        assert safe_cell(v) == "'" + v


def test_safe_cell_no_toca_numeros_fechas_ni_texto_comun():
    assert safe_cell(Decimal("-12.50")) == Decimal("-12.50")
    assert safe_cell(-3) == -3
    assert safe_cell(1.5) == 1.5
    assert safe_cell(date(2026, 1, 2)) == date(2026, 1, 2)
    assert safe_cell(None) is None
    assert safe_cell("") == ""
    assert safe_cell("Juan Pérez") == "Juan Pérez"
    # Texto que es solo un número (o el guion de "sin dato") no puede armar una fórmula.
    assert safe_cell("-1234,56") == "-1234,56"
    assert safe_cell("-") == "-"


def test_sanear_workbook_deja_formulas_como_texto():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "=1+1"
    ws["B1"] = Decimal("10.00")
    sanear_workbook(wb)
    assert ws["A1"].value == "'=1+1"
    assert ws["A1"].data_type == "s"
    assert ws["B1"].value == Decimal("10.00")


def test_export_movimientos_titular_malicioso_no_es_formula():
    xlsx = export_movimientos("ext", [{
        "orden": 1, "fecha": date(2026, 1, 5), "mes": 1,
        "titular": '=HYPERLINK("http://evil","clic")', "monto": Decimal("-100.50"), "saldo": Decimal("5"),
        "cliente_acreditado": "@cliente",
    }])
    ws = openpyxl.load_workbook(io.BytesIO(xlsx)).active
    assert ws.cell(6, 4).value == "'=HYPERLINK(\"http://evil\",\"clic\")"
    assert ws.cell(6, 4).data_type == "s"
    assert ws.cell(6, 7).value == "'@cliente"
    # El importe negativo sigue siendo número con su formato.
    assert ws.cell(6, 5).value == -100.5
    assert ws.cell(6, 5).number_format == '"$"#,##0.00'


def _fila_contable(desc):
    return {
        "fecha": date(2026, 3, 1), "numero_asiento": 7, "codigo_cuenta": "1.1.01",
        "nombre_cuenta": "=cmd", "debe": Decimal("10.00"), "haber": Decimal("0"), "descripcion": desc,
    }


def test_export_contable_csv_neutraliza_descripcion():
    content, _, _ = _export_csv([_fila_contable("=HYPERLINK(1)")], ";", "utf-8", "DD/MM/YYYY", {})
    filas = list(csv.reader(io.StringIO(content.decode("utf-8")), delimiter=";"))
    assert filas[1][3] == "'=cmd"
    assert filas[1][6] == "'=HYPERLINK(1)"
    assert filas[1][4] == "10.00"


def test_export_regisoft_neutraliza_descripcion():
    content, _, _ = _export_regisoft([_fila_contable("+SUM(A1)")])
    filas = list(csv.reader(io.StringIO(content.decode("utf-8"))))
    assert filas[1][2] == "'+SUM(A1)"
