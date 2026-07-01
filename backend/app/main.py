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
from app.db_safety import SAFETY_NET_DDL
from app.routers import auth, extractos, planillas, me, admin, auditoria, historial, clientes_dir
from app.routers import organizaciones
from app.routers import liquidaciones
from app.routers import caja
from app.routers import contabilidad
from app.routers import cheques
from app.routers import pagos
from app.routers import papelera
from app.routers import backup_admin
from app.routers import analisis
from app.routers import search as search_router
from app.routers import public_router
from app.routers import push_router
from app.routers import agente
from app.routers import tarjetas
from app.routers import iva
from app.routers import monotributo
from app.routers import iibb
from app.routers import sueldos
from app.routers import google_auth
from app.routers import arca
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog, PasswordResetToken  # noqa: F401
from app.models.egreso import Egreso, CategoriaEgreso  # noqa: F401
from app.models.monotributo import CategoriaMonotributo, MonotributoConfig, ControlMonotributo  # noqa: F401
from app.models.iibb import JurisdiccionIIBB, IIBBConfig, ProyeccionIIBB  # noqa: F401
from app.models.sueldos import (  # noqa: F401
    ConvenioColectivo, CategoriaConvenio, Empleado, ConfigSueldos,
    EscalaGanancias, LiquidacionSueldoPeriodo, DetalleLiquidacionEmpleado,
)
from app.models.caja import ArqueoDiario  # noqa: F401
from app.models.push_subscription import PushSubscription  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401
from app.models.login_approval import LoginApproval  # noqa: F401
from app.models.twofa_code import TwofaCode  # noqa: F401
from app.models.arca import ArcaConfig, ComprobanteArca  # noqa: F401

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

# Sentry — monitoreo de errores (opt-in, requiere SENTRY_DSN en env)
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.05,
        send_default_pii=False,
        environment="production" if not settings.debug else "development",
    )
    logger.info("Sentry inicializado")

# Rate limiter — protección brute force
limiter = Limiter(key_func=get_remote_address)


