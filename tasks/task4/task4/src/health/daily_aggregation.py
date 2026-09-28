"""
Shared hourly -> daily aggregation.

This is the fix for the target-granularity bug: synthetic health
labels and model training/prediction must all happen at DAILY
granularity, one row per (ward_id, date). Previously
generate_synthetic_health() ran on hourly rows, producing ~24
different "daily_mortality" values per ward-day, which is wrong.

Missing vulnerability is preserved as NaN here (never zero-filled).
Downstream code must decide explicitly what to do with NaN rather
than silently treating "unknown" as "zero risk".
"""
from __future__ import annotations
import numpy as np
import pandas as pd

NO_VULN_FLAG = "NO_VULNERABILITY_MATCH"


def _dedup_flags(flag_values: pd.Series) -> str:
    """Merge a ward-day's hourly quality_flag values into one string
    with no repeated tokens.

    FIXED: the previous version deduplicated whole per-row strings
    ("A|B" vs "A|C" are different strings even though both contain
    "A"), so aggregating 24 hourly rows could produce a "daily"
    quality_flag with the same token repeated many times over. This
    splits every row's flags on "|" first, then dedupes at the token
    level.
    """
    tokens: set[str] = set()
    for value in flag_values.dropna().astype(str):
        for token in value.split("|"):
            token = token.strip()
            if token:
                tokens.add(token)
    return "|".join(sorted(tokens))


def aggregate_to_daily(features: pd.DataFrame) -> pd.DataFrame:
    """features: output of feature_builder.build_features() (hourly rows,
    ward_id-bridged, with heat_persistence_hours/doy_sin/doy_cos already
    computed). Returns one row per (ward_id, date)."""
    df = features.copy()
    df["date"] = df["timestamp_utc"].dt.date

    agg = df.groupby(["ward_id", "date"]).agg(
        timestamp_utc=("timestamp_utc", "max"),
        temperature_c=("temperature_c", "mean") if "temperature_c" in df else ("thermal_stress_0_100", "mean"),
        thermal_stress_mean=("thermal_stress_0_100", "mean"),
        thermal_stress_max=("thermal_stress_0_100", "max"),
        heat_persistence_hours=("heat_persistence_hours", "max"),
        doy_sin=("doy_sin", "first"),
        doy_cos=("doy_cos", "first"),
        vulnerability_0_100=("vulnerability_0_100", "first"),  # NaN stays NaN — no fillna here
        quality_flag=("quality_flag", _dedup_flags),
    ).reset_index()

    if "temperature_c" not in df.columns:
        agg = agg.drop(columns=["temperature_c"])

    missing_vuln = agg["vulnerability_0_100"].isna()
    already_flagged = agg["quality_flag"].astype(str).str.split("|").apply(lambda toks: NO_VULN_FLAG in toks)
    needs_flag = missing_vuln & ~already_flagged
    agg["quality_flag"] = np.where(
        needs_flag,
        agg["quality_flag"].astype(str) + "|" + NO_VULN_FLAG,
        agg["quality_flag"],
    )
    return agg
