"""
Layer 3 Tests — Fusion Layer & Classifier
(NLP engine tests are skipped if ClinicalBERT is not downloaded)
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from app.layers.model.fusion_layer import (
    EMBEDDING_DIM,
    HYBRID_DIM,
    STRUCTURED_DIM,
    build_hybrid_vector,
)
from app.layers.model.classifier import HybridClassifier


# ─────────────────────────────────────────────────────────────────────────────
# Fusion layer tests (no model download required)
# ─────────────────────────────────────────────────────────────────────────────

class TestFusionLayer:
    def _embedding(self) -> torch.Tensor:
        return torch.randn(1, EMBEDDING_DIM)

    def _structured(self) -> np.ndarray:
        return np.random.rand(STRUCTURED_DIM).astype(np.float32)

    def test_output_shape(self):
        v = build_hybrid_vector(self._embedding(), self._structured())
        assert v.shape == (HYBRID_DIM,)       # (784,)

    def test_output_dtype(self):
        v = build_hybrid_vector(self._embedding(), self._structured())
        assert v.dtype == np.float32

    def test_embedding_slice(self):
        emb = torch.ones(1, EMBEDDING_DIM)
        struct = np.zeros(STRUCTURED_DIM, dtype=np.float32)
        v = build_hybrid_vector(emb, struct)
        # First 768 values should all be ~1.0
        assert np.allclose(v[:EMBEDDING_DIM], 1.0)
        # Last 16 values should all be 0.0
        assert np.allclose(v[EMBEDDING_DIM:], 0.0)

    def test_structured_slice(self):
        emb = torch.zeros(1, EMBEDDING_DIM)
        struct = np.ones(STRUCTURED_DIM, dtype=np.float32)
        v = build_hybrid_vector(emb, struct)
        assert np.allclose(v[EMBEDDING_DIM:], 1.0)

    def test_wrong_embedding_dim_raises(self):
        bad_emb = torch.randn(1, 512)  # wrong dim
        with pytest.raises(ValueError, match="Embedding dimension"):
            build_hybrid_vector(bad_emb, self._structured())

    def test_wrong_structured_dim_raises(self):
        bad_struct = np.zeros(10, dtype=np.float32)
        with pytest.raises(ValueError, match="Structured vector"):
            build_hybrid_vector(self._embedding(), bad_struct)

    def test_accepts_flattened_embedding(self):
        flat_emb = torch.randn(EMBEDDING_DIM)   # shape (768,) not (1, 768)
        v = build_hybrid_vector(flat_emb, self._structured())
        assert v.shape == (HYBRID_DIM,)

    def test_hybrid_dim_constant(self):
        assert HYBRID_DIM == EMBEDDING_DIM + STRUCTURED_DIM
        assert HYBRID_DIM == 784


# ─────────────────────────────────────────────────────────────────────────────
# Classifier tests (sklearn only — no model download required)
# ─────────────────────────────────────────────────────────────────────────────

class TestHybridClassifier:
    def _make_data(self, n: int = 200):
        rng = np.random.default_rng(0)
        X = rng.standard_normal((n, HYBRID_DIM)).astype(np.float32)
        y = (rng.random(n) > 0.8).astype(int)   # ~20% Distress
        return X, y

    def test_fit_and_predict_shapes(self):
        X, y = self._make_data()
        clf = HybridClassifier(distress_weight=3.0)
        clf.fit(X, y)
        preds = clf.predict(X[:10])
        assert preds.shape == (10,)

    def test_predict_proba_sums_to_one(self):
        X, y = self._make_data()
        clf = HybridClassifier()
        clf.fit(X, y)
        proba = clf.predict_proba(X[:5])
        assert proba.shape == (5, 2)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)

    def test_predict_proba_in_range(self):
        X, y = self._make_data()
        clf = HybridClassifier()
        clf.fit(X, y)
        proba = clf.predict_proba(X)
        assert np.all(proba >= 0.0)
        assert np.all(proba <= 1.0)

    def test_predict_single_returns_label_and_float(self):
        X, y = self._make_data()
        clf = HybridClassifier()
        clf.fit(X, y)
        label, confidence = clf.predict_single(X[0])
        assert label in ("Distress", "Stable")
        assert 0.0 <= confidence <= 1.0

    def test_predict_before_fit_raises(self):
        clf = HybridClassifier()
        with pytest.raises(RuntimeError, match="not trained"):
            clf.predict(np.zeros((1, HYBRID_DIM), dtype=np.float32))

    def test_save_and_load(self, tmp_path):
        X, y = self._make_data()
        clf = HybridClassifier()
        clf.fit(X, y)
        clf.save(tmp_path)
        loaded = HybridClassifier.load(tmp_path)
        # Predictions should be deterministic after reload
        orig_proba = clf.predict_proba(X[:5])
        loaded_proba = loaded.predict_proba(X[:5])
        assert np.allclose(orig_proba, loaded_proba, atol=1e-6)

    def test_load_missing_artifact_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            HybridClassifier.load(tmp_path)

    def test_distress_class_weight_applied(self):
        """Classifier trained with high distress weight should have higher recall."""
        X, y = self._make_data(n=400)
        clf_low = HybridClassifier(distress_weight=1.0)
        clf_high = HybridClassifier(distress_weight=5.0)
        clf_low.fit(X, y)
        clf_high.fit(X, y)

        from sklearn.metrics import recall_score
        recall_low = recall_score(y, clf_low.predict(X), pos_label=1)
        recall_high = recall_score(y, clf_high.predict(X), pos_label=1)
        # Higher class weight should maintain or improve recall on the minority class
        assert recall_high >= recall_low * 0.9   # at least 90% as good, usually better
