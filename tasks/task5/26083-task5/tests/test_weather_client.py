"""
Unit tests for the Task 1 weather pipeline.
Covers: successful fetch, malformed response, timeout, missing variable,
unit/UTC normalization, and cache fallback — per playbook AI code prompt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from src.cache import WeatherCache
from src.weather_client import WeatherAPIError, WeatherClient
from src.weather_schema import QualityFlag, SourceType, WeatherRecord

WARD_ID = "TEST_WARD_01"
LAT, LON = 17.385, 78.4867


def _open_meteo_payload(n_hours: int = 120, missing_radiation: bool = False) -> dict:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    times = [(base.replace(hour=0)).isoformat() for _ in range(n_hours)]
    # give distinct timestamps
    from datetime import timedelta
    times = [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(n_hours)]

    return {
        "hourly": {
            "time": times,
            "temperature_2m": [30.0 + (i % 5) for i in range(n_hours)],
            "relative_humidity_2m": [55.0 for _ in range(n_hours)],
            "wind_speed_10m": [3.2 for _ in range(n_hours)],
            "shortwave_radiation": [None if missing_radiation else 400.0 for _ in range(n_hours)],
        }
    }


class DummyTransport(httpx.BaseTransport):
    """Routes requests to a canned handler for testing without real network calls."""

    def __init__(self, handler):
        self.handler = handler

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)


@pytest.fixture
def tmp_cache(tmp_path: Path) -> WeatherCache:
    return WeatherCache(cache_dir=tmp_path / "cache")


def _client_with_handler(handler, tmp_cache) -> WeatherClient:
    http_client = httpx.Client(transport=DummyTransport(handler))
    return WeatherClient(cache=tmp_cache, http_client=http_client, max_retries=2, retry_backoff_s=0.01)


# --- successful fetch ----------------------------------------------------

def test_successful_open_meteo_fetch(tmp_cache):
    def handler(request: httpx.Request) -> httpx.Response:
        if "power.larc.nasa.gov" in str(request.url):
            return httpx.Response(200, json={"properties": {"parameter": {}}})
        return httpx.Response(200, json=_open_meteo_payload(120))

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    assert len(records) == 120
    assert all(isinstance(r, WeatherRecord) for r in records)
    assert records[0].source_type == SourceType.OPEN_METEO_FORECAST
    assert records[0].quality_flag == QualityFlag.OK
    assert records[0].ward_id == WARD_ID


# --- malformed response ---------------------------------------------------

def test_malformed_open_meteo_falls_back_to_fixture(tmp_cache, tmp_path, monkeypatch):
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    fixture_path = fixture_dir / "demo_fixture_v1.json"
    fixture_path.write_text(_valid_fixture_json(hours=120))

    import src.weather_normalizer as normalizer
    monkeypatch.setattr(normalizer, "DEMO_FIXTURE_PATH", fixture_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if "power.larc.nasa.gov" in str(request.url):
            return httpx.Response(200, json={"bad": "shape"})  # also malformed
        return httpx.Response(200, json={"unexpected": "shape"})  # missing "hourly" key

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    assert all(r.source_type == SourceType.DEMO_FIXTURE for r in records)
    assert all(r.quality_flag == QualityFlag.DEMO_FIXTURE for r in records)


# --- timeout ---------------------------------------------------------------

def test_timeout_triggers_retry_then_nasa_fallback(tmp_cache):
    call_count = {"open_meteo": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "open-meteo.com" in url:
            call_count["open_meteo"] += 1
            raise httpx.TimeoutException("simulated timeout", request=request)
        if "power.larc.nasa.gov" in url:
            return httpx.Response(200, json=_nasa_power_payload(120))
        raise AssertionError("unexpected URL")

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    assert call_count["open_meteo"] == 2  # retried up to max_retries
    assert all(r.source_type == SourceType.NASA_POWER_HOURLY for r in records)
    assert all(r.quality_flag == QualityFlag.FALLBACK_SOURCE for r in records)


# --- missing variable (partial data) ---------------------------------------

def test_missing_radiation_backfilled_from_nasa(tmp_cache):
    def handler(request: httpx.Request) -> httpx.Response:
        if "power.larc.nasa.gov" in str(request.url):
            return httpx.Response(200, json=_nasa_power_payload(120))
        return httpx.Response(200, json=_open_meteo_payload(120, missing_radiation=True))

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    assert all(r.solar_radiation_wm2 is not None for r in records)
    assert all(r.quality_flag == QualityFlag.FALLBACK_SOURCE for r in records)
    # temperature etc. still came from Open-Meteo, unaffected
    assert all(r.temperature_c is not None for r in records)


def test_open_meteo_missing_hourly_block_raises_before_fixture(tmp_cache):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"no_hourly_key": True})

    client = _client_with_handler(handler, tmp_cache)
    # NASA also fails -> should end up at fixture; verify no crash and
    # correct error propagation path via monkeypatched fixture is covered
    # in test_malformed_open_meteo_falls_back_to_fixture. Here we assert
    # the low-level normalizer raises cleanly.
    from src.weather_normalizer import normalize_open_meteo_forecast
    with pytest.raises(ValueError):
        normalize_open_meteo_forecast({"no_hourly_key": True}, WARD_ID, LAT, LON)


# --- unit / UTC normalization ------------------------------------------------

def test_timestamps_are_utc_aware(tmp_cache):
    def handler(request: httpx.Request) -> httpx.Response:
        if "power.larc.nasa.gov" in str(request.url):
            return httpx.Response(200, json={"properties": {"parameter": {}}})
        return httpx.Response(200, json=_open_meteo_payload(120))

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    for r in records:
        assert r.timestamp_utc.tzinfo is not None
        assert r.timestamp_utc.utcoffset().total_seconds() == 0


# --- cache fallback ----------------------------------------------------------

def test_cache_hit_skips_network(tmp_cache):
    sample = [
        WeatherRecord(
            ward_id=WARD_ID,
            timestamp_utc=datetime(2026, 5, 1, tzinfo=timezone.utc),
            temperature_c=32.0,
            relative_humidity_pct=50.0,
            wind_speed_ms=2.5,
            solar_radiation_wm2=500.0,
            latitude=LAT,
            longitude=LON,
            source_type=SourceType.OPEN_METEO_FORECAST,
            quality_flag=QualityFlag.OK,
        )
    ]
    tmp_cache.write(WARD_ID, [r.model_dump(mode="json") for r in sample])

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network should not be called when cache is fresh")

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=1)

    assert len(records) == 1
    assert records[0].temperature_c == 32.0


def test_stale_cache_falls_through_to_network(tmp_cache, monkeypatch):
    from datetime import timedelta
    from src.cache import CacheEntry

    stale_entry = CacheEntry(
        ward_id=WARD_ID,
        fetched_at_utc=datetime.now(timezone.utc) - timedelta(hours=48),
        payload=[],
    )
    monkeypatch.setattr(tmp_cache, "read", lambda ward_id: stale_entry)

    called = {"hit": False}

    def handler(request: httpx.Request) -> httpx.Response:
        called["hit"] = True
        if "power.larc.nasa.gov" in str(request.url):
            return httpx.Response(200, json={"properties": {"parameter": {}}})
        return httpx.Response(200, json=_open_meteo_payload(120))

    client = _client_with_handler(handler, tmp_cache)
    client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    assert called["hit"] is True


# --- integration proof: output validates directly against schema for Task 2 --

def test_output_matches_canonical_schema_for_task2(tmp_cache):
    def handler(request: httpx.Request) -> httpx.Response:
        if "power.larc.nasa.gov" in str(request.url):
            return httpx.Response(200, json={"properties": {"parameter": {}}})
        return httpx.Response(200, json=_open_meteo_payload(120))

    client = _client_with_handler(handler, tmp_cache)
    records = client.fetch_hourly_weather(WARD_ID, LAT, LON, hours=120)

    # Simulate Task 2 receiving these over the wire (JSON round-trip)
    dumped = [r.model_dump(mode="json") for r in records]
    reconstructed = [WeatherRecord(**d) for d in dumped]
    assert len(reconstructed) == len(records)
    for r in reconstructed:
        assert r.ward_id == WARD_ID
        assert r.quality_flag is not None


# --- helpers -----------------------------------------------------------

def _nasa_power_payload(n_hours: int) -> dict:
    from datetime import timedelta
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    t2m, rh2m, ws10m, rad = {}, {}, {}, {}
    for i in range(n_hours):
        ts = (base + timedelta(hours=i)).strftime("%Y%m%d%H")
        t2m[ts] = 31.0
        rh2m[ts] = 52.0
        ws10m[ts] = 2.8
        rad[ts] = 420.0
    return {
        "properties": {
            "parameter": {
                "T2M": t2m,
                "RH2M": rh2m,
                "WS10M": ws10m,
                "ALLSKY_SFC_SW_DWN": rad,
            }
        }
    }


def _valid_fixture_json(hours: int) -> str:
    import json
    from datetime import timedelta
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rows = [
        {
            "timestamp_utc": (base + timedelta(hours=i)).isoformat(),
            "temperature_c": 33.0,
            "relative_humidity_pct": 45.0,
            "wind_speed_ms": 2.0,
            "solar_radiation_wm2": 380.0,
        }
        for i in range(hours)
    ]
    return json.dumps({"fixture_version": "v1_0", "hourly_records": rows})
