"""Tests del pipeline de estandarización de planillas (`services/planilla_mapper.py`)
y sus endpoints (`/planillas/preview`, `/planillas/upload` con mapeo).

Los 3 formatos reales (Tucu, Green, Dani) se construyen INLINE con openpyxl y
datos DUMMY — no hay datos reales de terceros en el repo. Estructuras replicadas:

- TUCU: fila1 título "TRANSFERENCIAS"; fila2 headers; col "Cliente" constante.
- GREEN: fila1 vacía; datos arrancan en col B (offset); headers en fila2.
- DANI: headers en fila1; col "Cuenta" constante; algún CUIT de 10 dígitos.
"""
import io
from datetime import date, datetime
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.auth import get_password_hash, create_access_token
from app.services.planilla_mapper import estandarizar_planilla
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.planilla import PlanillaRow


# ── Constructores de fixtures inline ──────────────────────────────────────────

def _build_xlsx(rows, sheet_title="Hoja1") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _tucu_rows(extra_empty=0):
    rows = [
        ["TRANSFERENCIAS", None, None, None, None, None, None],
        ["FECHA TRANSFERENCIA", "Cliente", "CUENTA DEPOSITO", "Banco emisor",
         "Titular de la cuenta", "CUIT/CUIL/DNI", "MONTO"],
        ["2026-06-04", "Caneland", "00012345", "Mercado Pago", "Juan Perez", "20940508925", 100000],
        ["2026-06-05", "Caneland", "00012346", "Galicia", "Maria Lopez", "27123456784", 200000],
        ["2026-06-06", "Caneland", "00012347", "BBVA", "Pedro Gomez", "20111111112", 50000],
    ]
    for _ in range(extra_empty):
        rows.append([None] * 7)
    return rows


def _green_rows():
    return [
        [None] * 7,
        [None, "ORDEN", "FECHA TRANSFERENCIA", "Titular de la cuenta", "CUIT/CUIL",
         "Importe", "CONFIRMACION"],
        [None, "2026-06-01 10:00:00", "2026-06-04", "Ana Diaz", "20222222223", 150000, "OK"],
        [None, "2026-06-02 11:00:00", "2026-06-05", "Luis Fernandez", "27333333334", 250000, "OK"],
        # Fila válida SIN identidad (titular/cuit vacíos): se preserva.
        [None, "2026-06-03 12:00:00", "2026-06-06", None, None, 75000, None],
    ]


def _dani_rows():
    return [
        ["ID", "Importe", "Estado del pago", "Cuenta", "Fecha de transferencia",
         "Banco de origen", "Cuit", "Titular transferir", "Rendido"],
        # CUIT de 10 dígitos (no 11) — debe aceptarse.
        [1, 100000, "Pago", "Caneland", "2026-06-04", "Mercado pago", "2094050892", "Juan Perez", "No"],
        [2, 200000, "Pago", "Caneland", "2026-06-05", "Pvs", "20267910260", "Maria Lopez", "No"],
    ]


# ── Tests de detección (heurística pura, sin IA) ──────────────────────────────