def _run_alembic():
    """Sella la DB en la revisión head de Alembic (no corre `upgrade`).

    El esquema lo mantienen `Base.metadata.create_all()` + los safety-nets DDL
    idempotentes (`app/db_safety.py`), que ya construyen y mantienen todo. La cadena de
    migraciones está desincronizada del esquema real (`001` es un stamp baseline; 007–009
    referencian tablas viejas ya dropeadas — ver DATABASE_RULES / PROJECT_MEMORY D-8), así
    que correr `upgrade` intentaría migraciones derivadas contra un esquema que ya está al
    día y fallaría. Por eso solo SELLAMOS head: mantiene `alembic_version` reflejando la
    realidad (para tooling: history/autogenerate/stamp) sin ejecutar la cadena.
    `command.stamp(head)` crea la tabla `alembic_version` si no existe y es idempotente.
    """
    try:
        import os
        from alembic import command
        from alembic.config import Config

        # Path absoluto: backend/alembic.ini (relativo a este archivo: backend/app/main.py)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini = os.path.join(base_dir, "alembic.ini")
        logger.debug("alembic config: %s", alembic_ini)

        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")
        logger.info("Alembic sellado en head")
    except Exception as ex:
        logger.warning("Alembic error: %s", ex)

    # Safety net: DDL mínimo que debe existir aunque Alembic falle.
    # Fuente única e importable en app/db_safety.py (testeada en test_db_safety.py).
    _safety_cols = SAFETY_NET_DDL
    try:
        from sqlalchemy import text as _text
        with engine.connect() as _conn:
            for _sql in _safety_cols:
                _conn.execute(_text(_sql))
            _conn.commit()
    except Exception as ex:
        logger.warning("Safety net columnas: %s", ex)


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
        # Asientos — numero_asiento se usa en ordenamiento y numeración correlativa
        "CREATE INDEX IF NOT EXISTS idx_asientos_numero ON asientos(numero_asiento DESC)",
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
        # Cheques v2 — nueva columna banco_cuenta_id (banco usado al acreditar)
        "ALTER TABLE cheques ADD COLUMN banco_cuenta_id INTEGER REFERENCES plan_cuentas(id)",
        # Permitir borrar usuarios sin violar FK (columnas owner/creador se ponen en NULL)
        "ALTER TABLE auditoria_logs ALTER COLUMN usuario_id DROP NOT NULL",
        "ALTER TABLE planillas ALTER COLUMN usuario_id DROP NOT NULL",
        "ALTER TABLE extractos_bancarios ALTER COLUMN creado_por DROP NOT NULL",
        "ALTER TABLE liquidaciones ALTER COLUMN created_by DROP NOT NULL",
        "ALTER TABLE liquidaciones ALTER COLUMN cerrado_by DROP NOT NULL",
        "ALTER TABLE arqueos_diarios ALTER COLUMN creado_por DROP NOT NULL",
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
        # Cheques v2: migrar estado 'pendiente' → 'registrado'
        "UPDATE cheques SET estado='registrado' WHERE estado='pendiente'",
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
        from app.models.organizacion import Organizacion as Org
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
                "exportar_formato_contador": "excel_actual",
                "modo_asiento_um": "agrupado",
            }
            db.add(Org(id=1, nombre="Organización A", plan="pro", configuracion=config_org, activo=True))
            db.commit()
            logger.info("Organización A creada (id=1)")
        db.close()
    except Exception as ex:
        logger.warning("Error seed org: %s", ex)

    # 6. Seed contabilidad (plan de cuentas + reglas) — POR ORGANIZACIÓN
    # Siembra/completa el plan + reglas de TODAS las orgs (no solo la id=1), así
    # las orgs de prueba también llevan contabilidad. Idempotente: completa
    # parciales de deploys fallidos y agrega cuentas nuevas del patch en cada boot.
    try:
        from app.database import SessionLocal as SL
        from app.models.organizacion import Organizacion
        from app.services.seed_contable import seed_contabilidad_org, seed_categorias_egreso_org
        from app.services.monotributo_service import seed_monotributo_categorias
        from app.services.iibb_service import seed_iibb_jurisdiccion
        from app.services.sueldos_service import seed_config_sueldos

        db = SL()
        org_ids = [o.id for o in db.query(Organizacion.id).all()]
        if 1 not in org_ids:
            org_ids = [1] + org_ids  # garantiza org A aunque la query falle
        for oid in org_ids:
            try:
                seed_contabilidad_org(db, oid)
                seed_categorias_egreso_org(db, oid)
                # Categorías Monotributo (placeholder, editables) si la org no tiene ninguna
                seed_monotributo_categorias(db, oid)
                # Jurisdicción IIBB ilustrativa (editable) si la org no tiene ninguna
                seed_iibb_jurisdiccion(db, oid)
                # ConfigSueldos apagada (alícuotas de referencia editables) si la org no tiene ninguna
                seed_config_sueldos(db, oid)
            except Exception as ex_org:
                db.rollback()
                logger.warning("Error seed contabilidad org %s: %s", oid, ex_org)
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
        from app.services.tz import hoy_art

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
                    fecha = p.fecha_carga.date() if p.fecha_carga else hoy_art()
                except Exception:
                    fecha = hoy_art()
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

    # 7b. Backfill vínculo Cliente → cuenta contable (conservador)
    # Vincula cada cliente sin cuenta a la cuenta existente bajo 2-1-2-0 cuyo
    # nombre coincide (normalizado, sin acentos). Si no hay match claro, deja
    # el cliente sin vincular — NUNCA crea cuentas dudosas. Idempotente.
    try:
        import unicodedata as _ud
        from app.database import SessionLocal as SL
        from app.models.cliente import Cliente as Cli
        from app.models.contabilidad import PlanCuenta as PC

        def _norm(s):
            s = (s or "").strip().lower()
            s = "".join(c for c in _ud.normalize("NFKD", s) if not _ud.combining(c))
            return s

        db = SL()
        padre = db.query(PC).filter(PC.codigo == "2-1-2-0", PC.organizacion_id == 1).first()
        if padre:
            cuentas = db.query(PC).filter(PC.parent_id == padre.id, PC.organizacion_id == 1).all()
            por_nombre = {}
            for c in cuentas:
                por_nombre.setdefault(_norm(c.nombre), c)  # primera gana ante homónimos
            n_vinc = 0
            sin_match = []
            for cli in db.query(Cli).filter(Cli.organizacion_id == 1, Cli.cuenta_contable_id.is_(None)).all():
                cuenta = por_nombre.get(_norm(cli.nombre))
                if cuenta:
                    cli.cuenta_contable_id = cuenta.id
                    n_vinc += 1
                else:
                    sin_match.append(cli.nombre)
            if n_vinc:
                db.commit()
            logger.info("Backfill cuentas cliente: %d vinculados, %d sin match (%s)",
                        n_vinc, len(sin_match), ", ".join(sin_match[:10]) or "—")
        db.close()
    except Exception as ex:
        logger.warning("Error backfill cuentas cliente: %s", ex)

    # 7c. Cleanup único: eliminar planillas auto-recuperadas y clientes huérfanos
    try:
        from app.database import SessionLocal as SL
        from app.models.planilla import Planilla as Pl
        from app.models.cliente import Cliente as Cli
        from app.models.cheque import Cheque as Ch
        from app.models.egreso import Egreso as Eg
        from app.models.liquidacion import LiquidacionDetalle as LI
        db = SL()
        pl_auto = db.query(Pl).filter(Pl.nombre_archivo.like("Extracto auto-recuperado%")).all()
        if pl_auto:
            cli_ids = list({p.cliente_id for p in pl_auto})
            for pl in pl_auto:
                db.delete(pl)
            db.flush()
            borrados = 0
            for cid in cli_ids:
                restantes = db.query(Pl).filter(Pl.cliente_id == cid).count()
                if restantes > 0:
                    continue
                tiene_otros = (
                    db.query(Ch).filter(Ch.cliente_id == cid).count() > 0
                    or db.query(Eg).filter(Eg.cliente_id == cid).count() > 0
                    or db.query(LI).filter(LI.cliente_id == cid).count() > 0
                )
                if tiene_otros:
                    continue
                cli = db.query(Cli).get(cid)
                if cli:
                    db.delete(cli)
                    borrados += 1
            db.commit()
            logger.info("Cleanup auto-recuperados: %d planillas y %d clientes eliminados", len(pl_auto), borrados)
        db.close()
    except Exception as ex:
        logger.warning("Error cleanup auto-recuperados: %s", ex)

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

    # 9a. Asientos legacy (extracto/planilla/planilla_comision) — ya fueron eliminados
    # en la migración v3.9 (deploy junio 2026). Los gaps #518, #519, #520 en numero_asiento
    # corresponden a esos 3 asientos borrados. En el futuro NO se borran físicamente:
    # si aparecieran nuevos con esos módulos (no debería ocurrir) se loguea y se ignora.
    try:
        with engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM asientos WHERE modulo IN ('extracto','planilla','planilla_comision')"
            )).scalar()
            if count:
                logger.warning(
                    "Se encontraron %d asientos legacy (extracto/planilla) — fueron eliminados físicamente "
                    "en la migración v3.9 y no deberían reaparecer. Ignorados.", count
                )
            else:
                logger.info("Sin asientos legacy extracto/planilla (correcto).")
    except Exception as ex:
        logger.warning("Error verificando asientos legacy: %s", ex)

    # 9b. Crear asientos de documentación para los 3 gaps de migración v3.9
    # Los asientos #518, #519, #520 fueron eliminados físicamente en la migración v3.9
    # (módulos extracto/planilla con cuentas incorrectas). Se registran 3 asientos
    # ajuste_manual con numero_asiento = 518/519/520 para mantener la correlatividad.
    try:
        from app.database import SessionLocal as SL
        from app.models.contabilidad import Asiento
        _db = SL()
        try:
            for _num_orig in [518, 519, 520]:
                _existe = _db.query(Asiento).filter(
                    Asiento.organizacion_id == 1,
                    Asiento.numero_asiento == _num_orig,
                ).first()
                if not _existe:
                    _a = Asiento(
                        fecha=__import__('datetime').date(2026, 6, 3),
                        descripcion=f"BAJA LEGACY migración v3.9 — asiento #{_num_orig} (módulo extracto/planilla) fue eliminado físicamente al sanear el Libro Diario. Sin impacto contable.",
                        modulo="ajuste_manual",
                        organizacion_id=1,
                        numero_asiento=_num_orig,
                    )
                    _db.add(_a)
            _db.commit()

            # Eliminar los registros mal-numerados (888/889/890) si existen
            _db.query(Asiento).filter(
                Asiento.organizacion_id == 1,
                Asiento.modulo == "ajuste_manual",
                Asiento.descripcion.like("BAJA LEGACY migración v3.9%"),
                Asiento.numero_asiento > 520,
            ).delete(synchronize_session=False)
            _db.commit()
            logger.info("Asientos documentación gaps v3.9 en posiciones 518/519/520 (correlativos)")
        finally:
            _db.close()
    except Exception as ex:
        logger.warning("Error creando asientos documentación gaps: %s", ex)

    # 9. Fix numero_asiento NULL — asigna correlativo a asientos sin numerar
    try:
        from app.database import SessionLocal as SL
        from app.models.contabilidad import Asiento
        from sqlalchemy import func as _func
        db = SL()
        orgs_null = [r[0] for r in db.query(Asiento.organizacion_id).filter(
            Asiento.numero_asiento.is_(None)
        ).distinct().all()]
        total_fixed = 0
        for oid in orgs_null:
            max_num = db.query(_func.max(Asiento.numero_asiento)).filter(
                Asiento.organizacion_id == oid
            ).scalar() or 0
            sin_num = db.query(Asiento).filter(
                Asiento.organizacion_id == oid,
                Asiento.numero_asiento.is_(None),
            ).order_by(Asiento.fecha, Asiento.id).all()
            for a in sin_num:
                max_num += 1
                a.numero_asiento = max_num
                total_fixed += 1
        if total_fixed:
            db.commit()
            logger.info("numero_asiento asignado a %d asiento(s) sin numerar", total_fixed)
        db.close()
    except Exception as ex:
        logger.warning("Error fix numero_asiento: %s", ex)




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
            start_alertas_push_job, start_token_cleanup_job, start_r2_storage_alert_job,
        )
        start_backup_scheduler()
        start_alertas_push_job()       # 10:00 ART — push cheques/movs urgentes
        start_token_cleanup_job()      # 03:30 ART — purga tokens revocados
        start_r2_storage_alert_job()   # 09:00 ART — alerta si R2 > 8 GB
    except Exception as ex:
        logger.warning("No se pudo iniciar schedulers: %s", ex)
    yield
    try:
        stop_backup_scheduler()
    except Exception:
        pass


