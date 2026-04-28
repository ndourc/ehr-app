"""
Storage Layer — SQLAlchemy ORM models.
Stores every inference event with its raw inputs, processed features,
prediction, confidence score, and explainability token map for full
clinical auditability.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database import Base


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