class TestDeteccionHeuristica:

    def test_tucu_header_en_fila_2_y_columnas(self):
        r = estandarizar_planilla(_build_xlsx(_tucu_rows()), usar_ia=False)
        assert r["header_row"] == 2
        assert r["columnas"] == {"monto": 7, "cuit": 6, "titular": 5, "fecha": 1, "referencia": None}
        assert r["confianza"] >= 0.7
        assert r["origen"] == "heuristica"

    def test_green_header_fila_2_con_offset_columna_B(self):
        r = estandarizar_planilla(_build_xlsx(_green_rows()), usar_ia=False)
        assert r["header_row"] == 2
        # Datos arrancan en col B → índices desplazados.
        assert r["columnas"]["monto"] == 6
        assert r["columnas"]["cuit"] == 5
        assert r["columnas"]["titular"] == 4
        assert r["columnas"]["fecha"] == 3
        assert r["columnas"]["referencia"] == 2

    def test_dani_header_en_fila_1(self):
        r = estandarizar_planilla(_build_xlsx(_dani_rows()), usar_ia=False)
        assert r["header_row"] == 1
        assert r["columnas"]["monto"] == 2
        assert r["columnas"]["cuit"] == 7
        assert r["columnas"]["titular"] == 8
        assert r["columnas"]["fecha"] == 5
        assert r["columnas"]["referencia"] == 1

    def test_trampa_caneland_columna_cliente_no_es_titular(self):
        """La col 'Cliente' (constante 'Caneland') NO debe mapearse a titular."""
        r = estandarizar_planilla(_build_xlsx(_tucu_rows()), usar_ia=False)
        assert r["columnas"]["titular"] == 5  # 'Titular de la cuenta', no 'Cliente' (2)
        assert r["columnas"]["titular"] != 2

    def test_columna_constante_descartada_por_validacion(self):
        """Aunque el header matchee titular, si el contenido es constante se
        descarta y se elige la columna con titulares variados."""
        rows = [
            ["Nombre", "Titular de la cuenta", "Importe", "CUIT"],
            ["Caneland", "Juan Perez", 100000, "20940508925"],
            ["Caneland", "Maria Lopez", 200000, "27123456784"],
            ["Caneland", "Pedro Gomez", 50000, "20111111112"],
        ]
        r = estandarizar_planilla(_build_xlsx(rows), usar_ia=False)
        assert r["columnas"]["titular"] == 2  # la variada, no 'Nombre' (1, constante)
        assert r["columnas"]["titular"] != 1


# ── Tests de parseo a esquema canónico ────────────────────────────────────────

class TestParseoCanonico:

    def test_tucu_filas_canonicas_con_decimal(self):
        r = estandarizar_planilla(_build_xlsx(_tucu_rows()), usar_ia=False)
        assert r["filas_totales"] == 3
        f0 = r["filas"][0]
        assert isinstance(f0["monto"], Decimal)
        assert f0["monto"] == Decimal("100000")
        assert f0["cuit"] == "20940508925"
        assert f0["titular"] == "Juan Perez"
        assert f0["fecha"] == date(2026, 6, 4)

    def test_green_filas_canonicas(self):
        r = estandarizar_planilla(_build_xlsx(_green_rows()), usar_ia=False)
        assert r["filas_totales"] == 3
        montos = [f["monto"] for f in r["filas"]]
        assert montos == [Decimal("150000"), Decimal("250000"), Decimal("75000")]

    def test_dani_cuit_10_digitos_aceptado(self):
        r = estandarizar_planilla(_build_xlsx(_dani_rows()), usar_ia=False)
        assert r["filas_totales"] == 2
        assert r["filas"][0]["cuit"] == "2094050892"  # 10 dígitos, no se descarta
        assert len(r["filas"][0]["cuit"]) == 10

    def test_fila_con_monto_sin_identidad_se_preserva(self):
        r = estandarizar_planilla(_build_xlsx(_green_rows()), usar_ia=False)
        ultima = r["filas"][-1]
        assert ultima["monto"] == Decimal("75000")
        assert ultima["cuit"] is None
        assert ultima["titular"] is None

    def test_corta_al_final_pese_a_filas_vacias_infinitas(self):
        """~20 filas vacías tras los datos no deben inflar el resultado."""
        r = estandarizar_planilla(_build_xlsx(_tucu_rows(extra_empty=20)), usar_ia=False)
        assert r["filas_totales"] == 3


# ── Tests de detección de filas de resumen / total ───────────────────────────

