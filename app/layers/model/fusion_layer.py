"""
Layer 3: Model — Hybrid Fusion Layer
=====================================
Concatenates the ClinicalBERT CLS embedding (768-d) with the normalised
structured feature vector (16-d) to produce the canonical hybrid_vector.

Canonical layout (FIXED — do not reorder after training):
─────────────────────────────────────────────────────────
  Indices  0 : 768   ClinicalBERT CLS embedding
  Indices 768 : 784  Normalised structured features (FEATURE_ORDER)
─────────────────────────────────────────────────────────
  Total     784 dimensions
"""
from __future__ import annotations

import logging

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Derived from model architecture + schema spec; do not modify independently.
EMBEDDING_DIM: int = 768
STRUCTURED_DIM: int = 16
HYBRID_DIM: int = EMBEDDING_DIM + STRUCTURED_DIM  # 784


def build_hybrid_vector(
    embedding_vector: torch.Tensor,
    structured_vector: np.ndarray,
) -> np.ndarray:
    """
    Fuse transformer embedding with structured features into one flat vector.

    Parameters
    ----------
    embedding_vector : torch.Tensor
        CLS embedding from ClinicalBERT. Shape (1, 768) or (768,).
    structured_vector : np.ndarray
        Normalised structured features. Shape (16,).

    Returns
    -------
    np.ndarray
        Hybrid feature vector. Shape (784,), dtype float32.

    Raises
    ------
    ValueError
        If either input has an unexpected dimension.
    """
    emb_np = embedding_vector.detach().cpu().numpy().flatten().astype(np.float32)

    if emb_np.shape[0] != EMBEDDING_DIM:
        raise ValueError(
            f"[FusionLayer] Embedding dimension mismatch. "
            f"Expected {EMBEDDING_DIM}, got {emb_np.shape[0]}."
        )

    if structured_vector.shape[0] != STRUCTURED_DIM:
        raise ValueError(
            f"[FusionLayer] Structured vector dimension mismatch. "
            f"Expected {STRUCTURED_DIM}, got {structured_vector.shape[0]}."
        )

    hybrid = np.concatenate([emb_np, structured_vector.astype(np.float32)])

    logger.debug(
        "[FusionLayer] hybrid_vector built — shape=%s  "
        "emb[:3]=%s  struct=%s",
        hybrid.shape,
        emb_np[:3].tolist(),
        structured_vector.tolist(),
    )

    return hybrid
