"""
Layer 2: Processing — Structured Feature Processor
===================================================
Validates 16 ordinal variables and converts them to a normalised float32
numpy array of shape (16,).

FEATURE_ORDER is the single source of truth for column ordering.
Any change here must be reflected in:
  - fusion_layer.py  (HYBRID_DIM comment)
  - schemas.py       (StructuredInput field names)
  - README.md        (feature-vector table)

Normalisation:
  MinMax (x / 3.0)  →  [0.0, 1.0]
  (Divisor is 3.0 — the maximum ordinal value per the schema spec.)

All values are logged before and after normalisation (no silent processing).
"""
from __future__ import annotations

import logging

import numpy as np

from app.layers.ingestion.schemas import StructuredInput

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Canonical feature ordering — fixed; document changes in commit messages
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_ORDER: list[str] = [
    # Psychological State (indices 0–3)
    "mood_swings",
    "anxiety_level",
    "depression_indicators",
    "emotional_stability",
    # Behavioural Patterns (indices 4–7)
    "days_indoors",
    "social_interaction",
    "activity_level",
    "sleep_quality",
    # Coping & Stress Indicators (indices 8–11)
    "coping_struggles",
    "stress_level",
    "work_engagement",
    "motivation_level",
    # Cognitive Function (indices 12–14)
    "concentration_level",
    "decision_difficulty",
    "memory_issues",
    # Social Context (index 15)
    "support_system",
]

assert len(FEATURE_ORDER) == 16, (
    "FEATURE_ORDER must contain exactly 16 elements to match the schema spec."
)

_ORDINAL_MAX: float = 3.0   # scale upper bound per specification


def structured_to_vector(structured: StructuredInput) -> np.ndarray:
    """
    Convert a StructuredInput to a normalised float32 numpy vector of shape (16,).

    Steps
    -----
    1. Extract raw ordinal values in FEATURE_ORDER sequence.
    2. Log raw values (auditability requirement).
    3. Apply MinMax normalisation: value / 3.0.
    4. Log normalised statistics.

    Returns
    -------
    np.ndarray shape (16,), dtype float32
    """
    raw: dict[str, int] = {field: int(getattr(structured, field)) for field in FEATURE_ORDER}
    logger.info("[StructuredProcessor] Raw ordinal values: %s", raw)

    vector = np.array([raw[field] for field in FEATURE_ORDER], dtype=np.float32)
    normalised = vector / _ORDINAL_MAX

    logger.info(
        "[StructuredProcessor] Normalised vector — min=%.3f  max=%.3f  mean=%.3f",
        float(normalised.min()),
        float(normalised.max()),
        float(normalised.mean()),
    )
    return normalised


def vector_to_dict(vector: np.ndarray) -> dict[str, float]:
    """
    Map a (16,) numpy vector back to a labelled dict for auditable storage / display.
    """
    if vector.shape[0] != len(FEATURE_ORDER):
        raise ValueError(
            f"Expected vector of length {len(FEATURE_ORDER)}, got {vector.shape[0]}."
        )
    return {field: round(float(vector[i]), 6) for i, field in enumerate(FEATURE_ORDER)}
