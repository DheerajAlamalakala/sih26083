import numpy as np
import pandas as pd
from src.health.generate_synthetic_health import generate_synthetic_health

def _toy_daily(n=50, seed=0, with_missing_vuln=False):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "ward_id": ["W1"] * n,
        "timestamp_utc": pd.date_range("2026-05-10", periods=n, freq="D", tz="UTC"),
        "thermal_stress_mean": rng.uniform(0, 100, n),
        "thermal_stress_max": rng.uniform(0, 100, n),
        "vulnerability_0_100": rng.uniform(0, 100, n),
        "heat_persistence_hours": rng.uniform(0, 24, n),
        "doy_sin": rng.uniform(-1, 1, n),
        "doy_cos": rng.uniform(-1, 1, n),
        "quality_flag": ["OK"] * n,
    })
    if with_missing_vuln:
        df.loc[0, "vulnerability_0_100"] = np.nan
    return df

def test_one_label_per_ward_day_not_per_hour():
    out = generate_synthetic_health(_toy_daily(n=5))
    assert len(out) == 5  # one row in, one label out — no hourly expansion

def test_missing_vulnerability_gives_null_label_not_zero():
    out = generate_synthetic_health(_toy_daily(n=5, with_missing_vuln=True))
    assert pd.isna(out.loc[0, "daily_mortality"])
    assert "INSUFFICIENT_DATA_FOR_LABEL" in out.loc[0, "quality_flag"]

def test_counts_non_negative_where_labeled():
    out = generate_synthetic_health(_toy_daily())
    labeled = out.dropna(subset=["daily_mortality", "daily_hospitalizations"])
    assert (labeled["daily_mortality"] >= 0).all()
    assert (labeled["daily_hospitalizations"] >= 0).all()

def test_provenance_fields_set():
    out = generate_synthetic_health(_toy_daily())
    assert (out["is_synthetic"] == True).all()
    assert (out["source_type"] == "synthetic_demo").all()

def test_higher_thermal_and_vuln_raises_rate():
    low = _toy_daily(n=1000, seed=1)
    low["thermal_stress_mean"] = 5.0; low["vulnerability_0_100"] = 5.0; low["heat_persistence_hours"] = 0.0
    high = _toy_daily(n=1000, seed=1)
    high["thermal_stress_mean"] = 95.0; high["vulnerability_0_100"] = 95.0; high["heat_persistence_hours"] = 20.0
    low_out = generate_synthetic_health(low, seed=1)
    high_out = generate_synthetic_health(high, seed=1)
    assert high_out["daily_mortality"].mean() > low_out["daily_mortality"].mean()

def test_deterministic_given_seed():
    feats = _toy_daily()
    a = generate_synthetic_health(feats, seed=7)
    b = generate_synthetic_health(feats, seed=7)
    assert (a["daily_mortality"] == b["daily_mortality"]).all()
