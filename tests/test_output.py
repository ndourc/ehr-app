"""
Layer 4 Tests — Explainer & Predictor (output layer)
Uses mocks to avoid requiring a downloaded ClinicalBERT model in CI.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from app.layers.ingestion.schemas import TokenWeight
from app.layers.model.fusion_layer import EMBEDDING_DIM, HYBRID_DIM, STRUCTURED_DIM
from app.layers.output.explainer import extract_token_importance


# ─────────────────────────────────────────────────────────────────────────────
# Explainer tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExplainer:
    """Test attention-to-token mapping without a real model."""

    def _make_attentions(self, seq_len: int = 8, n_layers: int = 2, n_heads: int = 2):
        """Return fake attention tensors matching ClinicalBERT output format."""
        attentions = tuple(
            torch.rand(1, n_heads, seq_len, seq_len)
            for _ in range(n_layers)
        )
        return attentions

    def _make_tokenizer_output(self, tokens: list[str]):
        """
        Build a minimal BatchEncoding stub from a token list.
        input_ids are arbitrary; tokens are controlled via mock tokenizer.
        """
        from transformers import BatchEncoding
        input_ids = torch.tensor([[i for i in range(len(tokens))]])
        return BatchEncoding({"input_ids": input_ids})

    def _make_tokenizer_mock(self, tokens: list[str]):
        """Mock tokenizer that returns our controlled token list."""
        tokenizer = MagicMock()
        tokenizer.convert_ids_to_tokens.return_value = tokens
        return tokenizer

    def test_returns_list_of_token_weights(self):
        tokens = ["[CLS]", "patient", "feels", "anxious", "and", "NEG_sleep", "[SEP]"]
        attentions = self._make_attentions(seq_len=len(tokens))
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=5)
        assert isinstance(result, list)
        assert all(isinstance(t, TokenWeight) for t in result)

    def test_excludes_special_tokens(self):
        tokens = ["[CLS]", "patient", "anxious", "[SEP]"]
        attentions = self._make_attentions(seq_len=4)
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=10)
        words = [t.word for t in result]
        assert "[CLS]" not in words
        assert "[SEP]" not in words

    def test_top_k_limit_respected(self):
        tokens = ["[CLS]"] + [f"word{i}" for i in range(20)] + ["[SEP]"]
        attentions = self._make_attentions(seq_len=len(tokens))
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=5)
        assert len(result) <= 5

    def test_weights_normalised_to_max_one(self):
        tokens = ["[CLS]", "anxious", "isolated", "hopeless", "[SEP]"]
        attentions = self._make_attentions(seq_len=len(tokens))
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=10)
        if result:
            max_weight = max(t.weight for t in result)
            assert max_weight <= 1.0 + 1e-6

    def test_sorted_descending(self):
        tokens = ["[CLS]", "feel", "not", "NEG_happy", "and", "anxious", "[SEP]"]
        attentions = self._make_attentions(seq_len=len(tokens))
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=10)
        weights = [t.weight for t in result]
        assert weights == sorted(weights, reverse=True)

    def test_neg_prefix_humanised(self):
        """NEG_happy should appear as not_happy in output."""
        tokens = ["[CLS]", "NEG_happy", "NEG_sleeping", "[SEP]"]
        attentions = self._make_attentions(seq_len=len(tokens))
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=10)
        words = [t.word for t in result]
        # No raw NEG_ prefix should appear
        assert not any(w.startswith("NEG_") for w in words)
        # Human-readable not_ form may appear
        assert any(w.startswith("not_") for w in words)

    def test_wordpiece_merging(self):
        """Sub-word tokens (##suffix) should merge with their root."""
        tokens = ["[CLS]", "anxi", "##ous", "isolated", "[SEP]"]
        attentions = self._make_attentions(seq_len=len(tokens))
        tok_out = self._make_tokenizer_output(tokens)
        tokenizer = self._make_tokenizer_mock(tokens)

        result = extract_token_importance(attentions, tok_out, tokenizer, top_k=10)
        words = [t.word for t in result]
        # Sub-word pieces should be merged; "anxious" (or "anxi") present, "##ous" not
        assert not any("##" in w for w in words)


# ─────────────────────────────────────────────────────────────────────────────
# Predictor / PredictionPipeline integration test (mocked components)
# ─────────────────────────────────────────────────────────────────────────────

class TestPredictionPipeline:
    """End-to-end pipeline test with mocked NLP engine and classifier."""

    def _make_request(self):
        from app.layers.ingestion.schemas import PredictRequest, StructuredInput
        return PredictRequest(
            patient_id="PT_TEST",
            timestamp="2026-01-15T10:00:00",
            clinical_text="Patient reports extreme anxiety and cannot sleep at all.",
            structured=StructuredInput(
                mood_swings=3, anxiety_level=3, depression_indicators=2,
                emotional_stability=2, days_indoors=2, social_interaction=2,
                activity_level=1, sleep_quality=3, coping_struggles=2,
                stress_level=3, work_engagement=1, motivation_level=2,
                concentration_level=2, decision_difficulty=3, memory_issues=1,
                support_system=1,
            ),
        )

    def test_pipeline_predict_returns_inference_result(self):
        from app.layers.output.predictor import PredictionPipeline, InferenceResult

        with (
            patch("app.layers.output.predictor.ClinicalBERTEngine") as MockEngine,
            patch("app.layers.output.predictor.HybridClassifier") as MockCLF,
        ):
            # Mock NLP engine
            mock_engine = MockEngine.return_value
            from app.layers.model.nlp_engine import NLPOutput
            fake_nlp_out = NLPOutput(
                embedding_vector=torch.zeros(1, EMBEDDING_DIM),
                attentions=tuple(torch.rand(1, 2, 6, 6) for _ in range(2)),
                tokenizer_output=MagicMock(
                    **{"__getitem__": lambda self, k: torch.tensor([[0, 1, 2, 3, 4, 5]])}
                ),
                sentiment="negative",
                token_count=6,
            )
            mock_engine.encode.return_value = fake_nlp_out
            mock_engine.tokenizer = MagicMock()
            mock_engine.tokenizer.convert_ids_to_tokens.return_value = [
                "[CLS]", "patient", "anxious", "NEG_sleep", "worry", "[SEP]"
            ]

            # Mock classifier
            MockCLF.load.return_value.__class__ = MagicMock
            mock_clf = MagicMock()
            mock_clf.predict_single.return_value = ("Distress", 0.92)
            MockCLF.load.return_value = mock_clf

            pipeline = PredictionPipeline()
            pipeline.classifier = mock_clf  # inject directly
            pipeline.nlp_engine = mock_engine

            request = self._make_request()
            result = pipeline.predict(request)

            assert isinstance(result, InferenceResult)
            assert result.patient_id == "PT_TEST"
            assert result.prediction in ("Distress", "Stable")
            assert 0.0 <= result.confidence_score <= 1.0
            assert isinstance(result.important_tokens, list)

    def test_pipeline_not_ready_without_classifier(self):
        from app.layers.output.predictor import PredictionPipeline

        with (
            patch("app.layers.output.predictor.ClinicalBERTEngine"),
            patch("app.layers.output.predictor.HybridClassifier") as MockCLF,
        ):
            MockCLF.load.side_effect = FileNotFoundError("No artifact")
            pipeline = PredictionPipeline()
            assert not pipeline.is_ready

    def test_inference_result_to_response(self):
        from app.layers.output.predictor import InferenceResult
        from app.layers.ingestion.schemas import PredictResponse

        result = InferenceResult(
            patient_id="PT001",
            prediction="Distress",
            confidence_score=0.93,
            important_tokens=[TokenWeight(word="anxious", weight=0.87)],
            cleaned_text="anxious isolated",
            normalised_structured={},
            sentiment="negative",
            token_count=10,
            latency_ms=45.2,
        )
        response = result.to_response()
        assert isinstance(response, PredictResponse)
        assert response.prediction == "Distress"
        assert response.confidence_score == 0.93
        assert response.important_tokens[0].word == "anxious"
