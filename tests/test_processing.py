"""
Layer 2 Tests — Text & Structured Processors
"""
from __future__ import annotations

import numpy as np
import pytest

from app.layers.ingestion.schemas import StructuredInput
from app.layers.processing.structured_processor import (
    FEATURE_ORDER,
    structured_to_vector,
    vector_to_dict,
)
from app.layers.processing.text_processor import (
    expand_contractions,
    lowercase,
    preserve_negations,
    preprocess_text,
    remove_special_characters,
    remove_template_text,
)


# ─────────────────────────────────────────────────────────────────────────────
# Text processor tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRemoveTemplateText:
    def test_removes_patient_name_line(self):
        text = "Patient Name: John Doe\nPatient feels anxious today."
        result = remove_template_text(text)
        assert "Patient Name" not in result
        assert "anxious" in result

    def test_removes_signed_by(self):
        text = "Patient is stable. Signed by Dr Smith 2026-01-01."
        result = remove_template_text(text)
        assert "Signed by" not in result

    def test_preserves_clinical_content(self):
        text = "Patient reports severe anxiety and sleep disturbances."
        result = remove_template_text(text)
        assert "anxiety" in result
        assert "sleep disturbances" in result


class TestExpandContractions:
    def test_cant_expanded(self):
        assert "cannot" in expand_contractions("I can't sleep.")

    def test_wont_expanded(self):
        assert "will not" in expand_contractions("They won't engage.")

    def test_didnt_expanded(self):
        assert "did not" in expand_contractions("Patient didn't eat today.")

    def test_no_contraction_unchanged(self):
        text = "Patient is feeling well today."
        assert expand_contractions(text) == text


class TestLowercase:
    def test_lowercases_all(self):
        assert lowercase("ANXIETY Level HIGH") == "anxiety level high"


class TestRemoveSpecialCharacters:
    def test_removes_punctuation(self):
        result = remove_special_characters("hello, world! (test).")
        assert "," not in result
        assert "!" not in result
        assert "(" not in result

    def test_preserves_letters_and_digits(self):
        result = remove_special_characters("patient123 is okay")
        assert "patient123" in result
        assert "okay" in result

    def test_collapses_whitespace(self):
        result = remove_special_characters("a  b   c")
        assert "  " not in result


class TestPreserveNegations:
    """CRITICAL: negations must NEVER be dropped."""

    def test_not_is_preserved_and_next_word_prefixed(self):
        result = preserve_negations("patient does not feel happy")
        assert "not" in result
        assert "NEG_feel" in result

    def test_no_preserved(self):
        result = preserve_negations("patient has no motivation")
        assert "no" in result
        assert "NEG_motivation" in result

    def test_never_preserved(self):
        result = preserve_negations("patient never sleeps well")
        assert "never" in result
        assert "NEG_sleeps" in result

    def test_cannot_preserved(self):
        result = preserve_negations("cannot concentrate on tasks")
        assert "cannot" in result
        assert "NEG_concentrate" in result

    def test_multiple_negations(self):
        result = preserve_negations("not happy and not eating")
        assert result.count("NEG_") == 2

    def test_negation_at_end_no_crash(self):
        # Negation word at end of text — must not raise
        result = preserve_negations("feeling not")
        assert "not" in result

    def test_no_negation_text_unchanged(self):
        text = "patient feels well and motivated"
        result = preserve_negations(text)
        assert "NEG_" not in result

    def test_negation_trigger_word_retained_in_output(self):
        """The negation trigger itself must stay in the output."""
        result = preserve_negations("patient does not feel well")
        tokens = result.split()
        assert "not" in tokens


class TestPreprocessTextPipeline:
    def test_returns_string(self):
        result = preprocess_text("Patient reports severe anxiety.")
        assert isinstance(result, str)

    def test_lowercase_output(self):
        result = preprocess_text("SEVERE ANXIETY LEVEL REPORTED.")
        assert result == result.lower() or "NEG_" in result  # NEG_ is uppercase marker

    def test_negation_preserved_end_to_end(self):
        result = preprocess_text("Patient cannot sleep and does not eat.")
        # After pipeline, some form of negation marker should persist
        assert "neg_" in result.lower() or "not" in result or "cannot" in result

    def test_empty_after_template_removal_handled(self):
        # Mostly template text — result should be empty or very short string
        text = "Patient Name: John Doe. Signed by Dr. Smith."
        result = preprocess_text(text)
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# Structured processor tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_structured(**overrides) -> StructuredInput:
    defaults = {col: 1 for col in FEATURE_ORDER}
    defaults.update(overrides)
    return StructuredInput(**defaults)


class TestStructuredProcessor:
    def test_output_shape(self):
        s = _make_structured()
        v = structured_to_vector(s)
        assert v.shape == (16,)

    def test_output_dtype_float32(self):
        v = structured_to_vector(_make_structured())
        assert v.dtype == np.float32

    def test_normalisation_range(self):
        # With value=3 (max), normalised should be 1.0
        s = _make_structured(**{col: 3 for col in FEATURE_ORDER})
        v = structured_to_vector(s)
        assert np.allclose(v, 1.0)

    def test_normalisation_zero(self):
        s = _make_structured(**{col: 0 for col in FEATURE_ORDER})
        v = structured_to_vector(s)
        assert np.allclose(v, 0.0)

    def test_normalisation_midpoint(self):
        s = _make_structured(**{col: 1 for col in FEATURE_ORDER})
        v = structured_to_vector(s)
        assert np.allclose(v, 1 / 3)

    def test_feature_order_16_elements(self):
        assert len(FEATURE_ORDER) == 16

    def test_vector_to_dict_roundtrip(self):
        s = _make_structured(anxiety_level=2, stress_level=3)
        v = structured_to_vector(s)
        d = vector_to_dict(v)
        assert "anxiety_level" in d
        assert "stress_level" in d
        assert abs(d["anxiety_level"] - 2 / 3) < 1e-5
        assert abs(d["stress_level"] - 1.0) < 1e-5

    def test_vector_to_dict_wrong_length_raises(self):
        with pytest.raises(ValueError):
            vector_to_dict(np.zeros(10, dtype=np.float32))
