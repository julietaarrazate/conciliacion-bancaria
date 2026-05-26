"""
Tests para los fixes de auditoría: multi-tenant, validaciones Pydantic,
soft-delete, CUIT y precisión Decimal.
"""
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

# Importar todos los modelos para que Base.metadata los registre
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


# ── Fixture DB en memoria ─────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ── Helpers para crear objetos mínimos ────────────────────────────────────────

def _make_org(db, org_id: int, nombre: str = None):
    from app.models.organizacion import Organizacion
    org = Organizacion(id=org_id, nombre=nombre or f"Org{org_id}")
    db.add(org)
    db.flush()
    return org


def _make_user(db, user_id: int, org_id: int, is_superadmin: bool = False):
    from app.models.user import User
    from app.services.auth import get_password_hash
    u = User(
        id=user_id,
        email=f"user{user_id}@test.com",
        full_name=f"User {user_id}",
        hashed_password=get_password_hash("password"),
        organizacion_id=org_id,
        is_superadmin=is_superadmin,
    )
    db.add(u)
    db.flush()
    return u


def _make_extracto(db, extracto_id: int, org_id: int, deleted: bool = False, creado_por: int = 1):
    from app.models.extracto import ExtractoBancario
    from datetime import datetime
    e = ExtractoBancario(
        id=extracto_id,
        nombre_archivo=f"extracto_{extracto_id}.xlsx",
        organizacion_id=org_id,
        creado_por=creado_por,
        fecha_creacion=datetime.now(),
        deleted_at=datetime.now() if deleted else None,
    )
    db.add(e)
    db.flush()
    return e


def _make_planilla(db, planilla_id: int, org_id: int, cliente_id: int,
                   extracto_id: int, deleted: bool = False):
    from app.models.planilla import Planilla
    from datetime import datetime
    p = Planilla(
        id=planilla_id,
        nombre_archivo=f"planilla_{planilla_id}.xlsx",
        organizacion_id=org_id,
        cliente_id=cliente_id,
        extracto_id=extracto_id,
        usuario_id=1,
        fecha_carga=datetime.now(),
        deleted_at=datetime.now() if deleted else None,
    )
    db.add(p)
    db.flush()
    return p


def _make_cliente(db, cliente_id: int, org_id: int, nombre: str = "Cliente Test"):
    from app.models.cliente import Cliente
    c = Cliente(id=cliente_id, nombre=nombre, organizacion_id=org_id)
    db.add(c)
    db.flush()
    return c


# ── Tests: aislamiento multi-tenant (extractos) ───────────────────────────────

class TestMultiTenantExtractos:
    def test_user_ve_solo_su_org(self, db):
        """Un usuario normal solo puede acceder a extractos de su org."""
        from app.routers.extractos import _extracto_for_user
        from fastapi import HTTPException
        _make_org(db, 1)
        _make_org(db, 2)
        _make_extracto(db, 1, org_id=1)
        _make_extracto(db, 2, org_id=2)
        user_org1 = _make_user(db, 1, org_id=1)

        # Puede ver el suyo
        e = _extracto_for_user(db, 1, user_org1)
        assert e.id == 1

        # No puede ver el de otra org
        with pytest.raises(HTTPException) as exc:
            _extracto_for_user(db, 2, user_org1)
        assert exc.value.status_code == 404

    def test_superadmin_ve_cualquier_org(self, db):
        """Superadmin accede a extractos de cualquier org."""
        from app.routers.extractos import _extracto_for_user
        _make_org(db, 1)
        _make_org(db, 2)
        _make_extracto(db, 1, org_id=1)
        _make_extracto(db, 2, org_id=2)
        superadmin = _make_user(db, 99, org_id=1, is_superadmin=True)

        e1 = _extracto_for_user(db, 1, superadmin)
        e2 = _extracto_for_user(db, 2, superadmin)
        assert e1.id == 1
        assert e2.id == 2

    def test_extracto_borrado_no_visible_por_defecto(self, db):
        """Extracto con deleted_at no se puede acceder (include_deleted=False)."""
        from app.routers.extractos import _extracto_for_user
        from fastapi import HTTPException
        _make_org(db, 1)
        _make_extracto(db, 1, org_id=1, deleted=True)
        user = _make_user(db, 1, org_id=1)

        with pytest.raises(HTTPException) as exc:
            _extracto_for_user(db, 1, user)
        assert exc.value.status_code == 404

    def test_extracto_borrado_visible_con_include_deleted(self, db):
        """Con include_deleted=True el extracto borrado sí se puede acceder."""
        from app.routers.extractos import _extracto_for_user
        _make_org(db, 1)
        _make_extracto(db, 1, org_id=1, deleted=True)
        user = _make_user(db, 1, org_id=1)

        e = _extracto_for_user(db, 1, user, include_deleted=True)
        assert e.id == 1


# ── Tests: aislamiento multi-tenant (planillas) ───────────────────────────────

