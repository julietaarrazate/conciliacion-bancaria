import json
import logging
import threading
from contextlib import asynccontextmanager
from decimal import Decimal
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse as _BaseJSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import get_settings
from app.logging_config import setup_logging
from app.database import engine, Base
from app.routers import auth, extractos, planillas, me, admin, auditoria, historial, clientes_dir
from app.routers import organizaciones
from app.routers import liquidaciones
from app.routers import caja
from app.routers import contabilidad
from app.routers import cheques
from app.routers import pagos_gastos
from app.routers import papelera
from app.routers import backup_admin
from app.routers import analisis
from app.routers import search as search_router
from app.routers import public_router
from app.routers import push_router
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog, PasswordResetToken  # noqa: F401
from app.models.push_subscription import PushSubscription  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401
from app.models.organizacion import Organizacion

# ── Decimal → float encoder para SQLAlchemy Numeric columns ──────────────────
class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class JSONResponse(_BaseJSONResponse):
    """JSONResponse que serializa decimal.Decimal como float."""
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            cls=_DecimalEncoder,
            ensure_ascii=False,
        ).encode("utf-8")


settings = get_settings()
setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)

# Rate limiter — protección brute force
limiter = Limiter(key_func=get_remote_address)


def _run_alembic():
    """Aplica migraciones pendientes. Si la DB nunca tuvo Alembic, la sella como baseline."""
    try:
        import os
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import text

        # Path absoluto: backend/alembic.ini (relativo a este archivo: backend/app/main.py)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini = os.path.join(base_dir, "alembic.ini")
        logger.debug("alembic config: %s", alembic_ini)

        alembic_cfg = Config(alembic_ini)

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')"
            ))
            ya_tiene_alembic = result.scalar()

        if not ya_tiene_alembic:
            command.stamp(alembic_cfg, "head")
            logger.info("DB sellada como baseline v001")
        else:
            command.upgrade(alembic_cfg, "head")
            logger.info("migraciones Alembic aplicadas")
    except Exception as ex:
        logger.warning("Alembic error: %s", ex)


def _init_db():
    """Crea tablas, migraciones y seed en background — no bloquea el arranque."""
    import hashlib, os
    from app.database import SessionLocal
    from app.models.extracto import ExtractoBancario as Extracto

    # 1. Crear tablas (incluye Organizacion)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas OK")
    except Exception as e:
        logger.error("Error creando tablas: %s", e)
        return

    # 1.5 Alembic — versionar la DB
    _run_alembic()

    # 2. Índices de performance (CREATE INDEX IF NOT EXISTS — idempotente)
    indexes = [
        # MovimientoBanco: consultas más frecuentes
        "CREATE INDEX IF NOT EXISTS idx_mov_extracto_fecha ON movimientos_banco(extracto_id, fecha DESC)",
        "CREATE INDEX IF NOT EXISTS idx_mov_cliente ON movimientos_banco(cliente_acreditado) WHERE cliente_acreditado IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_mov_monto ON movimientos_banco(monto)",
        "CREATE INDEX IF NOT EXISTS idx_mov_org ON movimientos_banco(organizacion_id)",
        # Planillas
        "CREATE INDEX IF NOT EXISTS idx_planillas_org_fecha ON planillas(organizacion_id, fecha_carga DESC)",
        "CREATE INDEX IF NOT EXISTS idx_planillas_cliente ON planillas(cliente_id)",
        # PlanillaRows
        "CREATE INDEX IF NOT EXISTS idx_rows_planilla ON planilla_rows(planilla_id)",
        "CREATE INDEX IF NOT EXISTS idx_rows_status ON planilla_rows(status)",
        # AuditoriaLog
        "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON auditoria(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_accion ON auditoria(accion)",
        # Clientes
        "CREATE INDEX IF NOT EXISTS idx_clientes_org ON clientes(organizacion_id, nombre)",
    ]
    for sql in indexes:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception as ex:
            logger.debug("Index ya existe (ignorado): %s", ex)

    # 3. Migraciones de columnas — todas idempotentes (IF NOT EXISTS no disponible en todos los Postgres,
    #    se usa try/except para ignorar "column already exists")
    migrations = [
        "ALTER TABLE extractos_bancarios ADD COLUMN fingerprint VARCHAR",
        "ALTER TABLE movimientos_banco ADD COLUMN source VARCHAR DEFAULT 'extracto'",
        # Multi-tenant
        "ALTER TABLE users ADD COLUMN organizacion_id INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE",
        "ALTER TABLE clientes ADD COLUMN organizacion_id INTEGER DEFAULT 1",
        "ALTER TABLE extractos_bancarios ADD COLUMN organizacion_id INTEGER DEFAULT 1",
        "ALTER TABLE movimientos_banco ADD COLUMN organizacion_id INTEGER DEFAULT 1",
        "ALTER TABLE planillas ADD COLUMN organizacion_id INTEGER DEFAULT 1",
        "ALTER TABLE planilla_rows ADD COLUMN organizacion_id INTEGER DEFAULT 1",
        "ALTER TABLE planilla_rows ADD COLUMN referencia VARCHAR",
        "ALTER TABLE planilla_rows ADD COLUMN monto_acreditado FLOAT",
        "ALTER TABLE planilla_rows ADD COLUMN comentario_revision TEXT",
        "ALTER TABLE movimientos_banco ADD COLUMN um_lote INTEGER DEFAULT NULL",
        "ALTER TABLE planillas ALTER COLUMN extracto_id DROP NOT NULL",
        "ALTER TABLE planilla_rows ADD COLUMN fecha_acred DATE",
        "ALTER TABLE extractos_bancarios ADD COLUMN banco VARCHAR DEFAULT 'Banco Macro'",
        "ALTER TABLE cheques ADD COLUMN foto_comprobante TEXT",
    ]
    for sql in migrations:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception:
            pass  # columna ya existe

    # 2.5. Normalizar campo "mes" de movimientos: dejar solo el numero (1-12).
    # Casos viejos: "Mayo 2026", "May 2026", "5", "05/2026", etc.
    try:
        with engine.connect() as conn:
            # Postgres: extraer mes desde fecha cuando este disponible
            conn.execute(text("""
                UPDATE movimientos_banco
                SET mes = EXTRACT(MONTH FROM fecha)::text
                WHERE fecha IS NOT NULL
                  AND (mes IS NULL OR mes !~ '^[0-9]{1,2}$' OR LENGTH(mes) > 2)
            """))
            conn.commit()
        logger.info("mes normalizado a numero (1-12)")
    except Exception as ex:
        logger.warning("Error normalizando mes: %s", ex)

    # 3. Backfill organizacion_id=1 en tablas existentes (org principal)
    backfills = [
        "UPDATE users SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE clientes SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE extractos_bancarios SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE movimientos_banco SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE planillas SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE planilla_rows SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE extractos_bancarios SET banco='Banco Macro' WHERE banco IS NULL",
        # Propagar tipo a subcuentas: 1-x=activo, 2-x=pasivo, 3-x=resultado
        "UPDATE plan_cuentas SET tipo='activo'    WHERE codigo LIKE '1%' AND tipo IS NULL",
        "UPDATE plan_cuentas SET tipo='pasivo'    WHERE codigo LIKE '2%' AND tipo IS NULL",
        "UPDATE plan_cuentas SET tipo='resultado' WHERE codigo LIKE '3%' AND tipo IS NULL",
    ]
    for sql in backfills:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception as ex:
            logger.warning("Backfill error: %s", ex)

    # 4. Backfill fingerprints
    try:
        db = SessionLocal()
        sin_fp = db.query(Extracto).filter(Extracto.fingerprint.is_(None)).all()
        for e in sin_fp:
            movs = sorted(e.movimientos, key=lambda m: m.id)
            total = len(movs)
            if total == 0:
                e.fingerprint = "empty"
                continue
            raw = f"{total}|{movs[0].orden or 0}|{movs[-1].orden or 0}|{round(sum(m.monto for m in movs), 2)}"
            e.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if sin_fp:
            db.commit()
            logger.info("fingerprint calculado para %d extracto(s)", len(sin_fp))
        db.close()
    except Exception as ex:
        logger.warning("Error calculando fingerprints: %s", ex)

    # 5. Seed Organizacion principal (id=1)
    try:
        from app.database import SessionLocal as SL
        from app.models.organizacion import Organizacion as Org, CONFIG_DEFAULT
        db = SL()
        org_principal = db.query(Org).filter(Org.id == 1).first()
        if not org_principal:
            config_org = {
                "match_rules": ["monto_cuit"],
                "tolerancia_monto": 0.01,
                "dias_tolerancia_fecha": 5,
                "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
                "requiere_cierre_periodo": False,
                "notificaciones_whatsapp": False,
                "exportar_formato_contador": "excel_actual"
            }
            db.add(Org(id=1, nombre="Organización A", plan="pro", configuracion=config_org, activo=True))
            db.commit()
            logger.info("Organización A creada (id=1)")
        db.close()
    except Exception as ex:
        logger.warning("Error seed org: %s", ex)

    # 6. Seed contabilidad (plan de cuentas + reglas)
    # Checks plan_cuentas and reglas_contables INDEPENDENTLY so a partial
    # seed from a previous failed deploy is always completed on the next boot.
    try:
        from app.database import SessionLocal as SL
        from app.models.contabilidad import PlanCuenta, ReglaContable

        PLAN = [
            # (codigo, nombre, tipo, parent_codigo, nivel)
            ("1-0-0-0", "Activo",               "activo",    None,      1),
            ("2-0-0-0", "Pasivo",               "pasivo",    None,      1),
            ("3-0-0-0", "Resultado",            "resultado", None,      1),
            ("1-1-0-0", "Activo Corriente",     "activo",   "1-0-0-0",  2),
            ("1-2-0-0", "Activo no corriente",  "activo",   "1-0-0-0",  2),
            ("2-1-0-0", "Pasivo Corriente",     "pasivo",   "2-0-0-0",  2),
            ("3-1-0-0", "Ingresos",             "resultado","3-0-0-0",  2),
            ("3-2-0-0", "Gastos",               "resultado","3-0-0-0",  2),
            ("1-1-1-0", "Disponibilidades",     "activo",   "1-1-0-0",  3),
            ("1-1-2-0", "Créditos",             "activo",   "1-1-0-0",  3),
            ("1-2-1-0", "Bienes de Uso",        "activo",   "1-2-0-0",  3),
            ("2-1-1-0", "Pasivo a Confirmar",   "pasivo",   "2-1-0-0",  3),
            ("2-1-2-0", "Cliente",              "pasivo",   "2-1-0-0",  3),
            ("3-1-1-0", "Comisiones",           "resultado","3-1-0-0",  3),
            ("3-1-2-0", "Operaciones de cambio","resultado","3-1-0-0",  3),
            ("3-2-1-0", "Impuesto déb y créd",  "resultado","3-2-0-0",  3),
            ("3-2-2-0", "Gastos bancarios",     "resultado","3-2-0-0",  3),
            ("1-1-1-1", "Caja chica",           "activo",   "1-1-1-0",  4),
            ("1-1-1-2", "Efectivo",             "activo",   "1-1-1-0",  4),
            ("1-1-1-3", "Banco",                "activo",   "1-1-1-0",  4),
            ("1-1-1-3-1", "Banco Macro",        "activo",   "1-1-1-3",  5),
            ("2-1-1-1", "No identificado",      "pasivo",   "2-1-1-0",  4),
            ("2-1-2-1", "Green",                "pasivo",   "2-1-2-0",  4),
            ("2-1-2-2", "Tucu",                 "pasivo",   "2-1-2-0",  4),
            ("2-1-2-3", "Alojando",             "pasivo",   "2-1-2-0",  4),
        ]
        REGLAS = [
            # (evento, descripcion, debe_codigo, haber_codigo)
            ("carga_extracto",          "Carga extracto bancario",          "1-1-1-3", "2-1-0-0"),
            ("carga_planilla",          "Acreditación planilla cliente",    "2-1-0-0", "2-1-2-0"),
            ("carga_planilla_comision", "Comisión sobre planilla",          "2-1-0-0", "3-1-1-0"),
            ("carga_efectivo",          "Carga cobro en efectivo",          "1-1-1-2", "1-1-1-3"),
            ("carga_cheque",            "Carga cheque cliente",             "1-1-2-0", "2-1-2-0"),
            ("carga_cheque_comision",   "Comisión sobre cheque",            "1-1-2-0", "3-1-1-0"),
            ("acred_rechazo_banco",     "Acred/rechazo cheque — banco",     "1-1-1-3", "1-1-2-0"),
            ("acred_rechazo_pasivo",    "Acred/rechazo cheque — cliente",   "2-1-2-0", "1-1-2-0"),
            ("pago_cliente_banco",      "Pago cliente por banco",           "2-1-2-0", "1-1-1-3"),
            ("pago_cliente_efectivo",   "Pago cliente en efectivo",         "2-1-2-0", "1-1-1-2"),
            ("asig_gasto_banco",        "Gasto pagado por banco",           "3-2-0-0", "1-1-1-3"),
            ("asig_gasto_efectivo",     "Gasto pagado en efectivo",         "3-2-0-0", "1-1-1-2"),
        ]

        db = SL()
        n_cuentas = db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == 1).count()
        n_reglas  = db.query(ReglaContable).filter(ReglaContable.organizacion_id == 1).count()

        # Seed plan de cuentas if missing
        if n_cuentas == 0:
            code_to_id = {}
            for codigo, nombre, tipo, parent_codigo, nivel in PLAN:
                parent_id = code_to_id.get(parent_codigo) if parent_codigo else None
                c = PlanCuenta(
                    codigo=codigo, nombre=nombre, tipo=tipo,
                    parent_id=parent_id, nivel=nivel,
                    activo=True, organizacion_id=1
                )
                db.add(c)
                db.flush()
                code_to_id[codigo] = c.id
            db.commit()
            n_cuentas = len(PLAN)
            logger.info("Plan de cuentas sembrado (%d cuentas)", n_cuentas)
        else:
            # Build code→id map from existing rows (needed for reglas seed below)
            code_to_id = {c.codigo: c.id for c in db.query(PlanCuenta).filter(PlanCuenta.organizacion_id == 1).all()}

        # Patch: add new accounts to existing seeds (runs every boot, idempotent)
        PLAN_PATCH = [
            ("1-1-1-3-1", "Banco Macro", "activo", "1-1-1-3", 5),
        ]
        patch_added = 0
        for codigo, nombre, tipo, parent_codigo, nivel in PLAN_PATCH:
            if codigo not in code_to_id:
                parent_id = code_to_id.get(parent_codigo)
                c = PlanCuenta(
                    codigo=codigo, nombre=nombre, tipo=tipo,
                    parent_id=parent_id, nivel=nivel,
                    activo=True, organizacion_id=1
                )
                db.add(c)
                db.flush()
                code_to_id[codigo] = c.id
                patch_added += 1
        if patch_added:
            db.commit()
            logger.info("Plan patch: %d cuentas nuevas agregadas", patch_added)

        # Seed reglas if missing (independent of cuentas seed)
        if n_reglas == 0 and code_to_id:
            for evento, descripcion, debe_codigo, haber_codigo in REGLAS:
                if debe_codigo not in code_to_id or haber_codigo not in code_to_id:
                    logger.warning("Cuenta %s o %s no encontrada para regla %s", debe_codigo, haber_codigo, evento)
                    continue
                db.add(ReglaContable(
                    evento=evento, descripcion=descripcion,
                    cuenta_debe_id=code_to_id[debe_codigo],
                    cuenta_haber_id=code_to_id[haber_codigo],
                    activo=True, organizacion_id=1
                ))
            db.commit()
            logger.info("Reglas contables sembradas (%d reglas)", len(REGLAS))

        logger.info("Contabilidad: %d cuentas, %d reglas", n_cuentas, db.query(ReglaContable).filter(ReglaContable.organizacion_id==1).count())
        db.close()
    except Exception as ex:
        logger.warning("Error seed contabilidad: %s", ex)

    # 7. Backfill contabilidad — genera asientos para extractos/planillas existentes
    try:
        from app.database import SessionLocal as SL
        from app.models.extracto import ExtractoBancario as Ext
        from app.models.planilla import Planilla as Plan
        from app.models.contabilidad import Asiento as A
        from app.services.motor_contable import registrar_extracto, registrar_planilla
        from datetime import date as _date

        db = SL()

        # IDs que ya tienen asiento (para no duplicar)
        ids_ext  = {r[0] for r in db.query(A.referencia_id).filter(A.modulo == "extracto").all()}
        ids_plan = {r[0] for r in db.query(A.referencia_id).filter(A.modulo == "planilla").all()}

        # Backfill extractos
        n_ext = 0
        for e in db.query(Ext).filter(Ext.organizacion_id == 1).all():
            if e.id not in ids_ext:
                registrar_extracto(
                    db=db, extracto_id=e.id,
                    org_id=e.organizacion_id or 1,
                    usuario_id=e.creado_por,
                    nombre_archivo=e.nombre_archivo or "",
                    movimientos=e.movimientos,
                )
                n_ext += 1

        # Backfill planillas
        n_plan = 0
        for p in db.query(Plan).filter(Plan.organizacion_id == 1).all():
            if p.id not in ids_plan:
                try:
                    fecha = p.fecha_carga.date() if p.fecha_carga else _date.today()
                except Exception:
                    fecha = _date.today()
                registrar_planilla(
                    db=db, planilla_id=p.id,
                    org_id=p.organizacion_id or 1,
                    usuario_id=p.usuario_id,
                    cliente_nombre=p.cliente.nombre if p.cliente else "",
                    nombre_archivo=p.nombre_archivo or "",
                    rows=p.rows,
                    fecha_acred=fecha,
                )
                n_plan += 1

        if n_ext or n_plan:
            logger.info("Backfill contabilidad: %d extracto(s), %d planilla(s)", n_ext, n_plan)
        else:
            logger.info("Backfill contabilidad: todo al dia")
        db.close()
    except Exception as ex:
        logger.warning("Error backfill contabilidad: %s", ex)

    # 8. Seed usuarios
    try:
        from app.database import SessionLocal as SL
        from app.models.user import User as U, RoleEnum
        from app.services.auth import get_password_hash
        db = SL()

        # Superadmin Julieta — password desde variable de entorno SUPERADMIN_PASSWORD
        julieta_email = "julietaarrazate@gmail.com"
        julieta_pwd = os.environ.get("SUPERADMIN_PASSWORD", "")
        if julieta_pwd:
            julieta = db.query(U).filter(U.email == julieta_email).first()
            if not julieta:
                db.add(U(
                    email=julieta_email,
                    full_name="Julieta Arrazate",
                    hashed_password=get_password_hash(julieta_pwd),
                    role=RoleEnum.ADMIN.value,
                    is_active=True,
                    is_superadmin=True,
                    organizacion_id=1
                ))
                logger.info("Superadmin %s creado", julieta_email)
            else:
                # Siempre actualizar password y flags desde el env var
                julieta.hashed_password = get_password_hash(julieta_pwd)
                julieta.is_superadmin = True
                julieta.is_active = True
                julieta.role = RoleEnum.ADMIN.value
                logger.info("Superadmin %s actualizado", julieta_email)
            db.commit()
        else:
            logger.warning("SUPERADMIN_PASSWORD no definida — superadmin no creado")

        # Usuarios demo — solo en entorno de desarrollo
        if settings.debug:
            seeds_demo = [
                ("admin@julieta.com", "admin123", "Administrador", RoleEnum.ADMIN, False),
            ]
            created = 0
            for email, pwd, name, role, superadmin in seeds_demo:
                if not db.query(U).filter(U.email == email).first():
                    db.add(U(
                        email=email,
                        full_name=name,
                        hashed_password=get_password_hash(pwd),
                        role=role.value,
                        is_active=True,
                        is_superadmin=superadmin,
                        organizacion_id=1
                    ))
                    created += 1
            if created:
                db.commit()
                logger.info("%d usuario(s) demo creado(s)", created)
        db.close()
    except Exception as ex:
        logger.warning("Error seed users: %s", ex)

    _fix_orden_extracto19()


