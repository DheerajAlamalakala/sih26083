import pandas as pd
import pytest
from src.health.data_quality import (
    validate_vulnerability_uniqueness, check_stage1_hourly_coverage, DataQualityError,
)


def test_vulnerability_uniqueness_passes_for_unique_wards():
    vuln = pd.DataFrame({"ward_id": ["GHMC_W001", "GHMC_W002"], "vulnerability_0_100": [50.0, 60.0]})
    validate_vulnerability_uniqueness(vuln)  # should not raise


def test_vulnerability_uniqueness_raises_on_duplicate_ward():
    vuln = pd.DataFrame({
        "ward_id": ["GHMC_W001", "GHMC_W001", "GHMC_W002"],
        "vulnerability_0_100": [50.0, 55.0, 60.0],
    })
    with pytest.raises(DataQualityError):
        validate_vulnerability_uniqueness(vuln)


def _hourly(ward_timestamps: dict) -> pd.DataFrame:
    rows = []
    for ward_id, timestamps in ward_timestamps.items():
        for ts in timestamps:
            rows.append({"ward_id": ward_id, "timestamp_utc": ts, "thermal_stress_0_100": 50.0})
    return pd.DataFrame(rows)


def test_coverage_reports_no_issues_for_clean_hourly_data():
    ts = pd.date_range("2026-05-10", periods=5, freq="h", tz="UTC").astype(str).tolist()
    report = check_stage1_hourly_coverage(_hourly({"W1": ts}))
    assert report["malformed_timestamp_count"] == 0
    assert report["duplicate_timestamp_row_count"] == 0
    assert report["missing_hours_by_ward"] == {}


def test_coverage_detects_duplicate_timestamp_rows():
    ts = pd.date_range("2026-05-10", periods=3, freq="h", tz="UTC").astype(str).tolist()
    df = _hourly({"W1": ts + [ts[0]]})  # first hour duplicated
    report = check_stage1_hourly_coverage(df)
    assert report["duplicate_timestamp_row_count"] == 2  # both copies of the duplicated row


def test_coverage_detects_missing_hours():
    ts = ["2026-05-10T00:00:00Z", "2026-05-10T01:00:00Z", "2026-05-10T05:00:00Z"]  # 3-hour gap
    report = check_stage1_hourly_coverage(_hourly({"W1": ts}))
    assert report["missing_hours_by_ward"].get("W1", 0) == pytest.approx(3.0)


def test_coverage_detects_malformed_timestamps():
    df = _hourly({"W1": ["2026-05-10T00:00:00Z", "not-a-timestamp"]})
    report = check_stage1_hourly_coverage(df)
    assert report["malformed_timestamp_count"] == 1
