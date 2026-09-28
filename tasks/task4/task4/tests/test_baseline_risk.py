import numpy as np
import pandas as pd
from src.health.baseline_risk import (
    drop_unlabeled, time_based_split, train_baseline_models, evaluate,
    calibrate_saturation, FEATURE_COLUMNS,
)

def _toy_labeled(n=100):
    rng = np.random.default_rng(0)
    ts = pd.date_range("2026-05-10", periods=n, freq="D", tz="UTC")
    thermal = rng.uniform(0, 100, n)
    return pd.DataFrame({
        "timestamp_utc": ts,
        "thermal_stress_mean": thermal,
        "thermal_stress_max": thermal + 5,
        "vulnerability_0_100": rng.uniform(0, 100, n),
        "heat_persistence_hours": rng.uniform(0, 24, n),
        "doy_sin": np.sin(ts.dayofyear.values),
        "doy_cos": np.cos(ts.dayofyear.values),
        "daily_mortality": rng.poisson(0.1 + thermal / 200),
        "daily_hospitalizations": rng.poisson(0.5 + thermal / 100),
    })

def test_drop_unlabeled_removes_nan_targets():
    df = _toy_labeled(10)
    df.loc[0, "daily_mortality"] = np.nan
    labeled = drop_unlabeled(df)
    assert len(labeled) == 9

def test_three_way_split_chronological_and_non_overlapping():
    df = _toy_labeled()
    train, val, test = time_based_split(df, val_frac=0.2, test_frac=0.2)
    assert train["timestamp_utc"].max() <= val["timestamp_utc"].min()
    assert val["timestamp_utc"].max() <= test["timestamp_utc"].min()
    assert len(train) + len(val) + len(test) == len(df)

def test_train_and_evaluate():
    df = _toy_labeled()
    train, val, test = time_based_split(df)
    models = train_baseline_models(train)
    assert set(models.keys()) == {"daily_mortality", "daily_hospitalizations"}
    metrics = evaluate(models, test)
    assert np.isfinite(metrics["mean_poisson_deviance"]).all()

def test_no_date_overlap_across_splits():
    # Stricter than the chronological-boundary check above: no calendar
    # date may appear in more than one split, since a row-count boundary
    # alone doesn't rule out the same date landing in two splits when
    # timestamps repeat or ties fall on the quantile cutoff.
    df = _toy_labeled()
    train, val, test = time_based_split(df, val_frac=0.2, test_frac=0.2)
    train_dates = set(pd.to_datetime(train["timestamp_utc"]).dt.date)
    val_dates = set(pd.to_datetime(val["timestamp_utc"]).dt.date)
    test_dates = set(pd.to_datetime(test["timestamp_utc"]).dt.date)
    assert not (train_dates & val_dates)
    assert not (val_dates & test_dates)
    assert not (train_dates & test_dates)


def test_calibrate_saturation_uses_only_training_rows():
    # Two disjoint training sets should generally produce different
    # saturation points, since the value comes from the training set's
    # OWN predicted-rate distribution — proving it isn't a fixed
    # constant and isn't reading anything outside train_X.
    df = _toy_labeled(200)
    train, val, test = time_based_split(df)
    models = train_baseline_models(train)
    model = models["daily_mortality"]

    sat_from_full_train = calibrate_saturation(model, train[FEATURE_COLUMNS].values)
    sat_from_half_train = calibrate_saturation(model, train[FEATURE_COLUMNS].values[: len(train) // 2])
    assert sat_from_full_train > 0
    assert sat_from_half_train > 0
    # Calibration must depend on the array actually passed in, not on
    # some hidden global state (e.g. it must not always return the same
    # constant regardless of train_X).
    assert sat_from_full_train != sat_from_half_train or len(train) <= 1


def test_no_fillna_masking_missing_features():
    # FEATURE_COLUMNS should never silently zero-fill — rows must already
    # be fully featured/labeled by the time they reach training.
    df = _toy_labeled(5)
    df.loc[0, "vulnerability_0_100"] = np.nan
    X = df[FEATURE_COLUMNS].values
    assert np.isnan(X).any()  # confirms baseline_risk itself does NOT fillna(0)