class TestDeteccionTotales:

    def _rows_base(self):
        """3 movimientos reales (suma 350000), headers en fila 1."""
        return [
            ["Fecha", "Titular de la cuenta", "CUIT/CUIL/DNI", "MONTO"],
            ["2026-06-04", "Juan Perez", "20940508925", 100000],
            ["2026-06-05", "Maria Lopez", "27123456784", 200000],
            ["2026-06-06", "Pedro Gomez", "20111111112", 50000],
        ]

    def test_total_por_etiqueta_se_excluye(self):
        rows = self._rows_base()
        rows.append(["", "TOTAL", None, 350000])  # fila total etiquetada, sin cuit
        r = estandarizar_planilla(_build_xlsx(rows), usar_ia=False)
        assert r["filas_totales"] == 3
        assert r["filas_resumen"] == 1
        assert r["total_declarado"] == Decimal("350000")
        assert r["total_movimientos"] == Decimal("350000")
        assert r["total_cuadra"] is True
        # la fila total no quedó como movimiento
        assert all(f["titular"] != "TOTAL" for f in r["filas"])

    def test_total_por_aritmetica_sin_etiqueta_se_excluye(self):
        rows = self._rows_base()
        rows.append(["", None, None, 350000])  # sin etiqueta, monto = suma
        r = estandarizar_planilla(_build_xlsx(rows), usar_ia=False)
        assert r["filas_totales"] == 3
        assert r["filas_resumen"] == 1
        assert r["total_declarado"] == Decimal("350000")
        assert r["total_cuadra"] is True

    def test_varias_lineas_resumen_trailing_todas_excluidas(self):
        rows = self._rows_base()
        rows.append(["", "Suma", None, 350000])
        rows.append(["", "Comision", None, 3500])
        rows.append(["", "Bruto", None, 346500])
        r = estandarizar_planilla(_build_xlsx(rows), usar_ia=False)
        assert r["filas_totales"] == 3
        assert r["filas_resumen"] == 3
        # el total declarado es la fila etiquetada "Suma" (≈ suma de movimientos)
        assert r["total_declarado"] == Decimal("350000")
        assert r["total_cuadra"] is True

    def test_sin_total_movimientos_intactos(self):
        r = estandarizar_planilla(_build_xlsx(self._rows_base()), usar_ia=False)
        assert r["filas_totales"] == 3
        assert r["filas_resumen"] == 0
        assert r["total_declarado"] is None
        assert r["total_cuadra"] is None
        assert r["total_movimientos"] == Decimal("350000")

    def test_no_borra_movimiento_real_con_cuit_aunque_monto_coincida(self):
        """Un movimiento trailing con cuit NO es resumen aunque su monto = suma."""
        rows = self._rows_base()
        # fila trailing con cuit y monto = suma de las anteriores (350000)
        rows.append(["2026-06-07", "Cliente Grande", "30500010753", 350000])
        r = estandarizar_planilla(_build_xlsx(rows), usar_ia=False)
        assert r["filas_totales"] == 4  # no se borró
        assert r["filas_resumen"] == 0
        assert r["total_declarado"] is None
        assert any(f["cuit"] == "30500010753" for f in r["filas"])

    def test_descuadre_total_distinto_de_suma(self):
        rows = self._rows_base()
        rows.append(["", "TOTAL", None, 999999])  # etiquetada pero no cuadra
        r = estandarizar_planilla(_build_xlsx(rows), usar_ia=False)
        assert r["filas_totales"] == 3
        assert r["filas_resumen"] == 1
        assert r["total_declarado"] == Decimal("999999")
        assert r["total_movimientos"] == Decimal("350000")
        assert r["total_cuadra"] is False


# ── Blindaje Dani: bloque de cálculos del cliente NO contamina los movimientos ─

