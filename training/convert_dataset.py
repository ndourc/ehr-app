"""
training/convert_dataset.py
============================
Converts the raw Mental Health Dataset (survey-style CSV) into a format
compatible with the EHR Predictive Engine training pipeline.

Output columns (matches `python -m training.train --csv` format):
  patient_id, clinical_text, label,
  + all 16 ordinal feature columns (0-3 scale)

Usage
-----
  python -m training.convert_dataset
  python -m training.convert_dataset --input "training/Mental Health Dataset.csv" \
                                     --output training/ehr_training_data.csv
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

from app.utils.logging_config import configure_logging
from training.data_generator import FEATURE_COLUMNS

configure_logging()
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Ordinal encoding maps  (source column values -> 0..3 integer)
# -----------------------------------------------------------------------------

_DAYS_INDOORS_MAP: dict[str, int] = {
    "go out every day":   0,
    "1-14 days":          1,
    "15-30 days":         2,
    "more than 2 months": 3,
}

_MOOD_SWINGS_MAP: dict[str, int] = {
    "low":    0,
    "medium": 1,
    "high":   2,
}

# Yes/No binary fields -> high (2) or none (0); unmapped values -> 1 (mild)
_YESNO_HIGH: dict[str, int] = {"yes": 2, "no": 0}

# Work_Interest: Yes=engaged(0), Maybe=neutral(1), No=disengaged(2)
_WORK_INTEREST: dict[str, int] = {"yes": 0, "maybe": 1, "no": 2}

# Social_Weakness: No weakness(0), Maybe(1), Yes=high withdrawal(2)
_SOCIAL_WEAKNESS: dict[str, int] = {"no": 0, "maybe": 1, "yes": 2}

# family_history used only as support-system synthesis proxy
_FAMILY_SUPPORT: dict[str, int] = {"yes": 0, "no": 2}

# -----------------------------------------------------------------------------
# Neutral behavioural-observation sentence pools (indexed by ordinal score 0..3)
# No clinical/mental-health terminology; occupational-wellness framing only.
# -----------------------------------------------------------------------------

_STRESS_POOL: list[str] = [
    "Stress levels are minimal; the participant manages workload without difficulty.",
    "Some elevation in pressure noted, though the participant describes it as manageable.",
    "Stress levels are elevated; the participant reports difficulty unwinding after work.",
    "The participant describes stress as pervasive and consistently difficult to control.",
]
_WORK_POOL: list[str] = [
    "Engagement with assigned tasks is strong; work is described as meaningful.",
    "Work interest is variable; output is maintained but motivation fluctuates.",
    "Shows reduced engagement; tasks feel effortful and difficult to initiate.",
    "Has largely disengaged from work duties; unable to find purpose in tasks.",
]
_SOCIAL_POOL: list[str] = [
    "Maintains regular contact with peers and participates in group activities.",
    "Social interactions are somewhat reduced; prefers smaller gatherings recently.",
    "Experiencing noticeable difficulty sustaining peer connections.",
    "Has largely withdrawn from social activities and group engagement.",
]
_INDOORS_POOL: list[str] = [
    "Leaves the premises daily and maintains an active external routine.",
    "Has remained primarily indoors for approximately one to two weeks.",
    "Has spent most of the past month at home with minimal outdoor activity.",
    "Has not left their residence in more than two months.",
]
_MOOD_POOL: list[str] = [
    "Emotional state is stable and consistent throughout the reporting period.",
    "Reports moderate variability in mood, generally within a manageable range.",
    "Mood fluctuations are frequent and at times interfere with daily functioning.",
    "Experiences severe and unpredictable emotional shifts throughout each day.",
]
_COPING_POOL: list[str] = [
    "Applies effective strategies to manage pressure and maintain equilibrium.",
    "Coping strategies are partially effective; some periods are more challenging.",
    "Reports difficulty applying coping strategies when under sustained pressure.",
    "Feels unable to cope adequately; current strategies are largely ineffective.",
]


def _pick(pool: list[str], score: int) -> str:
    return pool[min(int(score), len(pool) - 1)]


def _generate_text(row: pd.Series) -> str:
    """Compose a neutral behavioural observation note from the ordinal values."""
    return " ".join([
        _pick(_STRESS_POOL,  row["stress_level"]),
        _pick(_WORK_POOL,    row["work_engagement"]),
        _pick(_SOCIAL_POOL,  row["social_interaction"]),
        _pick(_INDOORS_POOL, row["days_indoors"]),
        _pick(_MOOD_POOL,    row["mood_swings"]),
        _pick(_COPING_POOL,  row["coping_struggles"]),
    ])


# -----------------------------------------------------------------------------
# Synthesize the 9 ordinal fields absent from the source dataset
# -----------------------------------------------------------------------------

def _synth(base: float, rng: np.random.Generator, sigma: float = 0.6) -> int:
    """Gaussian perturbation of a base value, clipped to [0, 3]."""
    return int(np.clip(round(rng.normal(loc=base, scale=sigma)), 0, 3))


def _add_synthesized_fields(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    stress         = df["stress_level"].values.astype(float)
    mood           = df["mood_swings"].values.astype(float)
    coping         = df["coping_struggles"].values.astype(float)
    work           = df["work_engagement"].values.astype(float)
    indoors        = df["days_indoors"].values.astype(float)
    label          = df["label"].values.astype(float)
    support_base   = df.pop("_family_support_base").values.astype(float)

    # anxiety_level: correlated with stress
    df["anxiety_level"] = [_synth(v, rng) for v in stress]

    # depression_indicators: blend of mood instability + coping failure
    df["depression_indicators"] = [_synth(v, rng) for v in (mood + coping) / 2]

    # emotional_stability: inverse of mood_swings
    df["emotional_stability"] = [_synth(v, rng) for v in (3 - mood)]

    # activity_level: inverse of isolation + inverse of work disengagement
    df["activity_level"] = [_synth(v, rng) for v in ((3 - indoors) + (3 - work)) / 2]

    # sleep_quality: correlated with stress
    df["sleep_quality"] = [_synth(v, rng) for v in stress]

    # motivation_level: blend of work disengagement + coping failure
    df["motivation_level"] = [_synth(v, rng) for v in (work + coping) / 2]

    # concentration_level: correlated with work disengagement
    df["concentration_level"] = [_synth(v, rng) for v in work]

    # decision_difficulty: correlated with coping failure
    df["decision_difficulty"] = [_synth(v, rng) for v in coping]

    # memory_issues: mild correlation with overall at-risk status
    df["memory_issues"] = [_synth(v, rng) for v in label * 1.5 + coping * 0.5]

    # support_system: derived from family_history proxy
    df["support_system"] = [_synth(v, rng) for v in (3 - support_base)]

    return df


# -----------------------------------------------------------------------------
# Main conversion
# -----------------------------------------------------------------------------

_REQUIRED_COLS = {
    "treatment", "Days_Indoors", "Growing_Stress", "Mood_Swings",
    "Coping_Struggles", "Work_Interest", "Social_Weakness",
}


def convert(input_path: Path, output_path: Path, seed: int = 42) -> pd.DataFrame:
    logger.info("[Convert] Reading source dataset: %s", input_path)
    raw = pd.read_csv(input_path)

    missing = _REQUIRED_COLS - set(raw.columns)
    if missing:
        raise ValueError(f"Source CSV missing required columns: {missing}")

    # 1. Drop exact duplicate rows (dataset is a Cartesian expansion)
    before = len(raw)
    raw = raw.drop_duplicates().reset_index(drop=True)
    logger.info("[Convert] Deduplication: %d -> %d rows", before, len(raw))

    # 2. Label: treatment Yes->1 (At-Risk), No->0 (Engaged)
    raw["label"] = raw["treatment"].str.strip().str.lower().map({"yes": 1, "no": 0})
    raw = raw.dropna(subset=["label"]).reset_index(drop=True)
    raw["label"] = raw["label"].astype(int)

    # 3. Build output dataframe with directly mapped fields
    df = pd.DataFrame()

    occ = raw.get("Occupation", pd.Series(["UNK"] * len(raw))).str[:3].str.upper().fillna("UNK")
    cty = raw.get("Country",    pd.Series(["XX"]  * len(raw))).str[:2].str.upper().fillna("XX")
    df["patient_id"] = occ + "-" + cty + "-" + pd.RangeIndex(1, len(raw) + 1).astype(str).str.zfill(5)
    df["label"] = raw["label"].values

    def encode(series: pd.Series, mapping: dict[str, int], default: int = 1) -> pd.Series:
        return series.str.strip().str.lower().map(mapping).fillna(default).astype(int)

    df["mood_swings"]        = encode(raw["Mood_Swings"],      _MOOD_SWINGS_MAP)
    df["days_indoors"]       = encode(raw["Days_Indoors"],     _DAYS_INDOORS_MAP)
    df["stress_level"]       = encode(raw["Growing_Stress"],   _YESNO_HIGH)
    df["coping_struggles"]   = encode(raw["Coping_Struggles"], _YESNO_HIGH)
    df["work_engagement"]    = encode(raw["Work_Interest"],    _WORK_INTEREST)
    df["social_interaction"] = encode(raw["Social_Weakness"],  _SOCIAL_WEAKNESS)

    # Stash family_history as synthesis proxy; dropped inside _add_synthesized_fields
    family_col = raw.get("family_history", pd.Series(["no"] * len(raw)))
    df["_family_support_base"] = encode(family_col, _FAMILY_SUPPORT)

    # 4. Synthesize the 9 missing ordinal fields
    df = _add_synthesized_fields(df, seed=seed)

    # 5. Generate neutral clinical text from the encoded ordinal values
    logger.info("[Convert] Generating behavioural observation notes...")
    df["clinical_text"] = df.apply(_generate_text, axis=1)

    # 6. Reorder to match training/train.py --csv expected column order
    output_cols = ["patient_id", "clinical_text", "label"] + FEATURE_COLUMNS
    df = df[output_cols]

    # 7. Validate all feature values are within [0, 3]
    for col in FEATURE_COLUMNS:
        bad = df[(df[col] < 0) | (df[col] > 3)]
        if not bad.empty:
            logger.warning("[Convert] %d out-of-range values in '%s' — clamping.", len(bad), col)
            df[col] = df[col].clip(0, 3)

    # 8. Report
    n_at_risk = (df["label"] == 1).sum()
    n_engaged = (df["label"] == 0).sum()
    logger.info(
        "[Convert] Final: %d samples  |  Engaged: %d  At-Risk: %d  (%.1f%% at-risk)",
        len(df), n_engaged, n_at_risk, 100 * n_at_risk / len(df),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info("[Convert] Saved -> %s", output_path)
    return df


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert the Mental Health Dataset to EHR training format."
    )
    p.add_argument(
        "--input",  type=Path,
        default=Path("training/Mental Health Dataset.csv"),
        help="Path to the source Mental Health Dataset CSV.",
    )
    p.add_argument(
        "--output", type=Path,
        default=Path("training/ehr_training_data.csv"),
        help="Where to write the converted EHR-compatible CSV.",
    )
    p.add_argument("--seed", type=int, default=42, help="Random seed.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    convert(args.input, args.output, seed=args.seed)
