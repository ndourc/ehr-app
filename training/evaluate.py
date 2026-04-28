"""
Training — Evaluation Utilities
=================================
Computes and prints the full suite of performance metrics required by
the project specification:

  * Accuracy
  * Precision  (macro + per-class)
  * Recall     (macro + per-class) — Priority metric: Recall(Distress) ≥ 0.90
  * F1-score   (macro + per-class)
  * ROC-AUC

Also renders and saves a confusion matrix and ROC curve.

Usage
-----
    from training.evaluate import evaluate_model
    report = evaluate_model(y_true, y_pred, y_proba[:, 1], label="Hybrid")
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)


def evaluate_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba_distress: np.ndarray,
    label: str = "Model",
    artifacts_dir: str | Path = "artifacts",
    save_plots: bool = True,
) -> dict:
    """
    Compute and print all required evaluation metrics.

    Parameters
    ----------
    y_true             : Ground-truth labels {0, 1}.
    y_pred             : Hard predictions {0, 1}.
    y_proba_distress   : Probability of Distress class (column 1 of predict_proba).
    label              : Descriptive name printed in the report header.
    artifacts_dir      : Where to save confusion-matrix and ROC curve images.
    save_plots         : If True, save matplotlib figures.

    Returns
    -------
    dict with keys: accuracy, precision, recall, f1, roc_auc,
                    distress_recall, distress_precision, distress_f1
    """
    acc = accuracy_score(y_true, y_pred)
    roc_auc = roc_auc_score(y_true, y_proba_distress)
    report = classification_report(
        y_true, y_pred, target_names=["Stable", "Distress"], output_dict=True
    )
    cm = confusion_matrix(y_true, y_pred)

    distress_recall = report["Distress"]["recall"]
    distress_precision = report["Distress"]["precision"]
    distress_f1 = report["Distress"]["f1-score"]
    macro_precision = report["macro avg"]["precision"]
    macro_recall = report["macro avg"]["recall"]
    macro_f1 = report["macro avg"]["f1-score"]

    _print_report(
        label, acc, roc_auc,
        macro_precision, macro_recall, macro_f1,
        distress_precision, distress_recall, distress_f1,
        cm,
    )

    if save_plots:
        _save_confusion_matrix(cm, label, artifacts_dir)
        _save_roc_curve(y_true, y_proba_distress, roc_auc, label, artifacts_dir)

    return {
        "accuracy": round(acc, 4),
        "precision": round(macro_precision, 4),
        "recall": round(macro_recall, 4),
        "f1": round(macro_f1, 4),
        "roc_auc": round(roc_auc, 4),
        "distress_recall": round(distress_recall, 4),
        "distress_precision": round(distress_precision, 4),
        "distress_f1": round(distress_f1, 4),
    }


def _print_report(
    label, acc, roc_auc,
    macro_p, macro_r, macro_f1,
    d_prec, d_rec, d_f1, cm,
) -> None:
    sep = "─" * 55
    print(f"\n{sep}")
    print(f"  Evaluation Report — {label}")
    print(sep)
    print(f"  Accuracy             : {acc:.4f}")
    print(f"  ROC-AUC              : {roc_auc:.4f}")
    print(f"  Macro Precision      : {macro_p:.4f}")
    print(f"  Macro Recall         : {macro_r:.4f}")
    print(f"  Macro F1             : {macro_f1:.4f}")
    print(f"  Distress Precision   : {d_prec:.4f}")
    print(f"  Distress Recall      : {d_rec:.4f}   ← target ≥ 0.90")
    print(f"  Distress F1          : {d_f1:.4f}")
    print(f"  Confusion Matrix:\n{cm}")

    # Clinical target check
    if d_rec < 0.90:
        print(f"  ⚠  Recall target NOT met ({d_rec:.4f} < 0.90). "
              "Consider increasing DISTRESS_CLASS_WEIGHT.")
    else:
        print(f"  ✓  Recall target met ({d_rec:.4f} ≥ 0.90).")
    if acc < 0.85:
        print(f"  ⚠  Accuracy target NOT met ({acc:.4f} < 0.85).")
    else:
        print(f"  ✓  Accuracy target met ({acc:.4f} ≥ 0.85).")
    print(sep)


def _save_confusion_matrix(
    cm: np.ndarray, label: str, artifacts_dir: str | Path
) -> None:
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig, ax = plt.subplots(figsize=(5, 4))
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=["Stable", "Distress"],
            yticklabels=["Stable", "Distress"],
            ax=ax,
        )
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_title(f"Confusion Matrix — {label}")
        path = Path(artifacts_dir) / f"cm_{label.replace(' ', '_').lower()}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Confusion matrix saved → {path}")
    except ImportError:
        print("  [Skipped] matplotlib/seaborn not available for plot saving.")


def _save_roc_curve(
    y_true: np.ndarray,
    y_score: np.ndarray,
    roc_auc: float,
    label: str,
    artifacts_dir: str | Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
        from sklearn.metrics import roc_curve

        fpr, tpr, _ = roc_curve(y_true, y_score)
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.plot(fpr, tpr, label=f"AUC = {roc_auc:.4f}", color="steelblue")
        ax.plot([0, 1], [0, 1], "--", color="grey")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title(f"ROC Curve — {label}")
        ax.legend()
        path = Path(artifacts_dir) / f"roc_{label.replace(' ', '_').lower()}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  ROC curve saved → {path}")
    except ImportError:
        print("  [Skipped] matplotlib not available for plot saving.")