class TestBlindajeDaniBloqueCalculo:
    """Regresión (blindaje Dani): una planilla con los movimientos reales, luego un
    HUECO de filas vacías y después un bloque de liquidación del cliente
    ("Suma"/"Comi"/"Bruto"/"Transfer 1/2"/"Neto") en otra columna NO debe:
      - contar el bloque de cálculo como movimientos,
      - dejar ningún "Transfer N"/"Suma"/"Bruto"/"Neto" en `filas`,
      - tomar el "Neto"/"Bruto"/"Transfer" del cliente como total_declarado espurio.
    """

    def _dani_con_bloque_calculo(self):
        # Movimientos reales: ID (col A), Importe (col B), Fecha, Cuit, Titular.
        # El monto vive en la col B; el bloque de cálculo del cliente pone sus
        # etiquetas en la col B (texto → no parsea como monto) y los importes
        # calculados en la col C.
        return [
            ["ID", "Importe", "Fecha", "Cuit", "Titular"],
            [1, 100000, "2026-06-04", "20940508925", "Juan Perez"],
            [2, 200000, "2026-06-05", "27123456784", "Maria Lopez"],
            [3, 50000, "2026-06-06", "20111111112", "Pedro Gomez"],
            # HUECO de filas vacías entre los movimientos y el bloque de cálculo.
            [None, None, None, None, None],
            [None, None, None, None, None],
            [None, None, None, None, None],
            # Bloque de liquidación del cliente (col B = etiqueta, col C = monto).
            [None, "Suma", 350000, None, None],
            [None, "Comi", 3500, None, None],
            [None, "Bruto", 346500, None, None],
            [None, "Transfer 1", 173250, None, None],
            [None, "Transfer 2", 173250, None, None],
            [None, "Neto", 346500, None, None],
        ]

    def test_solo_extrae_los_movimientos_reales(self):
        r = estandarizar_planilla(_build_xlsx(self._dani_con_bloque_calculo()), usar_ia=False)
        # Solo los 3 movimientos reales; el bloque de cálculo queda afuera.
        assert r["filas_totales"] == 3
        assert r["columnas"]["monto"] == 2  # col B "Importe", no la col del bloque
        montos = {f["monto"] for f in r["filas"]}
        assert montos == {Decimal("100000"), Decimal("200000"), Decimal("50000")}

    def test_ninguna_etiqueta_de_calculo_queda_en_filas(self):
        r = estandarizar_planilla(_build_xlsx(self._dani_con_bloque_calculo()), usar_ia=False)
        etiquetas_prohibidas = {"suma", "comi", "bruto", "neto",
                                "transfer 1", "transfer 2"}
        for f in r["filas"]:
            # Ni el titular ni ningún valor de texto puede ser una etiqueta de cálculo.
            titular = (f.get("titular") or "").strip().lower()
            assert titular not in etiquetas_prohibidas
            assert not titular.startswith("transfer")
        # Ninguno de los importes espurios del bloque (comisión, neto/bruto).
        montos = {f["monto"] for f in r["filas"]}
        assert Decimal("3500") not in montos      # comisión
        assert Decimal("346500") not in montos     # bruto / neto
        assert Decimal("173250") not in montos     # transfers

    def test_total_declarado_no_es_espurio(self):
        r = estandarizar_planilla(_build_xlsx(self._dani_con_bloque_calculo()), usar_ia=False)
        # El bloque de cálculo NO debe interpretarse como total declarado.
        # total_declarado debe ser None (los movimientos reales tienen cuit, no
        # hay fila de resumen trailing) o, en el peor caso, el total real —
        # nunca el "Neto"/"Bruto"/"Transfer" del cliente.
        assert r["total_declarado"] in (None, Decimal("350000"))
        assert r["total_declarado"] != Decimal("346500")  # no el Neto/Bruto
        assert r["total_movimientos"] == Decimal("350000")


# ── Tests de mapeo manual (Capa 1 determinística) ─────────────────────────────

