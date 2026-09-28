import pandas as pd
from src.health.feature_builder import (
    apply_ward_bridge, add_heat_persistence, add_seasonality, build_features
)

def _toy_stage1():
    return pd.DataFrame({
        "ward_id": ["HYD_W001", "HYD_W001", "HYD_PAIR_DRY"],
        "timestamp_utc": pd.to_datetime(
            ["2026-05-10T00:00:00Z", "2026-05-10T01:00:00Z", "2026-05-10T00:00:00Z"], utc=True
        ),
        "thermal_stress_0_100": [70.0, 65.0, 50.0],
        "quality_flag": ["OK", "OK", "OK"],
    })

def test_apply_ward_bridge_flags_unmatched():
    df = apply_ward_bridge(_toy_stage1())
    assert df.loc[df["ward_id_raw"] == "HYD_W001", "ward_id"].iloc[0] == "GHMC_W001"
    unmatched_row = df[df["ward_id_raw"] == "HYD_PAIR_DRY"].iloc[0]
    assert "WARD_ID_UNMATCHED" in unmatched_row["quality_flag"]

def test_heat_persistence_counts_high_hours():
    df = apply_ward_bridge(_toy_stage1())
    df = add_heat_persistence(df)
    ghmc_rows = df[df["ward_id"] == "GHMC_W001"].sort_values("timestamp_utc")
    # both hours are >= 60 threshold -> cumulative count should reach 2 by 2nd hour
    assert ghmc_rows["heat_persistence_hours"].iloc[-1] == 2

def test_seasonality_columns_present_and_bounded():
    df = add_seasonality(_toy_stage1())
    assert df["doy_sin"].between(-1, 1).all()
    assert df["doy_cos"].between(-1, 1).all()

def test_build_features_end_to_end(tmp_path):
    stage1_path = tmp_path / "stage1.csv"
    vuln_path = tmp_path / "vuln.csv"
    _toy_stage1().assign(
        temperature_c=30, relative_humidity_pct=60, wind_speed_ms=1,
        solar_radiation_wm2=0, wbgt_c=26, utci_c=30, heat_index_c=33,
        thermal_risk_level="high", method_version="v1",
    ).to_csv(stage1_path, index=False)
    pd.DataFrame({
        "ward_id": ["GHMC_W001"],
        "elderly_exposure_0_100": [50.0],
        "outdoor_worker_exposure_0_100": [60.0],
        "vulnerability_0_100": [55.0],
        "quality_flag": ["VERIFIED_OFFICIAL_TGRAC_LAYER"],
    }).to_csv(vuln_path, index=False)

    merged = build_features(str(stage1_path), str(vuln_path))
    assert "vulnerability_0_100" in merged.columns
    matched = merged[merged["ward_id"] == "GHMC_W001"]
    assert (matched["vulnerability_0_100"] == 55.0).all()
