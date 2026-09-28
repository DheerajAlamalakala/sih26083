"""
Task 4 — baseline mortality/hospitalization models.

FIXED vs v1_0:
- Operates on daily-aggregated ward-day rows (see daily_aggregation.py),
  not hourly rows with mislabeled "daily" targets.
- Three-way time-based split (train/validation/test), not train/test only.
- Rows with missing vulnerability (NaN daily_mortality/hospitalizations)
  are EXCLUDED from training/evaluation rather than zero-filled.

With only ~10 valid ward-days of demo data, a train/val/test split is
almost comically small — that's an honest reflection of the current
data, not a bug in the split logic. Retrain once real multi-ward,
multi-week data exists.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_poisson_deviance, mean_absolute_error

MODEL_VERSION = "baseline_poisson_v1_2"  # bumped: calibration is now persisted at training time

FEATURE_COLUMNS = [
    "thermal_stress_mean",
    "thermal_stress_max",
    "vulnerability_0_100",
    "heat_persistence_hours",
    "doy_sin",
    "doy_cos",
]

TARGETS = ["daily_mortality", "daily_hospitalizations"]


def drop_unlabeled(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with no valid label (missing vulnerability -> NaN target)
    must never enter training or evaluation."""
    return df.dropna(subset=TARGETS).copy()


def time_based_split(df: pd.DataFrame, val_frac: float = 0.2, test_frac: float = 0.2):
    """Chronological train/validation/test split. Cutoffs are computed
    on timestamp quantiles across the whole (already-labeled) dataset."""
    df = df.sort_values("timestamp_utc")
    train_cutoff = df["timestamp_utc"].quantile(1 - val_frac - test_frac)
    val_cutoff = df["timestamp_utc"].quantile(1 - test_frac)

    train = df[df["timestamp_utc"] <= train_cutoff]
    val = df[(df["timestamp_utc"] > train_cutoff) & (df["timestamp_utc"] <= val_cutoff)]
    test = df[df["timestamp_utc"] > val_cutoff]
    return train, val, test


def _prep_xy(df: pd.DataFrame, target: str):
    X = df[FEATURE_COLUMNS].values  # no fillna(0): rows here are already fully labeled/featured
    y = df[target].values
    return X, y


def train_baseline_models(train_df: pd.DataFrame) -> dict[str, PoissonRegressor]:
    models = {}
    for target in TARGETS:
        X, y = _prep_xy(train_df, target)
        model = PoissonRegressor(alpha=1e-3, max_iter=500)
        model.fit(X, y)
        models[target] = model
    return models


def calibrate_saturation(model: PoissonRegressor, train_X: np.ndarray, percentile: float = 90.0) -> float:
    """Where the model's 0-100 risk-score scale saturates, based on the
    TRAINING set's predicted-rate distribution (its 90th percentile by
    default).

    FIXED vs v1_1: this must be computed ONCE, here, at training time,
    and persisted to models/{MODEL_VERSION}_metadata.json. predict.py
    previously recomputed it from whatever rows happened to be in the
    current inference batch — which meant the same ward-day could
    score differently depending on what else was being scored
    alongside it in that call. Inference now only loads this value;
    it never recalculates it.
    """
    train_rates = model.predict(train_X)
    sat = np.percentile(train_rates, percentile)
    return float(max(sat, 1e-6))


def evaluate(models: dict, eval_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target, model in models.items():
        X, y_true = _prep_xy(eval_df, target)
        y_pred = np.clip(model.predict(X), 1e-6, None)
        rows.append({
            "target": target,
            "mean_poisson_deviance": mean_poisson_deviance(np.clip(y_true, 0, None) + 1e-6, y_pred),
            "mae": mean_absolute_error(y_true, y_pred),
            "n": len(y_true),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from src.health.feature_builder import build_features
    from src.health.daily_aggregation import aggregate_to_daily
    from src.health.generate_synthetic_health import generate_synthetic_health

    features = build_features(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    daily = aggregate_to_daily(features)
    synthetic = generate_synthetic_health(daily)
    labeled = drop_unlabeled(synthetic)

    train, val, test = time_based_split(labeled)
    print(f"Labeled ward-days: {len(labeled)} (train={len(train)}, val={len(val)}, test={len(test)})")
    print("NOTE: this is far too small a sample for a real skill estimate — pipeline sanity check only.")

    models = train_baseline_models(train)
    print("\nValidation metrics:")
    print(evaluate(models, val).to_string(index=False))
    print("\nTest metrics:")
    print(evaluate(models, test).to_string(index=False))
