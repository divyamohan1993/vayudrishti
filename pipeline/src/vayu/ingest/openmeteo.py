"""Open-Meteo ingest (spec 3). Zero-auth ERA5 archive + forecast.

One hourly call per point (station or grid cell). Times are requested in UTC and
parsed to tz-aware UTC so they join directly to the OpenAQ hourly table. Archive
responses are cached per station and reused unless stale (ERA5 finalizes with a
few days' lag, so the last ~2 days are refetched).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from vayu.logging_setup import get_logger
from vayu.timeutils import now_utc

log = get_logger("ingest.openmeteo")

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "boundary_layer_height",
]
RENAME = {
    "wind_direction_10m": "wind_dir_10m",
    "temperature_2m": "temp_2m",
    "relative_humidity_2m": "rh_2m",
    "precipitation": "precip_mm",
    "boundary_layer_height": "blh_m",
}
METEO_COLS = ["wind_speed_10m", "wind_dir_10m", "temp_2m", "rh_2m", "precip_mm", "blh_m"]


def _parse_hourly(payload: dict) -> pd.DataFrame:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    df = pd.DataFrame({"ts_utc": pd.to_datetime(times).tz_localize("UTC")})
    for var in HOURLY_VARS:
        df[var] = hourly.get(var)
    df = df.rename(columns=RENAME)
    return df[["ts_utc", *METEO_COLS]]


def fetch_archive(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    resp = requests.get(ARCHIVE_URL, params=params, timeout=90, headers={"User-Agent": "vayu"})
    resp.raise_for_status()
    return _parse_hourly(resp.json())


def fetch_forecast(
    lat: float, lon: float, *, forecast_days: int = 4, past_days: int = 3
) -> pd.DataFrame:
    """Forecast + recent-past hourly meteo (for nowcast last-mile and forecast)."""
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "forecast_days": forecast_days,
        "past_days": past_days,
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=60, headers={"User-Agent": "vayu"})
    resp.raise_for_status()
    return _parse_hourly(resp.json())


def fetch_archive_cached(
    station_id: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    cache_dir: Path,
) -> pd.DataFrame:
    cache = cache_dir / f"meteo_{station_id}.parquet"
    if cache.exists():
        cached = pd.read_parquet(cache)
        if not cached.empty:
            fresh_to = cached["ts_utc"].max()
            need_to = pd.Timestamp(end_date, tz="UTC")
            if fresh_to >= need_to - pd.Timedelta(days=2):
                return cached
    df = fetch_archive(lat, lon, start_date, end_date)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


def default_end_date() -> str:
    # ERA5 archive lags a few days; ask up to yesterday, gaps arrive as NaN.
    return (now_utc() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
