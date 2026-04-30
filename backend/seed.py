"""
Script de seed: crea las tablas + un usuario admin inicial.

Uso:
    python seed.py

Crea:
- admin@caneland.com / admin123 (rol admin)
- operador@caneland.com / operador123 (rol operador)
"""

from app.database import engine, Base, SessionLocal
from app.models import User
from app.models.user import RoleEnum
from app.services.auth import get_password_hash


def init_db():
    """Crea todas las tablas"""
    print("Creando tablas...")
    Base.metadata.create_all(bind=engine)
    print("OK tablas creadas.")


def seed_users():
    """Crea usuarios iniciales si no existen"""
    db = SessionLocal()
    try:
        seeds = [
            {
                "email": "admin@caneland.com",
                "password": "admin123",
                "full_name": "Administrador",
                "role": RoleEnum.ADMIN
            },
            {
                "email": "operador@caneland.com",
                "password": "operador123",
                "full_name": "Operador Caneland",
                "role": RoleEnum.OPERADOR
            }
        ]

        for s in seeds:
            existing = db.query(User).filter(User.email == s["email"]).first()
            if existing:
                print(f"-  ya existe: {s['email']}")
                continue

            user = User(
                email=s["email"],
                full_name=s["full_name"],
                hashed_password=get_password_hash(s["password"]),
                role=s["role"],
                is_active=True
            )
            db.add(user)
            print(f"+  creado: {s['email']} (password: {s['password']})")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_users()
    print("\nListo. Iniciá el server con:")
    print("    uvicorn app.main:app --reload")