class TestMapeoManual:

    def test_mapeo_manual_dict_parsea_deterministico(self):
        mapeo = {"header_row": 2,
                 "columnas": {"monto": 7, "cuit": 6, "titular": 5, "fecha": 1, "referencia": None}}
        r = estandarizar_planilla(_build_xlsx(_tucu_rows()), mapeo=mapeo, usar_ia=False)
        assert r["origen"] == "manual"
        assert r["confianza"] == 1.0
        assert r["header_row"] == 2
        assert r["filas_totales"] == 3
        assert r["filas"][0]["monto"] == Decimal("100000")

    def test_perfil_con_fingerprint_que_no_matchea_cae_a_heuristica(self):
        mapeo = {"fingerprint": "no-matchea-nada", "header_row": 2,
                 "columnas": {"monto": 7, "cuit": 6, "titular": 5, "fecha": 1, "referencia": None}}
        r = estandarizar_planilla(_build_xlsx(_tucu_rows()), mapeo=mapeo, usar_ia=False)
        assert r["origen"] == "heuristica"

    def test_perfil_con_fingerprint_correcto_usa_perfil(self):
        # Primero detecto para obtener el fingerprint real del archivo.
        base = estandarizar_planilla(_build_xlsx(_tucu_rows()), usar_ia=False)
        mapeo = {"fingerprint": base["fingerprint"], "header_row": 2,
                 "columnas": base["columnas"]}
        r = estandarizar_planilla(_build_xlsx(_tucu_rows()), mapeo=mapeo, usar_ia=False)
        assert r["origen"] == "perfil"
        assert r["confianza"] == 1.0


# ── Fixtures para los endpoints ───────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add(Organizacion(id=1, nombre="OrgMapper"))
    session.add(Organizacion(id=2, nombre="OrgAjena"))
    session.commit()

    session.add(User(
        email="admin@mapper.test", full_name="Admin Mapper",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin", is_superadmin=False,
    ))
    # Cliente de OTRA org (para test de aislamiento multi-tenant)
    session.add(Cliente(id=99, nombre="ClienteAjeno", organizacion_id=2))
    session.commit()

    yield session
    session.close()


@pytest.fixture
def client(db):
    def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)


def _token(db, email="admin@mapper.test"):
    user = db.query(User).filter(User.email == email).first()
    return create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_extracto(db):
    extracto = ExtractoBancario(
        nombre_archivo="extracto.xlsx", organizacion_id=1, creado_por=1,
        fecha_creacion=datetime.utcnow(),
    )
    db.add(extracto)
    db.flush()
    db.add(MovimientoBanco(
        extracto_id=extracto.id, orden=1, fecha=date(2026, 6, 1), mes="junio",
        titular="Juan Perez", monto=Decimal("100000"), saldo=Decimal("100000"),
        source="extracto", organizacion_id=1,
    ))
    db.commit()
    db.refresh(extracto)
    return extracto


