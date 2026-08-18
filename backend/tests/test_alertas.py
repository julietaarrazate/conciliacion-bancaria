"""Tests de app.services.reportes_service.calcular_alertas — foco en las 2 alertas
nuevas de alto valor:

1. "planillas_descuadre": Planilla.total_declarado (lo que el cliente declaró)
   difiere en más de $1 de la suma real de sus PlanillaRow.monto.
2. "filas_ambiguas": PlanillaRow.status LIKE 'ambiguo%' (el motor de conciliación
   encontró 2+ candidatos con el mismo score y no puede elegir sin arriesgar).

Ambas deben respetar el aislamiento multi-tenant (organizacion_id).
"""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from datetime import timedelta
from zoneinfo import ZoneInfo

from app.database import Base
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente
from app.models.cheque import Cheque
from app.models.planilla import Planilla, PlanillaRow
from app.services.auth import get_password_hash
from app.services import reportes_service as svc


def _hoy_art():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()


def _cheque(db, org_id, cliente_id, fecha_deposito, estado="registrado", monto="1000.00"):
    ch = Cheque(
        organizacion_id=org_id,
        cliente_id=cliente_id,
        monto=Decimal(monto),
        estado=estado,
        fecha_deposito=fecha_deposito,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


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

    for oid, nombre in ((1, "Principal"), (2, "Org2"), (3, "Org3")):
        session.add(Organizacion(id=oid, nombre=nombre))
    session.commit()

    user = User(
        email="u@org.test", full_name="U",
        hashed_password=get_password_hash("pw123"),
        organizacion_id=1, is_active=True, role="admin",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


def _cliente(db, org_id, nombre="Cliente Test"):
    c = Cliente(nombre=nombre, organizacion_id=org_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _planilla(db, org_id, cliente_id, usuario_id, total_declarado=None, nombre="planilla.xlsx"):
    p = Planilla(
        cliente_id=cliente_id,
        usuario_id=usuario_id,
        organizacion_id=org_id,
        nombre_archivo=nombre,
        fecha_carga=datetime.utcnow(),
        total_declarado=total_declarado,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _row(db, org_id, planilla_id, monto, status="ok"):
    r = PlanillaRow(
        planilla_id=planilla_id,
        organizacion_id=org_id,
        monto=Decimal(str(monto)),
        status=status,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _tipo(alertas, tipo):
    return next((a for a in alertas if a["tipo"] == tipo), None)


class TestPlanillasDescuadre:

    def test_descuadre_aparece_con_cantidad_correcta(self, db):
        cli = _cliente(db, 1)
        # total declarado 1000, filas suman 700 -> descuadre de 300 (> $1)
        p = _planilla(db, 1, cli.id, 1, total_declarado=Decimal("1000.00"))
        _row(db, 1, p.id, "500.00")
        _row(db, 1, p.id, "200.00")

        result = svc.calcular_alertas(db, 1)
        a = _tipo(result["alertas"], "planillas_descuadre")
        assert a is not None
        assert a["cantidad"] == 1
        assert a["link"] == "/conciliaciones"

    def test_sin_descuadre_no_aparece(self, db):
        cli = _cliente(db, 1)
        # total declarado cuadra exactamente con la suma de filas
        p = _planilla(db, 1, cli.id, 1, total_declarado=Decimal("700.00"))
        _row(db, 1, p.id, "500.00")
        _row(db, 1, p.id, "200.00")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "planillas_descuadre") is None

    def test_diferencia_menor_a_un_peso_no_cuenta(self, db):
        cli = _cliente(db, 1)
        # diferencia de $0.50 -> dentro de la tolerancia, no debe contar
        p = _planilla(db, 1, cli.id, 1, total_declarado=Decimal("700.50"))
        _row(db, 1, p.id, "500.00")
        _row(db, 1, p.id, "200.00")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "planillas_descuadre") is None

    def test_sin_total_declarado_no_cuenta(self, db):
        cli = _cliente(db, 1)
        p = _planilla(db, 1, cli.id, 1, total_declarado=None)
        _row(db, 1, p.id, "500.00")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "planillas_descuadre") is None

    def test_planilla_borrada_no_cuenta(self, db):
        cli = _cliente(db, 1)
        p = _planilla(db, 1, cli.id, 1, total_declarado=Decimal("1000.00"))
        _row(db, 1, p.id, "1.00")
        p.deleted_at = datetime.utcnow()
        db.commit()

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "planillas_descuadre") is None

    def test_multitenant_descuadre_de_otra_org_no_aparece(self, db):
        """Descuadre creado en la org 2 no debe filtrarse a la org 3 (ni a la 1)."""
        cli2 = _cliente(db, 2)
        p2 = _planilla(db, 2, cli2.id, 1, total_declarado=Decimal("1000.00"))
        _row(db, 2, p2.id, "1.00")

        result_org3 = svc.calcular_alertas(db, 3)
        assert _tipo(result_org3["alertas"], "planillas_descuadre") is None

        result_org1 = svc.calcular_alertas(db, 1)
        assert _tipo(result_org1["alertas"], "planillas_descuadre") is None

        result_org2 = svc.calcular_alertas(db, 2)
        assert _tipo(result_org2["alertas"], "planillas_descuadre") is not None


class TestFilasAmbiguas:

    def test_fila_ambigua_cuenta(self, db):
        cli = _cliente(db, 1)
        p = _planilla(db, 1, cli.id, 1)
        _row(db, 1, p.id, "100.00", status="ambiguo (2 candidatos, mismo score)")
        _row(db, 1, p.id, "50.00", status="ok")

        result = svc.calcular_alertas(db, 1)
        a = _tipo(result["alertas"], "filas_ambiguas")
        assert a is not None
        assert a["cantidad"] == 1
        assert a["link"] == "/conciliaciones"

    def test_sin_filas_ambiguas_no_aparece(self, db):
        cli = _cliente(db, 1)
        p = _planilla(db, 1, cli.id, 1)
        _row(db, 1, p.id, "100.00", status="ok")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "filas_ambiguas") is None

    def test_multitenant_ambiguas_de_otra_org_no_aparece(self, db):
        cli2 = _cliente(db, 2)
        p2 = _planilla(db, 2, cli2.id, 1)
        _row(db, 2, p2.id, "100.00", status="ambiguo (2 candidatos, mismo score)")

        result_org3 = svc.calcular_alertas(db, 3)
        assert _tipo(result_org3["alertas"], "filas_ambiguas") is None

        result_org2 = svc.calcular_alertas(db, 2)
        assert _tipo(result_org2["alertas"], "filas_ambiguas") is not None


