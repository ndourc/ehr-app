"""
Training — Synthetic EHR Data Generator
=========================================
Generates a realistic, heavily imbalanced dataset that mimics the
expected distribution of clinical EHR records.

  * 80 % Stable patients, 20 % Distress patients (configurable).
  * Structured features are drawn from label-specific distributions.
  * Clinical text is sampled from template sentences that reflect the
    patient's label and individual feature scores.
  * Each sample is returned as a dict matching the PredictRequest schema
    so it can be fed directly into the preprocessing pipeline.

Usage
-----
    from training.data_generator import generate_dataset
    df = generate_dataset(n_samples=1000, distress_ratio=0.2, seed=42)
"""
from __future__ import annotations

import random
from typing import Sequence

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Feature columns (must match FEATURE_ORDER in structured_processor.py)
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_COLUMNS: list[str] = [
    "mood_swings", "anxiety_level", "depression_indicators", "emotional_stability",
    "days_indoors", "social_interaction", "activity_level", "sleep_quality",
    "coping_struggles", "stress_level", "work_engagement", "motivation_level",
    "concentration_level", "decision_difficulty", "memory_issues", "support_system",
]

# ─────────────────────────────────────────────────────────────────────────────
# Label-specific feature distributions
# mu = expected mean (0–3 scale); sigma = std dev
# ─────────────────────────────────────────────────────────────────────────────
_DISTRESS_MU = {
    "mood_swings": 2.5, "anxiety_level": 2.7, "depression_indicators": 2.6,
    "emotional_stability": 2.4, "days_indoors": 2.3, "social_interaction": 2.5,
    "activity_level": 2.4, "sleep_quality": 2.6, "coping_struggles": 2.7,
    "stress_level": 2.8, "work_engagement": 2.3, "motivation_level": 2.6,
    "concentration_level": 2.4, "decision_difficulty": 2.5, "memory_issues": 2.3,
    "support_system": 2.1,
}
_STABLE_MU = {
    "mood_swings": 0.6, "anxiety_level": 0.5, "depression_indicators": 0.4,
    "emotional_stability": 0.7, "days_indoors": 0.8, "social_interaction": 0.5,
    "activity_level": 0.6, "sleep_quality": 0.4, "coping_struggles": 0.5,
    "stress_level": 0.7, "work_engagement": 0.6, "motivation_level": 0.5,
    "concentration_level": 0.5, "decision_difficulty": 0.4, "memory_issues": 0.3,
    "support_system": 0.7,
}
_SIGMA = 0.6

# ─────────────────────────────────────────────────────────────────────────────
# Clinical text sentence pools
# ─────────────────────────────────────────────────────────────────────────────
_DISTRESS_SENTENCES: list[str] = [
    "Patient reports feeling extremely anxious and overwhelmed.",
    "Unable to sleep for more than 3 hours per night; insomnia is severe.",
    "States they cannot concentrate on any task for more than five minutes.",
    "Reports persistent feelings of sadness and hopelessness that never lift.",
    "Patient cannot stop worrying; breathing becomes difficult when anxious.",
    "Mentions feeling completely isolated from family and friends.",
    "Has not left the house in two weeks; afraid to go outside.",
    "Feeling exhausted all the time; no motivation to do anything.",
    "Reports recurring intrusive thoughts and difficulty controlling emotions.",
    "Cannot make simple decisions; feels paralysed by indecision.",
    "Memory has been terrible lately; forgetting basic daily tasks.",
    "Does not feel supported by anyone around them; feels completely alone.",
    "Crying spells occurring multiple times daily without clear triggers.",
    "Patient is not eating regularly; appetite has disappeared entirely.",
    "Describes mood as crashing unexpectedly throughout the day.",
    "Cannot engage in work; lost interest in all previously enjoyed activities.",
]

_STABLE_SENTENCES: list[str] = [
    "Patient reports feeling generally well and emotionally balanced.",
    "Sleeping approximately 7–8 hours per night without interruptions.",
    "Concentration is adequate; able to complete daily tasks effectively.",
    "Mood has been stable with no significant swings reported.",
    "Engaging socially with friends and family on a regular basis.",
    "Leaving the house daily; maintaining an active routine.",
    "Reports a good support system at home and in the workplace.",
    "Work engagement is positive; finds the job manageable and satisfying.",
    "No significant anxiety noted; feels calm in most situations.",
    "Decision-making is functioning well; no notable difficulties.",
    "Memory and cognitive function appear intact.",
    "Motivation level is appropriate; patient is pursuing personal goals.",
    "Coping methods are effective; patient uses exercise and journaling.",
    "Stress levels manageable; patient handles pressure without distress.",
    "No depressive indicators observed; affect is bright and appropriate.",
    "Patient reports feeling connected and not isolated.",
]

_NEGATION_FRAGMENTS: list[str] = [
    "Patient does not express suicidal ideation.",
    "Does not report panic attacks recently.",
    "Cannot identify any specific trigger for the current episode.",
    "States they have not been able to enjoy activities they once loved.",
    "Has not spoken to a counsellor or therapist in the past month.",
]


def _sample_features(label: int, rng: np.random.Generator) -> dict[str, int]:
    """Draw ordinal feature values from label-specific distributions."""
    mu_map = _DISTRESS_MU if label == 1 else _STABLE_MU
    values: dict[str, int] = {}
    for col in FEATURE_COLUMNS:
        raw = rng.normal(loc=mu_map[col], scale=_SIGMA)
        values[col] = int(np.clip(round(raw), 0, 3))
    return values


def _sample_text(label: int, rng: random.Random) -> str:
    """Compose a short synthetic clinical note from sentence pools."""
    pool = _DISTRESS_SENTENCES if label == 1 else _STABLE_SENTENCES
    n_sentences = rng.randint(3, 6)
    chosen = rng.sample(pool, min(n_sentences, len(pool)))
    # Inject a negation fragment into distress notes ~40% of the time
    if label == 1 and rng.random() < 0.4:
        chosen.append(rng.choice(_NEGATION_FRAGMENTS))
    return " ".join(chosen)


def generate_dataset(
    n_samples: int = 1000,
    distress_ratio: float = 0.20,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic EHR dataset.

    Parameters
    ----------
    n_samples      : Total number of samples.
    distress_ratio : Proportion labelled as Distress (1). Default 20 %.
    seed           : Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: patient_id, clinical_text, label (0/1), + 16 feature cols.
    """
    np_rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)

    n_distress = int(n_samples * distress_ratio)
    n_stable = n_samples - n_distress

    rows: list[dict] = []
    for i, label in enumerate([0] * n_stable + [1] * n_distress):
        feats = _sample_features(label, np_rng)
        row = {
            "patient_id": f"PT{i + 1:05d}",
            "clinical_text": _sample_text(label, py_rng),
            "label": label,
        }
        row.update(feats)
        rows.append(row)

    df = pd.DataFrame(rows)
    # Shuffle
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    print(
        f"[DataGenerator] Generated {len(df)} samples — "
        f"Stable: {(df.label == 0).sum()}  Distress: {(df.label == 1).sum()}"
    )
    return df
