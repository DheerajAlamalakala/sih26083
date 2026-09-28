from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HourlyWeatherData(BaseModel):
  timestamp: datetime
  temperature_2m: float = Field(..., description="Air temperature in Celsius")
  relative_humidity_2m: float = Field(
      ..., description="Relative humidity percentage"
  )
  wind_speed_10m: float = Field(..., description="Wind speed at 10m in km/h")
  direct_normal_irradiance: float = Field(
      ..., description="Direct solar irradiance in W/m2"
  )
  surface_pressure: float = Field(..., description="Surface pressure in hPa")


class WeatherForecastResponse(BaseModel):
  latitude: float
  longitude: float
  elevation: float
  timezone: str
  source_type: str = Field(
      "open_meteo_live", description="open_meteo_live or offline_fixture"
  )
  fetched_at: datetime
  hourly: list[HourlyWeatherData]
