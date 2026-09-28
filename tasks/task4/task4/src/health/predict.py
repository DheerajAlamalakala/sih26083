"""
Task 4 — predict.py (inference only)

FIXED vs v1_0:
- Loads models saved by train_models.py instead of retraining on the
  same data it predicts on (was a training-set inference loop).
- Operates on daily-aggregated ward-days, matching the corrected
  daily_mortality/hospitalizations target definition.
- Drivers are computed per-target from that target's own model
  (previously hospitalization output wrongly reused mortality's
  drivers).
- Rows with no vulnerability match get null risk scores and a
  low-confidence flag instead of a fabricated zero-vulnerability
  prediction.

FIXED vs v1_1:
- Risk-score calibration (the saturation point for the 0-100
  transform) is now loaded from models/{MODEL_VERSION}_metadata.json,
  where train_models.py persisted it from the TRAINING set alone.
  v1_1 recomputed this per inference batch, which meant the same
  ward-day could score differently depending on what else was in
  that call — a real bug, not just a documentation gap.
- Adds forecast_issued_at_utc to the output schema, per the
  HealthRiskRecord contract. It is always null right now: Task 1 does
  not yet deliver a real forecast-issue timestamp, and forecast_day
  here is still derived from cumcount() over historical rows, not a
  genuine forecast horizon (see FORECAST_APPROX_FLAG). Adding the
  field now means Task 5/6 don't need a schema change later; it must
  stay null until Task 1 supplies a real issue time.

Never recomputes WBGT/UTCI/HI — those pass through from Stage 1.
"""
from __future__ import annotations
import json
import os
import numpy as np
import pandas as pd
import joblib

from src.health.feature_builder import build_features
from src.health.daily_aggregation import aggregate_to_daily
from src.health.baseline_risk import FEATURE_COLUMNS, MODEL_VERSION

RISK_LEVEL_BANDS = [(25.0, "low"), (50.0, "moderate"), (75.0, "high"), (100.01, "severe")]
FORECAST_APPROX_FLAG = "FORECAST_DAY_APPROXIMATED"
NO_PREDICTION_FLAG = "INSUFFICIENT_DATA_FOR_PREDICTION"

TARGET_TO_RISK_COL = {
    "daily_mortality": "mortality_risk_0_100",
    "daily_hospitalizations": "hospitalization_risk_0_100",
}


def _risk_level(score) -> str:
    if pd.isna(score):
        return "unknown"
    for upper, label in RISK_LEVEL_BANDS:
        if score < upper:
            return label
    return "severe"


def load_models(models_dir: str = "models", model_version: str = MODEL_VERSION) -> dict:
    models = {}
    for target in TARGET_TO_RISK_COL:
        path = f"{models_dir}/{target}_{model_version}.joblib"
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No saved model at {path}. Run `python3 -m src.health.train_models` first — "
                f"predict.py does not train models itself."
            )
        models[target] = joblib.load(path)
    return models


def load_calibration(models_dir: str = "models", model_version: str = MODEL_VERSION) -> dict:
    """Load the per-target risk-score saturation points that
    train_models.py computed from the training set and persisted.
    predict.py must never recompute these from an inference batch —
    see the module docstring."""
    path = f"{models_dir}/{model_version}_metadata.json"
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No training metadata at {path}. Run `python3 -m src.health.train_models` "
            f"first — predict.py loads calibration, it never recomputes it."
        )
    with open(path) as f:
        metadata = json.load(f)
    calibration = metadata.get("calibration")
    if not calibration:
        raise ValueError(
            f"{path} has no 'calibration' section. Retrain with the current "
            f"train_models.py to regenerate it."
        )
    return calibration


def _count_to_risk_0_100(rate: np.ndarray, saturation: float) -> np.ndarray:
    return 100.0 * (1.0 - np.exp(-rate / saturation))


def _top_drivers(model, feature_row: np.ndarray, feature_names: list[str], k: int = 3) -> str:
    contributions = model.coef_ * feature_row
    order = np.argsort(-np.abs(contributions))[:k]
    return ",".join(feature_names[i] for i in order)


def predict_health_risk(stage1_path: str, vulnerability_path: str,
                         models_dir: str = "models") -> pd.DataFrame:
    models = load_models(models_dir)
    calibration = load_calibration(models_dir)

    features = build_features(stage1_path, vulnerability_path)
    daily = aggregate_to_daily(features)

    daily = daily.sort_values(["ward_id", "timestamp_utc"]).copy()
    daily["forecast_day"] = daily.groupby("ward_id").cumcount() + 1
    daily = daily[daily["forecast_day"] <= 5]
    daily["quality_flag"] = daily["quality_flag"].astype(str) + "|" + FORECAST_APPROX_FLAG

    # HealthRiskRecord contract field. Always null today: Task 1 has no
    # real forecast-issue timestamp yet, and forecast_day above is a
    # cumcount() over historical rows, not a genuine forecast horizon.
    # Kept in the schema now so Task 5/6 don't need a breaking change
    # once Task 1 supplies real forecast issuance.
    daily["forecast_issued_at_utc"] = pd.NaT

    has_vuln = daily["vulnerability_0_100"].notna()
    X_all = daily[FEATURE_COLUMNS].fillna(0).values  # only fed to the model for rows we null out below anyway

    for target, model in models.items():
        risk_col = TARGET_TO_RISK_COL[target]
        saturation = calibration[target]
        pred_rate = np.clip(model.predict(X_all), 0, None)
        risk = _count_to_risk_0_100(pred_rate, saturation)
        daily[risk_col] = np.where(has_vuln, risk, np.nan)

        driver_col = f"{target}_drivers"
        daily[driver_col] = [
            _top_drivers(model, row, FEATURE_COLUMNS) if has else None
            for row, has in zip(X_all, has_vuln)
        ]

    daily["mortality_risk_level"] = daily["mortality_risk_0_100"].apply(_risk_level)
    daily["hospitalization_risk_level"] = daily["hospitalization_risk_0_100"].apply(_risk_level)

    daily["quality_flag"] = np.where(~has_vuln, daily["quality_flag"] + "|" + NO_PREDICTION_FLAG, daily["quality_flag"])

    daily["is_synthetic"] = True
    daily["source_type"] = "synthetic_demo"
    daily["model_version"] = MODEL_VERSION

    out_cols = [
        "ward_id", "timestamp_utc", "forecast_day", "forecast_issued_at_utc",
        "thermal_stress_mean", "vulnerability_0_100",
        "mortality_risk_0_100", "hospitalization_risk_0_100",
        "mortality_risk_level", "hospitalization_risk_level",
        "daily_mortality_drivers", "daily_hospitalizations_drivers",
        "is_synthetic", "source_type", "model_version", "quality_flag",
    ]
    result = daily[out_cols].rename(columns={
        "timestamp_utc": "valid_time_utc",
        "daily_mortality_drivers": "mortality_drivers",
        "daily_hospitalizations_drivers": "hospitalization_drivers",
    })
    return result


if __name__ == "__main__":
    records = predict_health_risk(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    pd.set_option("display.width", 200)
    print(records.to_string(index=False))
    records.to_csv("sample/stage2_health_risk_output.csv", index=False)
    print(f"\nWrote {len(records)} HealthRiskRecord rows")
