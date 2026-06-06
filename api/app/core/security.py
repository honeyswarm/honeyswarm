"""Token + secret helpers.

* Enrollment-token generation/hashing for hive registration.
* Password hashing (bcrypt) and JWT access/refresh tokens for user auth.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# --- hive enrollment tokens ---


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), token_hash)


# --- user passwords ---


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; truncate defensively.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ---

ACCESS = "access"
REFRESH = "refresh"
DASHBOARDS = "dashboards"


def _create_token(subject: str, token_type: str, expires: timedelta, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    if extra:
        claims.update(extra)
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, roles: list[str]) -> str:
    return _create_token(
        subject, ACCESS, timedelta(minutes=settings.access_token_ttl_minutes), {"roles": roles}
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, REFRESH, timedelta(days=settings.refresh_token_ttl_days))


def create_dashboards_token(subject: str) -> str:
    """Short-lived token (cookie) authorizing access to the Dashboards proxy."""
    return _create_token(
        subject, DASHBOARDS, timedelta(minutes=settings.dashboards_token_ttl_minutes)
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
