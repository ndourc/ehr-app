"""
Training — End-to-End Training Script
=======================================
Trains the Hybrid Classifier (Random Forest + SVM ensemble) on the
784-dimensional hybrid feature vector (768-d ClinicalBERT embedding +
16-d normalised structured features).

Steps
-----
  1. Load or generate training data.
  2. Apply text preprocessing pipeline to all samples.
  3. Encode each clinical note with ClinicalBERT → CLS embeddings.
     Embeddings are cached to disk to avoid recomputation on reruns.
  4. Normalise structured features.
  5. Build hybrid feature matrix (n_samples × 784).
  6. Stratified train/test split (80/20).
  7. Apply SMOTE to the training hybrid vectors (data-level resampling).
  8. Train HybridClassifier (RF + SVM with class-weighted loss).
  9. Evaluate on held-out test set.
  10. Save classifier artifact to artifacts/.

Usage
-----
    # With synthetic data (default)
    python -m training.train

    # With a CSV file (patient_id, clinical_text, label, + 16 feature cols)
    python -m training.train --csv data/training_data.csv --samples 2000
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is on sys.path when run as a module
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.layers.model.classifier import HybridClassifier
from app.layers.model.fusion_layer import build_hybrid_vector
from app.layers.model.nlp_engine import ClinicalBERTEngine
from app.layers.processing.structured_processor import FEATURE_ORDER
from app.layers.processing.text_processor import preprocess_text
from app.utils.logging_config import configure_logging
from training.data_generator import FEATURE_COLUMNS, generate_dataset
from training.evaluate import evaluate_model

configure_logging()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
_EMBEDDING_CACHE_FILE = "embedding_cache.npz"
_TEST_SIZE = 0.20
_RANDOM_STATE = 42


# ─────────────────────────────────────────────────────────────────────────────
# Embedding computation with caching
# ─────────────────────────────────────────────────────────────────────────────

def compute_or_load_embeddings(
    texts: list[str],
    engine: ClinicalBERTEngine,
    cache_path: Path,
) -> np.ndarray:
    """
    Encode texts with ClinicalBERT. Loads from cache if available;
    computes and caches otherwise.

    Returns
    -------
    np.ndarray  shape (n_samples, 768)
    """
    if cache_path.exists():
        logger.info("[Train] Loading embeddings from cache: %s", cache_path)
        data = np.load(cache_path)
        return data["embeddings"]

    logger.info("[Train] Computing ClinicalBERT embeddings for %d texts…", len(texts))
    embeddings: list[np.ndarray] = []

    for i, text in enumerate(texts):
        cleaned = preprocess_text(text)
        nlp_out = engine.encode(cleaned)
        emb = nlp_out.embedding_vector.detach().cpu().numpy().flatten()
        embeddings.append(emb)
        if (i + 1) % 50 == 0 or (i + 1) == len(texts):
            logger.info(
                "[Train] Encoded %d / %d (%.1f%%)",
                i + 1, len(texts), 100 * (i + 1) / len(texts),
            )

    result = np.stack(embeddings, axis=0).astype(np.float32)
    np.savez_compressed(cache_path, embeddings=result)
    logger.info("[Train] Embeddings cached to %s.", cache_path)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Structured feature matrix
# ─────────────────────────────────────────────────────────────────────────────

def build_structured_matrix(df: pd.DataFrame) -> np.ndarray:
    """Extract and normalise the 16 structured columns → (n, 16) float32."""
    raw = df[FEATURE_COLUMNS].values.astype(np.float32)
    return raw / 3.0  # MinMax normalisation: scale 0–3 → 0–1


# ─────────────────────────────────────────────────────────────────────────────
# Main training function
# ─────────────────────────────────────────────────────────────────────────────

def train(
    df: pd.DataFrame,
    artifacts_dir: Path,
    test_size: float = _TEST_SIZE,
    random_state: int = _RANDOM_STATE,
) -> None:
    """
    Full training pipeline.

    Parameters
    ----------
    df            : DataFrame with columns: patient_id, clinical_text, label, + 16 features
    artifacts_dir : Where to save model artifacts and embedding cache
    test_size     : Fraction of data held out for evaluation
    random_state  : Reproducibility seed
    """
    from sklearn.model_selection import train_test_split

    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load NLP engine ────────────────────────────────────────────────
    logger.info("[Train] Loading ClinicalBERT engine…")
    engine = ClinicalBERTEngine()

    # ── 2. Compute / load embeddings ──────────────────────────────────────
    cache_path = artifacts_dir / _EMBEDDING_CACHE_FILE
    embeddings = compute_or_load_embeddings(
        df["clinical_text"].tolist(), engine, cache_path
    )

    # ── 3. Build structured matrix ────────────────────────────────────────
    structured_matrix = build_structured_matrix(df)

    # ── 4. Build hybrid matrix ────────────────────────────────────────────
    hybrid_matrix = np.concatenate([embeddings, structured_matrix], axis=1)
    labels = df["label"].values.astype(int)
    logger.info("[Train] Hybrid matrix shape: %s", hybrid_matrix.shape)
    logger.info(
        "[Train] Label distribution — Stable: %d  Distress: %d",
        int((labels == 0).sum()), int((labels == 1).sum()),
    )

    # ── 5. Stratified train / test split ──────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        hybrid_matrix, labels,
        test_size=test_size,
        stratify=labels,
        random_state=random_state,
    )
    logger.info(
        "[Train] Split → train: %d  test: %d", len(X_train), len(X_test)
    )

    # ── 6. SMOTE oversampling on training set ─────────────────────────────
    try:
        from imblearn.over_sampling import SMOTE  # noqa: PLC0415

        smote = SMOTE(random_state=random_state)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
        logger.info(
            "[Train] SMOTE applied — resampled training set: %d samples. "
            "Distress: %d  Stable: %d",
            len(X_train_res),
            int((y_train_res == 1).sum()),
            int((y_train_res == 0).sum()),
        )
    except ImportError:
        logger.warning("[Train] imbalanced-learn not installed; SMOTE skipped.")
        X_train_res, y_train_res = X_train, y_train

    # ── 7. Train HybridClassifier ─────────────────────────────────────────
    classifier = HybridClassifier(
        distress_weight=settings.DISTRESS_CLASS_WEIGHT,
        random_state=random_state,
    )
    classifier.fit(X_train_res, y_train_res)

    # ── 8. Evaluate on test set ───────────────────────────────────────────
    y_pred = classifier.predict(X_test)
    y_proba = classifier.predict_proba(X_test)[:, 1]
    evaluate_model(
        y_test, y_pred, y_proba,
        label="Hybrid (RF+SVM Ensemble)",
        artifacts_dir=artifacts_dir,
    )

    # ── 9. Save artifact ──────────────────────────────────────────────────
    artifact_path = classifier.save(artifacts_dir)
    logger.info("[Train] Training complete. Artifact → %s", artifact_path)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the EHR Predictive Engine.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to a CSV file with columns: patient_id, clinical_text, label, + 16 features. "
             "If omitted, synthetic data is generated.",
    )
    parser.add_argument(
        "--samples", type=int, default=1000,
        help="Number of synthetic samples to generate (ignored if --csv is provided).",
    )
    parser.add_argument(
        "--distress-ratio", type=float, default=0.20,
        help="Proportion of Distress samples in synthetic data (default 0.20).",
    )
    parser.add_argument(
        "--artifacts-dir", type=Path,
        default=Path(settings.ARTIFACTS_DIR),
        help="Directory to save model artifacts.",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.csv:
        logger.info("[Train] Loading data from CSV: %s", args.csv)
        df = pd.read_csv(args.csv)
    else:
        logger.info(
            "[Train] Generating %d synthetic samples (distress_ratio=%.2f)…",
            args.samples, args.distress_ratio,
        )
        df = generate_dataset(
            n_samples=args.samples,
            distress_ratio=args.distress_ratio,
            seed=args.seed,
        )

    train(df, artifacts_dir=args.artifacts_dir, random_state=args.seed)
