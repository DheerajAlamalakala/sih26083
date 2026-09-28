"""
File-based cache for the last known-good weather payload per ward.
Used as tier 1 of the fallback chain: latest valid cached forecast
takes priority over calling external APIs again on transient failure.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data/cache/weather")
DEFAULT_FRESHNESS_WINDOW = timedelta(hours=6)


@dataclass
class CacheEntry:
    ward_id: str
    fetched_at_utc: datetime
    payload: dict  # raw list[WeatherRecord]-as-dict, pre-validated

    def is_fresh(self, window: timedelta = DEFAULT_FRESHNESS_WINDOW) -> bool:
        return datetime.now(timezone.utc) - self.fetched_at_utc <= window


class WeatherCache:
    """Simple JSON-on-disk cache, one file per ward_id."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, ward_id: str) -> Path:
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in ward_id)
        return self.cache_dir / f"{safe_id}.json"

    def write(self, ward_id: str, records: list[dict]) -> None:
        entry = {
            "ward_id": ward_id,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "payload": records,
        }
        path = self._path_for(ward_id)
        try:
            path.write_text(json.dumps(entry, indent=2, default=str))
            logger.info("cache_write ward_id=%s records=%d", ward_id, len(records))
        except OSError as exc:
            # Cache write failure should never crash the pipeline
            logger.warning("cache_write_failed ward_id=%s error=%s", ward_id, exc)

    def read(self, ward_id: str) -> Optional[CacheEntry]:
        path = self._path_for(ward_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            fetched_at = datetime.fromisoformat(raw["fetched_at_utc"])
            return CacheEntry(
                ward_id=raw["ward_id"],
                fetched_at_utc=fetched_at,
                payload=raw["payload"],
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("cache_read_corrupt ward_id=%s error=%s", ward_id, exc)
            return None
