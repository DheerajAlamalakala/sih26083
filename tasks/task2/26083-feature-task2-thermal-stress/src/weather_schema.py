"""
Canonical weather record schema for SIH26083 Task 1.
This is the integration contract with Task 2 (Stage 1 - Thermal Stress).
Task 2 must be able to consume this schema without knowing any
API-specific field names.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    """Where a given record's values actually came from."""
    OPEN_METEO_FORECAST = "open_meteo_forecast"
    OPEN_METEO_HISTORICAL = "open_meteo_historical"
    OPEN_METEO_SINGLE_RUN = "open_meteo_single_run"
    NASA_POWER_HOURLY = "nasa_power_hourly"
    CACHE = "cache"
    DEMO_FIXTURE = "demo_fixture"


class QualityFlag(str, Enum):
    """
    Transparent data-quality state. Per playbook rules: never silently
    substitute a generic 24-hour average for missing extreme-weather data.
    Any deviation from a clean primary-source fetch must be flagged here.
    """
    OK = "ok"                                # primary source, complete
    FALLBACK_SOURCE = "fallback_source"       # NASA POWER used instead of Open-Meteo
    CACHE_STALE = "cache_stale"               # served from cache, past freshness window
    DEMO_FIXTURE = "demo_fixture"             # all live sources failed
    PARTIAL_MISSING_FIELD = "partial_missing_field"  # one or more fields is null
    UNIT_NORMALIZED = "unit_normalized"       # value was converted from a non-native unit


class WeatherRecord(BaseModel):
    """
    Canonical normalized weather record. One instance per ward per hour.
    Mirrors the schema defined in the SIH26083 playbook (Task 1 -> Task 2 contract).
    """
    ward_id: str = Field(..., min_length=1)
    timestamp_utc: datetime
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = Field(None, ge=0, le=100)
    wind_speed_ms: Optional[float] = Field(None, ge=0)
    solar_radiation_wm2: Optional[float] = Field(None, ge=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    source_type: SourceType
    quality_flag: QualityFlag

    @field_validator("timestamp_utc")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}