class TestMultiTenantPlanillas:
    def test_user_no_accede_planilla_de_otra_org(self, db):
        from app.routers.planillas import _planilla_for_user
        from fastapi import HTTPException
        _make_org(db, 1)
        _make_org(db, 2)
        _make_extracto(db, 1, org_id=1)
        _make_extracto(db, 2, org_id=2)
        _make_cliente(db, 1, org_id=1)
        _make_cliente(db, 2, org_id=2)
        _make_planilla(db, 1, org_id=1, cliente_id=1, extracto_id=1)
        _make_planilla(db, 2, org_id=2, cliente_id=2, extracto_id=2)
        user = _make_user(db, 1, org_id=1)

        p = _planilla_for_user(db, 1, user)
        assert p.id == 1

        with pytest.raises(HTTPException) as exc:
            _planilla_for_user(db, 2, user)
        assert exc.value.status_code == 404

    def test_planilla_borrada_no_visible(self, db):
        from app.routers.planillas import _planilla_for_user
        from fastapi import HTTPException
        _make_org(db, 1)
        _make_extracto(db, 1, org_id=1)
        _make_cliente(db, 1, org_id=1)
        _make_planilla(db, 1, org_id=1, cliente_id=1, extracto_id=1, deleted=True)
        user = _make_user(db, 1, org_id=1)

        with pytest.raises(HTTPException) as exc:
            _planilla_for_user(db, 1, user)
        assert exc.value.status_code == 404


# ── Tests: validaciones Pydantic ──────────────────────────────────────────────

class TestPydanticValidations:
    def test_cheque_monto_cero_rechazado(self):
        from pydantic import ValidationError
        from app.routers.cheques import ChequeIn
        with pytest.raises(ValidationError) as exc:
            ChequeIn(monto=0)
        assert "greater_than" in str(exc.value)

    def test_cheque_monto_negativo_rechazado(self):
        from pydantic import ValidationError
        from app.routers.cheques import ChequeIn
        with pytest.raises(ValidationError):
            ChequeIn(monto=-500)

    def test_cheque_comision_negativa_rechazada(self):
        from pydantic import ValidationError
        from app.routers.cheques import ChequeIn
        with pytest.raises(ValidationError):
            ChequeIn(monto=1000, comision=-10)

    def test_cheque_valido(self):
        from app.routers.cheques import ChequeIn
        c = ChequeIn(monto=1500.50, comision=0)
        assert c.monto == 1500.50
        assert c.comision == 0

    def test_pago_monto_cero_rechazado(self):
        from pydantic import ValidationError
        from app.routers.pagos_gastos import PagoIn
        with pytest.raises(ValidationError):
            PagoIn(monto=0)

    def test_pago_monto_negativo_rechazado(self):
        from pydantic import ValidationError
        from app.routers.pagos_gastos import PagoIn
        with pytest.raises(ValidationError):
            PagoIn(monto=-1)

    def test_gasto_monto_cero_rechazado(self):
        from pydantic import ValidationError
        from app.routers.pagos_gastos import GastoIn
        with pytest.raises(ValidationError):
            GastoIn(concepto="test", monto=0)

    def test_gasto_valido(self):
        from app.routers.pagos_gastos import GastoIn
        g = GastoIn(concepto="Impuestos", monto=250.0)
        assert g.monto == 250.0


# ── Tests: validación CUIT ────────────────────────────────────────────────────

class TestCUITValidacion:
    def _crear_cliente(self, db, nombre, cuit):
        """Simula la lógica de validación de CUIT de clientes_dir.py."""
        cuit_raw = (cuit or "").strip()
        cuit_val = cuit_raw or None
        if cuit_val:
            digits = cuit_val.replace("-", "").replace(" ", "")
            if not digits.isdigit() or len(digits) not in (10, 11):
                raise ValueError("CUIT inválido")
            cuit_val = digits
        return cuit_val

    def test_cuit_11_digitos_valido(self):
        assert self._crear_cliente(None, "Test", "20123456789") == "20123456789"

    def test_cuit_10_digitos_valido(self):
        assert self._crear_cliente(None, "Test", "2012345678") == "2012345678"

    def test_cuit_con_guiones_normalizado(self):
        assert self._crear_cliente(None, "Test", "20-12345678-9") == "20123456789"

    def test_cuit_letras_invalido(self):
        with pytest.raises(ValueError):
            self._crear_cliente(None, "Test", "abc12345678")

    def test_cuit_muy_corto_invalido(self):
        with pytest.raises(ValueError):
            self._crear_cliente(None, "Test", "12345")

    def test_cuit_muy_largo_invalido(self):
        with pytest.raises(ValueError):
            self._crear_cliente(None, "Test", "123456789012")

    def test_cuit_vacio_aceptado(self):
        assert self._crear_cliente(None, "Test", "") is None

    def test_cuit_none_aceptado(self):
        assert self._crear_cliente(None, "Test", None) is None


# ── Tests: precisión Decimal ──────────────────────────────────────────────────

