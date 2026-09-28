import json
import os


def generate_gis_geojson(
    weather_fixture_path: str = "data/processed/weather/mock_weather.json",
    output_geojson_path: str = "data/processed/weather/gis_weather.geojson",
):
  """Reads the weather fixture and converts spatial points to GeoJSON format for GIS integration."""
  if not os.path.exists(weather_fixture_path):
    raise FileNotFoundError(f"Fixture file not found at {weather_fixture_path}")

  with open(weather_fixture_path, "r") as f:
    data = json.load(f)

  lat = data.get("latitude")
  lon = data.get("longitude")
  hourly_records = data.get("hourly", [])

  # Construct GeoJSON FeatureCollection
  features = []
  for record in hourly_records:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "timestamp": record.get("timestamp"),
            "temperature_2m": record.get("temperature_2m"),
            "relative_humidity_2m": record.get("relative_humidity_2m"),
            "wind_speed_10m": record.get("wind_speed_10m"),
            "direct_normal_irradiance": record.get("direct_normal_irradiance"),
            "surface_pressure": record.get("surface_pressure"),
        },
    }
    features.append(feature)

  geojson_data = {
      "type": "FeatureCollection",
      "crs": {
          "type": "name",
          "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
      },
      "features": features,
  }

  os.makedirs(os.path.dirname(output_geojson_path), exist_ok=True)
  with open(output_geojson_path, "w") as f:
    json.dump(geojson_data, f, indent=2)

  print(
      f" Successfully generated GeoJSON with {len(features)} spatial features"
      f" at {output_geojson_path}"
  )


if __name__ == "__main__":
  generate_gis_geojson()