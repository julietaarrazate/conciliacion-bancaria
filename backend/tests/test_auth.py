"""Tests para autenticación"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    verify_token,
    register_user,
    authenticate_user
)
from app.schemas.user import UserRegister

@pytest.fixture
def db():
    """Crea una BD en memoria para tests"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()

def test_password_hash_and_verify():
    """Test hash y verificación de contraseña"""
    password = "test123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_verify_token():
    """Test creación y verificación de JWT"""
    data = {"sub": "user@example.com", "user_id": 1}
    token = create_access_token(data)

    assert token is not None
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "user@example.com"
    assert payload["user_id"] == 1

def test_register_user(db):
    """Test registro de usuario"""
    user_data = UserRegister(
        email="test@example.com",
        full_name="Test User",
        password="password123"
    )

    user = register_user(db, user_data)
    assert user is not None
    assert user.email == "test@example.com"
    assert user.full_name == "Test User"

def test_register_user_duplicate_email(db):
    """Test que no permite emails duplicados"""
    user_data = UserRegister(
        email="test@example.com",
        full_name="Test User",
        password="password123"
    )

    # Primer registro OK
    user1 = register_user(db, user_data)
    assert user1 is not None

    # Segundo registro con mismo email debe fallar
    user2 = register_user(db, user_data)
    assert user2 is None

def test_authenticate_user(db):
    """Test autenticación de usuario"""
    user_data = UserRegister(
        email="test@example.com",
        full_name="Test User",
        password="password123"
    )

    register_user(db, user_data)

    # Autenticación correcta
    user = authenticate_user(db, "test@example.com", "password123")
    assert user is not None
    assert user.email == "test@example.com"

    # Contraseña incorrecta
    user = authenticate_user(db, "test@example.com", "wrongpassword")
    assert user is None

    # Email no existe
    user = authenticate_user(db, "notfound@example.com", "password123")
    assert user is None
