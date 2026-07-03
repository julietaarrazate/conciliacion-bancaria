"""Tests para el servicio de export contable.

Cubre:
  - CSV genérico (separadores, encodings, formato fecha, columnas)
  - Tango TXT (tab-separated, coma decimal, latin-1)
  - Holistor TXT (punto y coma, coma decimal, latin-1)
  - Regisoft CSV (coma, punto decimal, utf-8)
  - Mapeo de cuentas (con y sin mapeo, advertencias)
  - Partida doble: suma debe == suma haber por asiento
  - Rango de fechas (desde/hasta filtra correctamente)
  - Formato desconocido lanza ValueError
"""
import pytest
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.contabilidad import PlanCuenta, Asiento, AsientoDetalle
from app.models.organizacion import Organizacion
from app.services.export_contable import exportar_asientos


ORG_ID = 99  # ID de test, no colisiona con producción


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    org = Organizacion(id=ORG_ID, nombre="Test Export SA", plan="pro", activo=True, configuracion={})
    session.add(org)
    session.flush()

    # Cuentas mínimas
    c1 = PlanCuenta(id=101, codigo="1-1-1-3-1", nombre="Banco Macro", tipo="activo", nivel=4, activo=True, organizacion_id=ORG_ID)
    c2 = PlanCuenta(id=102, codigo="2-1-1-1",   nombre="No identificado", tipo="pasivo", nivel=3, activo=True, organizacion_id=ORG_ID)
    c3 = PlanCuenta(id=103, codigo="2-1-2-1",   nombre="Cliente Verde",   tipo="pasivo", nivel=4, activo=True, organizacion_id=ORG_ID)
    session.add_all([c1, c2, c3])
    session.flush()

    # Asiento 1: UM lote (Banco D / NoId H) — 2026-06-01
    a1 = Asiento(
        id=201, numero_asiento=1, fecha=date(2026, 6, 1),
        descripcion="UM lote 1 — 3 movimientos", modulo="um_lote",
        organizacion_id=ORG_ID,
    )
    session.add(a1)
    session.flush()
    session.add(AsientoDetalle(asiento_id=201, cuenta_id=101, debe=Decimal("50000.00"), haber=Decimal("0")))
    session.add(AsientoDetalle(asiento_id=201, cuenta_id=102, debe=Decimal("0"), haber=Decimal("50000.00")))

    # Asiento 2: reclasificación (NoId D / Cliente H) — 2026-06-02
    a2 = Asiento(
        id=202, numero_asiento=2, fecha=date(2026, 6, 2),
        descripcion="TT Verde — planilla.xlsx", modulo="um_reclass_planilla",
        organizacion_id=ORG_ID,
    )
    session.add(a2)
    session.flush()
    session.add(AsientoDetalle(asiento_id=202, cuenta_id=102, debe=Decimal("30000.50"), haber=Decimal("0")))
    session.add(AsientoDetalle(asiento_id=202, cuenta_id=103, debe=Decimal("0"), haber=Decimal("30000.50")))

    # Asiento 3: fecha futura — para test de rango
    a3 = Asiento(
        id=203, numero_asiento=3, fecha=date(2026, 7, 15),
        descripcion="Asiento julio", modulo="egreso",
        organizacion_id=ORG_ID,
    )
    session.add(a3)
    session.flush()
    session.add(AsientoDetalle(asiento_id=203, cuenta_id=103, debe=Decimal("1000.00"), haber=Decimal("0")))
    session.add(AsientoDetalle(asiento_id=203, cuenta_id=101, debe=Decimal("0"), haber=Decimal("1000.00")))

    session.commit()
    yield session
    session.close()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _lineas(content_bytes, encoding="utf-8"):
    return content_bytes.decode(encoding, errors="replace").strip().split("\n")


# ── CSV genérico ─────────────────────────────────────────────────────────────

def test_csv_columnas_default(db):
    content, filename, ct, sin_mapeo = exportar_asientos(
        db, ORG_ID, None, None, "csv", {}
    )
    assert filename.endswith(".csv")
    assert "csv" in ct
    lineas = _lineas(content)
    # Header
    assert lineas[0] == "fecha,numero_asiento,codigo_cuenta,nombre_cuenta,debe,haber,descripcion"
    # Al menos 5 filas de datos (2 detalles en a1 + 2 en a2 + 2 en a3)
    assert len(lineas) >= 7


def test_csv_separador_punto_coma(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, None, None, "csv",
        {"separador": ";"}
    )
    lineas = _lineas(content)
    assert ";" in lineas[0]
    partes = lineas[1].split(";")
    assert len(partes) == 7


def test_csv_separador_tab(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, None, None, "csv",
        {"separador": "\t"}
    )
    lineas = _lineas(content)
    assert "\t" in lineas[0]


