import json


def join_demographic_exposure(wards: list, census_filepath: str) -> list:
  """Joins GIS ward polygon spatial structures with demographic exposure attributes from the census GeoJSON file."""
  with open(census_filepath, "r") as f:
    data = json.load(f)

  features = data.get("features", [])

  # Build dictionary keyed by ward_id, extracting attributes from properties
  census_dict = {}
  for feat in features:
    props = feat.get("properties", {})
    ward_id = props.get("ward_id")
    if ward_id:
      census_dict[ward_id] = props

  joined_results = []
  for ward in wards:
    w_id = ward["ward_id"]
    demo_data = census_dict.get(w_id, {})

    merged_record = {
        "ward_id": w_id,
        "ward_name": ward.get("ward_name") or demo_data.get("ward_name"),
        "zone_name": ward.get("zone_name") or demo_data.get("zone_name"),
        "elderly_pct": demo_data.get("elderly_pct", ward.get("elderly_pct", 0.0)),
        "outdoor_worker_pct": demo_data.get(
            "outdoor_worker_pct", ward.get("outdoor_worker_pct", 0.0)
        ),
        "slum_density_pct": demo_data.get(
            "slum_density_pct", ward.get("slum_density_pct", 0.0)
        ),
        "green_cover_pct": demo_data.get(
            "green_cover_pct", ward.get("green_cover_pct", 0.0)
        ),
        "geometry": ward["geometry"],
        "source_vintage": ward.get(
            "source_vintage",
            demo_data.get("source_vintage", "TGRAC_2021_V1"),
        ),
        "data_source": ward.get(
            "data_source", demo_data.get("data_source", "TGRAC_OFFICIAL")
        ),
    }
    joined_results.append(merged_record)

  return joined_results