class TestAlertasCheques:
    """Regresión del bug: las alertas contaban cheques por estado == 'pendiente', pero
    el estado canónico es 'registrado' (el backfill migra 'pendiente' -> 'registrado'),
    así que SIEMPRE daban 0. Ahora cuentan los estados 'en cartera' (registrado/pendiente)."""

    def test_cheque_registrado_por_vencer_dispara_urgente(self, db):
        """El bug: un cheque en el estado canónico 'registrado' antes NO se contaba."""
        cli = _cliente(db, 1)
        _cheque(db, 1, cli.id, _hoy_art() + timedelta(days=3), estado="registrado")

        result = svc.calcular_alertas(db, 1)
        a = _tipo(result["alertas"], "cheques_urgentes")
        assert a is not None
        assert a["cantidad"] == 1
        assert a["link"] == "/cheques"

    def test_cheque_pendiente_legacy_tambien_cuenta(self, db):
        cli = _cliente(db, 1)
        _cheque(db, 1, cli.id, _hoy_art() + timedelta(days=2), estado="pendiente")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "cheques_urgentes") is not None

    def test_cheque_vencido_dispara_vencidos(self, db):
        cli = _cliente(db, 1)
        _cheque(db, 1, cli.id, _hoy_art() - timedelta(days=5), estado="registrado")

        result = svc.calcular_alertas(db, 1)
        a = _tipo(result["alertas"], "cheques_vencidos")
        assert a is not None
        assert a["cantidad"] == 1

    def test_cheque_acreditado_no_dispara_alerta(self, db):
        """Un cheque ya acreditado/rechazado/anulado está resuelto: no es urgente ni vencido."""
        cli = _cliente(db, 1)
        _cheque(db, 1, cli.id, _hoy_art() + timedelta(days=2), estado="acreditado")
        _cheque(db, 1, cli.id, _hoy_art() - timedelta(days=2), estado="rechazado")
        _cheque(db, 1, cli.id, _hoy_art() - timedelta(days=2), estado="anulado")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "cheques_urgentes") is None
        assert _tipo(result["alertas"], "cheques_vencidos") is None

    def test_cheque_lejano_no_es_urgente(self, db):
        cli = _cliente(db, 1)
        # fecha_deposito a 30 días: fuera de la ventana de 7 días de "urgente"
        _cheque(db, 1, cli.id, _hoy_art() + timedelta(days=30), estado="registrado")

        result = svc.calcular_alertas(db, 1)
        assert _tipo(result["alertas"], "cheques_urgentes") is None

    def test_multitenant_cheque_de_otra_org_no_aparece(self, db):
        cli2 = _cliente(db, 2)
        _cheque(db, 2, cli2.id, _hoy_art() + timedelta(days=2), estado="registrado")

        result_org1 = svc.calcular_alertas(db, 1)
        assert _tipo(result_org1["alertas"], "cheques_urgentes") is None

        result_org2 = svc.calcular_alertas(db, 2)
        assert _tipo(result_org2["alertas"], "cheques_urgentes") is not None

    def test_proximos_vencimiento_incluye_registrado(self, db):
        """_cheques_proximos_vencimiento (dashboard resumen) tenía el mismo bug."""
        cli = _cliente(db, 1)
        _cheque(db, 1, cli.id, _hoy_art() + timedelta(days=10), estado="registrado")

        proximos = svc._cheques_proximos_vencimiento(db, 1, dias=30)
        assert len(proximos) == 1