def test_csv_encoding_latin1(db):
    content, _, ct, _ = exportar_asientos(
        db, ORG_ID, None, None, "csv",
        {"encoding": "latin-1"}
    )
    assert "latin-1" in ct
    # Debe decodificarse en latin-1 sin error
    content.decode("latin-1")


def test_csv_formato_fecha_iso(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "csv",
        {"formato_fecha": "YYYY-MM-DD"}
    )
    lineas = _lineas(content)
    # Línea 1 (primera data) debe tener la fecha en ISO
    assert "2026-06-01" in lineas[1]


def test_csv_formato_fecha_dmy(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "csv",
        {"formato_fecha": "DD/MM/YYYY"}
    )
    lineas = _lineas(content)
    assert "01/06/2026" in lineas[1]


def test_csv_partida_doble(db):
    """Para cada asiento, suma debe == suma haber."""
    import csv as _csv, io

    content, _, _, _ = exportar_asientos(db, ORG_ID, None, None, "csv", {})
    reader = _csv.DictReader(io.StringIO(content.decode("utf-8")))
    totales: dict[str, dict] = {}
    for row in reader:
        nro = row["numero_asiento"]
        if nro not in totales:
            totales[nro] = {"debe": Decimal("0"), "haber": Decimal("0")}
        totales[nro]["debe"] += Decimal(row["debe"])
        totales[nro]["haber"] += Decimal(row["haber"])

    for nro, t in totales.items():
        assert t["debe"] == t["haber"], f"Asiento #{nro}: debe {t['debe']} != haber {t['haber']}"


# ── Tango ──────────────────────────────────────────────────────────────────

def test_tango_estructura(db):
    content, filename, ct, _ = exportar_asientos(
        db, ORG_ID, None, None, "tango", {}
    )
    assert "tango" in filename
    assert filename.endswith(".txt")
    assert "latin-1" in ct
    lineas = content.decode("latin-1").strip().split("\r\n")
    # Sin header; primera línea = primera fila de datos
    partes = lineas[0].split("\t")
    assert len(partes) == 6, f"Esperaba 6 columnas, got {len(partes)}: {partes}"


def test_tango_coma_decimal(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "tango", {}
    )
    lineas = content.decode("latin-1").strip().split("\r\n")
    for linea in lineas:
        partes = linea.split("\t")
        # debe y haber (columnas 3 y 4) deben usar coma decimal
        debe = partes[3]
        haber = partes[4]
        assert "," in debe or debe == "0,00", f"Debe sin coma decimal: {debe}"
        assert "," in haber or haber == "0,00", f"Haber sin coma decimal: {haber}"


def test_tango_fecha_dmy(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "tango", {}
    )
    lineas = content.decode("latin-1").strip().split("\r\n")
    assert lineas[0].startswith("01/06/2026")


# ── Holistor ──────────────────────────────────────────────────────────────

def test_holistor_estructura(db):
    content, filename, ct, _ = exportar_asientos(
        db, ORG_ID, None, None, "holistor", {}
    )
    assert "holistor" in filename
    assert "latin-1" in ct
    lineas = content.decode("latin-1").strip().split("\r\n")
    partes = lineas[0].split(";")
    # fecha;cuenta;debe;haber;leyenda = 5 columnas
    assert len(partes) == 5, f"Esperaba 5 columnas, got {len(partes)}: {partes}"


def test_holistor_fecha_dmy(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "holistor", {}
    )
    lineas = content.decode("latin-1").strip().split("\r\n")
    assert lineas[0].startswith("01/06/2026")


def test_holistor_coma_decimal(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "holistor", {}
    )
    lineas = content.decode("latin-1").strip().split("\r\n")
    for linea in lineas:
        partes = linea.split(";")
        debe = partes[2]
        haber = partes[3]
        assert "," in debe or debe == "0,00"
        assert "," in haber or haber == "0,00"


# ── Regisoft ─────────────────────────────────────────────────────────────────

def test_regisoft_headers(db):
    content, filename, ct, _ = exportar_asientos(
        db, ORG_ID, None, None, "regisoft", {}
    )
    assert "regisoft" in filename
    assert "utf-8" in ct
    lineas = _lineas(content)
    assert lineas[0] == "Fecha,Cuenta,Detalle,Debe,Haber"


def test_regisoft_punto_decimal(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "regisoft", {}
    )
    lineas = _lineas(content)
    for linea in lineas[1:]:
        partes = linea.split(",")
        debe = partes[3]
        assert "." in debe, f"Debe sin punto decimal: {debe}"


def test_regisoft_fecha_dmy(db):
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-02", "2026-06-02", "regisoft", {}
    )
    lineas = _lineas(content)
    assert lineas[1].startswith("02/06/2026")


# ── Mapeo de cuentas ────────────────────────────────────────────────────────

def test_csv_sin_mapeo_no_advierte(db):
    """Sin mapeo configurado y formato csv → no hay advertencias."""
    content, _, _, sin_mapeo = exportar_asientos(
        db, ORG_ID, None, None, "csv", {}
    )
    assert sin_mapeo == []


