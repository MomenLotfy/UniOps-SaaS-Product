from __future__ import annotations
"""Security utilities — JWT creation/decoding and password hashing."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import warnings

# Suppress bcrypt/passlib version mismatch warning
warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")
warnings.filterwarnings("ignore", ".*AttributeError.*__about__.*")

# Monkey-patch passlib bcrypt to avoid AttributeError with bcrypt>=4.x
try:
    import bcrypt
    if not hasattr(bcrypt, '__about__'):
        bcrypt.__about__ = type('obj', (object,), {'__version__': bcrypt.__version__})()
except Exception:
    pass

import jwt as PyJWT
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWTError = PyJWT.exceptions.PyJWTError
ExpiredSignatureError = PyJWT.exceptions.ExpiredSignatureError


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(
    user_id: str,
    email: str,
    tenant_id: str,
    roles: list[str],
    extra_claims: Optional[dict] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "email": email,
        "tenant_id": tenant_id,
        "roles": roles,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return PyJWT.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return PyJWT.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = PyJWT.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except PyJWT.exceptions.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except PyJWT.exceptions.PyJWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")
