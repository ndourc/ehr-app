"""
Layer 3: Model — Hybrid Classifier
=====================================
Binary classification on the 784-d hybrid_vector using an ensemble of:
  * Random Forest   (RF)
  * Support Vector Machine with RBF kernel (SVM)

Ensemble strategy: average predicted probabilities from both models.

Class encoding:
  0  →  "Stable"
  1  →  "Distress"

Both models apply model-level class weighting to penalise false negatives
(missed Distress cases), as specified by DISTRESS_CLASS_WEIGHT in config.

Serialised with joblib; load once at startup via HybridClassifier.load().
"""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC

from app.config import settings

logger = logging.getLogger(__name__)

_LABEL_MAP: dict[int, str] = {0: "Stable", 1: "Distress"}
_ARTIFACT_FILENAME = "classifier.joblib"


class HybridClassifier:
    """
    Random Forest + SVM ensemble with class-weighted loss.

    Parameters
    ----------
    distress_weight : float
        Weight assigned to label=1 (Distress) relative to label=0 (Stable).
        Higher values penalise false negatives more aggressively.
    random_state : int
        Seed for reproducibility.
    """

    def __init__(
        self,
        distress_weight: float | None = None,
        random_state: int = 42,
    ) -> None:
        distress_weight = distress_weight or settings.DISTRESS_CLASS_WEIGHT
        class_weights = {0: 1.0, 1: distress_weight}

        self.rf = RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            min_samples_leaf=2,
            class_weight=class_weights,
            n_jobs=-1,
            random_state=random_state,
        )
        self.svm = SVC(
            probability=True,
            kernel="rbf",
            C=1.0,
            gamma="scale",
            class_weight=class_weights,
            random_state=random_state,
        )
        self._is_fitted = False

    # ──────────────────────────────────────────────────────────────────────
    # Training
    # ──────────────────────────────────────────────────────────────────────

    def fit(self, X: np.ndarray, y: np.ndarray) -> "HybridClassifier":
        """
        Train both classifiers.

        Parameters
        ----------
        X : np.ndarray  shape (n_samples, 784)
        y : np.ndarray  shape (n_samples,)  — binary {0, 1}
        """
        logger.info(
            "[Classifier] Training — samples=%d  features=%d  "
            "label distribution: {0: %d, 1: %d}",
            X.shape[0], X.shape[1],
            int((y == 0).sum()), int((y == 1).sum()),
        )
        self.rf.fit(X, y)
        logger.info("[Classifier] RandomForest trained.")
        self.svm.fit(X, y)
        logger.info("[Classifier] SVM trained.")
        self._is_fitted = True
        return self

    # ──────────────────────────────────────────────────────────────────────
    # Inference
    # ──────────────────────────────────────────────────────────────────────

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Ensemble probability: average RF and SVM probability outputs.

        Returns
        -------
        np.ndarray  shape (n_samples, 2)
            Column 0 = P(Stable), Column 1 = P(Distress).
        """
        self._assert_fitted()
        rf_proba = self.rf.predict_proba(X)
        svm_proba = self.svm.predict_proba(X)
        return (rf_proba + svm_proba) / 2.0

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Hard-label prediction (threshold 0.5 on P(Distress))."""
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def predict_single(self, hybrid_vector: np.ndarray) -> tuple[str, float]:
        """
        Convenience wrapper for single-sample inference.

        Returns
        -------
        (label, confidence_score)
            label            : "Distress" or "Stable"
            confidence_score : probability of the predicted class
        """
        proba = self.predict_proba(hybrid_vector.reshape(1, -1))[0]
        label_idx = int(proba[1] >= 0.5)
        label = _LABEL_MAP[label_idx]
        confidence = float(proba[label_idx])
        logger.info(
            "[Classifier] Prediction: %s | Confidence: %.4f | P(Distress): %.4f",
            label, confidence, proba[1],
        )
        return label, confidence

    # ──────────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────────

    def save(self, artifacts_dir: str | Path) -> Path:
        """Serialise the fitted classifier to disk with joblib."""
        self._assert_fitted()
        path = Path(artifacts_dir) / _ARTIFACT_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("[Classifier] Saved to %s.", path)
        return path

    @classmethod
    def load(cls, artifacts_dir: str | Path) -> "HybridClassifier":
        """Deserialise a previously saved HybridClassifier."""
        path = Path(artifacts_dir) / _ARTIFACT_FILENAME
        if not path.exists():
            raise FileNotFoundError(
                f"[Classifier] No artifact found at '{path}'. "
                "Run training/train.py to train the model first."
            )
        obj: HybridClassifier = joblib.load(path)
        logger.info("[Classifier] Loaded from %s.", path)
        return obj

    # ──────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────

    def _assert_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError(
                "HybridClassifier is not trained. "
                "Call .fit() or load a saved artifact."
            )