def test_tango_sin_mapeo_no_advierte(db):
    """Sin mapeo configurado y formato no-csv → sin_mapeo vacío (no hay mapeo esperado)."""
    _, _, _, sin_mapeo = exportar_asientos(
        db, ORG_ID, None, None, "tango", {}
    )
    assert sin_mapeo == []


def test_mapeo_aplicado_en_tango(db):
    """Con mapeo configurado, los códigos exportados son los del mapeo."""
    mapeo = {
        "1-1-1-3-1": "11030001",
        "2-1-1-1": "21010001",
        "2-1-2-1": "21020001",
    }
    content, _, _, sin_mapeo = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "tango",
        {"mapeo_cuentas_export": mapeo}
    )
    assert sin_mapeo == []
    lineas = content.decode("latin-1").strip().split("\r\n")
    # Los códigos en columna 2 (índice 2) deben ser los mapeados
    codigos = {l.split("\t")[2] for l in lineas if l.strip()}
    assert "11030001" in codigos
    assert "21010001" in codigos
    # Ningún código debe ser el de Cuadra original
    assert "1-1-1-3-1" not in codigos
    assert "2-1-1-1" not in codigos


def test_mapeo_parcial_advierte_cuentas_faltantes(db):
    """Mapeo parcial → sin_mapeo lista los códigos sin mapear."""
    mapeo = {
        "1-1-1-3-1": "11030001",
        # 2-1-1-1 y 2-1-2-1 NO mapeados
    }
    _, _, _, sin_mapeo = exportar_asientos(
        db, ORG_ID, None, None, "tango",
        {"mapeo_cuentas_export": mapeo}
    )
    assert "2-1-1-1" in sin_mapeo
    assert "2-1-2-1" in sin_mapeo
    assert "1-1-1-3-1" not in sin_mapeo


def test_csv_con_mapeo_no_advierte(db):
    """Formato csv nunca advierte, sin importar el mapeo."""
    mapeo = {"1-1-1-3-1": "11030001"}  # parcial
    _, _, _, sin_mapeo = exportar_asientos(
        db, ORG_ID, None, None, "csv",
        {"mapeo_cuentas_export": mapeo}
    )
    assert sin_mapeo == []


def test_mapeo_codigos_en_csv(db):
    """En CSV el código exportado también usa el mapeo."""
    mapeo = {"1-1-1-3-1": "BANCOMACRO", "2-1-1-1": "NOID", "2-1-2-1": "VERDE"}
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "csv",
        {"mapeo_cuentas_export": mapeo}
    )
    texto = content.decode("utf-8")
    assert "BANCOMACRO" in texto
    assert "NOID" in texto
    # Código original NO debe aparecer
    assert "1-1-1-3-1" not in texto.split("\n", 1)[1]  # ignora header


# ── Rango de fechas ─────────────────────────────────────────────────────────

def test_rango_desde_filtra(db):
    """Solo trae asientos desde la fecha indicada."""
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-02", None, "csv", {}
    )
    import csv as _csv, io
    reader = _csv.DictReader(io.StringIO(content.decode("utf-8")))
    fechas = {row["fecha"] for row in reader}
    # No debe incluir 01/06/2026 (asiento 1)
    assert "01/06/2026" not in fechas
    assert "02/06/2026" in fechas


def test_rango_hasta_filtra(db):
    """Solo trae asientos hasta la fecha indicada."""
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, None, "2026-06-30", "csv", {}
    )
    import csv as _csv, io
    reader = _csv.DictReader(io.StringIO(content.decode("utf-8")))
    fechas = {row["fecha"] for row in reader}
    # No debe incluir julio
    assert "15/07/2026" not in fechas
    assert "01/06/2026" in fechas


def test_rango_exacto(db):
    """Solo trae asientos del día exacto."""
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2026-06-01", "2026-06-01", "csv", {}
    )
    import csv as _csv, io
    reader = _csv.DictReader(io.StringIO(content.decode("utf-8")))
    rows = list(reader)
    assert len(rows) == 2  # Solo 2 detalles del asiento 1
    for r in rows:
        assert r["fecha"] == "01/06/2026"


# ── Formato inválido ─────────────────────────────────────────────────────────

def test_formato_invalido_lanza_error(db):
    with pytest.raises(ValueError, match="Formato desconocido"):
        exportar_asientos(db, ORG_ID, None, None, "excel_macro", {})


# ── Sin datos ────────────────────────────────────────────────────────────────

def test_csv_sin_datos_devuelve_solo_header(db):
    """Rango sin asientos → solo el header, sin data rows."""
    content, _, _, _ = exportar_asientos(
        db, ORG_ID, "2030-01-01", "2030-01-31", "csv", {}
    )
    lineas = _lineas(content)
    # Solo la línea de header
    assert len(lineas) == 1
    assert lineas[0].startswith("fecha")
