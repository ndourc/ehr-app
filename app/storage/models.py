"""
Storage Layer — SQLAlchemy ORM models.
Stores every inference event with its raw inputs, processed features,
prediction, confidence score, and explainability token map for full
clinical auditability.

Also defines: User, PatientAssignment, AuditLog, Session for the auth
and RBAC system.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Auth / Identity
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    """System user — one row per account regardless of role."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "patient" | "clinician" | "analyst" | "admin"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    # For patient-role users: the clinical patient_id they own (e.g. "PT00001")
    patient_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    assignments_as_clinician: Mapped[list["PatientAssignment"]] = relationship(
        "PatientAssignment",
        foreign_keys="PatientAssignment.clinician_user_id",
        back_populates="clinician",
        lazy="select",
    )
    assignments_as_patient: Mapped[list["PatientAssignment"]] = relationship(
        "PatientAssignment",
        foreign_keys="PatientAssignment.patient_user_id",
        back_populates="patient",
        lazy="select",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", lazy="select"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", lazy="select"
    )


class PatientAssignment(Base):
    """Maps a clinician user to a patient user."""

    __tablename__ = "patient_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinician_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    clinician: Mapped["User"] = relationship(
        "User", foreign_keys=[clinician_user_id], back_populates="assignments_as_clinician"
    )
    patient: Mapped["User"] = relationship(
        "User", foreign_keys=[patient_user_id], back_populates="assignments_as_patient"
    )


class AuditLog(Base):
    """One row per auditable action performed by a user."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(256), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")


class Session(Base):
    """Refresh token session — one row per active device/session."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")


# ─────────────────────────────────────────────────────────────────────────────
# Prediction Records (unchanged schema)
# ─────────────────────────────────────────────────────────────────────────────

class PredictionRecord(Base):
    """One row per POST /predict request, written after inference completes."""

    __tablename__ = "prediction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Ingestion metadata ────────────────────────────────────────────────
    patient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # ── Who submitted this prediction ─────────────────────────────────────
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Raw input (unmodified, for audit) ─────────────────────────────────
    raw_clinical_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_structured_features: Mapped[dict] = mapped_column(JSON, nullable=False)

    # ── Processed / intermediate ──────────────────────────────────────────
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=True)
    normalised_structured: Mapped[dict] = mapped_column(JSON, nullable=True)

    # ── NLP metadata ──────────────────────────────────────────────────────
    sentiment: Mapped[str] = mapped_column(String(16), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=True)

    # ── Prediction output ─────────────────────────────────────────────────
    prediction: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)

    # ── Explainability (XAI) ──────────────────────────────────────────────
    important_tokens: Mapped[list] = mapped_column(JSON, nullable=False)

