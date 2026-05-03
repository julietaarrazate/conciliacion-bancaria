import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, extractos, planillas, me, admin, auditoria, historial, clientes_dir
from app.routers import organizaciones
from app.models import User, Cliente, ExtractoBancario, MovimientoBanco, Planilla, PlanillaRow, AuditoriaLog
from app.models.organizacion import Organizacion

settings = get_settings()


def _init_db():
    """Crea tablas, migraciones y seed en background — no bloquea el arranque."""
    import hashlib, os
    from app.database import SessionLocal
    from app.models.extracto import ExtractoBancario as Extracto

    # 1. Crear tablas (incluye Organizacion)
    try:
        Base.metadata.create_all(bind=engine)
        print("[db] Tablas OK")
    except Exception as e:
        print(f"[db] Warning tablas: {e}")
        return

    # 2. Migraciones de columnas — todas idempotentes (IF NOT EXISTS no disponible en todos los Postgres,
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
    ]
    for sql in migrations:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception:
            pass  # columna ya existe

    # 3. Backfill organizacion_id=1 en tablas existentes (Caneland)
    backfills = [
        "UPDATE users SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE clientes SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE extractos_bancarios SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE movimientos_banco SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE planillas SET organizacion_id=1 WHERE organizacion_id IS NULL",
        "UPDATE planilla_rows SET organizacion_id=1 WHERE organizacion_id IS NULL",
    ]
    for sql in backfills:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception as ex:
            print(f"[db] Warning backfill: {ex}")

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
            print(f"[db] fingerprint calculado para {len(sin_fp)} extracto(s)")
        db.close()
    except Exception as ex:
        print(f"[db] Warning fingerprint: {ex}")

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
            print("[db] Organización Caneland SA creada (id=1)")
        db.close()
    except Exception as ex:
        print(f"[db] Warning seed org: {ex}")

    # 6. Seed usuarios
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
                print(f"[db] Superadmin {julieta_email} creado")
            else:
                # Siempre actualizar password y flags desde el env var
                julieta.hashed_password = get_password_hash(julieta_pwd)
                julieta.is_superadmin = True
                julieta.is_active = True
                julieta.role = RoleEnum.ADMIN.value
                print(f"[db] Superadmin {julieta_email} actualizado")
            db.commit()
        else:
            print("[db] AVISO: SUPERADMIN_PASSWORD no definida")

        # Migrar admin@caneland.com → admin@julieta.com si existe el viejo
        old = db.query(U).filter(U.email == "admin@caneland.com").first()
        if old and not db.query(U).filter(U.email == "admin@julieta.com").first():
            old.email = "admin@julieta.com"
            old.full_name = "Administrador"
            db.commit()
            print("[db] admin@caneland.com → admin@julieta.com")

        # Usuarios demo
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
            print(f"[db] {created} usuario(s) demo creado(s)")
        db.close()
    except Exception as ex:
        print(f"[db] Warning seed users: {ex}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_init_db, daemon=True)
    t.start()
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(extractos.router)
app.include_router(planillas.router)
app.include_router(historial.router)
app.include_router(auditoria.router)
app.include_router(admin.router)
app.include_router(clientes_dir.router)
app.include_router(organizaciones.router)


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
