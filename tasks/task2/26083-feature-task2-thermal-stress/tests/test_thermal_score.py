"""
Unit tests for the Stage-1 deterministic thermal-stress pipeline
(SIH26083 Task 2). Verifies: one ThermalStressRecord per WeatherRecord,
correct handling of missing inputs, WBGT-driven risk banding, and that
the module performs no ML / randomness (pure function determinism).
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.thermal.thermal_score import (
    ThermalQualityFlag,
    ThermalRiskLevel,
    compute_thermal_stress_record,
    compute_thermal_stress_records,
)
from src.thermal.wbgt import compute_wbgt_c
from src.thermal.heat_index import compute_heat_index_c
from src.weather_schema import QualityFlag, SourceType, WeatherRecord

WARD_ID = "TEST_WARD_01"
LAT, LON = 17.385, 78.4867


def _weather(**overrides) -> WeatherRecord:
    base = dict(
        ward_id=WARD_ID,
        timestamp_utc=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
        temperature_c=38.0,
        relative_humidity_pct=45.0,
        wind_speed_ms=2.0,
        solar_radiation_wm2=650.0,
        latitude=LAT,
        longitude=LON,
        source_type=SourceType.OPEN_METEO_FORECAST,
        quality_flag=QualityFlag.OK,
    )
    base.update(overrides)
    return WeatherRecord(**base)


def test_wbgt_is_deterministic_and_reasonable():
    w1 = compute_wbgt_c(38.0, 45.0, 650.0)
    w2 = compute_wbgt_c(38.0, 45.0, 650.0)
    assert w1 == w2
    assert 20.0 < w1 < 45.0


def test_wbgt_none_when_inputs_missing():
    assert compute_wbgt_c(None, 45.0) is None
    assert compute_wbgt_c(38.0, None) is None


def test_heat_index_none_when_inputs_missing():
    assert compute_heat_index_c(None, 50.0) is None


def test_one_record_per_weather_record():
    records = [_weather(), _weather(temperature_c=42.0)]
    out = compute_thermal_stress_records(records)
    assert len(out) == 2
    assert all(r.ward_id == WARD_ID for r in out)


def test_high_heat_produces_high_or_extreme_risk():
    rec = compute_thermal_stress_record(_weather(temperature_c=42.0, relative_humidity_pct=60.0))
    assert rec.thermal_stress_0_100 is not None
    assert rec.thermal_risk_level in (ThermalRiskLevel.HIGH, ThermalRiskLevel.EXTREME)
    assert rec.quality_flag == ThermalQualityFlag.OK


def test_missing_weather_inputs_yield_null_score_not_fabricated_value():
    rec = compute_thermal_stress_record(_weather(temperature_c=None))
    assert rec.wbgt_c is None
    assert rec.thermal_stress_0_100 is None
    assert rec.thermal_risk_level is None
    assert rec.quality_flag == ThermalQualityFlag.INPUT_INCOMPLETE


def test_fallback_upstream_source_propagates_quality_flag():
    rec = compute_thermal_stress_record(
        _weather(quality_flag=QualityFlag.DEMO_FIXTURE, source_type=SourceType.DEMO_FIXTURE)
    )
    assert rec.quality_flag == ThermalQualityFlag.UPSTREAM_FALLBACK


def test_method_version_is_stamped():
    rec = compute_thermal_stress_record(_weather())
    assert rec.method_version.startswith("thermal_stage1_")


def test_output_preserves_ward_id_and_timestamp():
    ts = datetime(2026, 6, 1, 9, tzinfo=timezone.utc)
    rec = compute_thermal_stress_record(_weather(timestamp_utc=ts))
    assert rec.ward_id == WARD_ID
    assert rec.timestamp_utc == ts
