from datetime import datetime, timezone
import json
import os
import requests
from src.weather.schemas import HourlyWeatherData, WeatherForecastResponse

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather_forecast(
    lat: float = 17.3850,
    lon: float = 78.4867,
    days: int = 5,
    fixture_path: str = "data/processed/weather/mock_weather.json",
) -> WeatherForecastResponse:
  params = {
      "latitude": lat,
      "longitude": lon,
      "hourly": [
          "temperature_2m",
          "relative_humidity_2m",
          "wind_speed_10m",
          "direct_normal_irradiance",
          "surface_pressure",
      ],
      "forecast_days": days,
      "timezone": "auto",
  }

  try:
    response = requests.get(OPEN_METEO_URL, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    hourly_raw = data.get("hourly", {})
    timestamps = hourly_raw.get("time", [])

    hourly_records = []
    for idx, t_str in enumerate(timestamps):
      record = HourlyWeatherData(
          timestamp=datetime.fromisoformat(t_str),
          temperature_2m=hourly_raw["temperature_2m"][idx],
          relative_humidity_2m=hourly_raw["relative_humidity_2m"][idx],
          wind_speed_10m=hourly_raw["wind_speed_10m"][idx],
          direct_normal_irradiance=hourly_raw["direct_normal_irradiance"][
              idx
          ],
          surface_pressure=hourly_raw["surface_pressure"][idx],
      )
      hourly_records.append(record)

    forecast = WeatherForecastResponse(
        latitude=data["latitude"],
        longitude=data["longitude"],
        elevation=data["elevation"],
        timezone=data["timezone"],
        source_type="open_meteo_live",
        fetched_at=datetime.now(timezone.utc),
        hourly=hourly_records,
    )

    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    with open(fixture_path, "w") as f:
      f.write(forecast.model_dump_json(indent=2))

    return forecast

  except Exception as err:
    print(
        f"Warning: Failed to fetch live data ({err}). Trying offline"
        " fixture..."
    )
    if os.path.exists(fixture_path):
      with open(fixture_path, "r") as f:
        cached_data = json.load(f)
        cached_data["source_type"] = "offline_fixture"
        return WeatherForecastResponse(**cached_data)
    raise RuntimeError(f"Missing fixture file at {fixture_path}")


if __name__ == "__main__":
  res = fetch_weather_forecast()
  print(
      f" Successfully retrieved {len(res.hourly)} hourly weather data points"
      f" via {res.source_type}."
  )