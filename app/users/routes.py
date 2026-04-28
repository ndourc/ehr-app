"""
Users — Admin Routes
=====================
GET    /api/v1/users               List all users       (admin)
POST   /api/v1/users               Create user          (admin)
GET    /api/v1/users/{user_id}     Get user detail      (admin)
PATCH  /api/v1/users/{user_id}     Update role / status (admin)
DELETE /api/v1/users/{user_id}     Deactivate user      (admin)
POST   /api/v1/users/{user_id}/reset-password  (admin)

POST   /api/v1/users/assignments   Assign patient to clinician (admin | clinician)
GET    /api/v1/users/assignments   List assignments            (admin | clinician)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import require_roles
from app.auth.hashing import hash_password
from app.storage.database import get_db
from app.storage.models import PatientAssignment, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])

_VALID_ROLES = {"patient", "clinician", "analyst", "admin"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    role: str
    patient_profile_id: str | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    patient_profile_id: str | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class AssignmentCreate(BaseModel):
    clinician_username: str
    patient_username: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    patient_profile_id: str | None

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[UserOut]:
    rows = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return [UserOut.model_validate(u) for u in rows]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> UserOut:
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    existing = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
        is_active=True,
        patient_profile_id=body.patient_profile_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> UserOut:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> UserOut:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None:
        if body.role not in _VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.patient_profile_id is not None:
        user.patient_profile_id = body.patient_profile_id
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> dict:
    """Soft-delete: set is_active = False."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    return {"detail": "deactivated"}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    body: PasswordReset,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> dict:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"detail": "password updated"}


# ── Patient Assignments ───────────────────────────────────────────────────────

@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "clinician")),
) -> dict:
    clinician = (await db.execute(
        select(User).where(User.username == body.clinician_username, User.role == "clinician")
    )).scalar_one_or_none()
    if clinician is None:
        raise HTTPException(status_code=404, detail="Clinician not found")

    patient = (await db.execute(
        select(User).where(User.username == body.patient_username, User.role == "patient")
    )).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing = (await db.execute(
        select(PatientAssignment).where(
            PatientAssignment.clinician_user_id == clinician.id,
            PatientAssignment.patient_user_id == patient.id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Assignment already exists")

    db.add(PatientAssignment(clinician_user_id=clinician.id, patient_user_id=patient.id))
    await db.commit()
    return {"clinician": body.clinician_username, "patient": body.patient_username}


@router.get("/assignments", response_model=list[dict])
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "clinician")),
) -> list[dict]:
    stmt = select(PatientAssignment)
    if current_user.role == "clinician":
        stmt = stmt.where(PatientAssignment.clinician_user_id == current_user.id)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {"id": r.id, "clinician_user_id": r.clinician_user_id, "patient_user_id": r.patient_user_id}
        for r in rows
    ]
