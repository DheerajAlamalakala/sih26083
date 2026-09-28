"""
Deterministic Heat Index / UTCI-style apparent-temperature estimate.

Implements the NOAA/NWS Rothfusz regression (Heat Index) in Celsius.
No ML. A simplified UTCI-like proxy (`utci_c`) is derived from the same
inputs with a wind-chill-style wind adjustment, since a full UTCI
polynomial requires mean radiant temperature not available from this
pipeline's inputs; this is documented as an approximation, not the
official UTCI standard.
"""
from __future__ import annotations

from typing import Optional

from src.thermal.constants import HEAT_INDEX_SIMPLE_THRESHOLD_C


def _c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def _f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def compute_heat_index_c(
    temperature_c: Optional[float], relative_humidity_pct: Optional[float]
) -> Optional[float]:
    """NWS Rothfusz regression heat index, returned in Celsius."""
    if temperature_c is None or relative_humidity_pct is None:
        return None

    if temperature_c < HEAT_INDEX_SIMPLE_THRESHOLD_C:
        # NWS simple (Steadman) formula for lower temperatures
        hi_c = 0.5 * (
            temperature_c
            + 61.0
            + ((temperature_c - 68.0 * 5.0 / 9.0) * 1.2)
            + (relative_humidity_pct * 0.094)
        )
        return round(hi_c, 2)

    t = _c_to_f(temperature_c)
    r = relative_humidity_pct
    hi_f = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * r
        - 0.22475541 * t * r
        - 0.00683783 * t * t
        - 0.05481717 * r * r
        + 0.00122874 * t * t * r
        + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r
    )
    return round(_f_to_c(hi_f), 2)


def compute_utci_proxy_c(
    temperature_c: Optional[float],
    relative_humidity_pct: Optional[float],
    wind_speed_ms: Optional[float],
) -> Optional[float]:
    """
    Simplified UTCI-like apparent temperature proxy: heat index adjusted
    for wind speed (higher wind -> modest cooling effect on perceived
    heat). This is an internal approximation used only because full UTCI
    requires mean radiant temperature, which this pipeline does not have.
    """
    hi = compute_heat_index_c(temperature_c, relative_humidity_pct)
    if hi is None:
        return None
    if wind_speed_ms is None:
        return hi
    wind_adjustment = min(wind_speed_ms, 8.0) * 0.15
    return round(hi - wind_adjustment, 2)
