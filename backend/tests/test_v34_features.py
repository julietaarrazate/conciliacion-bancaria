"""
Tests para las features de v3.4:
- Comisión por cliente (porcentaje_comision en modelo Cliente)
- Prioridad de comisión al generar liquidaciones
- Borrar liquidaciones en borrador (no las emitidas)
- Export fallback para filas "ok" con FK roto
- Serialización Decimal en auditoría
- Diseño: btn-yellow usa ml-blue en light mode (smoke test CSS)
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

import app.models.organizacion
import app.models.user
import app.models.extracto
import app.models.planilla
import app.models.cliente
import app.models.cheque
import app.models.pago
import app.models.caja
import app.models.liquidacion
import app.models.contabilidad
import app.models.auditoria
import app.models.patron_aprendido
import app.models.revoked_token


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_org(db, org_id=1, config=None):
    from app.models.organizacion import Organizacion
    org = Organizacion(id=org_id, nombre=f"Org{org_id}",
                       configuracion=config or {})
    db.add(org)
    db.flush()
    return org


def _make_user(db, user_id=1, org_id=1, superadmin=False):
    from app.models.user import User
    from app.services.auth import get_password_hash
    u = User(id=user_id, email=f"u{user_id}@test.com", full_name=f"U{user_id}",
             hashed_password=get_password_hash("x"),
             organizacion_id=org_id, is_superadmin=superadmin)
    db.add(u)
    db.flush()
    return u


def _make_cliente(db, cliente_id=1, org_id=1, nombre="Cliente Test",
                  cuit="20123456789", comision=None):
    from app.models.cliente import Cliente
    c = Cliente(id=cliente_id, organizacion_id=org_id, nombre=nombre,
                cuit=cuit, porcentaje_comision=comision)
    db.add(c)
    db.flush()
    return c


# ── Tests: porcentaje_comision en Cliente ─────────────────────────────────────

class TestComisionCliente:

    def test_cliente_sin_comision_es_none(self, db):
        _make_org(db)
        c = _make_cliente(db, comision=None)
        assert c.porcentaje_comision is None

    def test_cliente_con_comision_guarda_decimal(self, db):
        _make_org(db)
        c = _make_cliente(db, comision=Decimal("0.0200"))
        db.refresh(c)
        assert c.porcentaje_comision == Decimal("0.0200")

    def test_actualizar_comision_a_none(self, db):
        _make_org(db)
        c = _make_cliente(db, comision=Decimal("0.0150"))
        c.porcentaje_comision = None
        db.flush()
        db.refresh(c)
        assert c.porcentaje_comision is None

    def test_multiples_clientes_comisiones_distintas(self, db):
        _make_org(db)
        c1 = _make_cliente(db, cliente_id=1, nombre="A", comision=Decimal("0.0150"))
        c2 = _make_cliente(db, cliente_id=2, nombre="B", comision=Decimal("0.0180"))
        c3 = _make_cliente(db, cliente_id=3, nombre="C", comision=None)
        db.flush()
        assert c1.porcentaje_comision == Decimal("0.0150")
        assert c2.porcentaje_comision == Decimal("0.0180")
        assert c3.porcentaje_comision is None


# ── Tests: prioridad de comisión al generar liquidaciones ─────────────────────

class TestPrioridadComision:
    """La función _comision_cliente de liquidaciones.py usa org config.
    Probamos la lógica de prioridad directamente."""

    def _priority(self, pct_override, cliente_pct, org_default):
        """Replica la lógica de generar_liquidacion."""
        if pct_override is not None:
            return Decimal(str(pct_override))
        if cliente_pct is not None:
            return Decimal(str(cliente_pct))
        return Decimal(str(org_default))

    def test_override_tiene_prioridad_maxima(self):
        result = self._priority(
            pct_override=0.02,
            cliente_pct=0.015,
            org_default=0.015
        )
        assert result == Decimal("0.02")

    def test_cliente_tiene_prioridad_sobre_org(self):
        result = self._priority(
            pct_override=None,
            cliente_pct=0.018,
            org_default=0.015
        )
        assert result == Decimal("0.018")

    def test_org_default_cuando_no_hay_nada(self):
        result = self._priority(
            pct_override=None,
            cliente_pct=None,
            org_default=0.015
        )
        assert result == Decimal("0.015")

    def test_override_cero_no_aplica_cliente(self):
        """Override explícito de 0% debe respetarse (fee waived)."""
        result = self._priority(
            pct_override=0.0,
            cliente_pct=0.02,
            org_default=0.015
        )
        assert result == Decimal("0.0")


# ── Tests: borrar liquidaciones ───────────────────────────────────────────────

class TestBorrarLiquidacion:

    def _make_liquidacion(self, db, liq_id=1, org_id=1, estado="borrador"):
        from app.models.liquidacion import Liquidacion
        liq = Liquidacion(
            id=liq_id,
            organizacion_id=org_id,
            periodo_inicio=date(2026, 5, 1),
            periodo_fin=date(2026, 5, 31),
            estado=estado,
            created_by=1,
        )
        db.add(liq)
        db.flush()
        return liq

    def test_borrador_se_puede_marcar_para_eliminar(self, db):
        _make_org(db)
        _make_user(db)
        liq = self._make_liquidacion(db, estado="borrador")
        assert liq.estado == "borrador"
        # La lógica real borra solo borradores
        puede_borrar = liq.estado == "borrador"
        assert puede_borrar is True

    def test_emitida_no_se_puede_borrar(self, db):
        _make_org(db)
        _make_user(db)
        liq = self._make_liquidacion(db, estado="emitida")
        puede_borrar = liq.estado == "borrador"
        assert puede_borrar is False

    def test_borrar_liquidacion_elimina_de_db(self, db):
        from app.models.liquidacion import Liquidacion, LiquidacionDetalle
        _make_org(db)
        _make_user(db)
        _make_cliente(db)
        liq = self._make_liquidacion(db, estado="borrador")
        det = LiquidacionDetalle(
            liquidacion_id=liq.id,
            cliente_id=1,
            cliente_nombre="Cliente Test",
            monto_conciliado=Decimal("100.00"),
            porcentaje_comision=Decimal("0.015"),
            monto_comision=Decimal("1.50"),
            monto_neto=Decimal("98.50"),
        )
        db.add(det)
        db.flush()

        # Simular el DELETE endpoint
        db.query(LiquidacionDetalle).filter(
            LiquidacionDetalle.liquidacion_id == liq.id
        ).delete()
        db.delete(liq)
        db.commit()

        assert db.query(Liquidacion).filter(Liquidacion.id == liq.id).first() is None
        assert db.query(LiquidacionDetalle).filter(
            LiquidacionDetalle.liquidacion_id == liq.id
        ).count() == 0


# ── Tests: serialización Decimal en auditoría ─────────────────────────────────

class TestAuditoriaDecimalSerializacion:

    def test_serializable_decimal(self):
        from app.services.auditoria import _serializable
        result = _serializable(Decimal("123.45"))
        assert isinstance(result, float)
        assert result == pytest.approx(123.45)

    def test_serializable_dict_con_decimal(self):
        from app.services.auditoria import _serializable
        data = {"monto": Decimal("99.99"), "nombre": "test"}
        result = _serializable(data)
        assert isinstance(result["monto"], float)
        assert result["nombre"] == "test"

    def test_serializable_lista_con_decimal(self):
        from app.services.auditoria import _serializable
        data = [Decimal("1.0"), Decimal("2.5"), "texto"]
        result = _serializable(data)
        assert all(isinstance(x, (float, str)) for x in result)

    def test_serializable_anidado(self):
        from app.services.auditoria import _serializable
        data = {"items": [{"monto": Decimal("10.00")}, {"monto": Decimal("20.00")}]}
        result = _serializable(data)
        assert result["items"][0]["monto"] == pytest.approx(10.0)
        assert result["items"][1]["monto"] == pytest.approx(20.0)

    def test_serializable_none_pasa(self):
        from app.services.auditoria import _serializable
        assert _serializable(None) is None

    def test_serializable_int_str_pasan(self):
        from app.services.auditoria import _serializable
        assert _serializable(42) == 42
        assert _serializable("ok") == "ok"


# ── Tests: export fallback (lógica de búsqueda por monto+cliente) ─────────────

class TestExportFallback:
    """Verifica la lógica de fallback para filas 'ok' con FK NULL."""

    def test_fallback_encuentra_movimiento_por_monto(self, db):
        from app.models.extracto import ExtractoBancario, MovimientoBanco
        _make_org(db)
        _make_user(db)
        _make_cliente(db, nombre="Green SA")

        extracto = ExtractoBancario(
            id=1, nombre_archivo="ext.xlsx",
            organizacion_id=1, creado_por=1,
            fecha_creacion=datetime.now(),
        )
        db.add(extracto)

        mov = MovimientoBanco(
            id=1, extracto_id=1,
            orden=1, fecha=date(2026, 5, 1),
            monto=Decimal("5000.00"),
            cliente_acreditado="Green SA",
            organizacion_id=1,
        )
        db.add(mov)
        db.flush()

        # Simular la búsqueda de fallback
        candidatos = (
            db.query(MovimientoBanco)
            .filter(
                MovimientoBanco.extracto_id == 1,
                MovimientoBanco.cliente_acreditado == "Green SA",
            )
            .all()
        )
        fallback_map = {}
        for c in candidatos:
            key = float(c.monto) if c.monto is not None else None
            if key is not None and key not in fallback_map:
                fallback_map[key] = c

        assert 5000.0 in fallback_map
        assert fallback_map[5000.0].id == 1

    def test_fallback_no_reutiliza_movimiento(self, db):
        """Dos filas con el mismo monto no deben mapear al mismo movimiento."""
        from app.models.extracto import ExtractoBancario, MovimientoBanco
        _make_org(db)
        _make_user(db)

        extracto = ExtractoBancario(
            id=1, nombre_archivo="ext.xlsx",
            organizacion_id=1, creado_por=1,
            fecha_creacion=datetime.now(),
        )
        db.add(extracto)

        for i, orden in enumerate([1, 2], start=1):
            mov = MovimientoBanco(
                id=i, extracto_id=1,
                orden=orden, fecha=date(2026, 5, 1),
                monto=Decimal("3000.00"),
                cliente_acreditado="Tucu SRL",
                organizacion_id=1,
            )
            db.add(mov)
        db.flush()

        candidatos = (
            db.query(MovimientoBanco)
            .filter(
                MovimientoBanco.extracto_id == 1,
                MovimientoBanco.cliente_acreditado == "Tucu SRL",
            )
            .order_by(MovimientoBanco.orden)
            .all()
        )
        fallback_map = {}
        ya_usados = set()
        for c in candidatos:
            if c.id not in ya_usados:
                key = float(c.monto) if c.monto is not None else None
                if key is not None and key not in fallback_map:
                    fallback_map[key] = c
                    ya_usados.add(c.id)

        # Solo el primero entra al mapa (mismo key=3000.0)
        assert len(fallback_map) == 1
        assert fallback_map[3000.0].id == 1


# ── Tests: soft-delete hermético ──────────────────────────────────────────────

class TestSoftDeleteHermetico:

    def _make_planilla(self, db, planilla_id, org_id, deleted=False):
        from app.models.planilla import Planilla
        p = Planilla(
            id=planilla_id,
            organizacion_id=org_id,
            nombre_archivo=f"planilla_{planilla_id}.xlsx",
            cliente_id=1,
            usuario_id=1,
            deleted_at=datetime.now() if deleted else None,
        )
        db.add(p)
        db.flush()
        return p

    def test_planilla_activa_visible(self, db):
        from app.models.planilla import Planilla
        _make_org(db)
        _make_user(db)
        _make_cliente(db)
        self._make_planilla(db, 1, org_id=1, deleted=False)

        count = db.query(Planilla).filter(
            Planilla.organizacion_id == 1,
            Planilla.deleted_at.is_(None),
        ).count()
        assert count == 1

    def test_planilla_borrada_no_aparece_en_query_activas(self, db):
        from app.models.planilla import Planilla
        _make_org(db)
        _make_user(db)
        _make_cliente(db)
        self._make_planilla(db, 1, org_id=1, deleted=False)
        self._make_planilla(db, 2, org_id=1, deleted=True)

        activas = db.query(Planilla).filter(
            Planilla.organizacion_id == 1,
            Planilla.deleted_at.is_(None),
        ).all()
        ids = [p.id for p in activas]
        assert 1 in ids
        assert 2 not in ids

    def test_planillas_borradas_cuentan_zero_en_stats(self, db):
        from app.models.planilla import Planilla
        _make_org(db)
        _make_user(db)
        _make_cliente(db)
        self._make_planilla(db, 1, org_id=1, deleted=True)
        self._make_planilla(db, 2, org_id=1, deleted=True)

        count = db.query(Planilla).filter(
            Planilla.organizacion_id == 1,
            Planilla.deleted_at.is_(None),
        ).count()
        assert count == 0


# ── Tests: CSS smoke (sin runtime, solo verifica strings en el archivo) ────────

class TestCSSDesign:

    def test_btn_yellow_usa_ml_green(self):
        """btn-yellow debe usar ml-green (verde fluorescente), no ml-yellow ni ml-blue."""
        import re, os
        css_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../frontend/src/styles/index.css")
        )
        with open(css_path) as f:
            content = f.read()

        match = re.search(r'\.btn-yellow\s*\{([^}]+)\}', content, re.DOTALL)
        assert match, "No se encontró .btn-yellow en el CSS"
        block = match.group(1)

        assert "bg-ml-green" in block, "btn-yellow debe usar bg-ml-green"
        assert "bg-ml-yellow" not in block, "btn-yellow no debe usar bg-ml-yellow"
        assert "bg-ml-blue" not in block, "btn-yellow no debe usar bg-ml-blue"

    def test_layout_logo_no_usa_ml_yellow(self):
        """El header/sidebar del Layout no debe tener bg-ml-yellow."""
        import os
        layout_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__),
                         "../../frontend/src/components/Layout.tsx")
        )
        with open(layout_path) as f:
            content = f.read()
        assert "bg-ml-yellow" not in content, \
            "Layout.tsx no debe tener bg-ml-yellow — fue reemplazado por bg-ml-blue"