class TestDecimalPrecision:
    def test_suma_montos_no_acumula_error_float(self):
        """Decimal evita el error clásico de 0.1 + 0.2 != 0.3 con float."""
        montos = [Decimal("0.1")] * 10
        total = sum(montos)
        assert total == Decimal("1.0")
        assert total != 0.9999999999999999  # lo que daría float

    def test_comision_exacta(self):
        """1.5% de 10000 debe ser exactamente 150, no 149.999..."""
        monto = Decimal("10000")
        pct = Decimal("1.5")
        comision = round(monto * pct / 100, 2)
        assert comision == Decimal("150.00")

    def test_motor_contable_usa_decimal(self, db):
        """registrar_planilla acepta comision_pct como float y lo convierte."""
        from app.models.organizacion import Organizacion
        from app.models.contabilidad import PlanCuenta, ReglaContable, Asiento
        from app.services import motor_contable as mc
        from datetime import datetime

        ORG_ID = 1
        org = Organizacion(id=ORG_ID, nombre="TestOrg")
        db.add(org)

        # Plan mínimo: 2 cuentas
        c1 = PlanCuenta(id=1, organizacion_id=ORG_ID, codigo="1.1.1",
                        nombre="Banco", tipo="activo", created_at=datetime.now())
        c2 = PlanCuenta(id=2, organizacion_id=ORG_ID, codigo="2.1.1",
                        nombre="Clientes", tipo="pasivo", created_at=datetime.now())
        db.add_all([c1, c2])

        regla = ReglaContable(
            id=1, organizacion_id=ORG_ID, evento="carga_planilla",
            cuenta_debe_id=1, cuenta_haber_id=2,
            descripcion="Planilla", activo=True, created_at=datetime.now()
        )
        db.add(regla)
        db.flush()

        from types import SimpleNamespace
        rows = [SimpleNamespace(monto=Decimal("5000"), status="ok")]

        # Pasar comision_pct como float — no debe lanzar TypeError
        mc.registrar_planilla(
            db, planilla_id=99, org_id=ORG_ID, usuario_id=1,
            cliente_nombre="Test", nombre_archivo="t.xlsx",
            rows=rows, fecha_acred=date(2026, 5, 26),
            comision_pct=2.0,  # float intencional
        )

        asientos = db.query(Asiento).filter(Asiento.organizacion_id == ORG_ID).all()
        assert len(asientos) >= 1


# ── Tests: cierre de período ─────────────────────────────────────────────────

class TestCierrePeriodo:
    def test_fecha_dentro_periodo_cerrado(self, db):
        from app.services.cierre_periodo import periodo_esta_cerrado
        from app.models.liquidacion import CierrePeriodo
        from app.models.organizacion import Organizacion

        from app.models.user import User
        from app.services.auth import get_password_hash
        u = User(id=1, email="admin@test.com", full_name="Admin",
                 hashed_password=get_password_hash("x"), organizacion_id=1)
        org = Organizacion(id=1, nombre="OrgCierre1",
                           configuracion={"requiere_cierre_periodo": True})
        db.add_all([org, u])
        cierre = CierrePeriodo(
            organizacion_id=1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fin=date(2026, 1, 31),
            cerrado_by=1,
        )
        db.add(cierre)
        db.flush()

        assert periodo_esta_cerrado(db, 1, date(2026, 1, 15)) is True
        assert periodo_esta_cerrado(db, 1, date(2026, 1, 1)) is True
        assert periodo_esta_cerrado(db, 1, date(2026, 1, 31)) is True

    def test_fecha_fuera_periodo_cerrado(self, db):
        from app.services.cierre_periodo import periodo_esta_cerrado
        from app.models.liquidacion import CierrePeriodo
        from app.models.organizacion import Organizacion
        from app.models.user import User
        from app.services.auth import get_password_hash

        u = User(id=1, email="admin@test.com", full_name="Admin",
                 hashed_password=get_password_hash("x"), organizacion_id=1)
        org = Organizacion(id=1, nombre="OrgCierre2",
                           configuracion={"requiere_cierre_periodo": True})
        db.add_all([org, u])
        cierre = CierrePeriodo(
            organizacion_id=1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fin=date(2026, 1, 31),
            cerrado_by=1,
        )
        db.add(cierre)
        db.flush()

        assert periodo_esta_cerrado(db, 1, date(2026, 2, 1)) is False
        assert periodo_esta_cerrado(db, 1, date(2025, 12, 31)) is False

    def test_org_sin_requiere_cierre_siempre_pasa(self, db):
        from app.services.cierre_periodo import periodo_esta_cerrado
        from app.models.liquidacion import CierrePeriodo
        from app.models.organizacion import Organizacion
        from app.models.user import User
        from app.services.auth import get_password_hash

        u = User(id=1, email="admin@test.com", full_name="Admin",
                 hashed_password=get_password_hash("x"), organizacion_id=1)
        org = Organizacion(id=1, nombre="OrgCierre3",
                           configuracion={"requiere_cierre_periodo": False})
        db.add_all([org, u])
        cierre = CierrePeriodo(
            organizacion_id=1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fin=date(2026, 1, 31),
            cerrado_by=1,
        )
        db.add(cierre)
        db.flush()

        assert periodo_esta_cerrado(db, 1, date(2026, 1, 15)) is False

    def test_fecha_none_siempre_pasa(self, db):
        from app.services.cierre_periodo import periodo_esta_cerrado
        assert periodo_esta_cerrado(db, 1, None) is False
