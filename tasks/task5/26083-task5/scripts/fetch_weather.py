#!/usr/bin/env python3
"""
Executable pipeline entry point for Task 1.

Usage:
    python scripts/fetch_weather.py --ward-id W001 --lat 17.385 --lon 78.4867 \
        --hours 120 --out data/processed/weather/sample_weather.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.weather_client import WeatherClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("fetch_weather")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch normalized weather data for a ward.")
    parser.add_argument("--ward-id", required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--hours", type=int, default=120)
    parser.add_argument("--out", type=Path, default=Path("data/processed/weather/sample_weather.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with WeatherClient() as client:
        try:
            records = client.fetch_hourly_weather(
                ward_id=args.ward_id,
                latitude=args.lat,
                longitude=args.lon,
                hours=args.hours,
            )
        except Exception:
            logger.exception("pipeline_failed ward_id=%s", args.ward_id)
            return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in records]
    args.out.write_text(json.dumps(payload, indent=2))

    quality_summary = {}
    for r in records:
        quality_summary[r.quality_flag] = quality_summary.get(r.quality_flag, 0) + 1

    logger.info(
        "pipeline_complete ward_id=%s records=%d out=%s quality_summary=%s",
        args.ward_id, len(records), args.out, quality_summary,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
