"""
Layer 3: Model — ClinicalBERT NLP Engine
==========================================
Responsibilities
----------------
  * Tokenise and encode pre-processed clinical text.
  * Extract a high-dimensional CLS-token embedding (shape: (1, hidden_size)).
  * Capture per-layer attention matrices for downstream explainability.
  * Emit a coarse-grained sentiment label: positive | negative | neutral | mixed.

Stack: Hugging Face Transformers + PyTorch (inference only, torch.no_grad).
Model: medicalai/ClinicalBERT (configurable via CLINICALBERT_MODEL env var).

This class is intended as a singleton — instantiate once at startup and
share across requests to avoid repeated model loading overhead.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
from transformers import AutoModel, AutoTokenizer, BatchEncoding

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class NLPOutput:
    """Outputs from a single ClinicalBERT encoding call."""

    embedding_vector: torch.Tensor   # shape (1, hidden_size)
    attentions: tuple                # tuple of per-layer tensors: (1, heads, seq, seq)
    tokenizer_output: BatchEncoding  # raw tokenizer output for token→word mapping
    sentiment: str                   # "positive" | "negative" | "neutral" | "mixed"
    token_count: int                 # number of tokens (including [CLS] and [SEP])


class ClinicalBERTEngine:
    """
    NLP engine backed by a domain-specific clinical BERT model.

    Attributes
    ----------
    embedding_dim : int
        Hidden size of the loaded model (typically 768 for BERT-base).
    """

    def __init__(self, model_name: str | None = None) -> None:
        model_name = model_name or settings.CLINICALBERT_MODEL
        logger.info("[NLPEngine] Loading tokenizer and model: %s", model_name)

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name, output_attentions=True)
        self.model.eval()

        self._model_name = model_name
        logger.info(
            "[NLPEngine] Model loaded. Hidden size: %d.  Layers: %d.  Heads: %d.",
            self.model.config.hidden_size,
            self.model.config.num_hidden_layers,
            self.model.config.num_attention_heads,
        )

    @property
    def embedding_dim(self) -> int:
        return self.model.config.hidden_size  # 768 for BERT-base

    @torch.no_grad()
    def encode(self, cleaned_text: str) -> NLPOutput:
        """
        Tokenise and forward-pass a single pre-processed clinical note.

        Parameters
        ----------
        cleaned_text : str
            Output from the text preprocessing pipeline.

        Returns
        -------
        NLPOutput
            Contains the CLS embedding, all attention layers, raw tokenizer
            output, a coarse sentiment label, and the token count.
        """
        logger.info("[NLPEngine] Encoding text — %d chars.", len(cleaned_text))

        tokenizer_output: BatchEncoding = self.tokenizer(
            cleaned_text,
            return_tensors="pt",
            truncation=True,
            max_length=settings.MAX_TOKEN_LENGTH,
            padding=False,
        )

        token_count: int = int(tokenizer_output["input_ids"].shape[1])

        model_output = self.model(
            **tokenizer_output,
            output_attentions=True,
        )

        # CLS token embedding — position 0 of the last hidden state
        embedding_vector: torch.Tensor = model_output.last_hidden_state[:, 0, :]

        sentiment = self._coarse_sentiment(embedding_vector)

        logger.info(
            "[NLPEngine] Encoding complete — tokens=%d  embedding=%s  sentiment=%s.",
            token_count,
            tuple(embedding_vector.shape),
            sentiment,
        )

        return NLPOutput(
            embedding_vector=embedding_vector,
            attentions=model_output.attentions,
            tokenizer_output=tokenizer_output,
            sentiment=sentiment,
            token_count=token_count,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _coarse_sentiment(embedding: torch.Tensor) -> str:
        """
        Lightweight heuristic sentiment proxy from the CLS activation pattern.
        For production, replace with a fine-tuned sentiment classification head.

        Labels: positive | negative | neutral | mixed
        """
        mean_val = float(embedding.mean())
        std_val = float(embedding.std())

        if std_val >= 0.55:
            return "mixed"
        if mean_val > 0.03:
            return "positive"
        if mean_val < -0.03:
            return "negative"
        return "neutral"
