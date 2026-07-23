"""CPCB National Air Quality Index methodology (spec 5.0). Owner: vayu-models.

Breakpoints are the official CPCB National AQI table (launched 2014, CPCB
"About AQI" / National AQI methodology), cross-checked against CPCB's own worked
example for PM2.5: sub-index = 51 at 31 ug/m3, 75 at 45, 100 at 60.

Sub-index formula (CPCB linear interpolation):

    Ip = (IHi - ILo) / (BPHi - BPLo) * (Cp - BPLo) + ILo

where BPLo/BPHi are the concentration breakpoints of the band containing Cp and
ILo/IHi the corresponding index endpoints. The overall AQI at a station is the
worst (max) sub-index, computed only when at least three pollutants are available
and at least one is a PM species (spec 5.0).

SEVERE-BAND CONVENTION (documented, /about-data + receipts honesty_notes):
CPCB defines the Severe band as an open interval ("250+" ug/m3 for PM2.5) with no
upper concentration. To render a continuous gradient across the Severe range while
respecting CPCB's 0-500 scale, VayuDrishti extends each pollutant's top band by
continuing the slope of the Very Poor band until the sub-index reaches 500, then
caps at 500. For PM2.5 this places index 500 at 380 ug/m3. This is a VayuDrishti
convention where CPCB is silent; raw pollutant concentration is always published
alongside the sub-index, so the 500 cap never hides true magnitude.
"""

from __future__ import annotations

import math

from vayu.constants import AQI_CATEGORIES

# (conc_lo, conc_hi, index_lo, index_hi). The final (Severe) band's conc_hi is the
# documented VayuDrishti slope-continuation extrapolation; concentrations above it
# saturate the sub-index at 500. Concentration units: ug/m3, except CO in mg/m3.
Band = tuple[float, float, float, float]

BREAKPOINTS: dict[str, list[Band]] = {
    # 24-hour averaging
    "pm25": [
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (250, 380, 401, 500),  # Severe: CPCB "250+"; 500 reached at 380 (documented)
    ],
    "pm10": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (430, 510, 401, 500),  # Severe: CPCB "430+"
    ],
    "no2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (400, 520, 401, 500),  # Severe: CPCB "400+"
    ],
    "so2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1600, 2400, 401, 500),  # Severe: CPCB "1600+"
    ],
    "nh3": [
        (0, 200, 0, 50),
        (201, 400, 51, 100),
        (401, 800, 101, 200),
        (801, 1200, 201, 300),
        (1200, 1800, 301, 400),
        (1800, 2400, 401, 500),  # Severe: CPCB "1800+"
    ],
    # 8-hour averaging
    "o3": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (748, 1287, 401, 500),  # Severe: CPCB "748+"
    ],
    "co": [  # mg/m3
        (0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10, 101, 200),
        (10, 17, 201, 300),
        (17, 34, 301, 400),
        (34, 51, 401, 500),  # Severe: CPCB "34+"
    ],
    "pb": [
        (0, 0.5, 0, 50),
        (0.5, 1.0, 51, 100),
        (1.1, 2.0, 101, 200),
        (2.1, 3.0, 201, 300),
        (3.1, 3.5, 301, 400),
        (3.5, 3.9, 401, 500),  # Severe: CPCB "3.5+"
    ],
}

# Pollutants that count as particulate matter for the "at least one PM" AQI rule.
PM_POLLUTANTS: tuple[str, ...] = ("pm25", "pm10")

# CPCB requires a minimum of 16 valid hourly values to form a 24-hour sub-index.
MIN_HOURS_24H = 16

# Headline metric label (spec 5.0). The grid/ward headline is always this.
HEADLINE_LABEL = "PM2.5 sub-index (24h)"

# Overall-AQI eligibility (spec 5.0): >= 3 pollutants incl. at least one PM species.
MIN_POLLUTANTS_FOR_AQI = 3

