import json


def calculate_ring_center(rings):
  """Calculates centroid (mean lon, mean lat) for Esri JSON polygon rings."""
  if not rings or not rings[0]:
    return 78.47, 17.38
  pts = rings[0]
  lons = [p[0] for p in pts]
  lats = [p[1] for p in pts]
  return sum(lons) / len(lons), sum(lats) / len(lats)


def load_tgrac_ward_layer(filepath: str) -> list:
  """Loads the GHMC ward layer supporting both GeoJSON and Esri JSON formats."""
  with open(filepath, "r") as f:
    data = json.load(f)

  wards = []
  features = data.get("features", [])

  for idx, feat in enumerate(features, 1):
    # Support both Esri JSON ('attributes') and GeoJSON ('properties')
    props = feat.get("attributes") or feat.get("properties") or {}
    geom = feat.get("geometry", {})

    # Extract polygon center
    if "rings" in geom:
      center_lon, center_lat = calculate_ring_center(geom["rings"])
    elif "coordinates" in geom and geom.get("type") == "Polygon":
      pts = geom["coordinates"][0]
      center_lon = sum(p[0] for p in pts) / len(pts)
      center_lat = sum(p[1] for p in pts) / len(pts)
    else:
      center_lon, center_lat = 78.47, 17.38

    # Extract ward identifiers from TGRAC schema
    ward_id = (
        props.get("WARD_ID")
        or props.get("ward_id")
        or props.get("OBJECTID")
        or f"GHMC_W{idx:03d}"
    )
    if isinstance(ward_id, int):
      ward_id = f"GHMC_W{ward_id:03d}"

    ward_name = (
        props.get("WARD_NAME")
        or props.get("ward_name")
        or f"GHMC Ward {ward_id}"
    )
    zone_name = (
        props.get("ZONE_NAME")
        or props.get("zone_name")
        or props.get("CIRCLE_NAME")
        or "GHMC Central"
    )

    ward_record = {
        "ward_id": str(ward_id),
        "ward_name": str(ward_name),
        "zone_name": str(zone_name),
        "center": (center_lon, center_lat),
        "elderly_pct": float(props.get("elderly_pct", 50.0)),
        "outdoor_worker_pct": float(props.get("outdoor_worker_pct", 50.0)),
        "slum_density_pct": float(props.get("slum_density_pct", 30.0)),
        "green_cover_pct": float(props.get("green_cover_pct", 20.0)),
        "geometry": geom,
        "source_vintage": "TGRAC_2021_V1",
        "data_source": "TGRAC_OFFICIAL",
    }
    wards.append(ward_record)

  return wards