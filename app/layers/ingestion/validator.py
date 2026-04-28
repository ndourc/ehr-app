"""
Layer 1: Data Ingestion — Extended Validator
============================================
Performs semantic validation beyond Pydantic's type enforcement:

  - clinical_text must contain at least MIN_TEXT_WORDS words.
  - Logs a warning for any structured field scoring 0 (None/Normal) so that
    clinicians can verify genuine normal readings vs. missing-value artefacts.

Raises ValidationError (subclass of ValueError) for hard failures.
All events are logged — no silent validation.
"""
from __future__ import annotations

import logging

from app.layers.ingestion.schemas import PredictRequest, StructuredInput

logger = logging.getLogger(__name__)

_MIN_TEXT_WORDS = 5

# Derived at import time to stay in sync with schema additions/removals.
_STRUCTURED_FIELDS: list[str] = list(StructuredInput.model_fields.keys())


class ValidationError(ValueError):
    """Raised when an incoming request fails extended semantic validation."""


def validate_request(request: PredictRequest) -> PredictRequest:
    """
    Run extended validation on a PredictRequest.
    Returns the (unchanged) request on success; raises ValidationError on failure.
    All checks are logged explicitly.
    """
    _validate_clinical_text(request.clinical_text)
    _audit_structured_values(request.structured)

    logger.info(
        "[Validator] Request OK — patient_id=%s timestamp=%s text_words=%d",
        request.patient_id,
        request.timestamp.isoformat(),
        len(request.clinical_text.split()),
    )
    return request


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_clinical_text(text: str) -> None:
    word_count = len(text.split())
    logger.debug("[Validator] clinical_text word count: %d", word_count)
    if word_count < _MIN_TEXT_WORDS:
        raise ValidationError(
            f"clinical_text is too short ({word_count} word(s)). "
            f"Minimum required: {_MIN_TEXT_WORDS}."
        )


def _audit_structured_values(structured: StructuredInput) -> None:
    """
    Zero-value audit: a score of 0 may indicate a missing value rather than a
    truly normal reading. Emit a WARNING so the record can be reviewed.
    """
    zero_fields = [
        field for field in _STRUCTURED_FIELDS if getattr(structured, field) == 0
    ]
    if zero_fields:
        logger.warning(
            "[Validator] The following structured fields scored 0 "
            "(verify: missing value vs. genuine Normal): %s",
            zero_fields,
        )
    else:
        logger.debug("[Validator] No zero-valued structured fields detected.")