# Index category boundaries (upper-inclusive), aligned to AQI_CATEGORIES ordering.
_CATEGORY_UPPER_BOUNDS: tuple[tuple[float, str], ...] = (
    (50, AQI_CATEGORIES[0]),   # Good
    (100, AQI_CATEGORIES[1]),  # Satisfactory
    (200, AQI_CATEGORIES[2]),  # Moderate
    (300, AQI_CATEGORIES[3]),  # Poor
    (400, AQI_CATEGORIES[4]),  # Very Poor
)
_SEVERE = AQI_CATEGORIES[5]


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def sub_index(pollutant: str, conc: float | None) -> int | None:
    """CPCB sub-index for one pollutant concentration, rounded to nearest integer.

    Returns None for missing (None/NaN) or negative input. Selects the lowest band
    whose upper breakpoint is >= conc; concentrations that fall in the 1-unit gaps
    between CPCB bands clamp to the band floor; concentrations above the top band
    saturate the sub-index at 500.
    """
    if _is_missing(conc) or conc < 0:
        return None
    key = pollutant.lower()
    bands = BREAKPOINTS.get(key)
    if bands is None:
        raise KeyError(f"Unknown pollutant '{pollutant}'. Known: {sorted(BREAKPOINTS)}")
    for lo, hi, ilo, ihi in bands:
        if conc <= hi:
            frac = max(0.0, conc - lo) / (hi - lo)
            return round(ilo + frac * (ihi - ilo))
    return 500  # above the top breakpoint: saturate at the CPCB ceiling


def category_for_index(index_value: float | None) -> str | None:
    """CPCB category string for an AQI or sub-index value (from the constants module)."""
    if _is_missing(index_value) or index_value < 0:
        return None
    for upper, name in _CATEGORY_UPPER_BOUNDS:
        if index_value <= upper:
            return name
    return _SEVERE


def trailing_24h_mean(hourly_values: list[float | None]) -> float | None:
    """Mean of the trailing 24 hourly values, requiring >= 16 valid ones (CPCB).

    Takes the last 24 slots, drops missing (None/NaN), and returns None if fewer
    than MIN_HOURS_24H valid values remain.
    """
    window = hourly_values[-24:]
    valid = [v for v in window if not _is_missing(v)]
    if len(valid) < MIN_HOURS_24H:
        return None
    return sum(valid) / len(valid)


def headline_subindex(pm25_24h_mean: float | None) -> dict | None:
    """Grid/ward headline: PM2.5 sub-index on the trailing-24h mean (spec 5.0).

    Returns {"subindex24h", "category", "label"} or None when PM2.5 is unavailable.
    """
    si = sub_index("pm25", pm25_24h_mean)
    if si is None:
        return None
    return {
        "subindex24h": si,
        "category": category_for_index(si),
        "label": HEADLINE_LABEL,
    }


def full_aqi(concentrations: dict[str, float | None]) -> dict | None:
    """Overall multi-pollutant AQI at a station (spec 5.0).

    ``concentrations`` maps pollutant -> concentration already averaged over the
    CPCB averaging period for that pollutant (24h for PM/NO2/SO2/NH3/Pb, 8h for
    CO/O3). Returns None unless at least three pollutants yield a sub-index and at
    least one is a PM species. The overall AQI is the worst (max) sub-index.
    """
    subs: dict[str, int] = {}
    for pollutant, conc in concentrations.items():
        key = pollutant.lower()
        if key not in BREAKPOINTS:
            continue
        si = sub_index(key, conc)
        if si is not None:
            subs[key] = si
    if len(subs) < MIN_POLLUTANTS_FOR_AQI:
        return None
    if not any(pm in subs for pm in PM_POLLUTANTS):
        return None
    dominant = max(subs, key=lambda k: subs[k])
    aqi_value = subs[dominant]
    return {
        "aqi": aqi_value,
        "category": category_for_index(aqi_value),
        "dominant_pollutant": dominant,
        "sub_indices": subs,
    }


def breakpoint_table_rows() -> list[dict]:
    """Serializable CPCB breakpoint table for the /about-data page (spec 5.0).

    One row per (pollutant, category) with the concentration band. The Severe band's
    upper bound is the documented VayuDrishti slope-continuation extrapolation.
    """
    rows: list[dict] = []
    for pollutant, bands in BREAKPOINTS.items():
        unit = "mg/m3" if pollutant == "co" else "ug/m3"
        for (lo, hi, ilo, ihi), category in zip(bands, AQI_CATEGORIES, strict=False):
            rows.append(
                {
                    "pollutant": pollutant,
                    "unit": unit,
                    "category": category,
                    "conc_low": lo,
                    "conc_high": hi,
                    "index_low": ilo,
                    "index_high": ihi,
                    "extrapolated": category == _SEVERE,
                }
            )
    return rows


__all__ = [
    "BREAKPOINTS",
    "PM_POLLUTANTS",
    "MIN_HOURS_24H",
    "HEADLINE_LABEL",
    "sub_index",
    "category_for_index",
    "trailing_24h_mean",
    "headline_subindex",
    "full_aqi",
    "breakpoint_table_rows",
]
