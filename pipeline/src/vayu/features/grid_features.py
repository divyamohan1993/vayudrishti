"""Grid-cell feature builder for nowcast inference (spec 5.1; vayu-models contract).

`build_grid_features(city, ts_utc)` returns one row per 0.01deg grid cell with the
cell-intrinsic features the nowcast model needs at inference time, using the same
definitions as the station feature store:

  cell_id, row, col, lat, lon,
  wind_speed_10m, wind_dir_10m, temp_2m, rh_2m, precip_mm, blh_m,   # Open-Meteo per cell
  s5p_no2, s5p_so2, s5p_co, s5p_aai, aod550,                        # satellite (NaN when off)
  frp_upwind, fire_count_upwind,                                    # FIRMS upwind at centroid
  road_density, builtup_frac, industrial_dist_km                   # land-use

vayu-models derives wind_u/v, the Asia/Kolkata calendar features, and the IDW /
nearest-distance / station-density features itself from the station parquet.

Cell meteo is real per-cell Open-Meteo (cached per city+date). Cell land-use and
satellite are assigned from the nearest station (documented approximation: full
per-cell OSM/GEE over thousands of cells is impractical at publish time, and both
fields vary slowly over ~1 km). Upwind is computed at each cell centroid.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from vayu import upwind
from vayu.cityconfig import load_city
from vayu.grid import cell_id, enumerate_cells, grid_meta
from vayu.ingest import firms, openmeteo
from vayu.ingest.gee_extractor import SAT_COLS, load_satellite_daily
from vayu.logging_setup import get_logger
from vayu.settings import get_settings
from vayu.timeutils import now_utc

log = get_logger("features.grid")

LANDUSE_COLS = ["road_density", "builtup_frac", "industrial_dist_km"]
GRID_COLS = [
    "cell_id", "row", "col", "lat", "lon",
    *openmeteo.METEO_COLS,
    *SAT_COLS,
    "frp_upwind", "fire_count_upwind",
    *LANDUSE_COLS,
]


def _station_frame(slug: str) -> pd.DataFrame:
    """station_id, lat, lon for the city's stations (from the feature-store parquet)."""
    path = get_settings().feature_store_dir / slug / "hourly.parquet"
    df = pd.read_parquet(path, columns=["station_id", "lat", "lon"])
    return df.groupby("station_id", as_index=False)[["lat", "lon"]].first()


def _nearest_station_idx(cell_lat, cell_lon, stat_lat, stat_lon) -> np.ndarray:
    """Index of the nearest station for each cell (great-circle)."""
    out = np.empty(len(cell_lat), dtype=int)
    for i in range(len(cell_lat)):
        d = upwind.haversine_km_np(float(cell_lat[i]), float(cell_lon[i]), stat_lat, stat_lon)
        out[i] = int(np.argmin(d))
    return out


COARSE_STEP_DEG = 0.05  # ~5 km meteo sampling; finer than Open-Meteo's native grid


def _coarse_points(bbox) -> tuple[np.ndarray, np.ndarray]:
    min_lon, min_lat, max_lon, max_lat = bbox
    lats = np.arange(min_lat, max_lat + COARSE_STEP_DEG, COARSE_STEP_DEG)
    lons = np.arange(min_lon, max_lon + COARSE_STEP_DEG, COARSE_STEP_DEG)
    grid_lat, grid_lon = np.meshgrid(lats, lons)
    return grid_lat.ravel(), grid_lon.ravel()


