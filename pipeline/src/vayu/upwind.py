"""Upwind FIRMS sector (spec 5.0, FROZEN). Owner: vayu-data.

Apex = a station or ward centroid. A fire counts as *upwind* when the great-circle
bearing from the apex to the fire lies within +/- 45 deg of ``wind_dir_10m`` and the
fire is within 100 km. Open-Meteo reports ``wind_dir_10m`` as the direction the wind
blows *from* (degrees clockwise from north), which is exactly the upwind bearing.

``frp_upwind`` = sum of FRP over qualifying fires in the trailing 24 h.
``fire_count_upwind`` = number of qualifying fires.

Bearings and distances are great-circle here. Land-use buffers are computed in a
projected CRS elsewhere (spec 5.0); the two are never mixed.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

EARTH_RADIUS_KM = 6371.0088
DEFAULT_MAX_KM = 100.0
DEFAULT_HALF_ANGLE_DEG = 45.0
DEFAULT_TRAILING_H = 24


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing apex(1) -> fire(2), degrees clockwise from N."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_diff_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, in [0, 180]."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def is_upwind(
    apex_lat: float,
    apex_lon: float,
    fire_lat: float,
    fire_lon: float,
    wind_dir_deg: float,
    *,
    max_km: float = DEFAULT_MAX_KM,
    half_angle_deg: float = DEFAULT_HALF_ANGLE_DEG,
) -> bool:
    """True if the fire is within range and inside the upwind sector."""
    if haversine_km(apex_lat, apex_lon, fire_lat, fire_lon) > max_km:
        return False
    bearing = initial_bearing_deg(apex_lat, apex_lon, fire_lat, fire_lon)
    return angular_diff_deg(bearing, wind_dir_deg) <= half_angle_deg


def upwind_aggregate(
    apex_lat: float,
    apex_lon: float,
    wind_dir_deg: float,
    fires: list[dict],
    now_utc: datetime,
    *,
    trailing_h: int = DEFAULT_TRAILING_H,
    max_km: float = DEFAULT_MAX_KM,
    half_angle_deg: float = DEFAULT_HALF_ANGLE_DEG,
) -> tuple[float, int]:
    """(frp_upwind, fire_count_upwind) for an apex at a given hour.

    ``fires`` is a list of dicts with ``lat``, ``lon``, ``frp`` and ``acq_utc``
    (tz-aware datetime). Fires outside the trailing window, beyond ``max_km``, or
    outside the +/- ``half_angle_deg`` sector are excluded.
    """
    window_start = now_utc - timedelta(hours=trailing_h)
    frp_sum = 0.0
    count = 0
    for fire in fires:
        acq = fire["acq_utc"]
        if acq <= window_start or acq > now_utc:
            continue
        if not is_upwind(
            apex_lat,
            apex_lon,
            fire["lat"],
            fire["lon"],
            wind_dir_deg,
            max_km=max_km,
            half_angle_deg=half_angle_deg,
        ):
            continue
        frp_sum += float(fire.get("frp") or 0.0)
        count += 1
    return (round(frp_sum, 4), count)
