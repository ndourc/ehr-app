"""
Layer 1: Data Ingestion — Pydantic Schemas
==========================================
Defines the strict input contracts for the dual-stream EHR payload.

Unstructured stream:
  patient_id  : str
  timestamp   : ISO-8601 datetime
  clinical_text: str

Structured stream (16 ordinal variables, scale 0–3):
  0 = None / Normal
  1 = Mild
  2 = Moderate
  3 = Severe

Feature schema is AUTHORITATIVE. Any schema change must be reflected in:
  - structured_processor.py  (FEATURE_ORDER)
  - fusion_layer.py          (HYBRID_DIM docstring)
  - README.md                (schema table)
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


# ── Ordinal type alias (strictly 0 | 1 | 2 | 3) ──────────────────────────
OrdinalScore = Annotated[int, Field(ge=0, le=3)]


# ─────────────────────────────────────────────────────────────────────────────
# Structured Input — 16 behavioural variables
# ─────────────────────────────────────────────────────────────────────────────
class StructuredInput(BaseModel):
    """
    Exactly 16 behavioural variables on a 0–3 ordinal scale.
    The canonical ordering is defined in FEATURE_ORDER (structured_processor.py)
    and must not change without a schema-version bump.
    """

    # ── Psychological State ───────────────────────────────────────────────
    mood_swings: OrdinalScore
    anxiety_level: OrdinalScore
    depression_indicators: OrdinalScore
    emotional_stability: OrdinalScore

    # ── Behavioural Patterns ──────────────────────────────────────────────
    days_indoors: OrdinalScore
    social_interaction: OrdinalScore
    activity_level: OrdinalScore
    sleep_quality: OrdinalScore

    # ── Coping & Stress Indicators ────────────────────────────────────────
    coping_struggles: OrdinalScore
    stress_level: OrdinalScore
    work_engagement: OrdinalScore
    motivation_level: OrdinalScore

    # ── Cognitive Function ────────────────────────────────────────────────
    concentration_level: OrdinalScore
    decision_difficulty: OrdinalScore
    memory_issues: OrdinalScore

    # ── Social Context ────────────────────────────────────────────────────
    support_system: OrdinalScore


# ─────────────────────────────────────────────────────────────────────────────
# Combined dual-stream request
# ─────────────────────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    """POST /predict combined payload — unstructured + structured streams."""

    patient_id: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime
    clinical_text: str = Field(..., min_length=1, max_length=8192)
    structured: StructuredInput


# ─────────────────────────────────────────────────────────────────────────────
# Output contracts
# ─────────────────────────────────────────────────────────────────────────────
class TokenWeight(BaseModel):
    """One attention-weighted token from the XAI explanation."""

    word: str
    weight: float


class PredictResponse(BaseModel):
    """Prediction + confidence + explainability token map."""

    patient_id: str
    prediction: str          # "Distress" | "Stable"
    confidence_score: float
    important_tokens: list[TokenWeight]
