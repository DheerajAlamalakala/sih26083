"""
Task 4 — synthetic health-outcome generator.

FIXED: now operates on DAILY-aggregated features (one row per
ward-day), not hourly rows. Previously this ran on hourly Stage-1
rows and stamped each hour with its own "daily_mortality" value,
which produced ~24 conflicting "daily" labels per ward-day — a
genuine target-definition bug, not a design choice.

Generates daily_mortality and daily_hospitalizations counts as a
function of Stage 1 thermal stress + Task 3 vulnerability + heat
persistence + seasonality, because no suitable public ward-level
health dataset is available for this PS (per playbook Task 4).

Rows with missing vulnerability (NaN, not zero-filled) are excluded
from rate calculation and get null counts + a quality flag, rather
than silently treated as "zero vulnerability".

Every row tagged is_synthetic=True, source_type='synthetic_demo',
synthetic_generation_version='v1_0'. Deterministic given a seed.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from src.health.feature_builder import build_features
from src.health.daily_aggregation import aggregate_to_daily, NO_VULN_FLAG

SYNTHETIC_GENERATION_VERSION = "v1_1"  # bumped: fixes daily-granularity bug from v1_0

BASE_MORTALITY_RATE = 0.05
BASE_HOSPITALIZATION_RATE = 0.4

MORTALITY_COEFS = dict(thermal=0.035, vuln=0.02, persistence=0.05, season=0.3)
HOSPITALIZATION_COEFS = dict(thermal=0.03, vuln=0.018, persistence=0.04, season=0.25)

INSUFFICIENT_DATA_FLAG = "INSUFFICIENT_DATA_FOR_LABEL"


def _seasonal_amplifier(doy_sin: pd.Series) -> pd.Series:
    return doy_sin


def _poisson_rate(df: pd.DataFrame, coefs: dict, base_rate: float) -> np.ndarray:
    thermal = df["thermal_stress_mean"].fillna(0) / 100.0
    vuln = df["vulnerability_0_100"].fillna(0) / 100.0  # only used where vuln is NOT NaN; see mask below
    persistence = df["heat_persistence_hours"].fillna(0) / 24.0
    season = _seasonal_amplifier(df["doy_sin"])

    log_rate = (
        np.log(base_rate)
        + coefs["thermal"] * thermal * 10
        + coefs["vuln"] * vuln * 10
        + coefs["persistence"] * persistence * 10
        + coefs["season"] * season
    )
    return np.exp(log_rate)


def generate_synthetic_health(daily_features: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """daily_features must already be one row per (ward_id, date) —
    see daily_aggregation.aggregate_to_daily(). Passing hourly rows
    here silently reproduces the original bug, so this is the only
    supported input shape."""
    rng = np.random.default_rng(seed)
    out = daily_features.copy()

    has_vuln = out["vulnerability_0_100"].notna()

    mortality_rate = _poisson_rate(out, MORTALITY_COEFS, BASE_MORTALITY_RATE)
    hosp_rate = _poisson_rate(out, HOSPITALIZATION_COEFS, BASE_HOSPITALIZATION_RATE)

    out["daily_mortality"] = np.where(has_vuln, rng.poisson(mortality_rate), np.nan)
    out["daily_hospitalizations"] = np.where(has_vuln, rng.poisson(hosp_rate), np.nan)

    out["quality_flag"] = np.where(
        ~has_vuln,
        out["quality_flag"].astype(str) + "|" + INSUFFICIENT_DATA_FLAG,
        out["quality_flag"],
    )

    out["is_synthetic"] = True
    out["source_type"] = "synthetic_demo"
    out["synthetic_generation_version"] = SYNTHETIC_GENERATION_VERSION

    return out


if __name__ == "__main__":
    features = build_features(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    daily = aggregate_to_daily(features)
    synthetic = generate_synthetic_health(daily)
    cols = ["ward_id", "date", "thermal_stress_mean", "vulnerability_0_100",
            "heat_persistence_hours", "daily_mortality", "daily_hospitalizations",
            "is_synthetic", "quality_flag"]
    print(synthetic[cols].to_string(index=False))
    print(f"\nTotal ward-days: {len(synthetic)}")
    valid = synthetic["daily_mortality"].notna()
    print(f"Ward-days with a valid label: {valid.sum()} / {len(synthetic)}")

    out_path = "data/synthetic/health_outcomes_demo.csv"
    synthetic.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")
