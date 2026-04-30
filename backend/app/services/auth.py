from datetime import datetime, timedelta
from typing import Optional
import hashlib
import os
import hmac
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserRegister
from app.config import get_settings

settings = get_settings()

# pbkdf2_sha256 - viene en stdlib, no necesita compilar nada en el deploy
PBKDF2_ITERATIONS = 120_000
PBKDF2_ALGO = "sha256"
SALT_LEN = 16


def get_password_hash(password: str) -> str:
    """Hashea password con pbkdf2_sha256 (stdlib, portable)"""
    salt = os.urandom(SALT_LEN)
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica password. Soporta pbkdf2_sha256 (nuevo) y bcrypt (legacy)"""
    if not hashed_password:
        return False
    try:
        if hashed_password.startswith("pbkdf2_sha256$"):
            _, iters_s, salt_hex, dk_hex = hashed_password.split("$")
            iters = int(iters_s)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(dk_hex)
            actual = hashlib.pbkdf2_hmac(PBKDF2_ALGO, plain_password.encode("utf-8"), salt, iters)
            return hmac.compare_digest(expected, actual)
        # Legacy bcrypt fallback
        if hashed_password.startswith("$2"):
            try:
                import bcrypt as _bcrypt
                return _bcrypt.checkpw(
                    plain_password.encode("utf-8")[:72],
                    hashed_password.encode("utf-8")
                )
            except Exception:
                return False
    except Exception:
        return False
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


def register_user(db: Session, user_data: UserRegister) -> Optional[User]:
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        return None
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
