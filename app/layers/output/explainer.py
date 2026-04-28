"""
Layer 4: Output — Attention-based NLP Explainer
================================================
Maps ClinicalBERT attention weights back to original words to expose the
specific linguistic features that drove the prediction.

Algorithm
---------
  1. Stack attention tensors from all transformer layers.
  2. Average across all layers AND across all attention heads.
     → A single (seq_len × seq_len) attention matrix.
  3. Take the CLS-token row (index 0) as per-token importance scores;
     the CLS token attends to each position encoding global semantics.
  4. Re-aggregate sub-word (WordPiece) tokens: a word's weight is the
     MAX across its constituent pieces (conservative; avoids averaging
     away short, high-signal pieces).
  5. Normalise weights to [0, 1] relative to the most-attended word.
  6. Translate NEG_-prefixed tokens back to human-readable "not_<word>".
  7. Return the top-k word–weight pairs sorted descending by weight.

No special tokens ([CLS], [SEP], [PAD]) appear in the output.
"""
from __future__ import annotations

import logging

import torch
from transformers import BatchEncoding, PreTrainedTokenizerBase

from app.layers.ingestion.schemas import TokenWeight

logger = logging.getLogger(__name__)

_NEG_PREFIX = "NEG_"


def extract_token_importance(
    attentions: tuple,
    tokenizer_output: BatchEncoding,
    tokenizer: PreTrainedTokenizerBase,
    top_k: int = 10,
) -> list[TokenWeight]:
    """
    Extract word-level attention importances from ClinicalBERT outputs.

    Parameters
    ----------
    attentions       : tuple of torch.Tensor
                       Per-layer attention, each (1, n_heads, seq_len, seq_len).
    tokenizer_output : BatchEncoding
                       Raw tokenizer result from the same encoding call.
    tokenizer        : PreTrainedTokenizerBase
                       Must be the same tokenizer used for encoding.
    top_k            : int
                       Number of top words to return.

    Returns
    -------
    list[TokenWeight]
        Sorted descending by weight; special tokens excluded.
    """
    # ── 1. Stack + average across layers and heads ────────────────────────
    attn_stack = torch.stack(attentions, dim=0)  # (L, 1, H, S, S)
    attn_stack = attn_stack.squeeze(1)            # (L, H, S, S)
    mean_attn = attn_stack.mean(dim=(0, 1))       # (S, S)  — avg layers & heads

    # ── 2. CLS row = how much each position is attended from CLS ──────────
    cls_attn = mean_attn[0, :].detach().cpu().numpy()  # (S,)

    # ── 3. Map sub-word (WordPiece) tokens → words ────────────────────────
    input_ids = tokenizer_output["input_ids"][0].tolist()
    wp_tokens = tokenizer.convert_ids_to_tokens(input_ids)

    _SPECIAL = {"[CLS]", "[SEP]", "[PAD]", "<s>", "</s>", "<pad>"}

    word_weights: list[tuple[str, float]] = []
    current_parts: list[str] = []
    current_weight: float = 0.0

    def _flush() -> None:
        if current_parts:
            word = "".join(current_parts)
            word_weights.append((word, current_weight))

    for token, weight in zip(wp_tokens, cls_attn):
        if token in _SPECIAL:
            _flush()
            current_parts = []
            current_weight = 0.0
            continue

        if token.startswith("##"):
            # Continuation sub-word — extend current word
            current_parts.append(token[2:])
            current_weight = max(current_weight, float(weight))
        else:
            _flush()
            current_parts = [token]
            current_weight = float(weight)

    _flush()

    if not word_weights:
        logger.warning("[Explainer] No word weights extracted.")
        return []

    # ── 4. Normalise to [0, 1] ────────────────────────────────────────────
    max_w = max(w for _, w in word_weights) or 1.0
    word_weights = [(word, round(w / max_w, 4)) for word, w in word_weights]

    # ── 5. Humanise NEG_ tokens ───────────────────────────────────────────
    word_weights = [
        (word.replace(_NEG_PREFIX, "not_") if word.startswith(_NEG_PREFIX) else word, weight)
        for word, weight in word_weights
    ]

    # ── 6. Sort and truncate ──────────────────────────────────────────────
    word_weights.sort(key=lambda x: x[1], reverse=True)
    top = word_weights[:top_k]

    logger.info(
        "[Explainer] Top-%d tokens: %s",
        top_k,
        [(w, f"{s:.4f}") for w, s in top],
    )
    return [TokenWeight(word=w, weight=s) for w, s in top]
