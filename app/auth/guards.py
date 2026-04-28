"""
Auth — RBAC Guards (FastAPI Dependencies)
==========================================
Usage in route definitions:

    @router.post("/predict")
    async def predict(current_user = Depends(require_roles("clinician", "analyst", "admin"))):
        ...
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token
from app.storage.database import get_db

if TYPE_CHECKING:
    from app.storage.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> "User":
    """Validate JWT and return the active user row."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub", "")
    except JWTError:
        raise credentials_exc

    from app.storage.models import User  # noqa: PLC0415 — avoids circular import

    stmt = select(User).where(User.username == username, User.is_active.is_(True))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exc
    return user


def require_roles(*roles: str):
    """
    Dependency factory — restricts endpoint to specific roles.

    Example
    -------
        Depends(require_roles("clinician", "admin"))
    """
    async def _guard(
        current_user=Depends(get_current_user),
    ) -> "User":
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted to access this resource.",
            )
        return current_user

    return _guard
