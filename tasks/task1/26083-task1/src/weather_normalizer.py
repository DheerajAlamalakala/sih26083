"""
Normalizes raw Open-Meteo / NASA POWER payloads into canonical WeatherRecord
objects. Also owns the versioned demo-fixture fallback (tier 3).

Design rule from the playbook: never silently impute missing extreme-weather
data with a generic 24-hour average. Missing values stay None and are
reflected in quality_flag, full stop.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.weather_schema import QualityFlag, SourceType, WeatherRecord

logger = logging.getLogger(__name__)

DEMO_FIXTURE_PATH = Path("data/raw/weather/demo_fixture_v1.json")
DEMO_FIXTURE_VERSION = "v1_0"


def normalize_open_meteo_forecast(
    raw: dict, ward_id: str, latitude: float, longitude: float
) -> list[WeatherRecord]:
    """
    Open-Meteo forecast response shape:
    {
      "hourly": {
        "time": [...],
        "temperature_2m": [...],
        "relative_humidity_2m": [...],
        "wind_speed_10m": [...],
        "shortwave_radiation": [...]
      }
    }
    """
    hourly = raw.get("hourly")
    if not hourly or "time" not in hourly:
        raise ValueError("open_meteo_response_missing_hourly_block")

    times = hourly["time"]
    temps = hourly.get("temperature_2m", [None] * len(times))
    humidity = hourly.get("relative_humidity_2m", [None] * len(times))
    wind = hourly.get("wind_speed_10m", [None] * len(times))
    radiation = hourly.get("shortwave_radiation", [None] * len(times))

    records: list[WeatherRecord] = []
    for i, ts in enumerate(times):
        missing_any = any(
            v is None or (i < len(v) and v[i] is None)
            for v in (temps, humidity, wind, radiation)
            if isinstance(v, list)
        )
        quality = QualityFlag.PARTIAL_MISSING_FIELD if missing_any else QualityFlag.OK

        records.append(
            WeatherRecord(
                ward_id=ward_id,
                timestamp_utc=_parse_open_meteo_time(ts),
                temperature_c=_safe_index(temps, i),
                relative_humidity_pct=_safe_index(humidity, i),
                wind_speed_ms=_safe_index(wind, i),
                solar_radiation_wm2=_safe_index(radiation, i),
                latitude=latitude,
                longitude=longitude,
                source_type=SourceType.OPEN_METEO_FORECAST,
                quality_flag=quality,
            )
        )
    return records


def normalize_nasa_power_hourly(
    raw: dict, ward_id: str, latitude: float, longitude: float
) -> list[WeatherRecord]:
    """
    NASA POWER hourly response shape (simplified):
    {
      "properties": {
        "parameter": {
          "T2M": {"2024010100": 27.3, ...},
          "RH2M": {...},
          "WS10M": {...},
          "ALLSKY_SFC_SW_DWN": {...}
        }
      }
    }
    NASA POWER is used only as a fallback (primarily for solar radiation);
    every record produced here is explicitly flagged FALLBACK_SOURCE.
    """
    params = raw.get("properties", {}).get("parameter")
    if not params:
        raise ValueError("nasa_power_response_missing_parameter_block")

    t2m = params.get("T2M", {})
    rh2m = params.get("RH2M", {})
    ws10m = params.get("WS10M", {})
    radiation = params.get("ALLSKY_SFC_SW_DWN", {})

    # NASA POWER keys are YYYYMMDDHH strings; union of all timestamp keys
    all_keys = sorted(set(t2m) | set(rh2m) | set(ws10m) | set(radiation))

    records: list[WeatherRecord] = []
    for key in all_keys:
        ts = datetime.strptime(key, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        records.append(
            WeatherRecord(
                ward_id=ward_id,
                timestamp_utc=ts,
                temperature_c=_nasa_null(t2m.get(key)),
                relative_humidity_pct=_nasa_null(rh2m.get(key)),
                wind_speed_ms=_nasa_null(ws10m.get(key)),
                solar_radiation_wm2=_nasa_null(radiation.get(key)),
                latitude=latitude,
                longitude=longitude,
                source_type=SourceType.NASA_POWER_HOURLY,
                quality_flag=QualityFlag.FALLBACK_SOURCE,
            )
        )
    return records


def load_demo_fixture(
    ward_id: str, latitude: float, longitude: float, hours: int = 120
) -> list[WeatherRecord]:
    """
    Tier-3 fallback: versioned local fixture. Used only when both live
    sources and cache have failed. Every record is explicitly marked
    DEMO_FIXTURE so downstream stages and the UI can label it clearly.
    """
    if not DEMO_FIXTURE_PATH.exists():
        raise FileNotFoundError(
            f"demo_fixture_missing path={DEMO_FIXTURE_PATH} "
            f"version={DEMO_FIXTURE_VERSION}"
        )

    raw = json.loads(DEMO_FIXTURE_PATH.read_text())
    rows = raw.get("hourly_records", [])[:hours]
    if not rows:
        raise ValueError("demo_fixture_empty")

    logger.warning(
        "using_demo_fixture ward_id=%s version=%s rows=%d",
        ward_id, DEMO_FIXTURE_VERSION, len(rows),
    )

    records = []
    for row in rows:
        records.append(
            WeatherRecord(
                ward_id=ward_id,
                timestamp_utc=datetime.fromisoformat(row["timestamp_utc"]),
                temperature_c=row.get("temperature_c"),
                relative_humidity_pct=row.get("relative_humidity_pct"),
                wind_speed_ms=row.get("wind_speed_ms"),
                solar_radiation_wm2=row.get("solar_radiation_wm2"),
                latitude=latitude,
                longitude=longitude,
                source_type=SourceType.DEMO_FIXTURE,
                quality_flag=QualityFlag.DEMO_FIXTURE,
            )
        )
    return records


def merge_radiation_fallback(
    primary: list[WeatherRecord], fallback: list[WeatherRecord]
) -> list[WeatherRecord]:
    """
    If Open-Meteo succeeded but is missing solar_radiation_wm2 for some
    hours, backfill only that field from NASA POWER, matched by hour.
    Everything else in `primary` is left untouched. Records that receive
    a backfilled value get quality_flag=FALLBACK_SOURCE.
    """
    fallback_by_hour = {r.timestamp_utc.replace(minute=0, second=0, microsecond=0): r for r in fallback}
    merged = []
    for rec in primary:
        if rec.solar_radiation_wm2 is None:
            hour_key = rec.timestamp_utc.replace(minute=0, second=0, microsecond=0)
            fb = fallback_by_hour.get(hour_key)
            if fb and fb.solar_radiation_wm2 is not None:
                rec = rec.model_copy(
                    update={
                        "solar_radiation_wm2": fb.solar_radiation_wm2,
                        "quality_flag": QualityFlag.FALLBACK_SOURCE,
                    }
                )
        merged.append(rec)
    return merged


# --- helpers -----------------------------------------------------------

def _parse_open_meteo_time(ts: str) -> datetime:
    # Open-Meteo returns "YYYY-MM-DDTHH:MM" in the requested timezone;
    # we always request timezone=UTC explicitly in the client.
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)


def _safe_index(arr: Optional[list], i: int) -> Optional[float]:
    if not isinstance(arr, list) or i >= len(arr):
        return None
    val = arr[i]
    return float(val) if val is not None else None


def _nasa_null(val) -> Optional[float]:
    # NASA POWER uses -999 as a documented missing-value sentinel.
    if val is None:
        return None
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return None
    return None if fval <= -900 else fval
