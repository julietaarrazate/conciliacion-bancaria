"""
Tests para los endpoints nuevos de Pagos (v3.12):
  - PATCH /pagos/{id}  — editar egreso (monto, fecha, beneficiario, etc.)
  - DELETE /pagos/{id} — eliminar egreso (verificar que el decorador existe)

Se usan llamadas directas a las funciones del router (sin TestClient),
pasando la sesión SQLite en memoria y un User mock con los permisos requeridos.
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

from app.models.egreso import Egreso
from app.models.organizacion import Organizacion
from app.models.user import User
from fastapi import HTTPException


# ── Fixture DB SQLite en memoria ─────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Org y usuario base
    org = Organizacion(id=1, nombre="TestOrg")
    session.add(org)
    from app.services.auth import get_password_hash
    user = User(
        id=1, email="admin@test.com", full_name="Admin",
        hashed_password=get_password_hash("pw"),
        organizacion_id=1, is_superadmin=False,
    )
    session.add(user)
    session.commit()
    yield session
    session.close()


def _mock_user(org_id=1, is_superadmin=False):
    u = MagicMock(spec=User)
    u.id = 1
    u.organizacion_id = org_id
    u.is_superadmin = is_superadmin
    return u


def _fake_request():
    from starlette.requests import Request
    from app.main import app as fastapi_app
    return Request(scope={
        "type": "http", "headers": [], "client": ("test", 0),
        "path": "/pagos/test", "method": "DELETE", "app": fastapi_app,
    })


def _crear_egreso(db, egreso_id=1, org_id=1, monto=1000, tipo="proveedor",
                  forma_pago="banco", beneficiario="Proveedor Test",
                  fecha=None):
    e = Egreso(
        id=egreso_id,
        organizacion_id=org_id,
        tipo=tipo,
        forma_pago=forma_pago,
        monto=Decimal(str(monto)),
        fecha=fecha or date(2026, 6, 1),
        beneficiario=beneficiario,
        compartido_whatsapp=False,
    )
    db.add(e)
    db.commit()
    return e


# ── Tests PATCH /pagos/{id} ───────────────────────────────────────────────────

class TestEditarEgreso:

    def test_editar_monto_actualiza_egreso(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=10, monto=1000)

        result = editar_egreso(
            egreso_id=10,
            payload={"monto": 1500},
            db=db,
            current_user=_mock_user(),
        )
        assert result["ok"] is True
        e = db.query(Egreso).filter(Egreso.id == 10).first()
        assert float(e.monto) == 1500.0

    def test_editar_fecha_actualiza_egreso(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=11, fecha=date(2026, 6, 1))

        editar_egreso(
            egreso_id=11,
            payload={"fecha": "2026-05-15"},
            db=db,
            current_user=_mock_user(),
        )
        e = db.query(Egreso).filter(Egreso.id == 11).first()
        assert e.fecha == date(2026, 5, 15)

    def test_editar_beneficiario(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=12, beneficiario="Viejo Nombre")

        editar_egreso(
            egreso_id=12,
            payload={"beneficiario": "Nuevo Nombre"},
            db=db,
            current_user=_mock_user(),
        )
        e = db.query(Egreso).filter(Egreso.id == 12).first()
        assert e.beneficiario == "Nuevo Nombre"

    def test_editar_beneficiario_vacio_lo_nulifica(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=13, beneficiario="Alguien")

        editar_egreso(
            egreso_id=13,
            payload={"beneficiario": ""},
            db=db,
            current_user=_mock_user(),
        )
        e = db.query(Egreso).filter(Egreso.id == 13).first()
        assert e.beneficiario is None

    def test_editar_monto_cero_devuelve_400(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=14, monto=500)

        with pytest.raises(HTTPException) as exc_info:
            editar_egreso(
                egreso_id=14,
                payload={"monto": 0},
                db=db,
                current_user=_mock_user(),
            )
        assert exc_info.value.status_code == 400

    def test_editar_monto_negativo_devuelve_400(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=15, monto=500)

        with pytest.raises(HTTPException) as exc_info:
            editar_egreso(
                egreso_id=15,
                payload={"monto": -100},
                db=db,
                current_user=_mock_user(),
            )
        assert exc_info.value.status_code == 400

    def test_editar_fecha_invalida_devuelve_400(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=16)

        with pytest.raises(HTTPException) as exc_info:
            editar_egreso(
                egreso_id=16,
                payload={"fecha": "no-es-fecha"},
                db=db,
                current_user=_mock_user(),
            )
        assert exc_info.value.status_code == 400

    def test_editar_egreso_inexistente_devuelve_404(self, db):
        from app.routers.pagos import editar_egreso

        with pytest.raises(HTTPException) as exc_info:
            editar_egreso(
                egreso_id=9999,
                payload={"monto": 500},
                db=db,
                current_user=_mock_user(),
            )
        assert exc_info.value.status_code == 404

    def test_editar_egreso_de_otra_org_devuelve_404(self, db):
        from app.routers.pagos import editar_egreso
        # Egreso en org 2
        from app.models.organizacion import Organizacion
        db.add(Organizacion(id=2, nombre="OtraOrg"))
        db.commit()
        _crear_egreso(db, egreso_id=17, org_id=2)

        # Usuario de org 1 intenta editarlo
        with pytest.raises(HTTPException) as exc_info:
            editar_egreso(
                egreso_id=17,
                payload={"monto": 999},
                db=db,
                current_user=_mock_user(org_id=1),
            )
        assert exc_info.value.status_code == 404

    def test_superadmin_puede_editar_cualquier_org(self, db):
        from app.routers.pagos import editar_egreso
        from app.models.organizacion import Organizacion
        db.add(Organizacion(id=3, nombre="OtraOrg3"))
        db.commit()
        _crear_egreso(db, egreso_id=18, org_id=3, monto=200)

        result = editar_egreso(
            egreso_id=18,
            payload={"monto": 300},
            db=db,
            current_user=_mock_user(org_id=1, is_superadmin=True),
        )
        assert result["ok"] is True
        e = db.query(Egreso).filter(Egreso.id == 18).first()
        assert float(e.monto) == 300.0

    def test_editar_multiples_campos_a_la_vez(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=19, monto=100, beneficiario="Viejo",
                      fecha=date(2026, 1, 1))

        editar_egreso(
            egreso_id=19,
            payload={
                "monto": 250,
                "fecha": "2026-06-01",
                "beneficiario": "Nuevo",
                "concepto": "Compra materiales",
                "referencia": "OP-001",
            },
            db=db,
            current_user=_mock_user(),
        )
        e = db.query(Egreso).filter(Egreso.id == 19).first()
        assert float(e.monto) == 250.0
        assert e.fecha == date(2026, 6, 1)
        assert e.beneficiario == "Nuevo"
        assert e.concepto == "Compra materiales"
        assert e.referencia == "OP-001"

    def test_editar_foto_base64_actualiza_comprobante(self, db):
        """Regresión ago 2026: el modal de editar pago no tenía forma de
        adjuntar/reemplazar el comprobante — el PATCH ya lo soporta."""
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=33)
        foto = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

        editar_egreso(
            egreso_id=33,
            payload={"foto_base64": foto},
            db=db,
            current_user=_mock_user(),
        )
        e = db.query(Egreso).filter(Egreso.id == 33).first()
        assert e.foto_comprobante == foto  # sin S3 configurado, guarda el data URL tal cual

    def test_editar_foto_base64_null_quita_comprobante(self, db):
        from app.routers.pagos import editar_egreso
        e = _crear_egreso(db, egreso_id=34)
        e.foto_comprobante = "data:image/png;base64,algo"
        db.commit()

        editar_egreso(
            egreso_id=34,
            payload={"foto_base64": None},
            db=db,
            current_user=_mock_user(),
        )
        db.refresh(e)
        assert e.foto_comprobante is None

    def test_editar_forma_pago_banco_a_efectivo_engancha_arqueo(self, db):
        """Regresión ago 2026: se cargó 'banco' por error siendo 'efectivo' —
        debe poder corregirse y quedar enganchado al arqueo del día."""
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=30, forma_pago="banco", fecha=date(2026, 6, 1))

        editar_egreso(
            egreso_id=30,
            payload={"forma_pago": "efectivo"},
            db=db,
            current_user=_mock_user(),
        )
        e = db.query(Egreso).filter(Egreso.id == 30).first()
        assert e.forma_pago == "efectivo"
        assert e.arqueo_id is not None

        from app.models.caja import ArqueoDiario
        arqueo = db.query(ArqueoDiario).filter(ArqueoDiario.id == e.arqueo_id).first()
        assert arqueo is not None
        assert arqueo.fecha == date(2026, 6, 1)

    def test_editar_forma_pago_efectivo_a_banco_desengancha_y_repone(self, db):
        from app.routers.pagos import editar_egreso
        from app.models.caja import ArqueoDiario, denominaciones_vacias

        arqueo = ArqueoDiario(
            organizacion_id=1, fecha=date(2026, 6, 1),
            saldo_inicial=0, pesos_agregados=0, ingresos=0,
            denominaciones=denominaciones_vacias(), creado_por=1,
        )
        db.add(arqueo)
        db.commit()
        e = _crear_egreso(db, egreso_id=31, forma_pago="efectivo", fecha=date(2026, 6, 1))
        e.arqueo_id = arqueo.id
        e.denominaciones_usadas = {"1000": 5}
        dens = dict(arqueo.denominaciones)
        dens["1000"] = int(dens.get("1000", 0)) - 5
        arqueo.denominaciones = dens
        db.commit()

        editar_egreso(
            egreso_id=31,
            payload={"forma_pago": "banco"},
            db=db,
            current_user=_mock_user(),
        )
        db.refresh(e)
        db.refresh(arqueo)
        assert e.forma_pago == "banco"
        assert e.arqueo_id is None
        assert e.denominaciones_usadas is None
        # Las 5 unidades de $1000 vuelven al arqueo
        assert arqueo.denominaciones["1000"] == 0

    def test_editar_forma_pago_invalida_devuelve_400(self, db):
        from app.routers.pagos import editar_egreso
        _crear_egreso(db, egreso_id=32, forma_pago="banco")

        with pytest.raises(HTTPException) as exc_info:
            editar_egreso(
                egreso_id=32,
                payload={"forma_pago": "cheque"},
                db=db,
                current_user=_mock_user(),
            )
        assert exc_info.value.status_code == 400


# ── Tests DELETE /pagos/{id} ──────────────────────────────────────────────────

class TestEliminarEgreso:

    def test_eliminar_egreso_existente(self, db):
        from app.routers.pagos import eliminar_egreso
        _crear_egreso(db, egreso_id=20, monto=500)

        result = eliminar_egreso(
            request=_fake_request(),
            egreso_id=20,
            db=db,
            current_user=_mock_user(),
        )
        assert result["ok"] is True
        assert db.query(Egreso).filter(Egreso.id == 20).first() is None

    def test_eliminar_egreso_inexistente_devuelve_404(self, db):
        from app.routers.pagos import eliminar_egreso

        with pytest.raises(HTTPException) as exc_info:
            eliminar_egreso(
                request=_fake_request(),
                egreso_id=9999,
                db=db,
                current_user=_mock_user(),
            )
        assert exc_info.value.status_code == 404

    def test_eliminar_egreso_otra_org_devuelve_404(self, db):
        from app.routers.pagos import eliminar_egreso
        from app.models.organizacion import Organizacion
        db.add(Organizacion(id=4, nombre="OtraOrg4"))
        db.commit()
        _crear_egreso(db, egreso_id=21, org_id=4)

        with pytest.raises(HTTPException) as exc_info:
            eliminar_egreso(
                request=_fake_request(),
                egreso_id=21,
                db=db,
                current_user=_mock_user(org_id=1),
            )
        assert exc_info.value.status_code == 404

    def test_endpoint_delete_esta_registrado(self):
        """Verifica que @router.delete('/{egreso_id}') existe en el router."""
        from app.routers.pagos import router
        rutas_delete = [
            r for r in router.routes
            if hasattr(r, 'methods') and 'DELETE' in r.methods
        ]
        assert len(rutas_delete) >= 1, (
            "No se encontró ninguna ruta DELETE en pagos router — "
            "el decorador @router.delete faltaba y no fue corregido"
        )
        paths_delete = [r.path for r in rutas_delete]
        assert any("egreso_id" in p or "{" in p for p in paths_delete), (
            f"Ruta DELETE encontrada pero sin path variable: {paths_delete}"
        )
