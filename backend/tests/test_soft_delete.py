"""Tests del comportamiento soft delete en extractos y planillas.

Verifica:
- Soft delete marca deleted_at pero conserva el registro
- Restaurar quita deleted_at y vuelve a estar disponible
- Las queries que filtran deleted_at IS NULL no ven los borrados
- Los registros borrados quedan disponibles para inspección/restore
"""

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


ORG_ID = 1


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    session.add(Organizacion(id=ORG_ID, nombre="Test SA", plan="pro", activo=True))
    session.add(User(id=1, email="x@x.com", full_name="X",
                     hashed_password="h", role="admin", is_active=True, organizacion_id=ORG_ID))
    session.add(Cliente(id=1, nombre="Green", organizacion_id=ORG_ID))
    session.commit()

    ext = ExtractoBancario(id=1, nombre_archivo="e.xlsx", fingerprint="abc",
                           organizacion_id=ORG_ID, creado_por=1)
    session.add(ext)
    session.flush()
    session.add(MovimientoBanco(extracto_id=1, monto=1000.0, organizacion_id=ORG_ID))

    p = Planilla(id=1, cliente_id=1, extracto_id=1, usuario_id=1,
                 nombre_archivo="p.xlsx", organizacion_id=ORG_ID)
    session.add(p)
    session.flush()
    session.add(PlanillaRow(planilla_id=1, monto=1000.0, status="ok",
                            organizacion_id=ORG_ID))
    session.commit()

    yield session
    session.close()


# ─── Extracto ────────────────────────────────────────────────────────────────

def test_extracto_soft_delete_marca_deleted_at(db):
    ext = db.query(ExtractoBancario).first()
    assert ext.deleted_at is None

    ext.deleted_at = datetime.utcnow()
    db.commit()

    refetch = db.query(ExtractoBancario).filter(ExtractoBancario.id == 1).first()
    assert refetch is not None
    assert refetch.deleted_at is not None


def test_extracto_borrado_no_aparece_en_query_filtrada(db):
    ext = db.query(ExtractoBancario).first()
    ext.deleted_at = datetime.utcnow()
    db.commit()

    activos = db.query(ExtractoBancario).filter(ExtractoBancario.deleted_at.is_(None)).all()
    assert len(activos) == 0

    borrados = db.query(ExtractoBancario).filter(ExtractoBancario.deleted_at.isnot(None)).all()
    assert len(borrados) == 1


def test_extracto_restaurar_quita_deleted_at(db):
    ext = db.query(ExtractoBancario).first()
    ext.deleted_at = datetime.utcnow()
    db.commit()

    ext.deleted_at = None
    db.commit()

    activos = db.query(ExtractoBancario).filter(ExtractoBancario.deleted_at.is_(None)).all()
    assert len(activos) == 1


def test_extracto_borrado_conserva_movimientos(db):
    """Soft delete NO debe borrar los movimientos asociados — quedan listos para restore."""
    ext = db.query(ExtractoBancario).first()
    movs_antes = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == 1).count()
    assert movs_antes == 1

    ext.deleted_at = datetime.utcnow()
    db.commit()

    movs_despues = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == 1).count()
    assert movs_despues == 1, "los movimientos deben quedar intactos"


# ─── Planilla ────────────────────────────────────────────────────────────────

def test_planilla_soft_delete_marca_deleted_at(db):
    p = db.query(Planilla).first()
    assert p.deleted_at is None

    p.deleted_at = datetime.utcnow()
    db.commit()

    refetch = db.query(Planilla).filter(Planilla.id == 1).first()
    assert refetch is not None
    assert refetch.deleted_at is not None


def test_planilla_borrada_conserva_rows(db):
    p = db.query(Planilla).first()
    rows_antes = db.query(PlanillaRow).filter(PlanillaRow.planilla_id == 1).count()
    assert rows_antes == 1

    p.deleted_at = datetime.utcnow()
    db.commit()

    rows_despues = db.query(PlanillaRow).filter(PlanillaRow.planilla_id == 1).count()
    assert rows_despues == 1


def test_planilla_restaurar_vuelve_a_estar_disponible(db):
    p = db.query(Planilla).first()
    p.deleted_at = datetime.utcnow()
    db.commit()

    p.deleted_at = None
    db.commit()

    activas = db.query(Planilla).filter(Planilla.deleted_at.is_(None)).all()
    assert len(activas) == 1


# ─── Comportamiento conjunto ────────────────────────────────────────────────

def test_borrar_y_restaurar_no_pierde_datos(db):
    """Ciclo completo: crear → borrar → restaurar → verificar todo igual."""
    ext = db.query(ExtractoBancario).first()
    p = db.query(Planilla).first()

    # Snapshot del estado original
    movs_original = db.query(MovimientoBanco).count()
    rows_original = db.query(PlanillaRow).count()

    # Soft delete
    ext.deleted_at = datetime.utcnow()
    p.deleted_at = datetime.utcnow()
    db.commit()

    # Restaurar
    ext.deleted_at = None
    p.deleted_at = None
    db.commit()

    # Verificar
    assert db.query(MovimientoBanco).count() == movs_original
    assert db.query(PlanillaRow).count() == rows_original
    assert db.query(ExtractoBancario).filter(ExtractoBancario.deleted_at.is_(None)).count() == 1
    assert db.query(Planilla).filter(Planilla.deleted_at.is_(None)).count() == 1
