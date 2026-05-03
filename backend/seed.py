"""
Script de seed: crea las tablas + usuarios iniciales.

Uso:
    python seed.py

Crea:
- Organización Caneland SA (id=1)
- julietaarrazate@gmail.com  (superadmin) — password desde env SUPERADMIN_PASSWORD
- admin@caneland.com / admin123  (admin, demo Caneland)
- operador@caneland.com / operador123  (operador, demo Caneland)

Para definir la contraseña del superadmin:
    export SUPERADMIN_PASSWORD="tu_contraseña_segura"
    python seed.py
"""

import os
from app.database import engine, Base, SessionLocal
from app.models import User, Organizacion
from app.models.user import RoleEnum
from app.services.auth import get_password_hash


def init_db():
    print("[seed] Creando tablas...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[seed] OK tablas creadas.")
    except Exception as e:
        print(f"[seed] ERROR creando tablas: {e}")
        raise


def seed_organizaciones():
    print("[seed] Creando organización Caneland SA...")
    db = SessionLocal()
    try:
        caneland = db.query(Organizacion).filter(Organizacion.id == 1).first()
        if not caneland:
            config = {
                "match_rules": ["monto_cuit"],
                "tolerancia_monto": 0.01,
                "dias_tolerancia_fecha": 0,
                "estados_habilitados": ["pendiente", "ok", "no está", "duplicado", "faltan datos"],
                "requiere_cierre_periodo": False,
                "notificaciones_whatsapp": False,
                "exportar_formato_contador": "excel_actual"
            }
            db.add(Organizacion(id=1, nombre="Caneland SA", plan="pro", configuracion=config, activo=True))
            db.commit()
            print("+  Caneland SA creada (id=1)")
        else:
            print("-  Caneland SA ya existe")
    finally:
        db.close()


def seed_users():
    print("[seed] Creando usuarios...")
    db = SessionLocal()
    try:
        # Superadmin Julieta
        julieta_email = "julietaarrazate@gmail.com"
        julieta_pwd = os.environ.get("SUPERADMIN_PASSWORD", "")
        existing_julieta = db.query(User).filter(User.email == julieta_email).first()

        if existing_julieta:
            print(f"-  ya existe: {julieta_email}")
        elif not julieta_pwd:
            print(f"!  AVISO: no se creó {julieta_email}.")
            print("   Definí la variable de entorno SUPERADMIN_PASSWORD y ejecutá seed.py de nuevo.")
        else:
            db.add(User(
                email=julieta_email,
                full_name="Julieta Arrazate",
                hashed_password=get_password_hash(julieta_pwd),
                role=RoleEnum.ADMIN.value,
                is_active=True,
                is_superadmin=True,
                organizacion_id=1
            ))
            print(f"+  creado superadmin: {julieta_email}")

        # Usuarios demo Caneland
        seeds_demo = [
            ("admin@caneland.com", "admin123", "Administrador", RoleEnum.ADMIN),
            ("operador@caneland.com", "operador123", "Operador Caneland", RoleEnum.OPERADOR),
        ]
        for email, pwd, name, role in seeds_demo:
            if db.query(User).filter(User.email == email).first():
                print(f"-  ya existe: {email}")
                continue
            db.add(User(
                email=email,
                full_name=name,
                hashed_password=get_password_hash(pwd),
                role=role.value,
                is_active=True,
                is_superadmin=False,
                organizacion_id=1
            ))
            print(f"+  creado: {email} (password: {pwd})")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_organizaciones()
    seed_users()
    print("\nListo. Iniciá el server con:")
    print("    uvicorn app.main:app --reload")