app = FastAPI(
    title=settings.app_name,
    version="3.24.0",
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

# Headers de seguridad bancaria + observabilidad de latencia.
# Mide cada request y la loguea como WARNING si supera settings.slow_request_ms,
# para que los logs de Render muestren qué endpoints están lentos con datos
# reales (en vez de adivinar con auditorías). Expone X-Process-Time para debug.
import time as _time

@app.middleware("http")
async def security_headers(request: Request, call_next):
    _start = _time.monotonic()
    response = await call_next(request)
    _elapsed_ms = (_time.monotonic() - _start) * 1000

    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(self), camera=(self), payment=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Process-Time"]            = f"{_elapsed_ms:.0f}ms"

    if _elapsed_ms >= settings.slow_request_ms:
        logger.warning(
            "SLOW %s %s → %s en %.0fms",
            request.method, request.url.path, response.status_code, _elapsed_ms,
        )
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
app.include_router(pagos.router)
app.include_router(papelera.router)
app.include_router(backup_admin.router)
app.include_router(analisis.router)
app.include_router(search_router.router)
app.include_router(public_router.router)
app.include_router(push_router.router)
app.include_router(agente.router)
app.include_router(tarjetas.router)
app.include_router(iva.router)
app.include_router(monotributo.router)
app.include_router(iibb.router)
app.include_router(sueldos.router)
app.include_router(google_auth.router)
app.include_router(arca.router)


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
