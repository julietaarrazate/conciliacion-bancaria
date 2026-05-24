import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog, PasswordResetToken  # noqa: F401
from app.models.organizacion import Organizacion

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

    # 3. Backfill organizacion_id=1 en tablas existentes (Caneland)
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

    # 5. Seed Organizacion Caneland (id=1)
    try:
        from app.database import SessionLocal as SL
        from app.models.organizacion import Organizacion as Org, CONFIG_DEFAULT
        db = SL()
        caneland = db.query(Org).filter(Org.id == 1).first()
        if not caneland:
            config_caneland = {
                "match_rules": ["monto_cuit"],
                "tolerancia_monto": 0.01,
                "dias_tolerancia_fecha": 5,
                "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
                "requiere_cierre_periodo": False,
                "notificaciones_whatsapp": False,
                "exportar_formato_contador": "excel_actual"
            }
            db.add(Org(id=1, nombre="Caneland SA", plan="pro", configuracion=config_caneland, activo=True))
            db.commit()
            logger.info("Organización Caneland SA creada (id=1)")
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

        # Migrar admin@caneland.com → admin@julieta.com si existe el viejo
        old = db.query(U).filter(U.email == "admin@caneland.com").first()
        if old and not db.query(U).filter(U.email == "admin@julieta.com").first():
            old.email = "admin@julieta.com"
            old.full_name = "Administrador"
            db.commit()
            logger.info("admin@caneland.com migrado a admin@julieta.com")

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.debug and settings.secret_key == "dev-secret-key-CAMBIAR-en-produccion":
        logger.critical("SECRET_KEY usa el valor por defecto — seteá SECRET_KEY en Render")
    t = threading.Thread(target=_init_db, daemon=True)
    t.start()
    # Scheduler de backup diario por email (no-op si RESEND_API_KEY no esta)
    try:
        from app.services.backup_scheduler import start_backup_scheduler, stop_backup_scheduler
        start_backup_scheduler()
    except Exception as ex:
        logger.warning("No se pudo iniciar el backup scheduler: %s", ex)
    yield
    try:
        stop_backup_scheduler()
    except Exception:
        pass


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    allow_methods=["*"],
    allow_headers=["*"],
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
