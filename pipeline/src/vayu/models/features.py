"""Feature engineering: feature-store parquet -> model matrix (spec 5.1).

Consumes the frozen 27-column parquet (vayu-data, spec 8). Engineers wind vector,
satellite missing indicators, IST calendar encodings, and per-timestamp spatial context
(IDW of OTHER stations, nearest-station distance, station count). LightGBM handles NaN
natively, so satellite/fire columns pass through with an added missing indicator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vayu.models.baseline_idw import haversine_km, idw_leave_one_out

TARGET = "pm25"

# Raw meteo/satellite/land-use columns used directly (NaN-tolerant in LightGBM).
_METEO = ["wind_speed_10m", "temp_2m", "rh_2m", "precip_mm", "blh_m"]
_SAT = ["s5p_no2", "s5p_so2", "s5p_co", "s5p_aai", "aod550"]
_FIRE = ["frp_upwind", "fire_count_upwind"]
_LANDUSE = ["road_density", "builtup_frac", "industrial_dist_km"]
_SAT_MISSING = ["s5p_no2_isnan", "aod550_isnan"]
_WIND = ["wind_u", "wind_v"]
_CALENDAR = ["hour_sin", "hour_cos", "doy_sin", "doy_cos", "is_weekend"]
_SPATIAL = ["idw_pm25", "nearest_dist_km", "station_count"]

FEATURE_COLS = _WIND + _METEO + _SAT + _SAT_MISSING + _FIRE + _LANDUSE + _CALENDAR + _SPATIAL


def add_wind_vector(df: pd.DataFrame) -> pd.DataFrame:
    """u/v components from speed + meteorological direction (FROM, deg clockwise from N)."""
    rad = np.radians(df["wind_dir_10m"].to_numpy(dtype=float))
    spd = df["wind_speed_10m"].to_numpy(dtype=float)
    df = df.copy()
    df["wind_u"] = -spd * np.sin(rad)
    df["wind_v"] = -spd * np.cos(rad)
    return df


def add_missing_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["s5p_no2_isnan"] = df["s5p_no2"].isna().astype(int)
    df["aod550_isnan"] = df["aod550"].isna().astype(int)
    return df


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    """IST diurnal/seasonal encodings (spec 5.0: calendar from Asia/Kolkata)."""
    ts = pd.to_datetime(df["ts_utc"], utc=True)
    local = ts.dt.tz_convert("Asia/Kolkata")
    hour = local.dt.hour.to_numpy()
    doy = local.dt.dayofyear.to_numpy()
    dow = local.dt.dayofweek.to_numpy()
    df = df.copy()
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.0)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.0)
    df["is_weekend"] = (dow >= 5).astype(int)
    return df


def add_spatial_context(df: pd.DataFrame) -> pd.DataFrame:
    """Per-timestamp IDW-of-other-stations, nearest-station distance, station count.

    These give the fusion model its spatial signal while remaining computable at an
    arbitrary inference point (grid cell) from the same station field.
    """
    df = df.copy()
    idw = np.full(len(df), np.nan)
    nearest = np.full(len(df), np.nan)
    count = np.zeros(len(df), dtype=int)
    for _, grp in df.groupby("ts_utc", sort=False):
        idxs = grp.index.to_numpy()
        lat = grp["lat"].to_numpy(float)
        lon = grp["lon"].to_numpy(float)
        val = grp[TARGET].to_numpy(float)
        n = len(grp)
        idw[df.index.get_indexer(idxs)] = idw_leave_one_out(lat, lon, val)
        for k in range(n):
            others = np.arange(n) != k
            if others.any():
                d = haversine_km(lat[others], lon[others], lat[k], lon[k])
                nearest[df.index.get_indexer(idxs[k:k + 1])[0]] = float(np.min(d))
            count[df.index.get_indexer(idxs[k:k + 1])[0]] = n
    df["idw_pm25"] = idw
    df["nearest_dist_km"] = nearest
    df["station_count"] = count
    return df


def build_station_frame(parquet_df: pd.DataFrame) -> pd.DataFrame:
    """Full feature frame for station rows with an observed PM2.5 target.

    Returns a frame carrying FEATURE_COLS + TARGET + station_id/lat/lon/ts_utc.
    """
    df = parquet_df.copy()
    df = df.reset_index(drop=True)
    df = add_wind_vector(df)
    df = add_missing_indicators(df)
    df = add_calendar(df)
    df = add_spatial_context(df)
    df = df[df[TARGET].notna()].reset_index(drop=True)
    return df


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Select the model feature columns, adding any missing as NaN (robust to sparse feeds)."""
    out = pd.DataFrame(index=df.index)
    for col in FEATURE_COLS:
        out[col] = df[col] if col in df.columns else np.nan
    return out


__all__ = ["FEATURE_COLS", "TARGET", "build_station_frame", "feature_matrix",
           "add_wind_vector", "add_missing_indicators", "add_calendar", "add_spatial_context"]
