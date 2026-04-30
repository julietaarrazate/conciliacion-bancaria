"""
Script rapido para crear UN admin. Para crear admin + operador, usa seed.py
"""
from app.database import SessionLocal, engine, Base
from app.models import User
from app.models.user import RoleEnum
from app.services.auth import get_password_hash

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

db = SessionLocal()

email = "admin@admin.com"
password = "admin123"

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
    print(f"ADMIN CREADO: {email} / {password}")

db.close()
