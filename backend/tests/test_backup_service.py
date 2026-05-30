"""Tests del servicio de backup.

Verifica que el export contenga TODAS las tablas críticas y que el JSON
sea serializable (sin tipos raros tipo datetime sin convertir).
"""

import json
import pytest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.organizacion import Organizacion
from app.models.user import User
from app.models.cliente import Cliente
from app.models.extracto import ExtractoBancario, MovimientoBanco
from app.models.planilla import Planilla, PlanillaRow
from app.models.cheque import Cheque
from app.models.egreso import Egreso
from app.models.contabilidad import PlanCuenta, ReglaContable
from app.services.backup_service import export_org_backup, BACKUP_VERSION


ORG_ID = 1


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    org = Organizacion(id=ORG_ID, nombre="Test SA", plan="pro", activo=True)
    session.add(org)
    session.commit()

    # Sembrar algo de cada tabla crítica
    u = User(id=1, email="test@x.com", full_name="Test",
             hashed_password="SECRET_QUE_NO_DEBE_APARECER",
             role="admin", is_active=True, organizacion_id=ORG_ID)
    session.add(u)

    c = Cliente(id=1, nombre="Green", organizacion_id=ORG_ID)
    session.add(c)
    session.flush()

    ext = ExtractoBancario(id=1, nombre_archivo="ext.xlsx", fingerprint="abc",
                           organizacion_id=ORG_ID, creado_por=1)
    session.add(ext)
    session.flush()
    session.add(MovimientoBanco(extracto_id=1, monto=1000.0, titular="X",
                                organizacion_id=ORG_ID, fecha=date(2026, 5, 23)))

    p = Planilla(id=1, cliente_id=1, extracto_id=1, usuario_id=1,
                 nombre_archivo="p.xlsx", organizacion_id=ORG_ID)
    session.add(p)
    session.flush()
    session.add(PlanillaRow(planilla_id=1, monto=1000.0, status="ok",
                            organizacion_id=ORG_ID))

    session.add(Cheque(organizacion_id=ORG_ID, monto=5000.0, estado="pendiente",
                       foto_comprobante="base64-fake-foto"))
    session.add(Egreso(organizacion_id=ORG_ID, tipo="pago_cliente", forma_pago="banco", monto=1000.0))
    session.add(Egreso(organizacion_id=ORG_ID, tipo="gasto", concepto="luz", forma_pago="banco", monto=500.0))

    session.add(PlanCuenta(codigo="1-0-0-0", nombre="Activo", tipo="activo",
                           nivel=1, organizacion_id=ORG_ID))
    session.commit()

    yield session
    session.close()


def test_backup_contiene_metadatos(db):
    backup = export_org_backup(db, ORG_ID)
    assert backup["backup_version"] == BACKUP_VERSION
    assert "exportado_at" in backup
    assert backup["organizacion"]["id"] == ORG_ID
    assert backup["organizacion"]["nombre"] == "Test SA"


def test_backup_contiene_todas_las_tablas_criticas(db):
    backup = export_org_backup(db, ORG_ID)
    tablas_esperadas = [
        "usuarios", "clientes", "extractos", "planillas",
        "cheques", "egresos", "categorias_egreso",
        "arqueos_diarios", "liquidaciones", "cierres_periodo",
        "plan_cuentas", "reglas_contables", "asientos",
        "patrones_aprendidos", "auditoria",
    ]
    for tabla in tablas_esperadas:
        assert tabla in backup, f"Falta '{tabla}' en el backup"


def test_backup_NUNCA_incluye_passwords(db):
    """Crítico: el backup no debe contener contraseñas hasheadas ni en claro."""
    backup = export_org_backup(db, ORG_ID)
    for u in backup["usuarios"]:
        assert "hashed_password" not in u, "El backup no debe incluir hashed_password"
        assert "password" not in u
    # Búsqueda paranoica en el JSON completo
    payload = json.dumps(backup, default=str)
    assert "SECRET_QUE_NO_DEBE_APARECER" not in payload


def test_backup_es_json_serializable(db):
    """Garantía: el backup se puede serializar a JSON sin errores."""
    backup = export_org_backup(db, ORG_ID)
    # Debe poder serializarse sin tipos exóticos
    payload = json.dumps(backup, default=str)
    # Y deserializar de vuelta sin perder estructura
    deserialized = json.loads(payload)
    assert deserialized["organizacion"]["nombre"] == "Test SA"


def test_backup_incluye_extracto_con_movimientos_anidados(db):
    backup = export_org_backup(db, ORG_ID)
    assert len(backup["extractos"]) == 1
    assert len(backup["extractos"][0]["movimientos"]) == 1
    assert backup["extractos"][0]["movimientos"][0]["monto"] == 1000.0


def test_backup_incluye_planilla_con_rows_anidados(db):
    backup = export_org_backup(db, ORG_ID)
    assert len(backup["planillas"]) == 1
    assert len(backup["planillas"][0]["rows"]) == 1
    assert backup["planillas"][0]["rows"][0]["status"] == "ok"


def test_backup_incluye_fotos_de_cheques(db):
    """Las fotos en base64 son parte del registro — deben estar en el backup."""
    backup = export_org_backup(db, ORG_ID)
    assert len(backup["cheques"]) == 1
    assert backup["cheques"][0]["foto_comprobante"] == "base64-fake-foto"


def test_backup_resumen_cuenta_correctamente(db):
    backup = export_org_backup(db, ORG_ID)
    r = backup["resumen"]
    assert r["usuarios"] == 1
    assert r["clientes"] == 1
    assert r["extractos"] == 1
    assert r["movimientos_total"] == 1
    assert r["planillas"] == 1
    assert r["filas_planilla_total"] == 1
    assert r["cheques"] == 1
    assert r["egresos"] == 2
    assert r["plan_cuentas"] == 1


def test_backup_org_inexistente_lanza_error(db):
    with pytest.raises(ValueError, match="no encontrada"):
        export_org_backup(db, 9999)


def test_backup_no_mezcla_datos_de_otras_orgs(db):
    """Si hay otra org con datos, el backup de la org 1 NO debe incluirlos."""
    other = Organizacion(id=2, nombre="Otra SA", plan="pro", activo=True)
    db.add(other)
    db.add(Cliente(nombre="ClienteDeOtraOrg", organizacion_id=2))
    db.commit()

    backup = export_org_backup(db, ORG_ID)
    nombres = [c["nombre"] for c in backup["clientes"]]
    assert "ClienteDeOtraOrg" not in nombres
