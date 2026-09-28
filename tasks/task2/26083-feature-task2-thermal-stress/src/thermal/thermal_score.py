"""
Stage-1 canonical output: ThermalStressRecord.

Consumes Task 1 WeatherRecord objects and produces exactly one
ThermalStressRecord per input record, per the Playbook Task-1 -> Task-2
contract. Deterministic only — no ML anywhere in this module.
Task 4 must consume this record directly and must never recompute
WBGT/UTCI/Heat Index itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.thermal.constants import METHOD_VERSION, THERMAL_MAX_WBGT_C, THERMAL_MIN_WBGT_C, THERMAL_RISK_BANDS
from src.thermal.heat_index import compute_heat_index_c, compute_utci_proxy_c
from src.thermal.wbgt import compute_wbgt_c
from src.weather_schema import QualityFlag, WeatherRecord


class ThermalRiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class ThermalQualityFlag(str, Enum):
    OK = "ok"
    INPUT_INCOMPLETE = "input_incomplete"  # one or more required weather inputs missing
    UPSTREAM_FALLBACK = "upstream_fallback"  # upstream WeatherRecord itself was a fallback/demo source


class ThermalStressRecord(BaseModel):
    """Canonical Stage-1 output. Integration contract with Task 4."""

    ward_id: str = Field(..., min_length=1)
    timestamp_utc: datetime
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    wbgt_c: Optional[float] = None
    utci_c: Optional[float] = None
    heat_index_c: Optional[float] = None
    thermal_stress_0_100: Optional[float] = None
    thermal_risk_level: Optional[ThermalRiskLevel] = None
    quality_flag: ThermalQualityFlag
    method_version: str = METHOD_VERSION

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


def _normalize_0_100(wbgt_c: float) -> float:
    span = THERMAL_MAX_WBGT_C - THERMAL_MIN_WBGT_C
    score = (wbgt_c - THERMAL_MIN_WBGT_C) / span * 100.0
    return round(max(0.0, min(100.0, score)), 2)


def _risk_level(score: float) -> ThermalRiskLevel:
    for name, lo, hi in THERMAL_RISK_BANDS:
        if lo <= score < hi:
            return ThermalRiskLevel(name)
    return ThermalRiskLevel.EXTREME


def compute_thermal_stress_record(weather: WeatherRecord) -> ThermalStressRecord:
    """
    Deterministically derive one ThermalStressRecord from one WeatherRecord.
    Never raises on missing fields; missing inputs simply yield None outputs
    with quality_flag=input_incomplete.
    """
    wbgt = compute_wbgt_c(weather.temperature_c, weather.relative_humidity_pct, weather.solar_radiation_wm2)
    heat_index = compute_heat_index_c(weather.temperature_c, weather.relative_humidity_pct)
    utci = compute_utci_proxy_c(weather.temperature_c, weather.relative_humidity_pct, weather.wind_speed_ms)

    if wbgt is not None:
        score = _normalize_0_100(wbgt)
        level = _risk_level(score)
    else:
        score = None
        level = None

    upstream_quality = weather.quality_flag
    upstream_is_fallback = upstream_quality in (
        QualityFlag.FALLBACK_SOURCE,
        QualityFlag.CACHE_STALE,
        QualityFlag.DEMO_FIXTURE,
        QualityFlag.PARTIAL_MISSING_FIELD,
    )

    if wbgt is None:
        quality = ThermalQualityFlag.INPUT_INCOMPLETE
    elif upstream_is_fallback:
        quality = ThermalQualityFlag.UPSTREAM_FALLBACK
    else:
        quality = ThermalQualityFlag.OK

    return ThermalStressRecord(
        ward_id=weather.ward_id,
        timestamp_utc=weather.timestamp_utc,
        temperature_c=weather.temperature_c,
        relative_humidity_pct=weather.relative_humidity_pct,
        wind_speed_ms=weather.wind_speed_ms,
        solar_radiation_wm2=weather.solar_radiation_wm2,
        wbgt_c=wbgt,
        utci_c=utci,
        heat_index_c=heat_index,
        thermal_stress_0_100=score,
        thermal_risk_level=level,
        quality_flag=quality,
        method_version=METHOD_VERSION,
    )


def compute_thermal_stress_records(weather_records: list[WeatherRecord]) -> list[ThermalStressRecord]:
    """Batch entry point: one output row per input row, order preserved."""
    return [compute_thermal_stress_record(w) for w in weather_records]
