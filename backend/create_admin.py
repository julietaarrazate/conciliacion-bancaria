"""
Script rapido para crear UN admin. Para crear admin + operador, usa seed.py

Email y contraseña se leen de CREATE_ADMIN_EMAIL / CREATE_ADMIN_PASSWORD; si no
están definidas, se piden por consola (la contraseña sin eco).
"""
import getpass
import os

from app.database import SessionLocal, engine, Base
from app.models import User
from app.models.user import RoleEnum
from app.services.auth import get_password_hash

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

email = (os.environ.get("CREATE_ADMIN_EMAIL") or input("Email del admin: ")).strip()
password = os.environ.get("CREATE_ADMIN_PASSWORD") or getpass.getpass("Contraseña: ")

if not email or not password:
    raise SystemExit("Email y contraseña son obligatorios.")

db = SessionLocal()

existing = db.query(User).filter(User.email == email).first()
if existing:
    print(f"Ya existe: {email}")
else:
    user = User(
        email=email,
        full_name="Admin",
        hashed_password=get_password_hash(password),
        role=RoleEnum.ADMIN.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    print(f"ADMIN CREADO: {email}")

db.close()
