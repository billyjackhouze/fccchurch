"""
JWT and password utilities for FFC Church auth system.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

SECRET_KEY    = os.getenv("JWT_SECRET", "fcc-church-secret-change-in-production-please")
ALGORITHM     = "HS256"
EXPIRY_HOURS  = int(os.getenv("JWT_EXPIRY_HOURS", "168"))   # 7 days default

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict, expires_hours: int = None) -> str:
    to_encode = data.copy()
    hours = expires_hours if expires_hours is not None else EXPIRY_HOURS
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=hours)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