def _upload(cliente_nombre, extracto_id, xlsx_bytes, filename="planilla.xlsx"):
    return {
        "url": f"/planillas/upload?cliente_nombre={cliente_nombre}&extracto_id={extracto_id}",
        "files": {"file": (filename, xlsx_bytes,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    }


# ── Tests: endpoint /planillas/preview ────────────────────────────────────────

class TestPreviewEndpoint:

    def test_preview_devuelve_columnas_disponibles_preview_y_deteccion(self, client, db):
        token = _token(db)
        r = client.post(
            "/planillas/preview",
            files={"file": ("tucu.xlsx", _build_xlsx(_tucu_rows()),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["header_row"] == 2
        assert data["columnas"]["monto"] == 7
        # columnas_disponibles con muestras para el modal
        assert len(data["columnas_disponibles"]) == 7
        assert all("muestras" in c and "header" in c for c in data["columnas_disponibles"])
        # preview con las primeras filas de datos
        assert len(data["preview"]) == 3
        assert data["preview"][0]["fila"] == 3
        # deteccion con métricas
        assert data["deteccion"]["filas_totales"] == 3
        assert "origen" in data["deteccion"]

    def test_preview_sin_auth_retorna_403(self, client):
        r = client.post("/planillas/preview",
                        files={"file": ("p.xlsx", b"data", "application/octet-stream")})
        assert r.status_code in (401, 403)

    def test_preview_cliente_de_otra_org_retorna_404(self, client, db):
        """Aislamiento multi-tenant: cliente de otra org → 404."""
        token = _token(db)
        r = client.post(
            "/planillas/preview?cliente_id=99",
            files={"file": ("tucu.xlsx", _build_xlsx(_tucu_rows()),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=_auth(token),
        )
        assert r.status_code == 404


# ── Tests: endpoint /planillas/upload (con y sin mapeo) ───────────────────────

class TestUploadConPipeline:

    def test_upload_sin_mapeo_usa_heuristica(self, client, db):
        extracto = _seed_extracto(db)
        token = _token(db)
        args = _upload("ClienteHeur", extracto.id, _build_xlsx(_dani_rows()))
        r = client.post(args["url"], files=args["files"], headers=_auth(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["deteccion"]["origen"] == "heuristica"
        assert data["deteccion"]["filas_totales"] == 2
        rows = db.query(PlanillaRow).filter(PlanillaRow.planilla_id == data["id"]).all()
        assert len(rows) == 2
        assert all(row.status == "pendiente" for row in rows)

    def test_upload_con_mapeo_guarda_perfil_en_cliente(self, client, db):
        import json as _json
        extracto = _seed_extracto(db)
        token = _token(db)
        mapeo = {"header_row": 2,
                 "columnas": {"monto": 7, "cuit": 6, "titular": 5, "fecha": 1, "referencia": None}}
        args = _upload("ClientePerfil", extracto.id, _build_xlsx(_tucu_rows()))
        r = client.post(
            args["url"], files=args["files"],
            data={"mapeo": _json.dumps(mapeo)}, headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["deteccion"]["origen"] == "manual"

        cliente = db.query(Cliente).filter(
            Cliente.nombre.ilike("ClientePerfil"), Cliente.organizacion_id == 1
        ).first()
        assert cliente is not None
        assert cliente.mapeo_planilla is not None
        assert cliente.mapeo_planilla["columnas"]["monto"] == 7
        assert "fingerprint" in cliente.mapeo_planilla
        assert "actualizado" in cliente.mapeo_planilla

    def test_upload_reutiliza_perfil_guardado(self, client, db):
        """Segundo upload sin mapeo reusa el perfil aprendido (origen=perfil)."""
        import json as _json
        extracto = _seed_extracto(db)
        token = _token(db)
        mapeo = {"header_row": 2,
                 "columnas": {"monto": 7, "cuit": 6, "titular": 5, "fecha": 1, "referencia": None}}
        args = _upload("ClienteReuso", extracto.id, _build_xlsx(_tucu_rows()))
        client.post(args["url"], files=args["files"],
                    data={"mapeo": _json.dumps(mapeo)}, headers=_auth(token))

        # Segundo upload del MISMO formato, sin mapeo → debe usar el perfil.
        args2 = _upload("ClienteReuso", extracto.id, _build_xlsx(_tucu_rows()))
        r2 = client.post(args2["url"], files=args2["files"], headers=_auth(token))
        assert r2.status_code == 200, r2.text
        assert r2.json()["deteccion"]["origen"] == "perfil"

    def test_upload_los_3_formatos_parsean(self, client, db):
        extracto = _seed_extracto(db)
        token = _token(db)
        for nombre, rows, n in [("Tucu", _tucu_rows(), 3),
                                ("Green", _green_rows(), 3),
                                ("Dani", _dani_rows(), 2)]:
            args = _upload(nombre, extracto.id, _build_xlsx(rows))
            r = client.post(args["url"], files=args["files"], headers=_auth(token))
            assert r.status_code == 200, f"{nombre}: {r.text}"
            assert r.json()["deteccion"]["filas_totales"] == n
