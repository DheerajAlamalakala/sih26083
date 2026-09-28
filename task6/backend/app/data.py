
"""Task 6 integration data adapters.

This layer reads the existing Task 1/3/4/5 demo artifacts without editing them.
It maps their existing fields into the Task 6 API contract.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO = PROJECT_ROOT / "demo_data"
TASK5_SRC = PROJECT_ROOT.parent / "tasks" / "task5" / "26083-task5" / "src"

if str(TASK5_SRC) not in sys.path:
    sys.path.insert(0, str(TASK5_SRC))

from alerts.action_engine import create_action_record  # type: ignore


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DEMO / name).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_health_risk() -> list[dict[str, Any]]:
    rows = _read_csv("health_risk.csv")
    result = []
    for r in rows:
        result.append({
            "ward_id": r["ward_id"],
            "valid_time_utc": r["valid_time_utc"],
            "forecast_day": int(r["forecast_day"]),
            "thermal_stress_0_100": _float_or_none(r.get("thermal_stress_mean")),
            "vulnerability_0_100": _float_or_none(r.get("vulnerability_0_100")),
            "mortality_risk_0_100": _float_or_none(r.get("mortality_risk_0_100")),
            "hospitalization_risk_0_100": _float_or_none(r.get("hospitalization_risk_0_100")),
            "mortality_risk_level": r.get("mortality_risk_level") or "unknown",
            "hospitalization_risk_level": r.get("hospitalization_risk_level") or "unknown",
            "drivers": _drivers(r.get("mortality_drivers"), r.get("hospitalization_drivers")),
            "is_synthetic": r.get("is_synthetic", "").lower() == "true",
            "source_type": r.get("source_type") or "unknown",
            "model_version": r.get("model_version") or "unknown",
            "quality_flag": r.get("quality_flag") or "UNKNOWN",
        })
    return result


def load_vulnerability() -> dict[str, dict[str, Any]]:
    result = {}
    for r in _read_csv("vulnerability.csv"):
        result[r["ward_id"]] = {
            "ward_id": r["ward_id"],
            "ward_name": r["ward_name"],
            "zone_name": r["zone_name"],
            "elderly_exposure_0_100": _float_or_none(r["elderly_exposure_0_100"]),
            "outdoor_worker_exposure_0_100": _float_or_none(r["outdoor_worker_exposure_0_100"]),
            "vulnerability_0_100": _float_or_none(r["vulnerability_0_100"]),
            "primary_alert": r["primary_alert"],
            "source_vintage": r["source_vintage"],
            "quality_flag": r["quality_flag"],
        }
    return result


def load_wards() -> dict[str, Any]:
    """Convert the supplied Esri-style `rings` geometry to displayable GeoJSON.

    The source file is not changed. Conversion happens only in the API response.
    """
    raw = json.loads((DEMO / "wards.geojson").read_text(encoding="utf-8"))
    features = []
    for feature in raw.get("features", []):
        geometry = feature.get("geometry", {})
        rings = geometry.get("rings", [])
        polygons = []
        for ring in rings:
            if len(ring) >= 3:
                polygons.append([[float(x), float(y)] for x, y in ring])
        if not polygons:
            continue
        # Existing source is Esri rings; expose as MultiPolygon for Leaflet/GeoJSON.
        coordinates = [[[x, y] for x, y in ring] for ring in polygons]
        geo_type = "Polygon" if len(coordinates) == 1 else "MultiPolygon"
        geo_coords = coordinates if geo_type == "Polygon" else [[[p for p in ring] for ring in coordinates]]
        # MultiPolygon shape: [[[ [x,y],... ]], ...]
        if geo_type == "MultiPolygon":
            geo_coords = [[ring] for ring in coordinates]
        props = dict(feature.get("properties", {}))
        features.append({
            "type": "Feature",
            "geometry": {"type": geo_type, "coordinates": geo_coords},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": features}


def load_weather_fixture() -> dict[str, Any]:
    return json.loads((DEMO / "weather_fixture.json").read_text(encoding="utf-8"))


def build_action_records(health_rows: list[dict[str, Any]], vulnerability: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Run the existing Task 5 action engine; Task 6 does not recalculate health risk."""
    records = []
    for row in health_rows:
        ward = vulnerability.get(row["ward_id"])
        if not ward:
            continue
        mortality = row["mortality_risk_0_100"]
        hospitalization = row["hospitalization_risk_0_100"]
        vuln = ward["vulnerability_0_100"]
        if mortality is None or hospitalization is None or vuln is None:
            continue
        action = create_action_record(
            ward_id=row["ward_id"],
            valid_time_utc=row["valid_time_utc"],
            forecast_day=row["forecast_day"],
            mortality_risk_0_100=float(mortality),
            hospitalization_risk_0_100=float(hospitalization),
            vulnerability_0_100=float(vuln),
            heat_persistence_hours=0,
        )
        records.append(action.__dict__)
    return records


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _drivers(*values: Any) -> list[str]:
    out = []
    for value in values:
        if value:
            out.extend([x.strip() for x in str(value).split(",") if x.strip()])
    return list(dict.fromkeys(out))
