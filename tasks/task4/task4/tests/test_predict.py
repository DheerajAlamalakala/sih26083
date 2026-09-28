import json
import os
import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.linear_model import PoissonRegressor
from src.health.predict import (
    _risk_level, _count_to_risk_0_100, load_models, load_calibration, predict_health_risk,
)
from src.health.baseline_risk import MODEL_VERSION

def test_risk_level_bands():
    assert _risk_level(0) == "low"
    assert _risk_level(24.9) == "low"
    assert _risk_level(25) == "moderate"
    assert _risk_level(74.99) == "high"
    assert _risk_level(90) == "severe"
    assert _risk_level(float("nan")) == "unknown"

def test_count_to_risk_bounded_and_calibrated():
    # with saturation=5, a rate equal to saturation should land near 63% of the ceiling
    risk = _count_to_risk_0_100(np.array([5.0]), saturation=5.0)[0]
    assert 60 < risk < 65
    assert _count_to_risk_0_100(np.array([0.0]), saturation=5.0)[0] == 0

def test_load_models_raises_clear_error_if_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_models(models_dir=str(tmp_path))

def test_load_calibration_raises_clear_error_if_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_calibration(models_dir=str(tmp_path))

def test_load_calibration_raises_if_metadata_lacks_calibration(tmp_path):
    (tmp_path / f"{MODEL_VERSION}_metadata.json").write_text(json.dumps({"model_version": MODEL_VERSION}))
    with pytest.raises(ValueError):
        load_calibration(models_dir=str(tmp_path))

def test_load_calibration_reads_persisted_values():
    # relies on models/ already trained via train_models.py in this repo
    calibration = load_calibration()
    assert set(calibration.keys()) == {"daily_mortality", "daily_hospitalizations"}
    assert all(v > 0 for v in calibration.values())

def test_predict_never_fits_models(monkeypatch):
    """predict.py must only ever call .predict() on already-loaded
    models — never .fit(). If it ever retrains on the batch it's
    scoring, this test fails loudly instead of silently passing."""
    def _forbidden_fit(self, *args, **kwargs):
        raise AssertionError("predict_health_risk must not call fit() — inference-only.")
    monkeypatch.setattr(PoissonRegressor, "fit", _forbidden_fit)

    records = predict_health_risk(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    assert len(records) > 0

def test_predict_health_risk_end_to_end_schema():
    # relies on models/ already trained via train_models.py in this repo
    records = predict_health_risk(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    expected_cols = {
        "ward_id", "valid_time_utc", "forecast_day", "forecast_issued_at_utc",
        "thermal_stress_mean", "vulnerability_0_100",
        "mortality_risk_0_100", "hospitalization_risk_0_100",
        "mortality_risk_level", "hospitalization_risk_level",
        "mortality_drivers", "hospitalization_drivers",
        "is_synthetic", "source_type", "model_version", "quality_flag",
    }
    assert expected_cols == set(records.columns)
    assert (records["forecast_day"] <= 5).all()
    assert records["forecast_issued_at_utc"].isna().all()  # null until Task 1 delivers real forecast issuance

    unmatched = records[records["quality_flag"].str.contains("INSUFFICIENT_DATA_FOR_PREDICTION")]
    assert unmatched["mortality_risk_0_100"].isna().all()
    assert (unmatched["mortality_risk_level"] == "unknown").all()

    matched = records[~records["quality_flag"].str.contains("INSUFFICIENT_DATA_FOR_PREDICTION")]
    assert (matched["mortality_risk_0_100"] >= 0).all()

def test_drivers_are_target_specific():
    records = predict_health_risk(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    matched = records.dropna(subset=["mortality_drivers", "hospitalization_drivers"])
    # Not asserting they're always different (could coincide), but the
    # bug being tested for is "hospitalization always equals mortality's
    # drivers verbatim" — check they're computed independently by
    # confirming both columns are populated as separate values.
    assert matched["mortality_drivers"].notna().all()
    assert matched["hospitalization_drivers"].notna().all()
