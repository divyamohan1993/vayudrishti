"""Inverse-distance-weighting spatial baseline (spec 5.1).

IDW is the honesty yardstick: the nowcast must beat it at every distance bucket <= 5km
(acceptance 3). Distances are great-circle km (station geometry is sparse; the projected
-CRS rule in spec 5.0 governs buffers/land-use, not this point-to-point weight).
"""

from __future__ import annotations

import numpy as np

EARTH_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.asarray, (lat1, lon1, lat2, lon2))
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return EARTH_KM * 2 * np.arcsin(np.sqrt(a))


def idw_predict(
    src_lat: np.ndarray, src_lon: np.ndarray, src_val: np.ndarray,
    dst_lat: np.ndarray, dst_lon: np.ndarray, *, power: float = 2.0, eps_km: float = 0.05,
) -> np.ndarray:
    """IDW estimate at each destination point from source (station) observations.

    A source coincident with a destination (< eps_km) returns that source's value.
    """
    src_lat = np.asarray(src_lat, float)
    src_lon = np.asarray(src_lon, float)
    src_val = np.asarray(src_val, float)
    dst_lat = np.asarray(dst_lat, float)
    dst_lon = np.asarray(dst_lon, float)
    out = np.full(dst_lat.shape, np.nan)
    valid = ~np.isnan(src_val)
    if not valid.any():
        return out
    slat, slon, sval = src_lat[valid], src_lon[valid], src_val[valid]
    for i in range(dst_lat.size):
        d = haversine_km(slat, slon, dst_lat[i], dst_lon[i])
        hit = np.where(d < eps_km)[0]
        if hit.size:
            out[i] = sval[hit[0]]
            continue
        w = 1.0 / np.power(d, power)
        out[i] = float(np.sum(w * sval) / np.sum(w))
    return out


def great_circle_matrix(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Pairwise great-circle distance matrix (km) for a set of points."""
    lat = np.radians(np.asarray(lat, float))
    lon = np.radians(np.asarray(lon, float))
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat)[:, None] * np.cos(lat)[None, :] * np.sin(dlon / 2) ** 2
    return EARTH_KM * 2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def idw_leave_one_out(lat: np.ndarray, lon: np.ndarray, val: np.ndarray, **kw) -> np.ndarray:
    """IDW prediction at each station from all OTHER stations (leave-self-out)."""
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    val = np.asarray(val, float)
    out = np.full(lat.shape, np.nan)
    idx = np.arange(lat.size)
    for i in idx:
        others = idx != i
        out[i] = idw_predict(lat[others], lon[others], val[others], lat[i:i + 1], lon[i:i + 1], **kw)[0]
    return out


__all__ = ["haversine_km", "idw_predict", "idw_leave_one_out"]
