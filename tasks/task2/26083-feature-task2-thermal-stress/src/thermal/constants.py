"""
Constants and thresholds for the deterministic Stage-1 thermal-stress
pipeline (SIH26083 Task 2). Per the Playbook, this stage MUST NOT use
machine learning; every formula here is a documented, published
approximation.

method_version is bumped whenever a formula, threshold or coefficient
changes, so downstream consumers (Task 4/5/6) can trace provenance.
"""
from __future__ import annotations

METHOD_VERSION = "thermal_stage1_v1_0"

# -- WBGT (outdoor, sun-exposed) approximation --------------------------
# Simplified WBGT estimate (Australian Bureau of Meteorology approximation,
# commonly used when a true black-globe/psychrometric WBGT sensor is
# unavailable): WBGT ~= 0.567*Ta + 0.393*e + 3.94
# where e = vapour pressure (hPa) derived from Ta and RH.
WBGT_TA_COEFF = 0.567
WBGT_VAPOUR_COEFF = 0.393
WBGT_CONSTANT = 3.94

# Solar-radiation adjustment: small upward correction to the base WBGT
# approximation when incoming shortwave radiation is high, since the
# formula above is calibrated for shaded/near-shade conditions.
SOLAR_ADJUSTMENT_THRESHOLD_WM2 = 400.0
SOLAR_ADJUSTMENT_MAX_C = 2.0
SOLAR_ADJUSTMENT_REF_WM2 = 1000.0

# -- Heat Index (NWS Rothfusz regression, degrees Celsius) --------------
# Standard NOAA/NWS Rothfusz regression, applied on Fahrenheit inputs and
# converted back to Celsius. Below 26.7 C (80 F) the simple Steadman
# average formula is used instead, per NWS guidance.
HEAT_INDEX_SIMPLE_THRESHOLD_C = 26.7

# -- Thermal stress 0-100 normalization ----------------------------------
# WBGT bounds used to rescale to a 0-100 index for the UI/action-engine.
# Below THERMAL_MIN_WBGT_C -> 0; at/above THERMAL_MAX_WBGT_C -> 100.
THERMAL_MIN_WBGT_C = 18.0
THERMAL_MAX_WBGT_C = 40.0

# Risk-level bands on the 0-100 thermal_stress score (aligned to the
# WBGT-based occupational heat-stress categories referenced in the
# Playbook: Low / Moderate / High / Extreme).
THERMAL_RISK_BANDS = (
    ("low", 0, 40),
    ("moderate", 40, 60),
    ("high", 60, 80),
    ("extreme", 80, 101),  # inclusive of 100
)
