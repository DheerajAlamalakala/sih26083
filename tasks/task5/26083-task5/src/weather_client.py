"""
Weather data pipeline client for SIH26083 Task 1.

Fallback order (per playbook):
  1. Latest valid cached forecast (if fresh)
  2. Open-Meteo Forecast API (primary)
  3. NASA POWER Hourly API (fallback, esp. for solar radiation)
  4. Versioned demo fixture
  5. quality_flag always set; never silently substitute a 24h mean.

Exposes a clean Python interface: Task 2 receives WeatherRecord objects
and never sees Open-Meteo/NASA-specific field names.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from src.cache import WeatherCache
from src.weather_normalizer import (
    load_demo_fixture,
    merge_radiation_fallback,
    normalize_nasa_power_hourly,
    normalize_open_meteo_forecast,
)
from src.weather_schema import WeatherRecord

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_S = 1.5
MIN_FORECAST_HOURS = 120


class WeatherAPIError(Exception):
    """Raised when a source cannot be used (network, timeout, malformed)."""


class WeatherClient:
    def __init__(
        self,
        cache: Optional[WeatherCache] = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_s: float = DEFAULT_RETRY_BACKOFF_S,
        http_client: Optional[httpx.Client] = None,
    ):
        self.cache = cache or WeatherCache()
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        self._client = http_client or httpx.Client(timeout=timeout_s)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "WeatherClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- public API -------------------------------------------------

    def fetch_hourly_weather(
        self,
        ward_id: str,
        latitude: float,
        longitude: float,
        hours: int = MIN_FORECAST_HOURS,
    ) -> list[WeatherRecord]:
        """
        Main entry point. Returns at least `hours` WeatherRecord objects
        for the given ward, applying the full fallback chain.
        """
        if hours < MIN_FORECAST_HOURS:
            logger.warning(
                "hours_below_recommended_minimum requested=%d minimum=%d",
                hours, MIN_FORECAST_HOURS,
            )

        # Tier 1: cache
        cached = self._try_cache(ward_id)
        if cached is not None:
            return cached

        # Tier 2: Open-Meteo (primary)
        try:
            records = self._fetch_open_meteo(ward_id, latitude, longitude, hours)
        except WeatherAPIError as exc:
            logger.warning("open_meteo_failed ward_id=%s error=%s", ward_id, exc)
            records = None

        # Tier 3: NASA POWER fallback — either full fallback or radiation backfill
        if records is None:
            try:
                records = self._fetch_nasa_power(ward_id, latitude, longitude, hours)
            except WeatherAPIError as exc:
                logger.warning("nasa_power_failed ward_id=%s error=%s", ward_id, exc)
                records = None
        else:
            missing_radiation = any(r.solar_radiation_wm2 is None for r in records)
            if missing_radiation:
                try:
                    nasa_records = self._fetch_nasa_power(ward_id, latitude, longitude, hours)
                    records = merge_radiation_fallback(records, nasa_records)
                except WeatherAPIError as exc:
                    logger.warning(
                        "nasa_power_radiation_backfill_failed ward_id=%s error=%s",
                        ward_id, exc,
                    )

        # Tier 4: demo fixture
        if records is None:
            logger.error(
                "all_live_sources_failed_using_fixture ward_id=%s", ward_id
            )
            records = load_demo_fixture(ward_id, latitude, longitude, hours)

        self.cache.write(ward_id, [r.model_dump(mode="json") for r in records])
        return records

    # -- source-specific fetchers ------------------------------------

    def _fetch_open_meteo(
        self, ward_id: str, latitude: float, longitude: float, hours: int
    ) -> list[WeatherRecord]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation",
            "timezone": "UTC",
            "forecast_days": max(1, min(16, (hours // 24) + 1)),
        }
        raw = self._get_with_retries(OPEN_METEO_FORECAST_URL, params)
        try:
            records = normalize_open_meteo_forecast(raw, ward_id, latitude, longitude)
        except (ValueError, KeyError) as exc:
            raise WeatherAPIError(f"malformed_open_meteo_response: {exc}") from exc

        if len(records) < hours:
            logger.warning(
                "open_meteo_returned_fewer_hours ward_id=%s got=%d requested=%d",
                ward_id, len(records), hours,
            )
        return records[:hours] if len(records) > hours else records

    def _fetch_nasa_power(
        self, ward_id: str, latitude: float, longitude: float, hours: int
    ) -> list[WeatherRecord]:
        from datetime import datetime, timedelta, timezone as tz

        end = datetime.now(tz.utc)
        start = end - timedelta(hours=hours)
        params = {
            "parameters": "T2M,RH2M,WS10M,ALLSKY_SFC_SW_DWN",
            "community": "RE",
            "longitude": longitude,
            "latitude": latitude,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
        raw = self._get_with_retries(NASA_POWER_URL, params)
        try:
            return normalize_nasa_power_hourly(raw, ward_id, latitude, longitude)
        except (ValueError, KeyError) as exc:
            raise WeatherAPIError(f"malformed_nasa_power_response: {exc}") from exc

    # -- cache & retry infra ------------------------------------------

    def _try_cache(self, ward_id: str) -> Optional[list[WeatherRecord]]:
        entry = self.cache.read(ward_id)
        if entry is None:
            return None
        if not entry.is_fresh():
            logger.info("cache_stale_skipping ward_id=%s", ward_id)
            return None
        try:
            return [WeatherRecord(**r) for r in entry.payload]
        except Exception as exc:  # noqa: BLE001 - cache corruption is non-fatal
            logger.warning("cache_payload_invalid ward_id=%s error=%s", ward_id, exc)
            return None

    def _get_with_retries(self, url: str, params: dict) -> dict:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._client.get(url, params=params, timeout=self.timeout_s)
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "request_timeout url=%s attempt=%d/%d", url, attempt, self.max_retries
                )
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.warning(
                    "request_http_error url=%s status=%s attempt=%d/%d",
                    url, exc.response.status_code, attempt, self.max_retries,
                )
                if exc.response.status_code < 500:
                    # Client errors (4xx) won't be fixed by retrying
                    break
            except httpx.RequestError as exc:
                last_exc = exc
                logger.warning(
                    "request_network_error url=%s attempt=%d/%d error=%s",
                    url, attempt, self.max_retries, exc,
                )
            except ValueError as exc:  # JSON decode failure
                last_exc = exc
                logger.warning("response_not_json url=%s attempt=%d/%d", url, attempt, self.max_retries)

            if attempt < self.max_retries:
                time.sleep(self.retry_backoff_s * attempt)

        raise WeatherAPIError(f"request_failed url={url} last_error={last_exc}")
