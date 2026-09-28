"""
Task 4 — training pipeline (separate from inference).

FIXED vs v1_0: predict.py used to retrain on every call, on the same
data it then predicted on. That's a training-set inference loop, not
deployment. This script is the only place models get fit; predict.py
only loads what this script saves.

Run this whenever new labeled data is available. Bump MODEL_VERSION
in baseline_risk.py when you do, so old predictions stay traceable
to the model that made them.
"""
from __future__ import annotations
import json
import joblib
from datetime import datetime, timezone

from src.health.feature_builder import build_features
from src.health.daily_aggregation import aggregate_to_daily
from src.health.generate_synthetic_health import generate_synthetic_health, SYNTHETIC_GENERATION_VERSION
from src.health.baseline_risk import (
    drop_unlabeled, time_based_split, train_baseline_models, evaluate,
    calibrate_saturation, FEATURE_COLUMNS, MODEL_VERSION,
)


def run_training(stage1_path: str, vulnerability_path: str, models_dir: str = "models") -> dict:
    features = build_features(stage1_path, vulnerability_path)
    daily = aggregate_to_daily(features)
    synthetic = generate_synthetic_health(daily)
    labeled = drop_unlabeled(synthetic)

    train, val, test = time_based_split(labeled)
    models = train_baseline_models(train)

    val_metrics = evaluate(models, val)
    test_metrics = evaluate(models, test)

    # Calibration is computed ONCE here, from the training set only, and
    # persisted. predict.py loads this value rather than recomputing it
    # from whatever batch it happens to be scoring at inference time.
    calibration = {
        target: calibrate_saturation(model, train[FEATURE_COLUMNS].values)
        for target, model in models.items()
    }

    for target, model in models.items():
        joblib.dump(model, f"{models_dir}/{target}_{MODEL_VERSION}.joblib")

    metadata = {
        "model_version": MODEL_VERSION,
        "synthetic_generation_version": SYNTHETIC_GENERATION_VERSION,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_train": len(train),
        "n_val": len(val),
        "n_test": len(test),
        "n_labeled_total": len(labeled),
        "warning": "Sample size is far too small for a real skill estimate — pipeline sanity check only.",
        "calibration": calibration,
        "val_metrics": val_metrics.to_dict(orient="records"),
        "test_metrics": test_metrics.to_dict(orient="records"),
    }
    with open(f"{models_dir}/{MODEL_VERSION}_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


if __name__ == "__main__":
    meta = run_training(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    print(json.dumps(meta, indent=2))
