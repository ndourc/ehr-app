"""
Storage — Seed Script
======================
Creates the six default development users if they do not already exist.

Password for all dev accounts: Password123!

Role       Username
---------  ----------
admin      admin1
clinician  doctor1
clinician  nurse1
analyst    analyst1
patient    patient1   (patient_profile_id = PT00001)
patient    patient2   (patient_profile_id = PT00002)
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.hashing import hash_password
from app.storage.models import PatientAssignment, User

logger = logging.getLogger(__name__)

_DEV_PASSWORD = "Password123!"

_SEED_USERS: list[dict] = [
    {"username": "admin1",   "role": "admin",     "patient_profile_id": None},
    {"username": "doctor1",  "role": "clinician", "patient_profile_id": None},
    {"username": "nurse1",   "role": "clinician", "patient_profile_id": None},
    {"username": "analyst1", "role": "analyst",   "patient_profile_id": None},
    {"username": "patient1", "role": "patient",   "patient_profile_id": "PT00001"},
    {"username": "patient2", "role": "patient",   "patient_profile_id": "PT00002"},
]


async def seed_users(db: AsyncSession) -> None:
    """Insert seed users that do not yet exist. Idempotent."""
    hashed = hash_password(_DEV_PASSWORD)
    created = 0

    for spec in _SEED_USERS:
        stmt = select(User).where(User.username == spec["username"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is None:
            db.add(User(
                username=spec["username"],
                hashed_password=hashed,
                role=spec["role"],
                is_active=True,
                patient_profile_id=spec["patient_profile_id"],
            ))
            created += 1

    if created:
        await db.commit()
        logger.info("[Seed] Created %d user(s).", created)

        # Assign both patients to doctor1
        await _seed_assignments(db)
    else:
        logger.info("[Seed] Users already present — skipping.")


async def _seed_assignments(db: AsyncSession) -> None:
    """Assign patient1 and patient2 to doctor1 (dev convenience)."""
    doctor = (await db.execute(
        select(User).where(User.username == "doctor1")
    )).scalar_one_or_none()

    if doctor is None:
        return

    for patient_username in ("patient1", "patient2"):
        patient = (await db.execute(
            select(User).where(User.username == patient_username)
        )).scalar_one_or_none()

        if patient is None:
            continue

        existing = (await db.execute(
            select(PatientAssignment).where(
                PatientAssignment.clinician_user_id == doctor.id,
                PatientAssignment.patient_user_id == patient.id,
            )
        )).scalar_one_or_none()

        if existing is None:
            db.add(PatientAssignment(
                clinician_user_id=doctor.id,
                patient_user_id=patient.id,
            ))

    await db.commit()
    logger.info("[Seed] Patient assignments created.")
