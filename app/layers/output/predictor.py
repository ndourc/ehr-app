"""
Layer 4: Output — Prediction Orchestrator
==========================================
PredictionPipeline wires together all four layers for a single inference
call. It is designed as a stateful singleton: load once at startup and
reuse across requests.

Internal dataclass InferenceResult carries the full output including
intermediate artefacts needed for auditable database storage.

Full inference flow
-------------------
  PredictRequest (validated)
       │
       ▼  Layer 2 — Text Preprocessing
  cleaned_text : str
       │
       ▼  Layer 2 — Structured Normalisation
  structured_vector : np.ndarray (16,)
       │
       ▼  Layer 3 — ClinicalBERT Encoding
  NLPOutput  {embedding, attentions, tokenizer_output, sentiment, token_count}
       │
       ▼  Layer 3 — Hybrid Fusion
  hybrid_vector : np.ndarray (784,)
       │
       ▼  Layer 3 — Ensemble Classification
  (label, confidence) : (str, float)
       │
       ▼  Layer 4 — Attention Explainer
  important_tokens : list[TokenWeight]
       │
       ▼
  InferenceResult  →  PredictResponse (API) + audit fields (DB)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.config import settings
from app.layers.ingestion.schemas import PredictRequest, PredictResponse, TokenWeight
from app.layers.model.classifier import HybridClassifier
from app.layers.model.fusion_layer import build_hybrid_vector
from app.layers.model.nlp_engine import ClinicalBERTEngine
from app.layers.output.explainer import extract_token_importance
from app.layers.processing.structured_processor import structured_to_vector, vector_to_dict
from app.layers.processing.text_processor import preprocess_text

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """Full output of one PredictionPipeline.predict() call."""

    # ── Core prediction ───────────────────────────────────────────────────
    patient_id: str
    prediction: str           # "Distress" | "Stable"
    confidence_score: float
    important_tokens: list[TokenWeight]

    # ── Intermediate data (stored for auditability) ───────────────────────
    cleaned_text: str
    normalised_structured: dict[str, float]
    sentiment: str
    token_count: int
    latency_ms: float

    def to_response(self) -> PredictResponse:
        """Convert to the public API response schema."""
        return PredictResponse(
            patient_id=self.patient_id,
            prediction=self.prediction,
            confidence_score=self.confidence_score,
            important_tokens=self.important_tokens,
        )


class PredictionPipeline:
    """
    Stateful inference pipeline. Instantiate once at application startup.

    If no trained classifier artifact is found, the pipeline loads in
    degraded mode and raises RuntimeError on prediction attempts.
    """

    def __init__(self) -> None:
        self.nlp_engine = ClinicalBERTEngine()

        try:
            self.classifier: HybridClassifier = HybridClassifier.load(
                settings.ARTIFACTS_DIR
            )
            logger.info("[Pipeline] Classifier artifact loaded.")
        except FileNotFoundError:
            logger.warning(
                "[Pipeline] No classifier artifact found at '%s'. "
                "Run  training/train.py  before serving prediction requests.",
                settings.ARTIFACTS_DIR,
            )
            self.classifier = None  # type: ignore[assignment]

    @property
    def is_ready(self) -> bool:
        return self.classifier is not None

    def predict(self, request: PredictRequest) -> InferenceResult:
        """
        Execute the full inference pipeline for one request.

        Parameters
        ----------
        request : PredictRequest
            Pre-validated combined EHR payload.

        Returns
        -------
        InferenceResult
            Prediction, confidence, XAI tokens, and all intermediate data.

        Raises
        ------
        RuntimeError
            If the classifier has not been trained/loaded.
        """
        if not self.is_ready:
            raise RuntimeError(
                "Classifier is not available. "
                "Train the model first (training/train.py)."
            )

        t_start = time.perf_counter()

        # ── Layer 2: Preprocessing ────────────────────────────────────────
        cleaned_text = preprocess_text(request.clinical_text)
        structured_vector: np.ndarray = structured_to_vector(request.structured)
        normalised_structured = vector_to_dict(structured_vector)

        # ── Layer 3: NLP Encoding ─────────────────────────────────────────
        nlp_output = self.nlp_engine.encode(cleaned_text)

        # ── Layer 3: Fusion ───────────────────────────────────────────────
        hybrid_vector = build_hybrid_vector(
            nlp_output.embedding_vector,
            structured_vector,
        )

        # ── Layer 3: Classification ───────────────────────────────────────
        label, confidence = self.classifier.predict_single(hybrid_vector)

        # ── Layer 4: Explainability ───────────────────────────────────────
        important_tokens = extract_token_importance(
            attentions=nlp_output.attentions,
            tokenizer_output=nlp_output.tokenizer_output,
            tokenizer=self.nlp_engine.tokenizer,
            top_k=settings.ATTENTION_TOP_K,
        )

        latency_ms = (time.perf_counter() - t_start) * 1_000

        logger.info(
            "[Pipeline] DONE — patient_id=%s  prediction=%s  "
            "confidence=%.4f  latency=%.1f ms",
            request.patient_id, label, confidence, latency_ms,
        )

        return InferenceResult(
            patient_id=request.patient_id,
            prediction=label,
            confidence_score=round(confidence, 4),
            important_tokens=important_tokens,
            cleaned_text=cleaned_text,
            normalised_structured=normalised_structured,
            sentiment=nlp_output.sentiment,
            token_count=nlp_output.token_count,
            latency_ms=round(latency_ms, 2),
        )
