"""
Training — Ablation Study
===========================
Compares three model variants to quantify the contribution of each
data modality:

  1. Structured-Only   — 16 normalised ordinal features, Random Forest
  2. NLP-Only          — 768-d ClinicalBERT CLS embedding, Random Forest
  3. Hybrid            — 784-d concatenation, RF + SVM ensemble (full model)

All three are trained and evaluated on the same stratified train/test split.
Results are printed as a side-by-side comparison table and saved to
artifacts/ablation_report.txt.

Usage
-----
    python -m training.ablation
    python -m training.ablation --samples 800 --csv data/training_data.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.layers.model.classifier import HybridClassifier
from app.layers.model.nlp_engine import ClinicalBERTEngine
from app.layers.processing.text_processor import preprocess_text
from app.utils.logging_config import configure_logging
from training.data_generator import FEATURE_COLUMNS, generate_dataset
from training.evaluate import evaluate_model
from training.train import compute_or_load_embeddings

configure_logging()
logger = logging.getLogger(__name__)


def _structured_matrix(df: pd.DataFrame) -> np.ndarray:
    return (df[FEATURE_COLUMNS].values.astype(np.float32) / 3.0)


def run_ablation(
    df: pd.DataFrame,
    artifacts_dir: Path,
    seed: int = 42,
) -> dict[str, dict]:
    """
    Train and evaluate all three model variants.

    Returns
    -------
    dict mapping variant name → evaluation metrics dict
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    try:
        from imblearn.over_sampling import SMOTE
    except ImportError:
        SMOTE = None
        logger.warning("[Ablation] imbalanced-learn not available; SMOTE disabled.")

    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # ── Prepare features ──────────────────────────────────────────────────
    logger.info("[Ablation] Loading ClinicalBERT for embedding computation…")
    engine = ClinicalBERTEngine()
    cache_path = artifacts_dir / "embedding_cache.npz"
    embeddings = compute_or_load_embeddings(
        df["clinical_text"].tolist(), engine, cache_path
    )
    structured = _structured_matrix(df)
    hybrid = np.concatenate([embeddings, structured], axis=1)
    labels = df["label"].values.astype(int)

    # ── Shared train/test split ───────────────────────────────────────────
    idx = np.arange(len(df))
    train_idx, test_idx = train_test_split(
        idx, test_size=0.20, stratify=labels, random_state=seed
    )

    def _smote_if_available(X_tr: np.ndarray, y_tr: np.ndarray):
        if SMOTE is not None:
            X_tr, y_tr = SMOTE(random_state=seed).fit_resample(X_tr, y_tr)
        return X_tr, y_tr

    dw = {0: 1.0, 1: settings.DISTRESS_CLASS_WEIGHT}

    results: dict[str, dict] = {}

    # ── Variant 1: Structured-Only ────────────────────────────────────────
    logger.info("[Ablation] Training Structured-Only model…")
    X_s_tr, y_s_tr = _smote_if_available(structured[train_idx], labels[train_idx])
    rf_s = RandomForestClassifier(
        n_estimators=300, class_weight=dw, n_jobs=-1, random_state=seed
    )
    rf_s.fit(X_s_tr, y_s_tr)
    y_pred_s = rf_s.predict(structured[test_idx])
    y_proba_s = rf_s.predict_proba(structured[test_idx])[:, 1]
    results["Structured-Only"] = evaluate_model(
        labels[test_idx], y_pred_s, y_proba_s,
        label="Structured-Only", artifacts_dir=artifacts_dir,
    )

    # ── Variant 2: NLP-Only ───────────────────────────────────────────────
    logger.info("[Ablation] Training NLP-Only model…")
    X_n_tr, y_n_tr = _smote_if_available(embeddings[train_idx], labels[train_idx])
    rf_n = RandomForestClassifier(
        n_estimators=300, class_weight=dw, n_jobs=-1, random_state=seed
    )
    rf_n.fit(X_n_tr, y_n_tr)
    y_pred_n = rf_n.predict(embeddings[test_idx])
    y_proba_n = rf_n.predict_proba(embeddings[test_idx])[:, 1]
    results["NLP-Only"] = evaluate_model(
        labels[test_idx], y_pred_n, y_proba_n,
        label="NLP-Only", artifacts_dir=artifacts_dir,
    )

    # ── Variant 3: Hybrid (full system) ──────────────────────────────────
    logger.info("[Ablation] Training Hybrid model…")
    X_h_tr, y_h_tr = _smote_if_available(hybrid[train_idx], labels[train_idx])
    clf_h = HybridClassifier(distress_weight=settings.DISTRESS_CLASS_WEIGHT, random_state=seed)
    clf_h.fit(X_h_tr, y_h_tr)
    y_pred_h = clf_h.predict(hybrid[test_idx])
    y_proba_h = clf_h.predict_proba(hybrid[test_idx])[:, 1]
    results["Hybrid"] = evaluate_model(
        labels[test_idx], y_pred_h, y_proba_h,
        label="Hybrid", artifacts_dir=artifacts_dir,
    )

    # ── Summary table ─────────────────────────────────────────────────────
    _print_summary(results)
    _save_report(results, artifacts_dir)
    return results


def _print_summary(results: dict[str, dict]) -> None:
    header = f"\n{'─'*72}"
    print(header)
    print(f"{'Ablation Study — Summary':^72}")
    print(f"{'─'*72}")
    cols = ["accuracy", "distress_recall", "distress_f1", "roc_auc"]
    col_w = 18
    print(f"{'Variant':<25}" + "".join(f"{c:<{col_w}}" for c in cols))
    print(f"{'─'*72}")
    for variant, metrics in results.items():
        row = f"{variant:<25}" + "".join(
            f"{metrics.get(c, 'N/A'):<{col_w}}" for c in cols
        )
        print(row)
    print(f"{'─'*72}")
    print("  Target: Accuracy ≥ 0.85  |  Distress Recall ≥ 0.90")
    print(f"{'─'*72}\n")


def _save_report(results: dict[str, dict], artifacts_dir: Path) -> None:
    report_path = artifacts_dir / "ablation_report.txt"
    lines = ["Ablation Study Report", "=" * 50, ""]
    for variant, metrics in results.items():
        lines.append(f"Variant: {variant}")
        for k, v in metrics.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Ablation] Report saved → {report_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ablation study.")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--samples", type=int, default=800)
    parser.add_argument("--distress-ratio", type=float, default=0.20)
    parser.add_argument(
        "--artifacts-dir", type=Path, default=Path(settings.ARTIFACTS_DIR)
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        df = generate_dataset(
            n_samples=args.samples,
            distress_ratio=args.distress_ratio,
            seed=args.seed,
        )

    run_ablation(df, artifacts_dir=args.artifacts_dir, seed=args.seed)
