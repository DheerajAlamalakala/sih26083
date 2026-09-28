"""
Task 4 — feature builder.

Joins Task 2's Stage-1 ThermalStressRecord output with Task 3's ward
vulnerability data, applies the ward_id bridge for demo-scale
mismatches, and derives the extra features the health models need
(heat persistence, seasonality). Never recomputes WBGT/UTCI/HI —
those come through untouched from Stage 1.

Output: one row per (ward_id, timestamp_utc) with everything the
synthetic generator and models need. Rows whose ward_id can't be
bridged to a real ward get quality_flag='WARD_ID_UNMATCHED' and are
kept (not silently dropped) so team members can see join coverage.
"""
from __future__ import annotations
import pandas as pd
import numpy as np

from src.health.ward_id_bridge import bridge_ward_id, UNMATCHED_FLAG
from src.health.data_quality import validate_vulnerability_uniqueness, check_stage1_hourly_coverage

PERSISTENCE_WINDOW_HOURS = 24
HIGH_STRESS_THRESHOLD = 60.0  # thermal_stress_0_100 considered "high" for persistence counting

DUPLICATE_TIMESTAMP_DROPPED_FLAG = "DUPLICATE_STAGE1_TIMESTAMP_DROPPED"


def load_stage1(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    coverage = check_stage1_hourly_coverage(df)
    if coverage["duplicate_timestamp_row_count"] > 0:
        # Duplicate (ward_id, timestamp) rows would silently corrupt the
        # hourly rolling-persistence window and the daily aggregation
        # (each duplicated hour counted twice). Drop rather than fail —
        # this is recoverable — but never silently: log it and flag it.
        print(
            f"WARNING: Stage 1 input has {coverage['duplicate_timestamp_row_count']} "
            f"duplicate (ward_id, timestamp_utc) rows. Dropping duplicates, keeping "
            f"the first occurrence of each."
        )
    if coverage["missing_hours_by_ward"]:
        print(f"NOTE: Stage 1 hourly gaps by ward (hours missing): {coverage['missing_hours_by_ward']}")

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    had_dupes = coverage["duplicate_timestamp_row_count"] > 0
    df = df.drop_duplicates(subset=["ward_id", "timestamp_utc"], keep="first").copy()
    if had_dupes:
        df["quality_flag"] = (
            df["quality_flag"].fillna("").astype(str) + "|" + DUPLICATE_TIMESTAMP_DROPPED_FLAG
        )
    return df


def load_vulnerability(path: str) -> pd.DataFrame:
    vuln = pd.read_csv(path)
    validate_vulnerability_uniqueness(vuln)
    return vuln


def apply_ward_bridge(stage1: pd.DataFrame) -> pd.DataFrame:
    stage1 = stage1.copy()
    bridged = stage1["ward_id"].map(bridge_ward_id)
    unmatched = bridged.isna()

    stage1["ward_id_raw"] = stage1["ward_id"]
    stage1["ward_id"] = bridged.where(~unmatched, stage1["ward_id_raw"])

    # Preserve any existing quality_flag; only overwrite when the
    # join itself is the problem, and never lose the original flag info.
    stage1["quality_flag"] = np.where(
        unmatched,
        stage1["quality_flag"].fillna("").astype(str) + ("|" if stage1["quality_flag"].notna().any() else "") + UNMATCHED_FLAG,
        stage1["quality_flag"],
    )
    return stage1


def add_heat_persistence(stage1: pd.DataFrame) -> pd.DataFrame:
    """Rolling count of hours in the trailing window where
    thermal_stress_0_100 >= HIGH_STRESS_THRESHOLD, per ward.
    Requires hourly, time-sorted data per ward (Task 1/2's contract).
    """
    stage1 = stage1.sort_values(["ward_id", "timestamp_utc"]).copy()
    is_high = (stage1["thermal_stress_0_100"] >= HIGH_STRESS_THRESHOLD).astype(int)
    stage1["_is_high_stress"] = is_high

    stage1["heat_persistence_hours"] = (
        stage1.groupby("ward_id")["_is_high_stress"]
        .rolling(window=PERSISTENCE_WINDOW_HOURS, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    stage1 = stage1.drop(columns=["_is_high_stress"])
    return stage1


def add_seasonality(stage1: pd.DataFrame) -> pd.DataFrame:
    stage1 = stage1.copy()
    stage1["day_of_year"] = stage1["timestamp_utc"].dt.dayofyear
    stage1["month"] = stage1["timestamp_utc"].dt.month
    # Simple cyclical encoding so "day 365" and "day 1" are close for the model
    stage1["doy_sin"] = np.sin(2 * np.pi * stage1["day_of_year"] / 365.25)
    stage1["doy_cos"] = np.cos(2 * np.pi * stage1["day_of_year"] / 365.25)
    return stage1


def build_features(stage1_path: str, vulnerability_path: str) -> pd.DataFrame:
    stage1 = load_stage1(stage1_path)
    vuln = load_vulnerability(vulnerability_path)

    stage1 = apply_ward_bridge(stage1)
    stage1 = add_heat_persistence(stage1)
    stage1 = add_seasonality(stage1)

    merged = stage1.merge(
        vuln[["ward_id", "elderly_exposure_0_100", "outdoor_worker_exposure_0_100",
              "vulnerability_0_100", "quality_flag"]],
        on="ward_id",
        how="left",
        suffixes=("", "_vuln"),
    )

    # Rows with no vulnerability match at all (join miss on the vuln side)
    no_vuln = merged["vulnerability_0_100"].isna()
    merged["quality_flag"] = np.where(
        no_vuln,
        merged["quality_flag"].fillna("").astype(str) + "|NO_VULNERABILITY_MATCH",
        merged["quality_flag"],
    )

    return merged


if __name__ == "__main__":
    features = build_features(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
    )
    print(features[["ward_id", "timestamp_utc", "thermal_stress_0_100",
                     "heat_persistence_hours", "vulnerability_0_100", "quality_flag"]].head(10))
    print(f"\nTotal rows: {len(features)}")
    print(f"Unmatched ward_id rows: {features['quality_flag'].str.contains('WARD_ID_UNMATCHED', na=False).sum()}")
    print(f"No vulnerability match: {features['quality_flag'].str.contains('NO_VULNERABILITY_MATCH', na=False).sum()}")
