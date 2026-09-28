"""
Deterministic WBGT (Wet Bulb Globe Temperature) estimation.

No ML. This is a published approximation used when true psychrometric /
black-globe sensor inputs are unavailable, per SIH26083 Playbook Stage-1
rules. Missing inputs propagate to `None` (never silently imputed).
"""
from __future__ import annotations

from typing import Optional

from src.thermal.constants import (
    SOLAR_ADJUSTMENT_MAX_C,
    SOLAR_ADJUSTMENT_REF_WM2,
    SOLAR_ADJUSTMENT_THRESHOLD_WM2,
    WBGT_CONSTANT,
    WBGT_TA_COEFF,
    WBGT_VAPOUR_COEFF,
)


def saturation_vapour_pressure_hpa(temperature_c: float) -> float:
    """Magnus-Tetens approximation of saturation vapour pressure (hPa)."""
    return 6.112 * pow(2.71828182845905, (17.62 * temperature_c) / (243.12 + temperature_c))


def vapour_pressure_hpa(temperature_c: float, relative_humidity_pct: float) -> float:
    """Actual vapour pressure (hPa) from temperature and relative humidity."""
    return saturation_vapour_pressure_hpa(temperature_c) * (relative_humidity_pct / 100.0)


def compute_wbgt_c(
    temperature_c: Optional[float],
    relative_humidity_pct: Optional[float],
    solar_radiation_wm2: Optional[float] = None,
) -> Optional[float]:
    """
    Estimate outdoor WBGT (deg C) from temperature, relative humidity and
    (optionally) incoming shortwave radiation.

    Returns None if a required input (temperature or humidity) is missing —
    callers must reflect this via quality_flag rather than substituting a
    default.
    """
    if temperature_c is None or relative_humidity_pct is None:
        return None

    e = vapour_pressure_hpa(temperature_c, relative_humidity_pct)
    wbgt = WBGT_TA_COEFF * temperature_c + WBGT_VAPOUR_COEFF * e + WBGT_CONSTANT

    if solar_radiation_wm2 is not None and solar_radiation_wm2 > SOLAR_ADJUSTMENT_THRESHOLD_WM2:
        excess = min(solar_radiation_wm2, SOLAR_ADJUSTMENT_REF_WM2) - SOLAR_ADJUSTMENT_THRESHOLD_WM2
        span = SOLAR_ADJUSTMENT_REF_WM2 - SOLAR_ADJUSTMENT_THRESHOLD_WM2
        wbgt += SOLAR_ADJUSTMENT_MAX_C * (excess / span)

    return round(wbgt, 2)
