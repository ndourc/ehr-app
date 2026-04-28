"""
Auth — Routes
==============
POST /api/v1/auth/login     Issue access + refresh tokens
POST /api/v1/auth/logout    Revoke refresh token
POST /api/v1/auth/refresh   Exchange refresh token for new access token
GET  /api/v1/auth/me        Return current user profile
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import get_current_user
from app.auth.hashing import verify_password
from app.auth.service import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from app.config import settings
from app.storage.database import get_db
from app.storage.models import AuditLog, Session, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    patient_profile_id: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _log_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    resource: str,
    ip: str,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip,
    )
    db.add(entry)
    # committed by caller


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate user and issue JWT access + refresh tokens."""
    stmt = select(User).where(User.username == body.username, User.is_active.is_(True))
    result = await db.execute(stmt)
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token = create_access_token(user.username, user.role)
    raw_refresh, hashed_refresh = create_refresh_token()

    # Persist refresh token
    session = Session(
        user_id=user.id,
        refresh_token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRY_DAYS),
    )
    db.add(session)
    await _log_action(db, user.id, "login", "/auth/login", _client_ip(request))
    await db.commit()

    logger.info("[Auth] Login — user=%s role=%s ip=%s", user.username, user.role, _client_ip(request))
    return LoginResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        role=user.role,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    body: RefreshRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke the supplied refresh token."""
    hashed = hash_refresh_token(body.refresh_token)
    stmt = select(Session).where(
        Session.user_id == current_user.id,
        Session.refresh_token_hash == hashed,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
    await _log_action(db, current_user.id, "logout", "/auth/logout", _client_ip(request))
    await db.commit()
    return {"detail": "logged out"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Exchange a valid refresh token for a new access token."""
    hashed = hash_refresh_token(body.refresh_token)
    stmt = select(Session).where(Session.refresh_token_hash == hashed)
    result = await db.execute(stmt)
    session: Session | None = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if session is None or (session.expires_at.tzinfo is None
                           and session.expires_at < now.replace(tzinfo=None)) or \
       (session.expires_at.tzinfo is not None and session.expires_at < now):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid or expired",
        )

    user_stmt = select(User).where(User.id == session.user_id, User.is_active.is_(True))
    user_result = await db.execute(user_stmt)
    user: User | None = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate refresh token
    raw_refresh, hashed_refresh = create_refresh_token()
    session.refresh_token_hash = hashed_refresh
    session.expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRY_DAYS)
    await db.commit()

    access_token = create_access_token(user.username, user.role)
    return LoginResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        role=user.role,
    )


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    """Return the profile of the authenticated user."""
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
        patient_profile_id=current_user.patient_profile_id,
    )
