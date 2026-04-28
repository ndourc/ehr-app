"""
Auth — JWT Service
==================
Handles access token and refresh token creation and verification.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = settings.JWT_ALGORITHM
_SECRET = settings.JWT_SECRET


def create_access_token(subject: str, role: str) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRY_MINUTES
    )
    payload = {
        "sub": subject,      # username
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """
    Generate a refresh token.

    Returns
    -------
    (raw_token, hashed_token)
        Store only the hash; return the raw token to the client.
    """
    raw = secrets.token_urlsafe(48)
    hashed = _hash_token(raw)
    return raw, hashed


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access token.

    Raises
    ------
    JWTError
        If the token is invalid or expired.
    """
    payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


def _hash_token(raw: str) -> str:
    """SHA-256 hash of *raw* for safe DB storage."""
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return _hash_token(raw)