def _fix_orden_extracto19():
    """Fix one-time: restaura los valores de orden del extracto 19 usando el
    mapping exacto del Excel del contador (Extracto_Macro_Mayo_19.5.xlsx).
    Solo corre si el max(orden) del extracto 19 != 17240 (ya fue arreglado)."""
    try:
        from app.database import SessionLocal as SL
        from app.models.extracto import MovimientoBanco
        from sqlalchemy import func
        db = SL()
        max_ord = db.query(func.max(MovimientoBanco.orden)).filter(
            MovimientoBanco.extracto_id == 19
        ).scalar()
        if max_ord == 17240:
            db.close()
            return  # ya esta bien
        ORDEN_MAP = {
    ("2026-05-19", 50000.0, 116767929.14): 17240,
    ("2026-05-19", 50000.0, 116717929.14): 17239,
    ("2026-05-19", 16800.0, 116667929.14): 17238,
    ("2026-05-19", 183381.81, 116651129.14): 17237,
    ("2026-05-19", 24727.0, 116467747.33): 17236,
    ("2026-05-19", 124275.16, 116443020.33): 17235,
    ("2026-05-19", 70860.26, 116318745.17): 17234,
    ("2026-05-19", 105000.0, 116247884.91): 17233,
    ("2026-05-19", 280515.23, 116142884.91): 17232,
    ("2026-05-19", 319932.33, 115862369.68): 17231,
    ("2026-05-19", 350048.82, 115542437.35): 17230,
    ("2026-05-19", 700000.0, 115192388.53): 17229,
    ("2026-05-19", 775935.56, 114492388.53): 17228,
    ("2026-05-19", 100000.0, 113716452.97): 17227,
    ("2026-05-19", 248692.0, 113616452.97): 17226,
    ("2026-05-18", -29365.12, 113367760.97): 17225,
    ("2026-05-18", -236148.13, 113397126.09): 17224,
    ("2026-05-18", -29.04, 113633274.22): 17223,
    ("2026-05-18", 37801.0, 113633303.26): 17222,
    ("2026-05-18", 84072.0, 113595502.26): 17221,
    ("2026-05-18", 233880.0, 113511430.26): 17220,
    ("2026-05-18", 50000.0, 113277550.26): 17219,
    ("2026-05-18", 50000.0, 113227550.26): 17218,
    ("2026-05-18", -121.0, 113177550.26): 17217,
    ("2026-05-18", -872277.15, 113177671.26): 17216,
    ("2026-05-18", 175469.38, 114049948.41): 17215,
    ("2026-05-18", 39900.0, 113874479.03): 17214,
    ("2026-05-18", 10000.0, 113834579.03): 17213,
    ("2026-05-18", 406411.0, 113824579.03): 17212,
    ("2026-05-18", 571293.47, 113418168.03): 17211,
    ("2026-05-18", 60000.0, 112846874.56): 17210,
    ("2026-05-18", 231270.07, 112786874.56): 17209,
    ("2026-05-18", 60000.0, 112555604.49): 17208,
    ("2026-05-18", -121.0, 112495604.49): 17207,
    ("2026-05-18", -2790825.83, 112495725.49): 17206,
    ("2026-05-18", 790000.0, 115286551.32): 17205,
    ("2026-05-18", 400000.0, 114496551.32): 17204,
    ("2026-05-18", 60000.0, 114096551.32): 17203,
    ("2026-05-18", 302793.0, 114036551.32): 17202,
    ("2026-05-18", 50000.0, 113733758.32): 17201,
    ("2026-05-18", 50000.0, 113683758.32): 17200,
    ("2026-05-18", 52500.0, 113633758.32): 17199,
    ("2026-05-18", -121.0, 113581258.32): 17198,
    ("2026-05-18", -525598.5, 113581379.32): 17197,
    ("2026-05-18", 700000.0, 114106977.82): 17196,
    ("2026-05-18", -55000.0, 113406977.82): 17195,
    ("2026-05-18", -121.0, 113461977.82): 17194,
    ("2026-05-18", -650000.0, 113462098.82): 17193,
    ("2026-05-18", 130000.0, 114112098.82): 17192,
    ("2026-05-18", 60000.0, 113982098.82): 17191,
    ("2026-05-18", 89857.17, 113922098.82): 17190,
    ("2026-05-18", 8000000.0, 113832241.65): 17189,
    ("2026-05-18", 120000.0, 105832241.65): 17188,
    ("2026-05-18", 100000.0, 105712241.65): 17187,
    ("2026-05-18", 28875.0, 105612241.65): 17186,
    ("2026-05-18", 86310.0, 105583366.65): 17185,
    ("2026-05-18", 137000.0, 105497056.65): 17184,
    ("2026-05-18", 30000.0, 105360056.65): 17183,
    ("2026-05-18", 50000.0, 105330056.65): 17182,
    ("2026-05-18", 50000.0, 105280056.65): 17181,
    ("2026-05-18", 134959.0, 105230056.65): 17180,
    ("2026-05-18", 200000.0, 105095097.65): 17179,
    ("2026-05-18", 523365.3, 104895097.65): 17178,
    ("2026-05-18", 95321.0, 104371732.35): 17177,
    ("2026-05-18", 81000.0, 104276411.35): 17176,
    ("2026-05-18", 221633.0, 104195411.35): 17175,
    ("2026-05-18", 59000.85, 103973778.35): 17174,
    ("2026-05-18", 220500.0, 103914777.5): 17173,
    ("2026-05-18", 439798.17, 103694277.5): 17172,
    ("2026-05-18", 227700.0, 103254479.33): 17171,
    ("2026-05-18", 4077.12, 103026779.33): 17170,
    ("2026-05-18", 259220.03, 103022702.21): 17169,
    ("2026-05-18", 88304.85, 102763482.18): 17168,
    ("2026-05-18", 333552.0, 102675177.33): 17167,
    ("2026-05-18", 230151.52, 102341625.33): 17166,
    ("2026-05-18", 30000.0, 102111473.81): 17165,
    ("2026-05-18", 79691.0, 102081473.81): 17164,
    ("2026-05-18", 414202.87, 102001782.81): 17163,
    ("2026-05-18", 50000.0, 101587579.94): 17162,
    ("2026-05-18", 110216.79, 101537579.94): 17161,
    ("2026-05-18", 107800.95, 101427363.15): 17160,
    ("2026-05-18", 50000.0, 101319562.2): 17159,
    ("2026-05-18", 140311.27, 101269562.2): 17158,
    ("2026-05-18", 437466.0, 101129250.93): 17157,
    ("2026-05-18", 180806.88, 100691784.93): 17156,
    ("2026-05-18", 606126.94, 100510978.05): 17155,
    ("2026-05-18", 62879.42, 99904851.11): 17154,
    ("2026-05-18", 184296.48, 99841971.69): 17153,
    ("2026-05-18", 128220.58, 99657675.21): 17152,
    ("2026-05-18", 266688.33, 99529454.63): 17151,
    ("2026-05-18", 99491.99, 99262766.3): 17150,
    ("2026-05-18", 91240.0, 99163274.31): 17149,
    ("2026-05-18", 111291.36, 99072034.31): 17148,
    ("2026-05-18", 1607795.02, 98960742.95): 17147,
    ("2026-05-18", 298915.06, 97352947.93): 17146,
    ("2026-05-18", 5578.55, 97054032.87): 17145,
    ("2026-05-18", 88400.0, 97048454.32): 17144,
    ("2026-05-18", 749198.32, 96960054.32): 17143,
    ("2026-05-18", 66000.0, 96210856.0): 17142,
    ("2026-05-18", 1572200.0, 96144856.0): 17141,
    ("2026-05-18", 110900.0, 94572656.0): 17140,
    ("2026-05-18", 597823.63, 94461756.0): 17139,
    ("2026-05-18", 369000.0, 93863932.37): 17138,
    ("2026-05-18", 557716.6, 93494932.37): 17137,
    ("2026-05-18", 222227.96, 92937215.77): 17136,
    ("2026-05-18", 575177.13, 92714987.81): 17135,
    ("2026-05-18", 288119.68, 92139810.68): 17134,
    ("2026-05-18", 1349835.08, 91851691.0): 17133,
    ("2026-05-18", 30000.0, 90501855.92): 17132,
    ("2026-05-18", 120000.0, 90471855.92): 17131,
    ("2026-05-18", 500000.0, 90351855.92): 17130,
    ("2026-05-18", 789000.0, 89851855.92): 17129,
    ("2026-05-18", 25000.0, 89062855.92): 17128,
    ("2026-05-18", 30000.0, 89037855.92): 17127,
    ("2026-05-18", 100000.0, 89007855.92): 17126,
    ("2026-05-18", 119327.0, 88907855.92): 17125,
    ("2026-05-18", 647478.0, 88788528.92): 17124,
    ("2026-05-18", 400000.0, 88141050.92): 17123,
    ("2026-05-18", 471239.1, 87741050.92): 17122,
    ("2026-05-18", 120000.0, 87269811.82): 17121,
    ("2026-05-18", 660000.0, 87149811.82): 17120,
    ("2026-05-18", 70200.0, 86489811.82): 17119,
    ("2026-05-18", 156800.0, 86419611.82): 17118,
    ("2026-05-18", 150000.0, 86262811.82): 17117,
    ("2026-05-18", 79500.0, 86112811.82): 17116,
    ("2026-05-18", 30000.0, 86033311.82): 17115,
    ("2026-05-18", 108000.0, 86003311.82): 17114,
    ("2026-05-18", 303645.96, 85895311.82): 17113,
    ("2026-05-18", 85000.0, 85591665.86): 17112,
    ("2026-05-18", 90000.0, 85506665.86): 17111,
    ("2026-05-18", 85000.0, 85416665.86): 17110,
    ("2026-05-18", 100000.0, 85331665.86): 17109,
    ("2026-05-18", 224000.0, 85231665.86): 17108,
    ("2026-05-18", 160261.58, 85007665.86): 17107,
    ("2026-05-18", 45000.0, 84847404.28): 17106,
    ("2026-05-18", 213320.64, 84802404.28): 17105,
    ("2026-05-18", 85000.0, 84589083.64): 17104,
    ("2026-05-18", 150000.0, 84504083.64): 17103,
    ("2026-05-18", 150000.0, 84354083.64): 17102,
    ("2026-05-18", 70000.0, 84204083.64): 17101,
    ("2026-05-18", 624081.0, 84134083.64): 17100,
    ("2026-05-18", 163500.0, 83510002.64): 17099,
    ("2026-05-18", 125000.0, 83346502.64): 17098,
    ("2026-05-18", 48500.0, 83221502.64): 17097,
    ("2026-05-18", 35595.0, 83173002.64): 17096,
    ("2026-05-18", 37327.0, 83137407.64): 17095,
    ("2026-05-18", 1000000.0, 83100080.64): 17094,
    ("2026-05-18", 68800.0, 82100080.64): 17093,
    ("2026-05-18", 34000.0, 82031280.64): 17092,
    ("2026-05-18", 44100.0, 81997280.64): 17091,
    ("2026-05-18", 71295.0, 81953180.64): 17090,
    ("2026-05-18", 18500.0, 81881885.64): 17089,
    ("2026-05-18", 33000.0, 81863385.64): 17088,
    ("2026-05-18", 294000.0, 81830385.64): 17087,
    ("2026-05-18", 708864.57, 81536385.64): 17086,
    ("2026-05-18", 100000.0, 80827521.07): 17085,
    ("2026-05-18", 32000.0, 80727521.07): 17084,
    ("2026-05-18", 137000.0, 80695521.07): 17083,
    ("2026-05-18", 50000.0, 80558521.07): 17082,
    ("2026-05-18", 621936.02, 80508521.07): 17081,
    ("2026-05-18", 26800.0, 79886585.05): 17080,
    ("2026-05-18", 17800.0, 79859785.05): 17079,
    ("2026-05-18", 486000.0, 79841985.05): 17078,
    ("2026-05-18", 109900.0, 79355985.05): 17077,
    ("2026-05-18", 56613.9, 79246085.05): 17076,
    ("2026-05-18", 20000.0, 79189471.15): 17075,
    ("2026-05-15", 548124.01, 79169471.15): 17074,
    ("2026-05-15", 141513.2, 79717595.16): 17073,
    ("2026-05-15", 125.84, 79859108.36): 17072,
    ("2026-05-15", 30000.0, 79859234.2): 17071,
    ("2026-05-15", 22500.0, 79829234.2): 17070,
    ("2026-05-15", 3109368.0, 79806734.2): 17069,
    ("2026-05-15", 60000.0, 76697366.2): 17068,
    ("2026-05-15", 20000.0, 76637366.2): 17067,
    ("2026-05-15", 150000.0, 76617366.2): 17066,
    ("2026-05-15", 314050.3, 76467366.2): 17065,
    ("2026-05-15", 165600.0, 76153315.9): 17064,
    ("2026-05-15", 287950.0, 75987715.9): 17063,
    ("2026-05-15", 2468498.12, 75699765.9): 17062,
    ("2026-05-15", 67000.0, 73231267.78): 17061,
    ("2026-05-15", 500000.0, 73164267.78): 17060,
    ("2026-05-15", 359310.0, 72664267.78): 17059,
    ("2026-05-15", 200000.0, 72304957.78): 17058,
    ("2026-05-15", 175000.0, 72104957.78): 17057,
    ("2026-05-15", 60000.0, 71929957.78): 17056,
    ("2026-05-15", 50000.0, 71869957.78): 17055,
    ("2026-05-15", 50000.0, 71819957.78): 17054,
    ("2026-05-15", 85000.0, 71769957.78): 17053,
    ("2026-05-15", 50000.0, 71684957.78): 17052,
    ("2026-05-15", 15000.0, 71634957.78): 17051,
    ("2026-05-15", 1896351.66, 71619957.78): 17050,
    ("2026-05-15", 121.0, 69723606.12): 17049,
    ("2026-05-15", 1200000.0, 69723727.12): 17048,
    ("2026-05-15", 121.0, 70923727.12): 17047,
    ("2026-05-15", 1200000.0, 70923848.12): 17046,
    ("2026-05-15", 121.0, 72123848.12): 17045,
    ("2026-05-15", 420000.0, 72123969.12): 17044,
    ("2026-05-15", 121.0, 72543969.12): 17043,
    ("2026-05-15", 1204609.88, 72544090.12): 17042,
    ("2026-05-15", 121.0, 73748700.0): 17041,
    ("2026-05-15", 1500000.0, 73748821.0): 17040,
    ("2026-05-15", 121.0, 75248821.0): 17039,
    ("2026-05-15", 500000.0, 75248942.0): 17038,
    ("2026-05-15", 126000.0, 75748942.0): 17037,
    ("2026-05-15", 50000.0, 75622942.0): 17036,
    ("2026-05-15", 50000.0, 75572942.0): 17035,
    ("2026-05-15", 222991.49, 75522942.0): 17034,
    ("2026-05-15", 50000.0, 75745933.49): 17033,
    ("2026-05-15", 121.0, 75695933.49): 17032,
    ("2026-05-15", 1000000.0, 75696054.49): 17031,
    ("2026-05-15", 40000.0, 76696054.49): 17030,
    ("2026-05-15", 80640.0, 76656054.49): 17029,
    ("2026-05-15", 121.0, 76736694.49): 17028,
    ("2026-05-15", 392415.0, 76736815.49): 17027,
    ("2026-05-15", 171674.2, 77129230.49): 17026,
    ("2026-05-15", 24000.0, 76957556.29): 17025,
    ("2026-05-15", 100000.0, 76933556.29): 17024,
    ("2026-05-15", 90000.0, 76833556.29): 17023,
    ("2026-05-15", 10720.92, 76743556.29): 17022,
    ("2026-05-15", 48000.0, 76732835.37): 17021,
    ("2026-05-15", 50000.0, 76684835.37): 17020,
    ("2026-05-15", 58000.0, 76634835.37): 17019,
    ("2026-05-15", 121.0, 76576835.37): 17018,
    ("2026-05-15", 980000.0, 76576956.37): 17017,
    ("2026-05-15", 281300.0, 77556956.37): 17016,
    ("2026-05-15", 180000.0, 77275656.37): 17015,
    ("2026-05-15", 300140.0, 77095656.37): 17014,
    ("2026-05-15", 160258.39, 76795516.37): 17013,
    ("2026-05-15", 121.0, 76635257.98): 17012,
    ("2026-05-15", 450000.0, 76635378.98): 17011,
    ("2026-05-15", 121.0, 77085378.98): 17010,
    ("2026-05-15", 1000000.0, 77085499.98): 17009,
    ("2026-05-15", 300000.0, 78085499.98): 17008,
    ("2026-05-15", 115000.0, 77785499.98): 17007,
    ("2026-05-15", 63000.0, 77670499.98): 17006,
    ("2026-05-15", 123511.0, 77607499.98): 17005,
    ("2026-05-15", 573528.0, 77483988.98): 17004,
    ("2026-05-15", 85071.67, 76910460.98): 17003,
    ("2026-05-15", 215292.88, 76825389.31): 17002,
    ("2026-05-15", 200670.0, 76610096.43): 17001,
    ("2026-05-15", 100000.0, 76409426.43): 17000,
    ("2026-05-15", 121.0, 76509426.43): 16999,
    ("2026-05-15", 45000000.0, 76509547.43): 16998,
    ("2026-05-15", 121.0, 121509547.43): 16997,
    ("2026-05-15", 35000000.0, 121509668.43): 16996,
    ("2026-05-15", 121.0, 156509668.43): 16995,
    ("2026-05-15", 556442.0, 156509789.43): 16994,
    ("2026-05-15", 142500.0, 157066231.43): 16993,
    ("2026-05-15", 162725.0, 157208731.43): 16992,
    ("2026-05-15", 1500000.0, 157046006.43): 16991,
    ("2026-05-15", 249700.0, 155546006.43): 16990,
    ("2026-05-15", 153000.0, 155795706.43): 16989,
    ("2026-05-15", 93449.6, 155948706.43): 16988,
    ("2026-05-15", 119702.46, 155855256.83): 16987,
    ("2026-05-15", 489736.45, 155735554.37): 16986,
    ("2026-05-15", 274086.24, 155245817.92): 16985,
    ("2026-05-15", 30000.0, 154971731.68): 16984,
    ("2026-05-15", 59000.0, 154941731.68): 16983,
    ("2026-05-15", 75002.1, 154882731.68): 16982,
    ("2026-05-15", 1634997.38, 154807729.58): 16981,
    ("2026-05-15", 64804.39, 153172732.2): 16980,
    ("2026-05-15", 72334.51, 153107927.81): 16979,
    ("2026-05-15", 564565.04, 153035593.3): 16978,
    ("2026-05-15", 667200.51, 152471028.26): 16977,
    ("2026-05-15", 110900.0, 151803827.75): 16976,
    ("2026-05-15", 114197.73, 151692927.75): 16975,
    ("2026-05-15", 148000.0, 151578730.02): 16974,
    ("2026-05-15", 478777.28, 151430730.02): 16973,
    ("2026-05-15", 75000.0, 150951952.74): 16972,
    ("2026-05-15", 271237.32, 150876952.74): 16971,
    ("2026-05-15", 96000.0, 150605715.42): 16970,
    ("2026-05-15", 118000.0, 150509715.42): 16969,
    ("2026-05-15", 20000.0, 150391715.42): 16968,
    ("2026-05-15", 109900.0, 150371715.42): 16967,
    ("2026-05-15", 43000.0, 150261815.42): 16966,
    ("2026-05-15", 191354.4, 150218815.42): 16965,
    ("2026-05-15", 120000.0, 150027461.02): 16964,
    ("2026-05-15", 196629.18, 149907461.02): 16963,
    ("2026-05-15", 209404.78, 149710831.84): 16962,
    ("2026-05-15", 195875.0, 149501427.06): 16961,
    ("2026-05-15", 38000.0, 149305552.06): 16960,
    ("2026-05-15", 169794.33, 149267552.06): 16959,
    ("2026-05-15", 131695.19, 149097757.73): 16958,
    ("2026-05-15", 80739.0, 148966062.54): 16957,
    ("2026-05-15", 151891.0, 148885323.54): 16956,
    ("2026-05-15", 563774.3, 148733432.54): 16955,
    ("2026-05-15", 132000.0, 148169658.24): 16954,
    ("2026-05-15", 359960.73, 148037658.24): 16953,
    ("2026-05-15", 50000.0, 147677697.51): 16952,
    ("2026-05-14", 19983.83, 147627697.51): 16951,
    ("2026-05-14", 124139.44, 147647681.34): 16950,
    ("2026-05-14", 38.72, 147771820.78): 16949,
    ("2026-05-14", 750660.0, 147771859.5): 16948,
    ("2026-05-14", 78000.0, 147021199.5): 16947,
    ("2026-05-14", 300000.0, 146943199.5): 16946,
    ("2026-05-14", 24900.0, 146643199.5): 16945,
    ("2026-05-14", 48000.0, 146618299.5): 16944,
    ("2026-05-14", 387344.59, 146570299.5): 16943,
    ("2026-05-14", 83013.0, 146182954.91): 16942,
    ("2026-05-14", 101637.58, 146099941.91): 16941,
    ("2026-05-14", 475933.5, 145998304.33): 16940,
    ("2026-05-14", 219360.8, 145522370.83): 16939,
    ("2026-05-14", 71300.0, 145303010.03): 16938,
    ("2026-05-14", 300000.0, 145231710.03): 16937,
    ("2026-05-14", 460929.39, 144931710.03): 16936,
    ("2026-05-14", 572724.0, 144470780.64): 16935,
    ("2026-05-14", 115378.64, 143898056.64): 16934,
    ("2026-05-14", 120000.0, 143782678.0): 16933,
    ("2026-05-14", 659000.0, 143662678.0): 16932,
    ("2026-05-14", 64400.0, 143003678.0): 16931,
    ("2026-05-14", 90000.0, 142939278.0): 16930,
    ("2026-05-14", 145700.0, 142849278.0): 16929,
    ("2026-05-14", 218911.0, 142703578.0): 16928,
    ("2026-05-14", 98643.6, 142484667.0): 16927,
    ("2026-05-14", 40000.0, 142386023.4): 16926,
    ("2026-05-14", 116755.0, 142346023.4): 16925,
    ("2026-05-14", 50715.0, 142229268.4): 16924,
    ("2026-05-14", 82700.0, 142178553.4): 16923,
    ("2026-05-14", 40000.0, 142095853.4): 16922,
    ("2026-05-14", 103050.01, 142055853.4): 16921,
    ("2026-05-14", 428261.85, 141952803.39): 16920,
    ("2026-05-14", 121.0, 141524541.54): 16919,
    ("2026-05-14", 329859.53, 141524662.54): 16918,
    ("2026-05-14", 25631.74, 141854522.07): 16917,
    ("2026-05-14", 110900.0, 141828890.33): 16916,
    ("2026-05-14", 40000.0, 141717990.33): 16915,
    ("2026-05-14", 109000.0, 141677990.33): 16914,
    ("2026-05-14", 315000.0, 141568990.33): 16913,
    ("2026-05-14", 121.0, 141253990.33): 16912,
    ("2026-05-14", 728750.0, 141254111.33): 16911,
    ("2026-05-14", 121.0, 141982861.33): 16910,
    ("2026-05-14", 460000.0, 141982982.33): 16909,
    ("2026-05-14", 121.0, 142442982.33): 16908,
    ("2026-05-14", 408000.0, 142443103.33): 16907,
    ("2026-05-14", 121.0, 142851103.33): 16906,
    ("2026-05-14", 898000.0, 142851224.33): 16905,
    ("2026-05-14", 121.0, 143749224.33): 16904,
    ("2026-05-14", 400000.0, 143749345.33): 16903,
    ("2026-05-14", 105299.04, 144149345.33): 16902,
    ("2026-05-14", 91862.36, 144254644.37): 16901,
    ("2026-05-14", 400000.0, 144162782.01): 16900,
    ("2026-05-14", 146888.0, 143762782.01): 16899,
    ("2026-05-14", 115079.4, 143615894.01): 16898,
    ("2026-05-14", 110168.81, 143500814.61): 16897,
    ("2026-05-14", 800000.0, 143390645.8): 16896,
    ("2026-05-14", 16800.0, 142590645.8): 16895,
    ("2026-05-14", 57700.0, 142573845.8): 16894,
    ("2026-05-14", 2845875.0, 142516145.8): 16893,
    ("2026-05-14", 87028.52, 139670270.8): 16892,
    ("2026-05-14", 107150.0, 139583242.28): 16891,
    ("2026-05-14", 334539.93, 139476092.28): 16890,
    ("2026-05-14", 332948.0, 139141552.35): 16889,
    ("2026-05-14", 186188.0, 138808604.35): 16888,
    ("2026-05-14", 175859.84, 138622416.35): 16887,
    ("2026-05-14", 193194.08, 138446556.51): 16886,
    ("2026-05-14", 825552.0, 138253362.43): 16885,
    ("2026-05-14", 1185250.0, 137427810.43): 16884,
    ("2026-05-14", 354100.0, 136242560.43): 16883,
    ("2026-05-14", 162344.97, 135888460.43): 16882,
    ("2026-05-14", 515427.7, 135726115.46): 16881,
    ("2026-05-14", 40000.0, 135210687.76): 16880,
    ("2026-05-14", 40000.0, 135170687.76): 16879,
    ("2026-05-14", 272927.94, 135130687.76): 16878,
    ("2026-05-14", 199553.01, 134857759.82): 16877,
    ("2026-05-14", 146840.2, 134658206.81): 16876,
    ("2026-05-14", 131767.0, 134511366.61): 16875,
    ("2026-05-14", 25500.0, 134379599.61): 16874,
    ("2026-05-14", 403051.86, 134354099.61): 16873,
    ("2026-05-14", 181979.28, 133951047.75): 16872,
    ("2026-05-14", 736984.4, 133769068.47): 16871,
    ("2026-05-14", 163372.83, 133032084.07): 16870,
    ("2026-05-14", 724303.55, 132868711.24): 16869,
    ("2026-05-14", 585433.89, 132144407.69): 16868,
    ("2026-05-14", 59500.0, 131558973.8): 16867,
    ("2026-05-14", 93000.0, 131499473.8): 16866,
    ("2026-05-14", 118262.0, 131406473.8): 16865,
    ("2026-05-14", 690396.71, 131288211.8): 16864,
    ("2026-05-14", 185226.61, 130597815.09): 16863,
    ("2026-05-13", 133684.86, 130412588.48): 16862,
    ("2026-05-13", 183663.23, 130546273.34): 16861,
    ("2026-05-13", 38.72, 130729936.57): 16860,
    ("2026-05-13", 57200.0, 130729975.29): 16859,
    ("2026-05-13", 274633.0, 130672775.29): 16858,
    ("2026-05-13", 126885.98, 130398142.29): 16857,
    ("2026-05-13", 88679.74, 130271256.31): 16856,
    ("2026-05-13", 210532.88, 130182576.57): 16855,
    ("2026-05-13", 71795.59, 129972043.69): 16854,
    ("2026-05-13", 600000.0, 129900248.1): 16853,
    ("2026-05-13", 84858.75, 129300248.1): 16852,
    ("2026-05-13", 103270.0, 129215389.35): 16851,
    ("2026-05-13", 46000.0, 129112119.35): 16850,
    ("2026-05-13", 548968.0, 129066119.35): 16849,
    ("2026-05-13", 109900.0, 128517151.35): 16848,
    ("2026-05-13", 34000.0, 128407251.35): 16847,
    ("2026-05-13", 225966.87, 128373251.35): 16846,
    ("2026-05-13", 40000.0, 128147284.48): 16845,
    ("2026-05-13", 900000.0, 128107284.48): 16844,
    ("2026-05-13", 163424.39, 127207284.48): 16843,
    ("2026-05-13", 111778.75, 127043860.09): 16842,
    ("2026-05-13", 65770.81, 126932081.34): 16841,
    ("2026-05-13", 57407.6, 126866310.53): 16840,
    ("2026-05-13", 128000.0, 126808902.93): 16839,
    ("2026-05-13", 40000.0, 126680902.93): 16838,
    ("2026-05-13", 100863.0, 126640902.93): 16837,
    ("2026-05-13", 12136.96, 126540039.93): 16836,
    ("2026-05-13", 808767.0, 126552176.89): 16835,
    ("2026-05-13", 195000.0, 125743409.89): 16834,
    ("2026-05-13", 448000.0, 125548409.89): 16833,
    ("2026-05-13", 35910.0, 125100409.89): 16832,
    ("2026-05-13", 391879.82, 125064499.89): 16831,
    ("2026-05-13", 100000.0, 124672620.07): 16830,
    ("2026-05-13", 283154.58, 124572620.07): 16829,
    ("2026-05-13", 9000.0, 124289465.49): 16828,
    ("2026-05-13", 121.0, 124280465.49): 16827,
    ("2026-05-13", 682732.0, 124280586.49): 16826,
    ("2026-05-13", 234129.0, 124963318.49): 16825,
    ("2026-05-13", 229507.49, 124729189.49): 16824,
    ("2026-05-13", 87777.0, 124499682.0): 16823,
    ("2026-05-13", 91900.0, 124411905.0): 16822,
    ("2026-05-13", 117511.0, 124320005.0): 16821,
    ("2026-05-13", 287855.68, 124202494.0): 16820,
    ("2026-05-13", 36479.62, 123914638.32): 16819,
    ("2026-05-13", 63859.46, 123878158.7): 16818,
    ("2026-05-13", 22000.0, 123814299.24): 16817,
    ("2026-05-13", 121.0, 123792299.24): 16816,
    ("2026-05-13", 9910394.89, 123792420.24): 16815,
    ("2026-05-13", 121.0, 133702815.13): 16814,
    ("2026-05-13", 10089605.11, 133702936.13): 16813,
    ("2026-05-13", 102804.96, 143792541.24): 16812,
    ("2026-05-13", 82918.6, 143689736.28): 16811,
    ("2026-05-13", 212480.55, 143606817.68): 16810,
    ("2026-05-13", 96267.61, 143394337.13): 16809,
    ("2026-05-13", 222471.62, 143298069.52): 16808,
    ("2026-05-13", 67200.0, 143075597.9): 16807,
    ("2026-05-13", 410046.15, 143008397.9): 16806,
    ("2026-05-13", 167636.0, 142598351.75): 16805,
    ("2026-05-13", 136400.0, 142430715.75): 16804,
    ("2026-05-13", 75000.0, 142294315.75): 16803,
    ("2026-05-13", 224653.0, 142219315.75): 16802,
    ("2026-05-13", 586739.84, 141994662.75): 16801,
    ("2026-05-13", 64378.26, 141407922.91): 16800,
    ("2026-05-13", 140000.0, 141343544.65): 16799,
    ("2026-05-13", 60000.0, 141483544.65): 16798,
    ("2026-05-13", 246472.36, 141543544.65): 16797,
    ("2026-05-13", 121.0, 141297072.29): 16796,
    ("2026-05-13", 487860.0, 141297193.29): 16795,
    ("2026-05-13", 124465.7, 141785053.29): 16794,
    ("2026-05-13", 371291.0, 141660587.59): 16793,
    ("2026-05-13", 96000.0, 141289296.59): 16792,
    ("2026-05-13", 109900.0, 141193296.59): 16791,
    ("2026-05-13", 81020.0, 141083396.59): 16790,
    ("2026-05-13", 121.0, 141002376.59): 16789,
    ("2026-05-13", 483150.0, 141002497.59): 16788,
    ("2026-05-13", 121.0, 141485647.59): 16787,
    ("2026-05-13", 414202.0, 141485768.59): 16786,
    ("2026-05-13", 88400.0, 141899970.59): 16785,
    ("2026-05-13", 200000.0, 141811570.59): 16784,
    ("2026-05-13", 68421.36, 141611570.59): 16783,
    ("2026-05-13", 123500.0, 141543149.23): 16782,
    ("2026-05-13", 500284.14, 141419649.23): 16781,
    ("2026-05-13", 30450.0, 140919365.09): 16780,
    ("2026-05-13", 110900.0, 140888915.09): 16779,
    ("2026-05-13", 900376.98, 140778015.09): 16778,
    ("2026-05-13", 7000000.0, 139877638.11): 16777,
    ("2026-05-13", 7556500.0, 132877638.11): 16776,
    ("2026-05-13", 112179.34, 125321138.11): 16775,
    ("2026-05-13", 185832.27, 125208958.77): 16774,
    ("2026-05-13", 72000.0, 125023126.5): 16773,
    ("2026-05-13", 132659.91, 124951126.5): 16772,
    ("2026-05-13", 167400.0, 124818466.59): 16771,
    ("2026-05-13", 199335.85, 124651066.59): 16770,
    ("2026-05-13", 366157.1, 124451730.74): 16769,
    ("2026-05-13", 142090.97, 124085573.64): 16768,
    ("2026-05-13", 487930.0, 123943482.67): 16767,
    ("2026-05-13", 85398.94, 123455552.67): 16766,
    ("2026-05-13", 153073.47, 123370153.73): 16765,
    ("2026-05-13", 23923.15, 123217080.26): 16764,
    ("2026-05-13", 50000.0, 123193157.11): 16763,
    ("2026-05-13", 144000.0, 123143157.11): 16762,
    ("2026-05-13", 86015.0, 122999157.11): 16761,
    ("2026-05-13", 412896.12, 122913142.11): 16760,
    ("2026-05-13", 100000.0, 122500245.99): 16759,
    ("2026-05-12", 26827.73, 122400245.99): 16758,
    ("2026-05-12", 159028.74, 122427073.72): 16757,
    ("2026-05-12", 48.4, 122586102.46): 16756,
    ("2026-05-12", 91400.0, 122586150.86): 16755,
    ("2026-05-12", 717766.24, 122494750.86): 16754,
    ("2026-05-12", 1000000.0, 121776984.62): 16753,
    ("2026-05-12", 300000.0, 120776984.62): 16752,
    ("2026-05-12", 300000.0, 120476984.62): 16751,
    ("2026-05-12", 400000.0, 120176984.62): 16750,
    ("2026-05-12", 22000.0, 119776984.62): 16749,
    ("2026-05-12", 76639.0, 119754984.62): 16748,
    ("2026-05-12", 35000.0, 119678345.62): 16747,
    ("2026-05-12", 1000000.0, 119643345.62): 16746,
    ("2026-05-12", 70000.0, 118643345.62): 16745,
    ("2026-05-12", 60000.0, 118573345.62): 16744,
    ("2026-05-12", 124058.88, 118513345.62): 16743,
    ("2026-05-12", 113127.99, 118389286.74): 16742,
    ("2026-05-12", 332750.72, 118276158.75): 16741,
    ("2026-05-12", 114754.7, 117943408.03): 16740,
    ("2026-05-12", 898564.83, 117828653.33): 16739,
    ("2026-05-12", 186047.64, 116930088.5): 16738,
    ("2026-05-12", 136335.8, 116744040.86): 16737,
    ("2026-05-12", 492333.0, 116607705.06): 16736,
    ("2026-05-12", 117000.0, 116115372.06): 16735,
    ("2026-05-12", 97535.01, 115998372.06): 16734,
    ("2026-05-12", 131118.44, 115900837.05): 16733,
    ("2026-05-12", 434482.59, 115769718.61): 16732,
    ("2026-05-12", 87440.66, 115335236.02): 16731,
    ("2026-05-12", 910953.84, 115247795.36): 16730,
    ("2026-05-12", 70000.0, 114336841.52): 16729,
    ("2026-05-12", 19268.0, 114266841.52): 16728,
    ("2026-05-12", 216713.25, 114247573.52): 16727,
    ("2026-05-12", 274900.0, 114030860.27): 16726,
    ("2026-05-12", 90700.0, 113755960.27): 16725,
    ("2026-05-12", 340332.97, 113665260.27): 16724,
    ("2026-05-12", 200000.0, 113324927.3): 16723,
    ("2026-05-12", 40000.0, 113124927.3): 16722,
    ("2026-05-12", 529830.0, 113084927.3): 16721,
    ("2026-05-12", 100000.0, 112555097.3): 16720,
    ("2026-05-12", 96000.0, 112455097.3): 16719,
    ("2026-05-12", 109900.0, 112359097.3): 16718,
    ("2026-05-12", 138150.39, 112249197.3): 16717,
    ("2026-05-12", 500000.0, 112111046.91): 16716,
    ("2026-05-12", 40000.0, 111611046.91): 16715,
    ("2026-05-12", 132500.0, 111571046.91): 16714,
    ("2026-05-12", 802991.86, 111438546.91): 16713,
    ("2026-05-12", 430103.59, 110635555.05): 16712,
    ("2026-05-12", 121.0, 110205451.46): 16711,
    ("2026-05-12", 1000000.0, 110205572.46): 16710,
    ("2026-05-12", 144272.08, 111205572.46): 16709,
    ("2026-05-12", 944156.42, 111061300.38): 16708,
    ("2026-05-12", 206525.0, 110117143.96): 16707,
    ("2026-05-12", 400000.0, 109910618.96): 16706,
    ("2026-05-12", 121.0, 109510618.96): 16705,
    ("2026-05-12", 853640.0, 109510739.96): 16704,
    ("2026-05-12", 121.0, 110364379.96): 16703,
    ("2026-05-12", 1408694.0, 110364500.96): 16702,
    ("2026-05-12", 65000.0, 111773194.96): 16701,
    ("2026-05-12", 67200.0, 111838194.96): 16700,
    ("2026-05-12", 380639.0, 111770994.96): 16699,
    ("2026-05-12", 179138.9, 111390355.96): 16698,
    ("2026-05-12", 138438.5, 111211217.06): 16697,
    ("2026-05-12", 248978.0, 111072778.56): 16696,
    ("2026-05-12", 386459.09, 110823800.56): 16695,
    ("2026-05-12", 121.0, 110437341.47): 16694,
    ("2026-05-12", 350000.0, 110437462.47): 16693,
    ("2026-05-12", 142800.0, 110787462.47): 16692,
    ("2026-05-12", 121.0, 110644662.47): 16691,
    ("2026-05-12", 793346.98, 110644783.47): 16690,
    ("2026-05-12", 269603.95, 111438130.45): 16689,
    ("2026-05-12", 77070.0, 111168526.5): 16688,
    ("2026-05-12", 794026.3, 111091456.5): 16687,
    ("2026-05-12", 65000.0, 110297430.2): 16686,
    ("2026-05-12", 105000.0, 110232430.2): 16685,
    ("2026-05-12", 107089.99, 110127430.2): 16684,
    ("2026-05-12", 187886.0, 110020340.21): 16683,
    ("2026-05-12", 125552.62, 109832454.21): 16682,
    ("2026-05-12", 409680.0, 109706901.59): 16681,
    ("2026-05-12", 140000.0, 109297221.59): 16680,
    ("2026-05-12", 797111.47, 109157221.59): 16679,
    ("2026-05-12", 70000.0, 108360110.12): 16678,
    ("2026-05-12", 27600.0, 108290110.12): 16677,
    ("2026-05-12", 160964.0, 108262510.12): 16676,
    ("2026-05-12", 22000.0, 108101546.12): 16675,
    ("2026-05-12", 29925.0, 108079546.12): 16674,
    ("2026-05-12", 22000.0, 108049621.12): 16673,
    ("2026-05-12", 106500.0, 108027621.12): 16672,
    ("2026-05-12", 2966466.0, 107921121.12): 16671,
    ("2026-05-12", 294545.7, 104954655.12): 16670,
    ("2026-05-12", 298540.23, 104660109.42): 16669,
    ("2026-05-12", 82390.69, 104361569.19): 16668,
    ("2026-05-12", 63000.0, 104279178.5): 16667,
    ("2026-05-12", 889368.04, 104216178.5): 16666,
    ("2026-05-12", 148624.25, 103326810.46): 16665,
    ("2026-05-12", 48000.0, 103178186.21): 16664,
    ("2026-05-12", 80000.0, 103130186.21): 16663,
    ("2026-05-12", 368000.0, 103050186.21): 16662,
    ("2026-05-12", 272000.0, 102682186.21): 16661,
    ("2026-05-12", 167000.0, 102410186.21): 16660,
    ("2026-05-12", 36000.0, 102243186.21): 16659,
    ("2026-05-12", 40000.0, 102207186.21): 16658,
    ("2026-05-12", 158258.49, 102167186.21): 16657,
    ("2026-05-12", 40000.0, 102008927.72): 16656,
    ("2026-05-12", 140527.55, 101968927.72): 16655,
    ("2026-05-12", 50000.0, 101828400.17): 16654,
    ("2026-05-12", 541287.71, 101778400.17): 16653,
    ("2026-05-12", 120803.06, 101237112.46): 16652,
    ("2026-05-12", 30700.0, 101116309.4): 16651,
    ("2026-05-12", 106586.72, 101085609.4): 16650,
    ("2026-05-12", 54000.0, 100979022.68): 16649,
    ("2026-05-12", 116852.35, 100925022.68): 16648,
    ("2026-05-12", 72000.0, 100808170.33): 16647,
    ("2026-05-12", 183525.79, 100736170.33): 16646,
    ("2026-05-11", 37399.21, 100552644.54): 16645,
    ("2026-05-11", 253718.23, 100590043.75): 16644,
    ("2026-05-11", 87.12, 100843761.98): 16643,
    ("2026-05-11", 142757.89, 100843849.1): 16642,
    ("2026-05-11", 75000.0, 100701091.21): 16641,
    ("2026-05-11", 120254.23, 100626091.21): 16640,
    ("2026-05-11", 104256.0, 100505836.98): 16639,
    ("2026-05-11", 400000.0, 100401580.98): 16638,
    ("2026-05-11", 384388.27, 100001580.98): 16637,
    ("2026-05-11", 758000.0, 99617192.71): 16636,
    ("2026-05-11", 92000.0, 98859192.71): 16635,
    ("2026-05-11", 168881.09, 98767192.71): 16634,
    ("2026-05-11", 129000.0, 98598311.62): 16633,
    ("2026-05-11", 87000.0, 98469311.62): 16632,
    ("2026-05-11", 200000.0, 98382311.62): 16631,
    ("2026-05-11", 175740.0, 98182311.62): 16630,
    ("2026-05-11", 428199.2, 98006571.62): 16629,
    ("2026-05-11", 56000.0, 97578372.42): 16628,
    ("2026-05-11", 30000.0, 97522372.42): 16627,
    ("2026-05-11", 128850.0, 97492372.42): 16626,
    ("2026-05-11", 104102.0, 97363522.42): 16625,
    ("2026-05-11", 171660.0, 97259420.42): 16624,
    ("2026-05-11", 96000.0, 97087760.42): 16623,
    ("2026-05-11", 65000.0, 96991760.42): 16622,
    ("2026-05-11", 550000.0, 96926760.42): 16621,
    ("2026-05-11", 100000.0, 96376760.42): 16620,
    ("2026-05-11", 56000.0, 96276760.42): 16619,
    ("2026-05-11", 540000.0, 96220760.42): 16618,
    ("2026-05-11", 232070.27, 95680760.42): 16617,
    ("2026-05-11", 109900.0, 95448690.15): 16616,
    ("2026-05-11", 20000.0, 95338790.15): 16615,
    ("2026-05-11", 121.0, 95318790.15): 16614,
    ("2026-05-11", 500500.0, 95318911.15): 16613,
    ("2026-05-11", 224500.0, 95819411.15): 16612,
    ("2026-05-11", 121.0, 95594911.15): 16611,
    ("2026-05-11", 1011843.74, 95595032.15): 16610,
    ("2026-05-11", 200000.0, 96606875.89): 16609,
    ("2026-05-11", 121.0, 96406875.89): 16608,
    ("2026-05-11", 503341.33, 96406996.89): 16607,
    ("2026-05-11", 152000.0, 96910338.22): 16606,
    ("2026-05-11", 146700.0, 96758338.22): 16605,
    ("2026-05-11", 81000.0, 96611638.22): 16604,
    ("2026-05-11", 34860.0, 96530638.22): 16603,
    ("2026-05-11", 97770.65, 96495778.22): 16602,
    ("2026-05-11", 86796.23, 96398007.57): 16601,
    ("2026-05-11", 121.0, 96311211.34): 16600,
    ("2026-05-11", 731500.0, 96311332.34): 16599,
    ("2026-05-11", 121.0, 97042832.34): 16598,
    ("2026-05-11", 664242.0, 97042953.34): 16597,
    ("2026-05-11", 90000.0, 97707195.34): 16596,
    ("2026-05-11", 178250.0, 97797195.34): 16595,
    ("2026-05-11", 1012908.89, 97618945.34): 16594,
    ("2026-05-11", 121.0, 96606036.45): 16593,
    ("2026-05-11", 800000.0, 96606157.45): 16592,
    ("2026-05-11", 215504.95, 97406157.45): 16591,
    ("2026-05-11", 31500.0, 97190652.5): 16590,
    ("2026-05-11", 516098.0, 97159152.5): 16589,
    ("2026-05-11", 589359.37, 96643054.5): 16588,
    ("2026-05-11", 100000.0, 96053695.13): 16587,
    ("2026-05-11", 240000.0, 95953695.13): 16586,
    ("2026-05-11", 22575.0, 95713695.13): 16585,
    ("2026-05-11", 383448.0, 95691120.13): 16584,
    ("2026-05-11", 160000.0, 95307672.13): 16583,
    ("2026-05-11", 224000.0, 95467672.13): 16582,
    ("2026-05-11", 884957.64, 95691672.13): 16581,
    ("2026-05-11", 121.0, 94806714.49): 16580,
    ("2026-05-11", 362356.0, 94806835.49): 16579,
    ("2026-05-11", 121.0, 95169191.49): 16578,
    ("2026-05-11", 575228.0, 95169312.49): 16577,
    ("2026-05-11", 165080.15, 95744540.49): 16576,
    ("2026-05-11", 169322.0, 95579460.34): 16575,
    ("2026-05-11", 121.0, 95748782.34): 16574,
    ("2026-05-11", 439773.16, 95748903.34): 16573,
    ("2026-05-11", 193935.0, 96188676.5): 16572,
    ("2026-05-11", 117390.42, 95994741.5): 16571,
    ("2026-05-11", 160000.0, 95877351.08): 16570,
    ("2026-05-11", 60000.0, 95717351.08): 16569,
    ("2026-05-11", 100000.0, 95657351.08): 16568,
    ("2026-05-11", 294436.08, 95557351.08): 16567,
    ("2026-05-11", 567735.81, 95262915.0): 16566,
    ("2026-05-11", 673515.98, 94695179.19): 16565,
    ("2026-05-11", 35700.0, 94021663.21): 16564,
    ("2026-05-11", 1463989.62, 93985963.21): 16563,
    ("2026-05-11", 136000.0, 92521973.59): 16562,
    ("2026-05-11", 140878.0, 92385973.59): 16561,
    ("2026-05-11", 110000.0, 92245095.59): 16560,
    ("2026-05-11", 75000.0, 92135095.59): 16559,
    ("2026-05-11", 1150000.0, 92060095.59): 16558,
    ("2026-05-11", 151894.87, 90910095.59): 16557,
    ("2026-05-11", 1500000.0, 90758200.72): 16556,
    ("2026-05-11", 200000.0, 89258200.72): 16555,
    ("2026-05-11", 1500000.0, 89058200.72): 16554,
    ("2026-05-11", 95000.0, 87558200.72): 16553,
    ("2026-05-11", 112293.6, 87463200.72): 16552,
    ("2026-05-11", 128438.49, 87350907.12): 16551,
    ("2026-05-11", 202657.02, 87222468.63): 16550,
    ("2026-05-11", 58000.0, 87019811.61): 16549,
    ("2026-05-11", 25500.0, 86961811.61): 16548,
    ("2026-05-11", 203745.94, 86936311.61): 16547,
    ("2026-05-11", 103575.0, 86732565.67): 16546,
    ("2026-05-11", 57225.0, 86628990.67): 16545,
    ("2026-05-11", 1592159.0, 86571765.67): 16544,
    ("2026-05-11", 110900.0, 84979606.67): 16543,
    ("2026-05-11", 198186.32, 84868706.67): 16542,
    ("2026-05-11", 159995.85, 84670520.35): 16541,
    ("2026-05-11", 142000.0, 84510524.5): 16540,
    ("2026-05-11", 109900.0, 84368524.5): 16539,
    ("2026-05-11", 62585.0, 84258624.5): 16538,
    ("2026-05-11", 117290.02, 84196039.5): 16537,
    ("2026-05-11", 280800.0, 84078749.48): 16536,
    ("2026-05-11", 96000.0, 83797949.48): 16535,
    ("2026-05-11", 128500.0, 83701949.48): 16534,
    ("2026-05-11", 65478.7, 83573449.48): 16533,
    ("2026-05-11", 104034.93, 83507970.78): 16532,
    ("2026-05-11", 80500.0, 83403935.85): 16531,
    ("2026-05-11", 288773.09, 83323435.85): 16530,
    ("2026-05-11", 313828.52, 83034662.76): 16529,
    ("2026-05-11", 497512.0, 82720834.24): 16528,
    ("2026-05-11", 84000.0, 82223322.24): 16527,
    ("2026-05-11", 353228.09, 82139322.24): 16526,
    ("2026-05-11", 342767.86, 81786094.15): 16525,
    ("2026-05-11", 465854.07, 81443326.29): 16524,
    ("2026-05-11", 218778.19, 80977472.22): 16523,
    ("2026-05-11", 110900.0, 80758694.03): 16522,
    ("2026-05-11", 651058.38, 80647794.03): 16521,
    ("2026-05-11", 143291.0, 79996735.65): 16520,
    ("2026-05-11", 633876.0, 79853444.65): 16519,
    ("2026-05-11", 412500.0, 79219568.65): 16518,
    ("2026-05-11", 71569.94, 78807068.65): 16517,
    ("2026-05-11", 204854.57, 78735498.71): 16516,
    ("2026-05-11", 100000.0, 78530644.14): 16515,
    ("2026-05-11", 333033.04, 78430644.14): 16514,
    ("2026-05-11", 346600.0, 78097611.1): 16513,
    ("2026-05-11", 500000.0, 77751011.1): 16512,
    ("2026-05-11", 800000.0, 77251011.1): 16511,
    ("2026-05-11", 180000.0, 76451011.1): 16510,
    ("2026-05-11", 210000.0, 76271011.1): 16509,
    ("2026-05-11", 127000.0, 76061011.1): 16508,
    ("2026-05-11", 65000.0, 75934011.1): 16507,
    ("2026-05-11", 741520.0, 75869011.1): 16506,
    ("2026-05-11", 694478.0, 75127491.1): 16505,
    ("2026-05-11", 569008.0, 74433013.1): 16504,
    ("2026-05-11", 26011.0, 73864005.1): 16503,
    ("2026-05-11", 807600.0, 73837994.1): 16502,
    ("2026-05-11", 120000.0, 73030394.1): 16501,
    ("2026-05-11", 65000.0, 72910394.1): 16500,
    ("2026-05-11", 700000.0, 72845394.1): 16499,
    ("2026-05-11", 60000.0, 72145394.1): 16498,
    ("2026-05-11", 650000.0, 72085394.1): 16497,
    ("2026-05-11", 56280.0, 71435394.1): 16496,
    ("2026-05-11", 151100.0, 71379114.1): 16495,
    ("2026-05-11", 164000.0, 71228014.1): 16494,
    ("2026-05-11", 107661.95, 71064014.1): 16493,
    ("2026-05-11", 2215000.0, 70956352.15): 16492,
    ("2026-05-11", 438000.0, 68741352.15): 16491,
    ("2026-05-11", 126000.0, 68303352.15): 16490,
    ("2026-05-11", 144000.0, 68177352.15): 16489,
    ("2026-05-11", 232100.0, 68033352.15): 16488,
    ("2026-05-11", 167450.0, 67801252.15): 16487,
    ("2026-05-11", 134900.0, 67633802.15): 16486,
    ("2026-05-11", 5000.0, 67498902.15): 16485,
    ("2026-05-11", 170229.0, 67493902.15): 16484,
    ("2026-05-11", 21500.0, 67323673.15): 16483,
    ("2026-05-11", 160000.0, 67302173.15): 16482,
    ("2026-05-11", 40000.0, 67142173.15): 16481,
    ("2026-05-11", 181500.0, 67102173.15): 16480,
    ("2026-05-11", 519929.0, 66920673.15): 16479,
    ("2026-05-11", 110900.0, 66400744.15): 16478,
    ("2026-05-11", 211800.0, 66289844.15): 16477,
    ("2026-05-11", 208300.0, 66078044.15): 16476,
    ("2026-05-11", 169500.0, 65869744.15): 16475,
    ("2026-05-11", 136000.0, 65700244.15): 16474,
    ("2026-05-11", 533565.38, 65564244.15): 16473,
    ("2026-05-11", 30000.0, 65030678.77): 16472,
    ("2026-05-11", 45000.0, 65000678.77): 16471,
    ("2026-05-11", 105000.0, 64955678.77): 16470,
    ("2026-05-11", 30000.0, 64850678.77): 16469,
    ("2026-05-11", 30000.0, 64820678.77): 16468,
    ("2026-05-08", 431929.38, 64790678.77): 16467,
    ("2026-05-08", 82921.71, 65222608.15): 16466,
    ("2026-05-08", 136.97, 65305529.86): 16465,
    ("2026-05-08", 46381.79, 65305666.83): 16464,
    ("2026-05-08", 554078.0, 65259285.04): 16463,
    ("2026-05-08", 80172.0, 64705207.04): 16462,
    ("2026-05-08", 285410.0, 64625035.04): 16461,
    ("2026-05-08", 100000.0, 64339625.04): 16460,
    ("2026-05-08", 601494.98, 64239625.04): 16459,
    ("2026-05-08", 60000.0, 63638130.06): 16458,
    ("2026-05-08", 200000.0, 63578130.06): 16457,
    ("2026-05-08", 5000.0, 63378130.06): 16456,
    ("2026-05-08", 173860.0, 63373130.06): 16455,
    ("2026-05-08", 53752.57, 63199270.06): 16454,
    ("2026-05-08", 201906.83, 63145517.49): 16453,
    ("2026-05-08", 64903.49, 62943610.66): 16452,
    ("2026-05-08", 35000.0, 62878707.17): 16451,
    ("2026-05-08", 1117192.26, 62843707.17): 16450,
    ("2026-05-08", 121.0, 61726514.91): 16449,
    ("2026-05-08", 20000000.0, 61726635.91): 16448,
    ("2026-05-08", 72000.0, 81726635.91): 16447,
    ("2026-05-08", 169155.0, 81654635.91): 16446,
    ("2026-05-08", 106018.1, 81485480.91): 16445,
    ("2026-05-08", 121.0, 81379462.81): 16444,
    ("2026-05-08", 730471.0, 81379583.81): 16443,
    ("2026-05-08", 121.0, 82110054.81): 16442,
    ("2026-05-08", 580500.0, 82110175.81): 16441,
    ("2026-05-08", 121.0, 82690675.81): 16440,
    ("2026-05-08", 415500.0, 82690796.81): 16439,
    ("2026-05-08", 121.0, 83106296.81): 16438,
    ("2026-05-08", 1857122.62, 83106417.81): 16437,
    ("2026-05-08", 1031700.0, 84963540.43): 16436,
    ("2026-05-08", 78650.0, 83931840.43): 16435,
    ("2026-05-08", 121.0, 83853190.43): 16434,
    ("2026-05-08", 542978.0, 83853311.43): 16433,
    ("2026-05-08", 69300.0, 84396289.43): 16432,
    ("2026-05-08", 121.0, 84326989.43): 16431,
    ("2026-05-08", 740200.0, 84327110.43): 16430,
    ("2026-05-08", 121.0, 85067310.43): 16429,
    ("2026-05-08", 3475386.57, 85067431.43): 16428,
    ("2026-05-08", 18.15, 88542818.0): 16427,
    ("2026-05-08", 274000.0, 88542836.15): 16426,
    ("2026-05-08", 234000.0, 88816836.15): 16425,
    ("2026-05-08", 20000.0, 89050836.15): 16424,
    ("2026-05-08", 170774.0, 89030836.15): 16423,
    ("2026-05-08", 1287576.11, 89201610.15): 16422,
    ("2026-05-08", 185000.0, 87914034.04): 16421,
    ("2026-05-08", 121.0, 87729034.04): 16420,
    ("2026-05-08", 900000.0, 87729155.04): 16419,
    ("2026-05-08", 121.0, 88629155.04): 16418,
    ("2026-05-08", 412500.0, 88629276.04): 16417,
    ("2026-05-08", 599731.01, 89041776.04): 16416,
    ("2026-05-08", 247293.74, 88442045.03): 16415,
    ("2026-05-08", 300000.0, 88194751.29): 16414,
    ("2026-05-08", 121.0, 87894751.29): 16413,
    ("2026-05-08", 396476.0, 87894872.29): 16412,
    ("2026-05-08", 121.0, 88291348.29): 16411,
    ("2026-05-08", 396476.0, 88291469.29): 16410,
    ("2026-05-08", 140315.24, 88687945.29): 16409,
    ("2026-05-08", 25000.0, 88547630.05): 16408,
    ("2026-05-08", 121000.0, 88522630.05): 16407,
    ("2026-05-08", 192000.0, 88401630.05): 16406,
    ("2026-05-08", 252044.65, 88209630.05): 16405,
    ("2026-05-08", 44000.0, 87957585.4): 16404,
    ("2026-05-08", 67694.0, 87913585.4): 16403,
    ("2026-05-08", 110000.0, 87845891.4): 16402,
    ("2026-05-08", 145000.0, 87955891.4): 16401,
    ("2026-05-08", 30000.0, 87810891.4): 16400,
    ("2026-05-08", 288000.0, 87780891.4): 16399,
    ("2026-05-08", 222416.5, 87492891.4): 16398,
    ("2026-05-08", 170000.0, 87270474.9): 16397,
    ("2026-05-08", 8376.11, 87100474.9): 16396,
    ("2026-05-08", 92794.92, 87092098.79): 16395,
    ("2026-05-08", 137315.23, 86999303.87): 16394,
    ("2026-05-08", 116463.16, 86861988.64): 16393,
    ("2026-05-08", 183200.0, 86745525.48): 16392,
    ("2026-05-08", 84182.38, 86562325.48): 16391,
    ("2026-05-08", 26850.0, 86478143.1): 16390,
    ("2026-05-08", 221000.0, 86451293.1): 16389,
    ("2026-05-08", 343101.65, 86230293.1): 16388,
    ("2026-05-08", 65000.0, 85887191.45): 16387,
    ("2026-05-08", 121.0, 85822191.45): 16386,
    ("2026-05-08", 20108262.03, 85822312.45): 16385,
    ("2026-05-08", 121.0, 105930574.48): 16384,
    ("2026-05-08", 19891737.97, 105930695.48): 16383,
    ("2026-05-08", 237280.22, 125822433.45): 16382,
    ("2026-05-08", 121.0, 125585153.23): 16381,
    ("2026-05-08", 750000.0, 125585274.23): 16380,
    ("2026-05-08", 64151.61, 126335274.23): 16379,
    ("2026-05-08", 150000.0, 126271122.62): 16378,
    ("2026-05-08", 22000.0, 126121122.62): 16377,
    ("2026-05-08", 75000.0, 126099122.62): 16376,
    ("2026-05-08", 547478.74, 126024122.62): 16375,
    ("2026-05-08", 113400.0, 125476643.88): 16374,
    ("2026-05-08", 118650.0, 125363243.88): 16373,
    ("2026-05-08", 327267.46, 125244593.88): 16372,
    ("2026-05-08", 143794.59, 124917326.42): 16371,
    ("2026-05-08", 356083.19, 124773531.83): 16370,
    ("2026-05-08", 100000.0, 124417448.64): 16369,
    ("2026-05-08", 85166.68, 124317448.64): 16368,
    ("2026-05-08", 173000.0, 124232281.96): 16367,
    ("2026-05-08", 68000.0, 124059281.96): 16366,
    ("2026-05-08", 379333.96, 123991281.96): 16365,
    ("2026-05-08", 138350.0, 123611948.0): 16364,
    ("2026-05-07", 53200.5, 123473598.0): 16363,
    ("2026-05-07", 104590.5, 123526798.5): 16362,
    ("2026-05-07", 145.2, 123631389.0): 16361,
    ("2026-05-07", 317913.0, 123631534.2): 16360,
    ("2026-05-07", 27512.64, 123313621.2): 16359,
    ("2026-05-07", 151048.05, 123286108.56): 16358,
    ("2026-05-07", 150821.0, 123135060.51): 16357,
    ("2026-05-07", 63000.0, 122984239.51): 16356,
    ("2026-05-07", 75000.0, 122921239.51): 16355,
    ("2026-05-07", 75000.0, 122846239.51): 16354,
    ("2026-05-07", 268000.0, 122771239.51): 16353,
    ("2026-05-07", 34142.71, 122503239.51): 16352,
    ("2026-05-07", 489811.52, 122469096.8): 16351,
    ("2026-05-07", 70000.0, 121979285.28): 16350,
    ("2026-05-07", 430000.0, 121909285.28): 16349,
    ("2026-05-07", 70000.0, 121479285.28): 16348,
    ("2026-05-07", 109900.0, 121409285.28): 16347,
    ("2026-05-07", 750200.0, 121299385.28): 16346,
    ("2026-05-07", 48300.0, 120549185.28): 16345,
    ("2026-05-07", 408879.23, 120500885.28): 16344,
    ("2026-05-07", 210000.0, 120092006.05): 16343,
    ("2026-05-07", 129474.95, 119882006.05): 16342,
    ("2026-05-07", 383552.85, 119752531.1): 16341,
    ("2026-05-07", 182177.84, 119368978.25): 16340,
    ("2026-05-07", 180108.19, 119186800.41): 16339,
    ("2026-05-07", 515458.59, 119006692.22): 16338,
    ("2026-05-07", 85960.99, 118491233.63): 16337,
    ("2026-05-07", 65000.0, 118405272.64): 16336,
    ("2026-05-07", 567954.72, 118340272.64): 16335,
    ("2026-05-07", 298988.5, 117772317.92): 16334,
    ("2026-05-07", 655854.14, 117473329.42): 16333,
    ("2026-05-07", 121.0, 116817475.28): 16332,
    ("2026-05-07", 471000.0, 116817596.28): 16331,
    ("2026-05-07", 109900.0, 117288596.28): 16330,
    ("2026-05-07", 106409.22, 117178696.28): 16329,
    ("2026-05-07", 512700.0, 117072287.06): 16328,
    ("2026-05-07", 95634.27, 116559587.06): 16327,
    ("2026-05-07", 100000.0, 116463952.79): 16326,
    ("2026-05-07", 106600.0, 116363952.79): 16325,
    ("2026-05-07", 437182.27, 116257352.79): 16324,
    ("2026-05-07", 121.0, 115820170.52): 16323,
    ("2026-05-07", 600000.0, 115820291.52): 16322,
    ("2026-05-07", 96000.0, 116420291.52): 16321,
    ("2026-05-07", 121.0, 116324291.52): 16320,
    ("2026-05-07", 365515.0, 116324412.52): 16319,
    ("2026-05-07", 86981.25, 116689927.52): 16318,
    ("2026-05-07", 1678416.0, 116602946.27): 16317,
    ("2026-05-07", 121.0, 114924530.27): 16316,
    ("2026-05-07", 545722.87, 114924651.27): 16315,
    ("2026-05-07", 121.0, 115470374.14): 16314,
    ("2026-05-07", 769028.48, 115470495.14): 16313,
    ("2026-05-07", 75000.0, 116239523.62): 16312,
    ("2026-05-07", 121.0, 116164523.62): 16311,
    ("2026-05-07", 750000.0, 116164644.62): 16310,
    ("2026-05-07", 121.0, 116914644.62): 16309,
    ("2026-05-07", 553371.0, 116914765.62): 16308,
    ("2026-05-07", 121.0, 117468136.62): 16307,
    ("2026-05-07", 750000.0, 117468257.62): 16306,
    ("2026-05-07", 76015.9, 118218257.62): 16305,
    ("2026-05-07", 98276.84, 118142241.72): 16304,
    ("2026-05-07", 255650.86, 118043964.88): 16303,
    ("2026-05-07", 121.0, 117788314.02): 16302,
    ("2026-05-07", 604848.0, 117788435.02): 16301,
    ("2026-05-07", 121.0, 118393283.02): 16300,
    ("2026-05-07", 600000.0, 118393404.02): 16299,
    ("2026-05-07", 197929.5, 118993404.02): 16298,
    ("2026-05-07", 174157.1, 118795474.52): 16297,
    ("2026-05-07", 94318.1, 118621317.42): 16296,
    ("2026-05-07", 867150.0, 118526999.32): 16295,
    ("2026-05-07", 73906.73, 117659849.32): 16294,
    ("2026-05-07", 668973.09, 117585942.59): 16293,
    ("2026-05-07", 121.0, 116916969.5): 16292,
    ("2026-05-07", 685000.0, 116917090.5): 16291,
    ("2026-05-07", 121.0, 117602090.5): 16290,
    ("2026-05-07", 353078.33, 117602211.5): 16289,
    ("2026-05-07", 178800.0, 117955289.83): 16288,
    ("2026-05-07", 107690.28, 117776489.83): 16287,
    ("2026-05-07", 68000.0, 117668799.55): 16286,
    ("2026-05-07", 121.0, 117600799.55): 16285,
    ("2026-05-07", 969500.0, 117600920.55): 16284,
    ("2026-05-07", 227004.0, 118570420.55): 16283,
    ("2026-05-07", 118434.48, 118343416.55): 16282,
    ("2026-05-07", 70000.0, 118224982.07): 16281,
    ("2026-05-07", 65095.99, 118154982.07): 16280,
    ("2026-05-07", 5000.0, 118089886.08): 16279,
    ("2026-05-07", 54290.33, 118084886.08): 16278,
    ("2026-05-07", 121.0, 118030595.75): 16277,
    ("2026-05-07", 320571.1, 118030716.75): 16276,
    ("2026-05-07", 280500.0, 118351287.85): 16275,
    ("2026-05-07", 75000.0, 118070787.85): 16274,
    ("2026-05-07", 121.0, 117995787.85): 16273,
    ("2026-05-07", 527289.0, 117995908.85): 16272,
    ("2026-05-07", 42525.0, 118523197.85): 16271,
    ("2026-05-07", 86731.75, 118480672.85): 16270,
    ("2026-05-07", 210320.0, 118393941.1): 16269,
    ("2026-05-07", 100000.0, 118183621.1): 16268,
    ("2026-05-07", 225174.0, 118083621.1): 16267,
    ("2026-05-07", 13158.69, 117858447.1): 16266,
    ("2026-05-07", 154349.01, 117845288.41): 16265,
    ("2026-05-07", 60000.0, 117690939.4): 16264,
    ("2026-05-07", 110900.0, 117630939.4): 16263,
    ("2026-05-07", 289190.47, 117520039.4): 16262,
    ("2026-05-07", 94134.99, 117230848.93): 16261,
    ("2026-05-07", 351260.0, 117136713.94): 16260,
    ("2026-05-07", 745390.0, 116785453.94): 16259,
    ("2026-05-07", 224550.0, 116040063.94): 16258,
    ("2026-05-07", 218000.0, 115815513.94): 16257,
    ("2026-05-07", 457941.02, 115597513.94): 16256,
    ("2026-05-07", 73043.83, 115139572.92): 16255,
    ("2026-05-06", 405909.06, 115066529.09): 16254,
    ("2026-05-06", 102123.32, 115472438.15): 16253,
    ("2026-05-06", 87.12, 115574561.47): 16252,
    ("2026-05-06", 112000.0, 115574648.59): 16251,
    ("2026-05-06", 168000.0, 115462648.59): 16250,
    ("2026-05-06", 27955.0, 115294648.59): 16249,
    ("2026-05-06", 206648.4, 115266693.59): 16248,
    ("2026-05-06", 70000.0, 115060045.19): 16247,
    ("2026-05-06", 202918.0, 114990045.19): 16246,
    ("2026-05-06", 60000.0, 114787127.19): 16245,
    ("2026-05-06", 116000.0, 114727127.19): 16244,
    ("2026-05-06", 187300.0, 114611127.19): 16243,
    ("2026-05-06", 69000.0, 114423827.19): 16242,
    ("2026-05-06", 95340.73, 114354827.19): 16241,
    ("2026-05-06", 99540.53, 114259486.46): 16240,
    ("2026-05-06", 119400.0, 114159945.93): 16239,
    ("2026-05-06", 99005.26, 114040545.93): 16238,
    ("2026-05-06", 160000.0, 113941540.67): 16237,
    ("2026-05-06", 203200.0, 114101540.67): 16236,
    ("2026-05-06", 70000.0, 113898340.67): 16235,
    ("2026-05-06", 144000.0, 113828340.67): 16234,
    ("2026-05-06", 907488.77, 113684340.67): 16233,
    ("2026-05-06", 121.0, 112776851.9): 16232,
    ("2026-05-06", 13605627.47, 112776972.9): 16231,
    ("2026-05-06", 100000.0, 126382600.37): 16230,
    ("2026-05-06", 121.0, 126282600.37): 16229,
    ("2026-05-06", 910000.0, 126282721.37): 16228,
    ("2026-05-06", 65467.0, 127192721.37): 16227,
    ("2026-05-06", 459000.0, 127127254.37): 16226,
    ("2026-05-06", 39587.81, 126668254.37): 16225,
    ("2026-05-06", 14200.0, 126628666.56): 16224,
    ("2026-05-06", 96187.0, 126614466.56): 16223,
    ("2026-05-06", 366434.74, 126518279.56): 16222,
    ("2026-05-06", 180000.0, 126151844.82): 16221,
    ("2026-05-06", 359537.38, 125971844.82): 16220,
    ("2026-05-06", 83023.6, 125612307.44): 16219,
    ("2026-05-06", 1122012.86, 125529283.84): 16218,
    ("2026-05-06", 109000.0, 124407270.98): 16217,
    ("2026-05-06", 479224.03, 124298270.98): 16216,
    ("2026-05-06", 658901.76, 123819046.95): 16215,
    ("2026-05-06", 929183.46, 123160145.19): 16214,
    ("2026-05-06", 213055.28, 122230961.73): 16213,
    ("2026-05-06", 40667.01, 122017906.45): 16212,
    ("2026-05-06", 549.0, 121977239.44): 16211,
    ("2026-05-06", 125825.0, 121976690.44): 16210,
    ("2026-05-06", 197061.0, 121850865.44): 16209,
    ("2026-05-06", 589844.32, 121653804.44): 16208,
    ("2026-05-06", 121.0, 121063960.12): 16207,
    ("2026-05-06", 3005949.59, 121064081.12): 16206,
    ("2026-05-06", 121.0, 124070030.71): 16205,
    ("2026-05-06", 16994050.41, 124070151.71): 16204,
    ("2026-05-06", 609043.65, 141064202.12): 16203,
    ("2026-05-06", 58601.61, 140455158.47): 16202,
    ("2026-05-06", 158984.03, 140513760.08): 16201,
    ("2026-05-06", 308500.0, 140354776.05): 16200,
    ("2026-05-06", 75000.0, 140046276.05): 16199,
    ("2026-05-06", 393925.0, 139971276.05): 16198,
    ("2026-05-06", 16499.52, 139577351.05): 16197,
    ("2026-05-06", 778016.26, 139560851.53): 16196,
    ("2026-05-06", 148717.0, 138782835.27): 16195,
    ("2026-05-06", 266283.0, 138634118.27): 16194,
    ("2026-05-06", 68000.0, 138367835.27): 16193,
    ("2026-05-06", 121.0, 138299835.27): 16192,
    ("2026-05-06", 14462122.74, 138299956.27): 16191,
    ("2026-05-06", 121.0, 152762079.01): 16190,
    ("2026-05-06", 11932249.79, 152762200.01): 16189,
    ("2026-05-06", 118130.33, 164694449.8): 16188,
    ("2026-05-06", 121.0, 164576319.47): 16187,
    ("2026-05-06", 329891.14, 164576440.47): 16186,
    ("2026-05-06", 121.0, 164906331.61): 16185,
    ("2026-05-06", 1817474.95, 164906452.61): 16184,
    ("2026-05-06", 121.0, 166723927.56): 16183,
    ("2026-05-06", 1997700.0, 166724048.56): 16182,
    ("2026-05-06", 121.0, 168721748.56): 16181,
    ("2026-05-06", 2076625.4, 168721869.56): 16180,
    ("2026-05-06", 100000.0, 170798494.96): 16179,
    ("2026-05-06", 594337.61, 170698494.96): 16178,
    ("2026-05-06", 149124.13, 170104157.35): 16177,
    ("2026-05-06", 199832.17, 169955033.22): 16176,
    ("2026-05-06", 231503.32, 169755201.05): 16175,
    ("2026-05-06", 300000.0, 169523697.73): 16174,
    ("2026-05-06", 12256.2, 169823697.73): 16173,
    ("2026-05-06", 227468.0, 169811441.53): 16172,
    ("2026-05-06", 487754.0, 169583973.53): 16171,
    ("2026-05-06", 99414.12, 169096219.53): 16170,
    ("2026-05-06", 89042.11, 168996805.41): 16169,
    ("2026-05-06", 97251.0, 168907763.3): 16168,
    ("2026-05-06", 455976.64, 168810512.3): 16167,
    ("2026-05-06", 172500.0, 168354535.66): 16166,
    ("2026-05-06", 514875.4, 168182035.66): 16165,
    ("2026-05-06", 52335.8, 167667160.26): 16164,
    ("2026-05-06", 72580.74, 167614824.46): 16163,
    ("2026-05-06", 210830.0, 167542243.72): 16162,
    ("2026-05-06", 1000000.0, 167331413.72): 16161,
    ("2026-05-06", 125821.46, 166331413.72): 16160,
    ("2026-05-05", 65701.32, 166205592.26): 16159,
    ("2026-05-05", 104296.28, 166271293.58): 16158,
    ("2026-05-05", 138.42, 166375589.86): 16157,
    ("2026-05-05", 677524.0, 166375728.28): 16156,
    ("2026-05-05", 70000.0, 165698204.28): 16155,
    ("2026-05-05", 109900.0, 165628204.28): 16154,
    ("2026-05-05", 30000.0, 165518304.28): 16153,
    ("2026-05-05", 166800.0, 165488304.28): 16152,
    ("2026-05-05", 315000.0, 165321504.28): 16151,
    ("2026-05-05", 155919.52, 165006504.28): 16150,
    ("2026-05-05", 91250.0, 164850584.76): 16149,
    ("2026-05-05", 120314.42, 164759334.76): 16148,
    ("2026-05-05", 70000.0, 164639020.34): 16147,
    ("2026-05-05", 463078.41, 164569020.34): 16146,
    ("2026-05-05", 554352.66, 164105941.93): 16145,
    ("2026-05-05", 367043.0, 163551589.27): 16144,
    ("2026-05-05", 951878.71, 163184546.27): 16143,
    ("2026-05-05", 150000.0, 162232667.56): 16142,
    ("2026-05-05", 641000.0, 162082667.56): 16141,
    ("2026-05-05", 160000.0, 161441667.56): 16140,
    ("2026-05-05", 121.0, 161281667.56): 16139,
    ("2026-05-05", 847000.0, 161281788.56): 16138,
    ("2026-05-05", 82536.22, 162128788.56): 16137,
    ("2026-05-05", 121.0, 162046252.34): 16136,
    ("2026-05-05", 700000.0, 162046373.34): 16135,
    ("2026-05-05", 121.0, 162746373.34): 16134,
    ("2026-05-05", 721000.0, 162746494.34): 16133,
    ("2026-05-05", 95022.0, 163467494.34): 16132,
    ("2026-05-05", 65072.07, 163372472.34): 16131,
    ("2026-05-05", 121.0, 163307400.27): 16130,
    ("2026-05-05", 1900000.0, 163307521.27): 16129,
    ("2026-05-05", 18.15, 165207521.27): 16128,
    ("2026-05-05", 276000.0, 165207539.42): 16127,
    ("2026-05-05", 102294.0, 165483539.42): 16126,
    ("2026-05-05", 247374.55, 165381245.42): 16125,
    ("2026-05-05", 340500.0, 165133870.87): 16124,
    ("2026-05-05", 234413.74, 164793370.87): 16123,
    ("2026-05-05", 80000.0, 164558957.13): 16122,
    ("2026-05-05", 50925.0, 164478957.13): 16121,
    ("2026-05-05", 121.0, 164428032.13): 16120,
    ("2026-05-05", 321600.0, 164428153.13): 16119,
    ("2026-05-05", 121.0, 164749753.13): 16118,
    ("2026-05-05", 352765.0, 164749874.13): 16117,
    ("2026-05-05", 121.0, 165102639.13): 16116,
    ("2026-05-05", 854367.4, 165102760.13): 16115,
    ("2026-05-05", 88172.15, 165957127.53): 16114,
    ("2026-05-05", 121.0, 165868955.38): 16113,
    ("2026-05-05", 375000.0, 165869076.38): 16112,
    ("2026-05-05", 121.0, 166244076.38): 16111,
    ("2026-05-05", 800000.0, 166244197.38): 16110,
    ("2026-05-05", 121.0, 167044197.38): 16109,
    ("2026-05-05", 320095.0, 167044318.38): 16108,
    ("2026-05-05", 121.0, 167364413.38): 16107,
    ("2026-05-05", 969500.0, 167364534.38): 16106,
    ("2026-05-05", 121.0, 168334034.38): 16105,
    ("2026-05-05", 567848.0, 168334155.38): 16104,
    ("2026-05-05", 121.0, 168902003.38): 16103,
    ("2026-05-05", 688345.35, 168902124.38): 16102,
    ("2026-05-05", 121.0, 169590469.73): 16101,
    ("2026-05-05", 669804.1, 169590590.73): 16100,
    ("2026-05-05", 419393.89, 170260394.83): 16099,
    ("2026-05-05", 32237.0, 169841000.94): 16098,
    ("2026-05-05", 68000.0, 169808763.94): 16097,
    ("2026-05-05", 295000.0, 169740763.94): 16096,
    ("2026-05-05", 277537.86, 169445763.94): 16095,
    ("2026-05-05", 155031.29, 169168226.08): 16094,
    ("2026-05-05", 493404.87, 169013194.79): 16093,
    ("2026-05-05", 263436.51, 168519789.92): 16092,
    ("2026-05-05", 452516.1, 168256353.41): 16091,
    ("2026-05-05", 251000.0, 167803837.31): 16090,
    ("2026-05-05", 1000000.0, 167552837.31): 16089,
    ("2026-05-05", 135994.49, 166552837.31): 16088,
    ("2026-05-05", 367155.0, 166416842.82): 16087,
    ("2026-05-05", 293775.39, 166049687.82): 16086,
    ("2026-05-05", 115747.91, 165755912.43): 16085,
    ("2026-05-05", 93885.3, 165640164.52): 16084,
    ("2026-05-05", 54830.81, 165546279.22): 16083,
    ("2026-05-05", 354792.41, 165491448.41): 16082,
    ("2026-05-05", 18.15, 165136656.0): 16081,
    ("2026-05-05", 261000.0, 165136674.15): 16080,
    ("2026-05-05", 217000.0, 165397674.15): 16079,
    ("2026-05-05", 94107.5, 165614674.15): 16078,
    ("2026-05-05", 12948.23, 165708781.65): 16077,
    ("2026-05-05", 250000.0, 165721729.88): 16076,
    ("2026-05-05", 423918.94, 165471729.88): 16075,
    ("2026-05-05", 136798.74, 165047810.94): 16074,
    ("2026-05-05", 296683.07, 164911012.2): 16073,
    ("2026-05-05", 218558.0, 164614329.13): 16072,
    ("2026-05-05", 58922.85, 164395771.13): 16071,
    ("2026-05-05", 1074589.0, 164336848.28): 16070,
    ("2026-05-05", 34371.07, 163262259.28): 16069,
    ("2026-05-05", 1230952.0, 163227888.21): 16068,
    ("2026-05-05", 100.0, 161996936.21): 16067,
    ("2026-05-05", 79315.3, 161997036.21): 16066,
    ("2026-05-05", 346238.57, 161917720.91): 16065,
    ("2026-05-05", 322611.37, 161571482.34): 16064,
    ("2026-05-05", 883557.0, 161248870.97): 16063,
    ("2026-05-05", 422089.87, 160365313.97): 16062,
    ("2026-05-04", 214010.83, 159943224.1): 16061,
    ("2026-05-04", 92000.0, 160157234.93): 16060,
    ("2026-05-04", 70000.0, 160065234.93): 16059,
    ("2026-05-04", 434954.63, 159995234.93): 16058,
    ("2026-05-04", 40150.0, 159560280.3): 16057,
    ("2026-05-04", 101600.0, 159520130.3): 16056,
    ("2026-05-04", 90000.0, 159418530.3): 16055,
    ("2026-05-04", 800000.0, 159328530.3): 16054,
    ("2026-05-04", 190247.0, 158528530.3): 16053,
    ("2026-05-04", 373859.25, 158338283.3): 16052,
    ("2026-05-04", 80350.0, 157964424.05): 16051,
    ("2026-05-04", 450000.0, 157884074.05): 16050,
    ("2026-05-04", 283325.51, 157434074.05): 16049,
    ("2026-05-04", 673682.0, 157150748.54): 16048,
    ("2026-05-04", 170000.0, 156477066.54): 16047,
    ("2026-05-04", 25500.0, 156307066.54): 16046,
    ("2026-05-04", 500000.0, 156281566.54): 16045,
    ("2026-05-04", 500000.0, 155781566.54): 16044,
    ("2026-05-04", 200328.37, 155281566.54): 16043,
    ("2026-05-04", 107520.0, 155081238.17): 16042,
    ("2026-05-04", 234586.43, 154973718.17): 16041,
    ("2026-05-04", 388373.38, 154739131.74): 16040,
    ("2026-05-04", 67400.0, 154350758.36): 16039,
    ("2026-05-04", 544984.75, 154283358.36): 16038,
    ("2026-05-04", 148354.87, 153738373.61): 16037,
    ("2026-05-04", 117540.04, 153590018.74): 16036,
    ("2026-05-04", 35385.0, 153472478.7): 16035,
    ("2026-05-04", 85678.58, 153437093.7): 16034,
    ("2026-05-04", 643574.33, 153351415.12): 16033,
    ("2026-05-04", 398473.0, 152707840.79): 16032,
    ("2026-05-04", 100000.0, 152309367.79): 16031,
    ("2026-05-04", 500000.0, 152209367.79): 16030,
    ("2026-05-04", 295002.04, 151709367.79): 16029,
    ("2026-05-04", 234045.83, 151414365.75): 16028,
    ("2026-05-04", 9700.0, 151180319.92): 16027,
    ("2026-05-04", 68000.0, 151170619.92): 16026,
    ("2026-05-04", 164164.5, 151102619.92): 16025,
    ("2026-05-04", 51450.0, 150938455.42): 16024,
    ("2026-05-04", 164037.31, 150887005.42): 16023,
    ("2026-05-04", 149516.0, 150722968.11): 16022,
    ("2026-05-04", 100000.0, 150573452.11): 16021,
    ("2026-05-04", 106581.87, 150473452.11): 16020,
    ("2026-05-04", 813876.62, 150366870.24): 16019,
    ("2026-05-04", 503970.35, 149552993.62): 16018,
    ("2026-05-04", 908018.35, 149049023.27): 16017,
    ("2026-05-04", 193009.0, 148141004.92): 16016,
    ("2026-05-04", 74650.0, 147947995.92): 16015,
    ("2026-05-04", 123361.62, 147873345.92): 16014,
    ("2026-05-04", 478368.76, 147749984.3): 16013,
    ("2026-05-04", 153033.87, 147271615.54): 16012,
    ("2026-05-04", 268934.0, 147118581.67): 16011,
    ("2026-05-04", 69800.0, 146849647.67): 16010,
    ("2026-05-04", 347257.52, 146779847.67): 16009,
    ("2026-05-04", 269713.03, 146432590.15): 16008,
    ("2026-05-04", 454176.38, 146162877.12): 16007,
    ("2026-05-04", 86227.37, 145708700.74): 16006,
    ("2026-05-04", 33750.0, 145622473.37): 16005,
    ("2026-05-04", 562474.37, 145588723.37): 16004,
    ("2026-05-04", 97765.66, 145026249.0): 16003,
    ("2026-05-04", 211098.05, 144928483.34): 16002,
    ("2026-05-04", 183709.39, 144717385.29): 16001,
    ("2026-05-04", 199323.0, 144533675.9): 16000,
    ("2026-05-04", 75000.0, 144334352.9): 15999,
    ("2026-05-04", 308242.59, 144259352.9): 15998,
    ("2026-05-04", 154483.02, 143951110.31): 15997,
    ("2026-05-04", 346523.86, 143796627.29): 15996,
    ("2026-05-04", 435800.0, 143450103.43): 15995,
    ("2026-05-04", 122989.55, 143014303.43): 15994,
    ("2026-05-04", 619046.89, 142516933.41): 15990,
    ("2026-05-04", 321000.0, 141897886.52): 15989,
    ("2026-05-04", 465000.0, 141576886.52): 15988,
    ("2026-05-04", 493757.97, 141111886.52): 15987,
    ("2026-05-04", 40957.0, 140200289.72): 15984,
    ("2026-05-04", 211170.05, 140159332.72): 15983,
    ("2026-05-04", 284373.21, 139948162.67): 15982,
    ("2026-05-04", 199396.12, 139305608.02): 15980,
    ("2026-05-04", 22000.0, 139106211.9): 15979,
    ("2026-05-04", 319323.33, 139084211.9): 15978,
    ("2026-05-04", 250000.0, 135522565.0): 15961,
    ("2026-05-04", 18900.0, 135272565.0): 15960,
    ("2026-05-04", 660547.18, 135127714.03): 15958,
    ("2026-05-04", 26000.0, 134467166.85): 15957,
    ("2026-05-04", 187701.0, 131169207.84): 15943,
    ("2026-05-04", 134000.0, 130981506.84): 15942,
    ("2026-05-04", 127050.0, 129470940.99): 15935,
    ("2026-04-30", 94040.0, 124614898.09): 15916,
    ("2026-04-30", 2315413.0, 124330858.09): 15912,
    ("2026-04-30", 53026.76, 122015445.09): 15911,
    ("2026-04-30", 200940.18, 120760200.23): 15903,
    ("2026-04-30", 500000.0, 120559260.05): 15902,
    ("2026-04-30", 500000.0, 119986278.06): 15900,
    ("2026-04-30", 353468.64, 119338291.35): 15898,
    ("2026-04-30", 180266.7, 118675389.59): 15896,
    ("2026-04-30", 245752.92, 118495122.89): 15895,
    ("2026-04-30", 109140.61, 117569369.97): 15893,
    ("2026-04-30", 338256.0, 117285462.44): 15890,
    ("2026-04-30", 132819.8, 111502623.32): 15887,
    ("2026-04-30", 258807.89, 109609806.13): 15878,
    ("2026-04-30", 443275.0, 107356274.32): 15872,
    ("2026-04-30", 100000.0, 106912999.32): 15871,
    ("2026-04-30", 293769.0, 106420013.12): 15867,
    ("2026-04-30", 16684.56, 106126244.12): 15866,
    ("2026-04-30", 227000.0, 104361295.14): 15854,
    ("2026-04-29", 150000.0, 103715277.16): 15844,
    ("2026-04-29", 58952.97, 102772077.16): 15842,
    ("2026-04-29", 94056.77, 102304909.51): 15837,
    ("2026-04-29", 2400.0, 100218969.77): 15827,
    ("2026-04-29", 127388.95, 100216569.77): 15826,
    ("2026-04-29", 200400.0, 100089180.82): 15825,
    ("2026-04-29", 19000.0, 101062534.13): 15812,
    ("2026-04-29", 155392.94, 100348003.99): 15802,
    ("2026-04-29", 100000.0, 140620853.05): 15797,
    ("2026-04-29", 65152.13, 142882088.17): 15793,
    ("2026-04-29", 64401.24, 142607740.48): 15790,
    ("2026-04-29", 185473.0, 140764836.29): 15785,
    ("2026-04-29", 60281.95, 140559363.29): 15783,
    ("2026-04-29", 2000.0, 140429453.58): 15781,
    ("2026-04-29", 4000.0, 138138600.26): 15776,
    ("2026-04-29", 422447.0, 135858401.53): 15764,
    ("2026-04-29", 200000.0, 132124357.68): 15747,
    ("2026-04-28", 1952800.0, 131231902.13): 15740,
    ("2026-04-28", 235969.95, 127180736.09): 15714,
    ("2026-04-28", 151852.31, 126227911.21): 15707,
    ("2026-04-28", 337633.0, 125316223.75): 15699,
    ("2026-04-28", 303283.83, 127029513.49): 15688,
    ("2026-04-28", 91313.91, 126064634.64): 15684,
    ("2026-04-28", 121323.46, 125689920.73): 15682,
    ("2026-04-28", 363311.06, 125297347.27): 15680,
    ("2026-04-28", 692569.19, 121120461.86): 15674,
    ("2026-04-28", 291675.0, 118955087.64): 15668,
    ("2026-04-27", 200424.0, 114220352.31): 15644,
    ("2026-04-27", 260000.0, 151357702.99): 15619,
    ("2026-04-27", 511400.0, 150803533.79): 15615,
    ("2026-04-27", 370000.0, 150183924.49): 15612,
    ("2026-04-27", 175500.0, 149717924.49): 15610,
    ("2026-04-27", 181043.64, 149350485.01): 15607,
    ("2026-04-27", 173959.84, 148625466.17): 15603,
    ("2026-04-27", 195700.0, 148451506.33): 15602,
    ("2026-04-27", 84932.92, 147868160.64): 15598,
    ("2026-04-27", 307812.63, 146845011.52): 15596,
    ("2026-04-27", 88226.36, 146537198.89): 15595,
    ("2026-04-27", 928957.0, 143748600.88): 15589,
    ("2026-04-27", 181800.55, 142819643.88): 15588,
    ("2026-04-27", 172833.0, 141898853.81): 15584,
    ("2026-04-27", 1000000.0, 140997937.08): 15580,
    ("2026-04-27", 50000.0, 139750037.08): 15577,
    ("2026-04-27", 217483.0, 139533992.03): 15575,
    ("2026-04-27", 318253.54, 138247039.37): 15571,
    ("2026-04-27", 498367.92, 136265000.14): 15564,
    ("2026-04-27", 867619.53, 135606679.28): 15560,
    ("2026-04-27", 323412.34, 134739059.75): 15559,
    ("2026-04-27", 58570.31, 137334378.72): 15550,
    ("2026-04-27", 26354.05, 137205797.15): 15548,
    ("2026-04-27", 493217.91, 137179443.1): 15547,
    ("2026-04-27", 433000.0, 136488213.19): 15545,
    ("2026-04-27", 351000.0, 135188454.19): 15542,
    ("2026-04-27", 136649.68, 132827885.53): 15537,
    ("2026-04-27", 85000.0, 127931213.06): 15523,
    ("2026-04-27", 98000.0, 127846213.06): 15522,
    ("2026-04-27", 800000.0, 127748213.06): 15521,
    ("2026-04-27", 205000.0, 126854213.06): 15518,
    ("2026-04-27", 105494.0, 123617179.06): 15492,
    ("2026-04-27", 659500.0, 122722042.06): 15485,
    ("2026-04-27", 547282.96, 121603634.98): 15482,
    ("2026-04-24", 176101.14, 121006763.98): 15476,
    ("2026-04-24", 617200.0, 115632029.39): 15444,
    ("2026-04-24", 1500.0, 115014829.39): 15443,
    ("2026-04-24", 400000.0, 120213320.73): 15426,
    ("2026-04-24", 279286.01, 118746007.59): 15422,
    ("2026-04-24", 239800.0, 118466721.58): 15421,
    ("2026-04-24", 606087.43, 117329005.58): 15418,
    ("2026-04-24", 195893.6, 115927896.95): 15414,
    ("2026-04-24", 64490.17, 115008203.35): 15410,
    ("2026-04-24", 394488.0, 114943713.18): 15409,
    ("2026-04-24", 24727.5, 113808101.32): 15406,
    ("2026-04-24", 74887.41, 113783373.82): 15405,
    ("2026-04-24", 122420.24, 113095840.36): 15402,
    ("2026-04-24", 148205.0, 112973420.12): 15401,
    ("2026-04-23", 96522.0, 111940386.03): 15390,
    ("2026-04-23", 250000.0, 110871776.44): 15381,
    ("2026-04-23", 344290.0, 106885028.24): 15368,
    ("2026-04-23", 556400.0, 106540738.24): 15367,
    ("2026-04-23", 850100.0, 105903199.24): 15359,
    ("2026-04-23", 27636.22, 105053099.24): 15358,
    ("2026-04-23", 126448.07, 105008804.02): 15356,
    ("2026-04-23", 153282.0, 105535983.17): 15344,
    ("2026-04-23", 75160.0, 105206138.29): 15342,
    ("2026-04-23", 600000.0, 104359979.75): 15339,
    ("2026-04-23", 256815.42, 102486317.79): 15332,
    ("2026-04-23", 1630386.0, 99209775.07): 15321,
    ("2026-04-23", 966000.0, 98311328.9): 15312,
    ("2026-04-23", 349921.0, 96424586.9): 15308,
    ("2026-04-23", 223000.0, 94675580.45): 15303,
    ("2026-04-23", 50000.0, 94452580.45): 15302,
    ("2026-04-23", 381139.44, 94297580.45): 15300,
    ("2026-04-23", 50000.0, 93820441.01): 15298,
    ("2026-04-23", 60000.0, 93770441.01): 15297,
    ("2026-04-23", 108650.5, 93497528.01): 15294,
    ("2026-04-22", 461200.0, 91647047.92): 15271,
    ("2026-04-22", 328859.0, 88959010.79): 15260,
    ("2026-04-22", 161553.29, 86083224.27): 15253,
    ("2026-04-22", 167017.8, 84674933.58): 15250,
    ("2026-04-22", 87201.96, 83992716.82): 15247,
    ("2026-04-22", 296344.01, 82869789.86): 15243,
    ("2026-04-22", 36660.0, 81449526.85): 15235,
    ("2026-04-22", 1536485.92, 79881901.31): 15232,
    ("2026-04-22", 985822.0, 78345415.39): 15231,
    ("2026-04-22", 60954.3, 135231838.43): 15223,
    ("2026-04-22", 600000.0, 136448930.64): 15209,
    ("2026-04-22", 425492.65, 135120657.51): 15206,
    ("2026-04-22", 607726.99, 134695164.86): 15205,
    ("2026-04-22", 102385.86, 130142906.87): 15203,
    ("2026-04-22", 94247.98, 130040521.01): 15202,
    ("2026-04-22", 9825.8, 128303012.12): 15191,
    ("2026-04-22", 98436.55, 128293186.32): 15190,
    ("2026-04-21", 378357.3, 121710394.47): 15177,
    ("2026-04-21", 487444.19, 121332037.17): 15176,
    ("2026-04-21", 228200.0, 119202364.69): 15165,
    ("2026-04-21", 83100.29, 114820907.04): 15161,
    ("2026-04-21", 293772.0, 111761220.58): 15136,
    ("2026-04-21", 83519.0, 111435423.58): 15134,
    ("2026-04-21", 2022516.75, 110541628.48): 15128,
    ("2026-04-21", 405036.0, 104277737.62): 15112,
    ("2026-04-21", 942973.56, 103872701.62): 15111,
    ("2026-04-21", 279324.0, 102753454.79): 15108,
    ("2026-04-21", 191484.0, 102474130.79): 15107,
    ("2026-04-21", 657040.35, 99164373.93): 15098,
    ("2026-04-20", 90757.45, 98207547.59): 15089,
    ("2026-04-20", 90000.0, 98116790.14): 15088,
    ("2026-04-20", 900000.0, 96925452.59): 15078,
    ("2026-04-20", 160050.07, 135767395.56): 15052,
    ("2026-04-20", 127659.0, 135607345.49): 15051,
    ("2026-04-20", 114460.0, 132942050.22): 15038,
    ("2026-04-20", 121745.72, 132827590.22): 15037,
    ("2026-04-20", 232971.44, 132231261.5): 15033,
    ("2026-04-20", 93710.0, 131257205.38): 15026,
    ("2026-04-20", 151050.3, 130883123.38): 15022,
    ("2026-04-20", 112262.88, 127743144.57): 15010,
    ("2026-04-20", 177287.0, 126988103.21): 15004,
    ("2026-04-20", 137790.0, 126549941.31): 15001,
    ("2026-04-20", 126826.67, 124609427.83): 14990,
    ("2026-04-20", 67043.98, 120482971.28): 14981,
    ("2026-04-20", 206007.0, 118597247.3): 14970,
    ("2026-04-20", 709500.0, 118352915.3): 14968,
    ("2026-04-17", 16732.0, 110444235.39): 14947,
    ("2026-04-17", 892200.0, 110227503.39): 14943,
    ("2026-04-17", 300000.0, 108389945.98): 14937,
    ("2026-04-17", 50000.0, 108089945.98): 14936,
    ("2026-04-17", 294300.0, 107908775.52): 14934,
    ("2026-04-17", 997570.0, 109050186.3): 14909,
    ("2026-04-17", 144686.0, 107886317.2): 14907,
    ("2026-04-17", 312000.0, 107741631.2): 14906,
    ("2026-04-17", 259319.19, 104558528.87): 14896,
    ("2026-04-17", 777800.0, 98970414.02): 14874,
    ("2026-04-16", 398708.13, 93941082.05): 14861,
    ("2026-04-16", 300000.0, 93424373.92): 14858,
    ("2026-04-16", 19665.0, 92435148.92): 14850,
    ("2026-04-16", 50000.0, 92549880.94): 14839,
    ("2026-04-16", 236730.0, 90538684.76): 14802,
    ("2026-04-16", 573000.0, 89609142.01): 14798,
    ("2026-04-15", 717800.0, 84872331.06): 14778,
    ("2026-04-15", 159532.0, 82599591.68): 14740,
    ("2026-04-15", 111768.52, 82023147.92): 14738,
    ("2026-04-15", 17638.99, 81501775.04): 14734,
    ("2026-04-15", 144286.75, 81484136.05): 14733,
    ("2026-04-15", 771254.0, 81339849.3): 14732,
    ("2026-04-15", 327596.33, 76935872.23): 14724,
    ("2026-04-15", 323311.85, 76608275.9): 14723,
    ("2026-04-15", 102765.67, 75686898.92): 14719,
    ("2026-04-15", 178381.79, 73780535.71): 14713,
    ("2026-04-15", 70087.03, 73416083.84): 14711,
    ("2026-04-15", 132865.23, 73345996.81): 14710,
    ("2026-04-15", 171744.54, 73065783.47): 14708,
    ("2026-04-15", 189554.0, 72894038.93): 14707,
    ("2026-04-14", 98114.0, 68215455.96): 14662,
    ("2026-04-14", 60000.0, 121652018.69): 14647,
    ("2026-04-14", 668800.0, 114934236.63): 14626,
    ("2026-04-14", 84146.62, 113712952.05): 14623,
    ("2026-04-14", 402462.0, 113628805.43): 14622,
    ("2026-04-14", 40201.81, 113226343.43): 14621,
    ("2026-04-14", 157411.86, 113021608.62): 14619,
    ("2026-04-14", 838325.0, 112864196.76): 14618,
    ("2026-04-13", 473103.33, 106959640.51): 14603,
    ("2026-04-13", 100806.46, 104299242.65): 14599,
    ("2026-04-13", 322347.51, 183665213.19): 14559,
    ("2026-04-13", 193836.0, 176452087.71): 14535,
    ("2026-04-13", 71175.0, 176258251.71): 14534,
    ("2026-04-13", 169600.0, 171116292.82): 14517,
    ("2026-04-13", 354142.0, 170056016.18): 14511,
    ("2026-04-13", 399072.47, 168824685.14): 14506,
    ("2026-04-13", 62798.78, 173844144.99): 14489,
    ("2026-04-13", 262238.63, 168199228.55): 14468,
    ("2026-04-13", 163449.0, 164421959.91): 14447,
    ("2026-04-13", 800507.57, 159106238.43): 14428,
    ("2026-04-10", 86200.0, 157621658.24): 14411,
    ("2026-04-10", 100000.0, 157163233.24): 14407,
    ("2026-04-10", 50000.0, 156539022.35): 14403,
    ("2026-04-10", 110000.0, 156280141.14): 14400,
    ("2026-04-10", 313200.0, 156170141.14): 14399,
    ("2026-04-10", 189131.0, 154474941.14): 14394,
    ("2026-04-10", 90320.0, 148923818.38): 14378,
    ("2026-04-10", 142422.68, 171751917.33): 14325,
    ("2026-04-10", 442800.0, 171061196.7): 14317,
    ("2026-04-10", 1593300.0, 169975552.37): 14314,
    ("2026-04-10", 81571.43, 168382252.37): 14313,
    ("2026-04-10", 31509.6, 168139822.12): 14309,
    ("2026-04-10", 220000.0, 168108312.52): 14308,
    ("2026-04-09", 333116.0, 167360616.05): 14299,
    ("2026-04-09", 320121.37, 165879157.02): 14292,
    ("2026-04-09", 50000.0, 165409035.65): 14289,
    ("2026-04-09", 637287.92, 165296035.65): 14287,
    ("2026-04-09", 20000.0, 164614177.73): 14285,
    ("2026-04-09", 124795.49, 162632991.73): 14279,
    ("2026-04-09", 440200.0, 164389803.77): 14244,
    ("2026-04-09", 283606.0, 156828646.64): 14177,
    ("2026-04-08", 916139.64, 145981172.25): 14052,
    ("2026-04-08", 245613.0, 143775601.44): 14003,
    ("2026-04-08", 20.0, 155648297.28): 13945,
    ("2026-04-08", 73440.77, 155547107.28): 13941,
    ("2026-04-08", 315900.0, 152642762.34): 13930,
    ("2026-04-08", 390994.49, 152326862.34): 13929,
    ("2026-04-07", 171.17, 149760448.16): 13913,
    ("2026-04-07", 94632.0, 148854535.39): 13906,
    ("2026-04-07", 557400.0, 140162049.18): 13718,
    ("2026-04-07", 1000000.0, 140008713.88): 13689,
    ("2026-04-07", 72241.95, 131194156.26): 13658,
    ("2026-04-07", 121134.92, 131121914.31): 13657,
    ("2026-04-07", 102849.7, 129129917.43): 13645,
    ("2026-04-06", 96000.0, 126020617.74): 13617,
    ("2026-04-06", 372300.0, 124315810.65): 13611,
    ("2026-04-06", 35000.0, 119294550.18): 13559,
    ("2026-04-06", 104902.38, 121811701.58): 13454,
    ("2026-04-06", 57918.35, 180222001.68): 13394,
    ("2026-04-06", 158450.0, 181830932.75): 13372,
    ("2026-04-06", 159120.0, 181637018.75): 13370,
    ("2026-04-06", 1.0, 180656870.96): 13364,
    ("2026-04-06", 65380.0, 180283628.96): 13362,
    ("2026-04-06", 1.0, 172415714.87): 13333,
    ("2026-04-06", 434212.56, 171909336.87): 13330,
    ("2026-04-06", 152810.0, 150306496.66): 13164,
    ("2026-04-06", 278091.22, 149073432.58): 13160,
    ("2026-04-01", 200000.0, 134322542.21): 13056,
    ("2026-04-01", 318369.62, 137557039.37): 12992,
    ("2026-04-01", 189291.06, 135958520.35): 12987,
    ("2026-04-01", 200000.0, 132328983.9): 12976,
    ("2026-03-31", 74944.71, 128392914.79): 12953,
    ("2026-03-31", 389432.87, 128222970.08): 12951,
    ("2026-03-31", 50000.0, 125811697.18): 12842,
    ("2026-03-31", 275481.0, 118549439.65): 12795,
    ("2026-03-30", 207658.85, 108338222.2): 12757,
    ("2026-03-30", 495000.0, 130169080.84): 12707,
    ("2026-03-30", 1287314.0, 194261314.16): 12591,
    ("2026-03-30", 1000000.0, 192974000.16): 12590,
    ("2026-03-27", 1339000.0, 186225433.56): 12550,
    ("2026-03-27", 100394.0, 180139643.38): 12525,
    ("2026-03-27", 700000.0, 188740405.2): 12495,
    ("2026-03-27", 78296.32, 197441507.23): 12471,
    ("2026-03-27", 113824.71, 194028134.91): 12464,
    ("2026-03-27", 40565.5, 193300807.2): 12460,
    ("2026-03-27", 495909.0, 189823361.7): 12452,
    ("2026-03-27", 99707.06, 192710464.32): 12435,
    ("2026-03-26", 215900.0, 169899030.91): 12288,
    ("2026-03-26", 95000.0, 167927056.95): 12281,
    ("2026-03-26", 598000.0, 167832056.95): 12280,
    ("2026-03-25", 50000.0, 156426488.24): 12237,
    ("2026-03-25", 75860.0, 156376488.24): 12236,
    ("2026-03-25", 406822.0, 155850628.24): 12234,
    ("2026-03-25", 42700.0, 154770552.22): 12231,
    ("2026-03-25", 384700.0, 154334531.13): 12229,
    ("2026-03-25", 162766.0, 178094693.47): 12198,
    ("2026-03-25", 50000.0, 177376531.47): 12196,
    ("2026-03-25", 50000.0, 176828128.95): 12193,
    ("2026-03-25", 50000.0, 174043612.51): 12178,
    ("2026-03-25", 160878.0, 250483559.44): 12148,
    ("2026-03-25", 442910.19, 249928363.57): 12144,
    ("2026-03-25", 102500.0, 240779867.7): 12112,
    ("2026-03-25", 137846.46, 228454021.29): 12044,
    ("2026-03-25", 30044.72, 227632257.35): 12040,
    ("2026-03-25", 1314688.02, 218938468.04): 12014,
    ("2026-03-25", 233472.51, 208121466.78): 11985,
    ("2026-03-20", 50000.0, 174178351.08): 11778,
    ("2026-03-20", 50000.0, 168824057.12): 11747,
    ("2026-03-20", 1.0, 165496540.07): 11735,
    ("2026-03-20", 1.0, 165370192.07): 11732,
    ("2026-03-20", 56000.0, 162340571.33): 11711,
    ("2026-03-19", 1.0, 149674967.97): 11652,
    ("2026-03-19", 158070.3, 170843919.48): 11619,
    ("2026-03-19", 413770.0, 167515880.1): 11596,
    ("2026-03-18", 183372.0, 147148556.29): 11536,
    ("2026-03-18", 139228.48, 147190172.46): 11510,
    ("2026-03-18", 50000.0, 144317882.93): 11503,
    ("2026-03-17", 111655.36, 180874013.95): 11374,
    ("2026-03-17", 116686.95, 175766456.45): 11359,
    ("2026-03-16", 108293.36, 159715709.16): 11279,
    ("2026-03-16", 150576.0, 154104508.64): 11249,
    ("2026-03-16", 31715.8, 150290259.36): 11227,
    ("2026-03-16", 300000.0, 149638038.64): 11220,
    ("2026-03-16", 71605.42, 144919500.96): 11197,
    ("2026-03-16", 207398.43, 139385723.08): 11179,
    ("2026-03-16", 57477.67, 138819754.46): 11177,
    ("2026-03-16", 281728.34, 137269879.26): 11172,
    ("2026-03-13", 500000.0, 95374237.83): 10903,
    ("2026-03-13", 1044113.0, 94716222.83): 10901,
    ("2026-03-13", 60000.0, 92157977.83): 10893,
    ("2026-03-13", 227829.0, 84284900.32): 10870,
    ("2026-03-13", 394864.0, 81447298.87): 10860,
    ("2026-03-12", 600.0, 74739438.05): 10817,
    ("2026-03-12", 246227.52, 96226140.26): 10709,
    ("2026-03-12", 366394.09, 95248979.42): 10704,
    ("2026-03-12", 261568.28, 94882585.33): 10703,
    ("2026-03-11", 136769.7, 79724909.95): 10666,
    ("2026-03-10", 203263.0, 73358386.22): 10589,
    ("2026-03-10", 148892.0, 71776989.5): 10580,
    ("2026-03-10", 219565.45, 71612161.65): 10545,
    ("2026-03-10", 120800.0, 67808607.6): 10534,
    ("2026-03-10", 297971.0, 66569357.52): 10525,
    ("2026-03-09", 50000.0, 58004380.54): 10498,
    ("2026-03-09", 175260.0, 57954380.54): 10497,
    ("2026-03-09", 50000.0, 57779120.54): 10496,
    ("2026-03-09", 260600.0, 60965221.88): 10427,
    ("2026-03-09", 80236.74, 54482414.97): 10416,
    ("2026-03-09", 108080.0, 48294891.55): 10396,
    ("2026-03-09", 241535.0, 37859765.41): 10357,
    ("2026-03-09", 100000.0, 37618230.41): 10356,
    ("2026-03-09", 250000.0, 37066730.41): 10352,
    ("2026-03-09", 439500.0, 36534035.41): 10350,
    ("2026-03-09", 900000.0, 36094535.41): 10349,
    ("2026-03-09", 883800.0, 35194535.41): 10348,
    ("2026-03-09", 900000.0, 34310735.41): 10347,
    ("2026-03-09", 497500.0, 33410735.41): 10346,
    ("2026-03-05", 274347.0, 19218327.81): 10232,
    ("2026-03-05", 50000.0, 19269912.81): 10222,
    ("2026-03-05", 60000.0, 19060243.07): 10195,
    ("2026-03-05", 865500.0, 18805243.07): 10192,
    ("2026-03-04", 159420.0, 13055054.4): 10171,
    ("2026-03-04", 653893.0, 22287905.92): 10159,
    ("2026-03-04", 211616.0, 21150350.92): 10155,
    ("2026-03-04", 184456.0, 35467516.55): 10146,
    ("2026-03-04", 12480.0, 35283060.55): 10145,
    ("2026-03-04", 100000.0, 35270580.55): 10144,
    ("2026-03-04", 293238.0, 48457116.55): 10120,
    ("2026-03-03", 194652.0, 39269492.91): 10080,
    ("2026-03-03", 269100.0, 55867963.8): 10046,
    ("2026-03-02", 72829.0, 80182870.19): 9931,
    ("2026-03-02", 22000.0, 75141362.18): 9899,
    ("2026-02-27", 25000.0, 69404446.3): 9869,
    ("2026-02-27", 50000.0, 69045446.3): 9866,
    ("2026-02-27", 100000.0, 69052402.3): 9849,
    ("2026-02-27", 50000.0, 68529547.3): 9845,
    ("2026-02-27", 50000.0, 69920673.3): 9824,
    ("2026-02-27", 150000.0, 111172766.61): 9762,
    ("2026-02-26", 600000.0, 109509704.46): 9750,
    ("2026-02-26", 50000.0, 107078715.46): 9742,
    ("2026-02-26", 50000.0, 106665151.46): 9740,
    ("2026-02-26", 3000.0, 106615151.46): 9739,
    ("2026-02-26", 35000.0, 106445181.46): 9737,
    ("2026-02-26", 50000.0, 106110181.46): 9735,
    ("2026-02-26", 6000.0, 109842502.46): 9731,
    ("2026-02-26", 50000.0, 109260766.46): 9728,
    ("2026-02-26", 80000.0, 110295084.43): 9716,
    ("2026-02-26", 50000.0, 110215084.43): 9715,
    ("2026-02-26", 100000.0, 108535515.43): 9707,
    ("2026-02-26", 50000.0, 104686409.43): 9682,
    ("2026-02-25", 1425.0, 116167695.66): 9643,
    ("2026-02-23", 178.79, 223457714.43): 9339,
    ("2026-02-23", 66500.0, 204257807.97): 9287,
    ("2026-02-20", 64000.0, 193728799.4): 9178,
    ("2026-02-20", 450000.0, 188963011.4): 9165,
    ("2026-02-20", 501000.0, 207546824.51): 9141,
    ("2026-02-20", 140200.0, 207045824.51): 9140,
    ("2026-02-19", 50000.0, 204123579.71): 9120,
    ("2026-02-19", 55000.0, 204023579.71): 9118,
    ("2026-02-19", 100000.0, 203462339.71): 9115,
    ("2026-02-19", 212477.0, 193001946.83): 9039,
    ("2026-02-18", 100000.0, 183561968.76): 8960,
    ("2026-02-18", 50000.0, 182847639.76): 8956,
    ("2026-02-18", 50000.0, 180067903.26): 8942,
    ("2026-02-18", 50000.0, 175575519.26): 8931,
    ("2026-02-18", 100000.0, 175375519.26): 8929,
    ("2026-02-18", 50000.0, 176075640.26): 8926,
    ("2026-02-18", 50000.0, 186016840.43): 8896,
    ("2026-02-18", 150000.0, 192984755.13): 8886,
    ("2026-02-18", 100000.0, 204216145.18): 8812,
    ("2026-02-18", 50000.0, 204041345.18): 8810,
    ("2026-02-18", 135000.0, 169881792.91): 8688,
    ("2026-02-18", 46000.0, 151032657.16): 8637,
    ("2026-02-12", 122000.0, 115846410.9): 8408,
    ("2026-02-12", 917000.0, 132856206.32): 8362,
    ("2026-02-10", 1443580.0, 174395945.25): 8159,
    ("2026-02-09", 37205.0, 162273168.12): 8069,
    ("2026-02-09", 271064.0, 227930001.32): 8016,
    ("2026-02-09", 552896.0, 227276437.32): 8014,
    ("2026-02-09", 150000.0, 234510307.96): 7975,
    ("2026-02-06", 579.41, 185452843.75): 7750,
    ("2026-02-06", 443769.0, 181697677.34): 7740,
    ("2026-02-06", 400000.0, 168903694.16): 7615,
    ("2026-02-05", 14200.0, 182316186.91): 7246,
    ("2026-02-04", 624000.0, 157595411.54): 7158,
    ("2026-02-04", 64961.0, 196058986.55): 7058,
    ("2026-02-04", 60000.0, 187803988.55): 7053,
    ("2026-02-03", 279000.0, 188167333.69): 6939,
    ("2026-02-02", 24081.0, 196655223.51): 6798,
    ("2026-02-02", 82000.0, 185202274.51): 6785,
        }
        movs = db.query(MovimientoBanco).filter(MovimientoBanco.extracto_id == 19).all()
        fixed = 0
        for m in movs:
            fecha_iso = m.fecha.isoformat() if m.fecha else None
            if fecha_iso is None or m.monto is None or m.saldo is None:
                continue
            key = (fecha_iso, round(float(m.monto), 2), round(float(m.saldo), 2))
            real_orden = ORDEN_MAP.get(key)
            if real_orden is not None:
                m.orden = real_orden
                fixed += 1
        db.commit()
        logger.info("Fix extracto 19: orden restaurado en %d movimientos", fixed)
        db.close()
    except Exception as ex:
        logger.warning("Fix extracto 19 orden: %s", ex)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.debug and settings.secret_key == "dev-secret-key-CAMBIAR-en-produccion":
        logger.critical("SECRET_KEY usa el valor por defecto — seteá SECRET_KEY en Render")
    t = threading.Thread(target=_init_db, daemon=True)
    t.start()
    # Scheduler de backup diario por email (no-op si RESEND_API_KEY no esta)
    try:
        from app.services.backup_scheduler import (
            start_backup_scheduler, stop_backup_scheduler,
            start_alertas_push_job, start_token_cleanup_job,
        )
        start_backup_scheduler()
        start_alertas_push_job()       # 10:00 ART — push cheques/movs urgentes
        start_token_cleanup_job()      # 03:30 ART — purga tokens revocados
    except Exception as ex:
        logger.warning("No se pudo iniciar schedulers: %s", ex)
    yield
    try:
        stop_backup_scheduler()
    except Exception:
        pass


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    debug=settings.debug,
    lifespan=lifespan,
    default_response_class=JSONResponse,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip: comprime respuestas >500 bytes. Reduce 60-80% los bytes en endpoints
# largos (movimientos, planillas, backups, asientos contables, dashboard).
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS: cerrado al dominio de produccion + previews de Vercel + dev local.
# Cualquier otro origen es rechazado.
import os as _os
_extra_origins = [o.strip() for o in _os.getenv("EXTRA_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://conciliacion-bancaria-ten.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
        *_extra_origins,
    ],
    allow_origin_regex=r"https://conciliacion-bancaria-.*-julietaarrazates-projects\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Headers de seguridad bancaria
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(extractos.router)
app.include_router(extractos.conciliaciones_router)
app.include_router(planillas.router)
app.include_router(historial.router)
app.include_router(auditoria.router)
app.include_router(admin.router)
app.include_router(clientes_dir.router)
app.include_router(organizaciones.router)
app.include_router(liquidaciones.router)
app.include_router(caja.router)
app.include_router(contabilidad.router)
app.include_router(cheques.router)
app.include_router(pagos_gastos.router)
app.include_router(papelera.router)
app.include_router(backup_admin.router)
app.include_router(analisis.router)
app.include_router(search_router.router)
app.include_router(public_router.router)
app.include_router(push_router.router)


@app.get("/")
def read_root():
    return {"status": "ok", "app": settings.app_name, "version": "2.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)[:100]}