def _grid_meteo(df: pd.DataFrame, slug: str, ts_utc: datetime, bbox) -> pd.DataFrame:
    """Per-cell Open-Meteo at ts, sampled on a ~5km coarse grid (cached per city+date)
    and nearest-assigned to cells. Meteo varies slowly, and Open-Meteo's native
    resolution is coarser than 1km, so this loses no signal while cutting API calls."""
    ts = pd.Timestamp(ts_utc).tz_convert("UTC") if ts_utc.tzinfo else pd.Timestamp(ts_utc, tz="UTC")
    date = ts.strftime("%Y-%m-%d")
    cache = get_settings().raw_dir / slug / "grid_meteo" / f"{date}.parquet"
    clat, clon = _coarse_points(bbox)
    if cache.exists():
        day = pd.read_parquet(cache)
    else:
        recent = (now_utc().date() - ts.date()).days <= 6
        past_days = min(7, max(1, (now_utc().date() - ts.date()).days + 1))
        frames = (
            openmeteo.fetch_forecast_multi(clat.tolist(), clon.tolist(), past_days=past_days)
            if recent
            else openmeteo.fetch_archive_multi(clat.tolist(), clon.tolist(), date, date)
        )
        parts = []
        for i, frame in enumerate(frames):
            frame = frame.copy()
            frame["pt"] = i
            parts.append(frame)
        day = pd.concat(parts, ignore_index=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        day.to_parquet(cache, index=False)

    hour = day[day["ts_utc"] == ts].set_index("pt").sort_index()
    nearest = _nearest_station_idx(df["lat"].to_numpy(), df["lon"].to_numpy(), clat, clon)
    hour = hour.reindex(range(len(clat)))
    for c in openmeteo.METEO_COLS:
        df[c] = hour[c].to_numpy()[nearest] if c in hour.columns else np.nan
    return df


def _add_nearest_landuse(df: pd.DataFrame, slug: str, nearest: np.ndarray, stations: pd.DataFrame):
    cache = get_settings().raw_dir / slug / "osm_landuse.parquet"
    if not cache.exists():
        for c in LANDUSE_COLS:
            df[c] = np.nan
        return df
    lu = pd.read_parquet(cache).set_index("station_id")
    lu = lu.reindex(stations["station_id"].astype(str).values)
    for c in LANDUSE_COLS:
        df[c] = lu[c].to_numpy()[nearest] if c in lu.columns else np.nan
    return df


def _add_nearest_satellite(df, slug, ts_utc, nearest, stations):
    daily = load_satellite_daily(get_settings().raw_dir / slug / "gee")
    date = pd.Timestamp(ts_utc).strftime("%Y-%m-%d")
    for c in SAT_COLS:
        df[c] = np.nan
    if daily.empty:
        return df
    day = daily[daily["date"].astype(str) == date].set_index("station_id")
    day = day.reindex(stations["station_id"].astype(str).values)
    for c in SAT_COLS:
        if c in day.columns:
            df[c] = day[c].to_numpy()[nearest]
    return df


def _add_grid_upwind(df: pd.DataFrame, fires: pd.DataFrame, ts_utc: datetime) -> pd.DataFrame:
    df["frp_upwind"] = 0.0
    df["fire_count_upwind"] = 0
    if fires is None or fires.empty:
        return df
    ts = np.datetime64(pd.Timestamp(ts_utc).tz_localize(None) if pd.Timestamp(ts_utc).tz
                       else pd.Timestamp(ts_utc))
    ft = pd.to_datetime(fires["acq_utc"], utc=True).dt.tz_localize(None).to_numpy()
    win = (ft > ts - np.timedelta64(upwind.DEFAULT_TRAILING_H, "h")) & (ft <= ts)
    if not win.any():
        return df
    flat = fires["lat"].to_numpy(dtype=float)[win]
    flon = fires["lon"].to_numpy(dtype=float)[win]
    ffrp = pd.to_numeric(fires["frp"], errors="coerce").fillna(0.0).to_numpy()[win]
    frp = np.zeros(len(df))
    cnt = np.zeros(len(df), dtype="int64")
    clat = df["lat"].to_numpy()
    clon = df["lon"].to_numpy()
    wdir = df["wind_dir_10m"].to_numpy(dtype=float)
    for i in range(len(df)):
        if np.isnan(wdir[i]):
            continue
        dist = upwind.haversine_km_np(float(clat[i]), float(clon[i]), flat, flon)
        near = dist <= upwind.DEFAULT_MAX_KM
        if not near.any():
            continue
        bearing = upwind.bearing_deg_np(float(clat[i]), float(clon[i]), flat[near], flon[near])
        sel = upwind.angular_diff_np(bearing, wdir[i]) <= upwind.DEFAULT_HALF_ANGLE_DEG
        if sel.any():
            frp[i] = round(float(ffrp[near][sel].sum()), 4)
            cnt[i] = int(sel.sum())
    df["frp_upwind"] = frp
    df["fire_count_upwind"] = cnt
    return df


def build_grid_features(
    city_slug: str, ts_utc: datetime, fires: pd.DataFrame | None = None
) -> pd.DataFrame:
    """One row per grid cell of nowcast-inference features at ``ts_utc`` (UTC)."""
    cfg = load_city(city_slug)
    meta = grid_meta(cfg.bbox_tuple)
    cells = enumerate_cells(cfg.bbox_tuple)
    df = pd.DataFrame(cells, columns=["row", "col", "lat", "lon"])
    df["cell_id"] = [
        cell_id(city_slug, int(r), int(c))
        for r, c in zip(df["row"], df["col"], strict=False)
    ]

    df = _grid_meteo(df, city_slug, ts_utc, cfg.bbox_tuple)

    stations = _station_frame(city_slug)
    nearest = _nearest_station_idx(
        df["lat"].to_numpy(), df["lon"].to_numpy(),
        stations["lat"].to_numpy(), stations["lon"].to_numpy(),
    )
    df = _add_nearest_landuse(df, city_slug, nearest, stations)
    df = _add_nearest_satellite(df, city_slug, ts_utc, nearest, stations)

    if fires is None:
        fires = firms.fetch_city_fires(cfg, None, get_settings().raw_dir / city_slug / "firms")
    df = _add_grid_upwind(df, fires, ts_utc)

    log.info(
        "grid.features",
        city=city_slug,
        ts=str(ts_utc),
        cells=len(df),
        rows_cols=f"{meta.n_rows}x{meta.n_cols}",
        meteo_nn=int(df["wind_speed_10m"].notna().sum()),
    )
    return df[GRID_COLS]
