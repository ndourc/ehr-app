"""
Layer 1 Tests — Data Ingestion (schemas & validator)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.layers.ingestion.schemas import PredictRequest, StructuredInput
from app.layers.ingestion.validator import ValidationError, validate_request


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _valid_structured() -> dict:
    return {
        "mood_swings": 2,
        "anxiety_level": 3,
        "depression_indicators": 2,
        "emotional_stability": 1,
        "days_indoors": 2,
        "social_interaction": 2,
        "activity_level": 1,
        "sleep_quality": 3,
        "coping_struggles": 2,
        "stress_level": 3,
        "work_engagement": 1,
        "motivation_level": 2,
        "concentration_level": 2,
        "decision_difficulty": 3,
        "memory_issues": 1,
        "support_system": 1,
    }


def _valid_request() -> dict:
    return {
        "patient_id": "PT00001",
        "timestamp": "2026-01-15T10:30:00",
        "clinical_text": "Patient reports severe anxiety and cannot sleep at night.",
        "structured": _valid_structured(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Schema validation tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStructuredInputSchema:
    def test_valid_all_fields_accepted(self):
        s = StructuredInput(**_valid_structured())
        assert s.anxiety_level == 3
        assert s.mood_swings == 2

    def test_exactly_16_fields(self):
        s = StructuredInput(**_valid_structured())
        assert len(s.model_fields) == 16

    def test_value_zero_is_valid(self):
        data = _valid_structured()
        data["mood_swings"] = 0
        s = StructuredInput(**data)
        assert s.mood_swings == 0

    def test_value_three_is_valid(self):
        data = _valid_structured()
        data["anxiety_level"] = 3
        s = StructuredInput(**data)
        assert s.anxiety_level == 3

    def test_value_above_three_rejected(self):
        data = _valid_structured()
        data["mood_swings"] = 4
        with pytest.raises(PydanticValidationError):
            StructuredInput(**data)

    def test_value_below_zero_rejected(self):
        data = _valid_structured()
        data["stress_level"] = -1
        with pytest.raises(PydanticValidationError):
            StructuredInput(**data)

    def test_float_value_rejected(self):
        data = _valid_structured()
        data["anxiety_level"] = 1.5
        with pytest.raises(PydanticValidationError):
            StructuredInput(**data)

    def test_missing_field_rejected(self):
        data = _valid_structured()
        del data["support_system"]
        with pytest.raises(PydanticValidationError):
            StructuredInput(**data)


class TestPredictRequestSchema:
    def test_valid_request_accepted(self):
        r = PredictRequest(**_valid_request())
        assert r.patient_id == "PT00001"

    def test_empty_patient_id_rejected(self):
        data = _valid_request()
        data["patient_id"] = ""
        with pytest.raises(PydanticValidationError):
            PredictRequest(**data)

    def test_empty_clinical_text_rejected(self):
        data = _valid_request()
        data["clinical_text"] = ""
        with pytest.raises(PydanticValidationError):
            PredictRequest(**data)

    def test_invalid_timestamp_rejected(self):
        data = _valid_request()
        data["timestamp"] = "not-a-date"
        with pytest.raises(PydanticValidationError):
            PredictRequest(**data)


# ─────────────────────────────────────────────────────────────────────────────
# Extended validator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExtendedValidator:
    def test_valid_request_passes(self):
        request = PredictRequest(**_valid_request())
        assert validate_request(request) is request

    def test_short_clinical_text_raises(self):
        data = _valid_request()
        data["clinical_text"] = "Short."  # 1 word
        request = PredictRequest(**data)
        with pytest.raises(ValidationError, match="too short"):
            validate_request(request)

    def test_five_word_text_passes(self):
        data = _valid_request()
        data["clinical_text"] = "Patient feels very emotionally stable."
        request = PredictRequest(**data)
        # Should not raise
        validate_request(request)

    def test_zero_fields_trigger_warning(self, caplog):
        data = _valid_request()
        data["structured"]["mood_swings"] = 0
        data["structured"]["anxiety_level"] = 0
        request = PredictRequest(**data)
        import logging
        with caplog.at_level(logging.WARNING):
            validate_request(request)
        # Warning should mention zero-scored fields (log message says "scored 0")
        assert any(
            "scored 0" in r.message.lower() or "zero" in r.message.lower()
            for r in caplog.records
        )
