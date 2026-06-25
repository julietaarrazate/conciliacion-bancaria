"""Tests del parser de planillas de clientes (`parsear_planilla_cliente`).

Cubre, entre otros, los bugs encontrados con una planilla real (cliente Dani /
Caneland, junio 2026):
- Bloques de resumen/notas debajo de la tabla real (separados por una fila
  vacía) no deben contarse como filas de pago.
- Valores no numéricos en la columna de importe (ej. "Suma", "Bruto") no
  deben contarse como filas de pago.
- Filas legítimas sin cuit/titular (dato faltante en origen) se preservan.
"""

import os
import tempfile
from openpyxl import Workbook

from app.services.excel_parser import parsear_planilla_cliente


def _xlsx_tmp(wb: Workbook) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    wb.save(tmp.name)
    tmp.close()
    return tmp.name


def _cleanup(path: str):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _wb_planilla_basica():
    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Importe", "Estado del pago", "Cuenta", "Fecha de transferencia",
               "Banco de origen", "Cuit", "Titular transferir", "Rendido"])
    ws.append([1, 100000, "Pago", "Caneland", "2026-06-04", "Mercado pago", "20940508925", "Juan Perez", "No"])
    ws.append([2, 200000, "Pago", "Caneland", "2026-06-05", "Pvs", "20267910260", "Maria Lopez", "No"])
    return wb


def test_planilla_basica_parsea_filas():
    wb = _wb_planilla_basica()
    path = _xlsx_tmp(wb)
    try:
        r = parsear_planilla_cliente(path)
        assert r["total"] == 2
        assert r["filas"][0]["monto"] == 100000
        assert r["filas"][0]["cuit"] == "20940508925"
        assert r["filas"][0]["titular"] == "Juan Perez"
    finally:
        _cleanup(path)


def test_fila_sin_cuit_ni_titular_se_preserva():
    """Dato faltante en origen (ej. "no se ve, ver foto") no debe descartar la fila."""
    wb = _wb_planilla_basica()
    ws = wb.active
    ws.append([3, 50000, "Pago", "Caneland", "2026-06-06", "no se ve ver foto", None, None, "No"])
    path = _xlsx_tmp(wb)
    try:
        r = parsear_planilla_cliente(path)
        assert r["total"] == 3
        fila = r["filas"][-1]
        assert fila["monto"] == 50000
        assert fila["cuit"] is None
        assert fila["titular"] is None
    finally:
        _cleanup(path)


def test_resumen_debajo_de_fila_vacia_no_se_cuenta():
    """Regresión: bloque de resumen (Suma/Comi/Bruto/Transfer N) separado por
    una fila vacía, sin cuit/titular, no debe contarse como pagos reales."""
    wb = _wb_planilla_basica()
    ws = wb.active
    ws.append([None, None, None, None, None, None, None, None, None])  # fila vacía separadora
    ws.append([None, "Suma", 300000, None, None, None, None, None, None])
    ws.append([None, "Comi", 10500, None, None, None, None, None, None])
    ws.append([None, "Bruto", 289500, None, None, None, None, None, None])
    ws.append([None, "Transfer 1", 100000, None, None, None, None, None, None])
    ws.append([None, "Transfer 2", 200000, None, None, None, None, None, None])
    path = _xlsx_tmp(wb)
    try:
        r = parsear_planilla_cliente(path)
        assert r["total"] == 2  # solo las 2 filas reales, el resumen se descarta
    finally:
        _cleanup(path)


def test_fila_vacia_en_medio_de_datos_no_corta_la_tabla():
    """Una fila vacía accidental seguida de más filas con identidad real
    no debe cortar el parseo (solo cortamos si lo que sigue ya no tiene cuit/titular)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Importe", "Estado del pago", "Cuenta", "Fecha de transferencia",
               "Banco de origen", "Cuit", "Titular transferir", "Rendido"])
    ws.append([1, 100000, "Pago", "Caneland", "2026-06-04", "Mercado pago", "20940508925", "Juan Perez", "No"])
    ws.append([None, None, None, None, None, None, None, None, None])  # fila vacía accidental
    ws.append([2, 200000, "Pago", "Caneland", "2026-06-05", "Pvs", "20267910260", "Maria Lopez", "No"])
    path = _xlsx_tmp(wb)
    try:
        r = parsear_planilla_cliente(path)
        assert r["total"] == 2
        assert r["filas"][1]["titular"] == "Maria Lopez"
    finally:
        _cleanup(path)


def test_monto_no_numerico_se_descarta():
    """Defensa adicional: si el importe no es numérico (ej. texto "Total"),
    la fila no debe contarse aunque no haya fila vacía separadora antes."""
    wb = _wb_planilla_basica()
    ws = wb.active
    ws.append([None, "Total", None, None, None, None, None, None, None])
    path = _xlsx_tmp(wb)
    try:
        r = parsear_planilla_cliente(path)
        assert r["total"] == 2
    finally:
        _cleanup(path)
