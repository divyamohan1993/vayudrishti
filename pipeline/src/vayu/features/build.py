"""Feature-store builder (spec 5.1, 8). Joins real sources into hourly.parquet.

Grain: one row per (station_id, ts_utc). Sources: OpenAQ archive (pollutants),
Open-Meteo (meteo), FIRMS upwind (fires), OSM (land-use), GEE (satellite, NaN
until wired), plus baked ward_id. The column set exactly matches
config/schemas/feature-store.schema.json and never changes with key state.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from vayu import upwind
from vayu.cityconfig import CityConfig, load_city, resolve_cities
from vayu.geo import assign_points_to_wards, read_geojson
from vayu.ingest import firms, openmeteo
from vayu.ingest import openaq_archive as oaq
from vayu.ingest.openaq_discover import discover_locations, load_seed
from vayu.ingest.osm_static import build_station_landuse
from vayu.lineage import LineageLog
from vayu.logging_setup import get_logger
from vayu.settings import get_settings, repo_root

log = get_logger("features.build")

SATELLITE_COLS = ["s5p_no2", "s5p_so2", "s5p_co", "s5p_aai", "aod550"]


def feature_columns() -> list[str]:
    schema = json.loads(
        (repo_root() / "config" / "schemas" / "feature-store.schema.json").read_text("utf-8")
    )
    return [c["name"] for c in schema["columns"]]


def active_station_ids(slug: str) -> list[int]:
    """Discovered OpenAQ stations with PM2.5 that report into the backfill window."""
    seed = load_seed(slug)
    if not seed:
        cfg = load_city(slug)
        seed = discover_locations(cfg)
    active = [
        s["location_id"]
        for s in seed
        if "pm25" in (s.get("parameters") or []) and (s.get("last") or "") >= "2025-02"
    ]
    return sorted(active)


def add_meteo(base: pd.DataFrame, slug: str, start: str, end: str, lin: LineageLog) -> pd.DataFrame:
    cache = get_settings().raw_dir / slug / "meteo"
    coords = base.groupby("station_id")[["lat", "lon"]].first()
    frames = []
    for station_id, row in coords.iterrows():
        m = openmeteo.fetch_archive_cached(
            station_id, float(row["lat"]), float(row["lon"]), start, end, cache
        )
        m["station_id"] = station_id
        frames.append(m)
    meteo = pd.concat(frames, ignore_index=True)
    lin.add(
        source="open-meteo-archive",
        url=openmeteo.ARCHIVE_URL,
        resource_id="era5:hourly",
        rows=len(meteo),
    )
    return base.merge(meteo, on=["station_id", "ts_utc"], how="left")


def add_upwind(df: pd.DataFrame, fires: pd.DataFrame | None) -> pd.DataFrame:
    """frp_upwind + fire_count_upwind per station-hour (numpy, sector + trailing 24h)."""
    frp = np.zeros(len(df))
    cnt = np.zeros(len(df), dtype="int64")
    if fires is not None and not fires.empty:
        # Cast to float64: empty FIRMS chunks can upcast these columns to object.
        flat = fires["lat"].to_numpy(dtype=float)
        flon = fires["lon"].to_numpy(dtype=float)
        ffrp = pd.to_numeric(fires["frp"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        ft = pd.to_datetime(fires["acq_utc"], utc=True).to_numpy()  # datetime64[ns]
        window = np.timedelta64(upwind.DEFAULT_TRAILING_H, "h")
        pos = np.arange(len(df))
        for _sid, idx in df.groupby("station_id").groups.items():
            sub = df.loc[idx]
            slat = float(sub["lat"].iloc[0])
            slon = float(sub["lon"].iloc[0])
            dist = upwind.haversine_km_np(slat, slon, flat, flon)
            near = dist <= upwind.DEFAULT_MAX_KM
            if not near.any():
                continue
            nbear = upwind.bearing_deg_np(slat, slon, flat[near], flon[near])
            nfrp = ffrp[near]
            nt = ft[near]
            positions = pos[df.index.get_indexer(idx)]
            ts = sub["ts_utc"].to_numpy()
            wdir = sub["wind_dir_10m"].to_numpy(dtype=float)
            for j, (t, wd) in enumerate(zip(ts, wdir, strict=False)):
                if np.isnan(wd):
                    continue
                inwin = (nt > t - window) & (nt <= t)
                if not inwin.any():
                    continue
                sel = upwind.angular_diff_np(nbear[inwin], wd) <= upwind.DEFAULT_HALF_ANGLE_DEG
                if sel.any():
                    frp[positions[j]] = round(float(nfrp[inwin][sel].sum()), 4)
                    cnt[positions[j]] = int(sel.sum())
    out = df.copy()
    out["frp_upwind"] = frp
    out["fire_count_upwind"] = cnt
    return out


def add_landuse(df: pd.DataFrame, cfg: CityConfig, lin: LineageLog) -> pd.DataFrame:
    cache = get_settings().raw_dir / cfg.slug / "osm_landuse.parquet"
    stations = df.groupby("station_id")[["lat", "lon"]].first().reset_index()
    lu = build_station_landuse(stations, cfg.bbox_tuple, cfg.utm_epsg, cache)
    lin.add(
        source="osm-overpass",
        url="https://overpass-api.de/api/interpreter",
        resource_id="highway+building+landuse=industrial",
        rows=len(lu),
    )
    return df.merge(lu, on="station_id", how="left")


def add_satellite(df: pd.DataFrame, cfg: CityConfig, lin: LineageLog) -> pd.DataFrame:
    """Broadcast cached daily GEE satellite values across each UTC day's hours.

    Reads the satellite cache warmed by `vayu ingest --sources gee`. Columns are
    always present; they stay NaN (schema-stable) when the cache is empty. The GEE
    backfill is a separate step so the core parquet never waits on it.
    """
    from vayu.ingest.gee_extractor import load_satellite_daily

    daily = load_satellite_daily(get_settings().raw_dir / cfg.slug / "gee")
    df = df.drop(columns=[c for c in SATELLITE_COLS if c in df.columns], errors="ignore")
    if daily.empty:
        for c in SATELLITE_COLS:
            df[c] = np.nan
        return df
    daily = daily.copy()
    daily["station_id"] = daily["station_id"].astype(str)
    daily["date"] = daily["date"].astype(str)
    keep = ["station_id", "date", *[c for c in SATELLITE_COLS if c in daily.columns]]
    df["date"] = df["ts_utc"].dt.strftime("%Y-%m-%d")
    df = df.merge(daily[keep], on=["station_id", "date"], how="left").drop(columns="date")
    for c in SATELLITE_COLS:
        if c not in df.columns:
            df[c] = np.nan
    lin.add(
        source="gee",
        url="https://earthengine.googleapis.com",
        resource_id="S5P+MCD19A2",
        rows=len(daily),
    )
    return df


def add_ward_id(df: pd.DataFrame, cfg: CityConfig, lin: LineageLog) -> pd.DataFrame:
    wards_path = get_settings().resolved_web_data_dir / cfg.slug / "wards.geojson"
    wards = read_geojson(wards_path)
    coords = df.groupby("station_id")[["lat", "lon"]].first().reset_index()
    pts = gpd.GeoDataFrame(
        {"station_id": coords["station_id"]},
        geometry=[Point(x, y) for x, y in zip(coords["lon"], coords["lat"], strict=False)],
        crs="EPSG:4326",
    )
    coords["ward_id"] = assign_points_to_wards(pts, wards, cfg.slug).to_numpy()
    lin.add(
        source="datameet-wards",
        url=cfg.wards.url or "local",
        resource_id=f"{cfg.wards.source}:wards.geojson",
        rows=len(wards),
    )
    return df.merge(coords[["station_id", "ward_id"]], on="station_id", how="left")


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = feature_columns()
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[cols].copy()
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["station_id"] = df["station_id"].astype("string")
    df["ward_id"] = df["ward_id"].astype("string")
    df["fire_count_upwind"] = (
        pd.to_numeric(df["fire_count_upwind"], errors="coerce").fillna(0).astype("int64")
    )
    for c in cols:
        if c not in ("ts_utc", "station_id", "ward_id", "fire_count_upwind"):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df.sort_values(["station_id", "ts_utc"]).reset_index(drop=True)


def validate(df: pd.DataFrame) -> None:
    expected = feature_columns()
    if list(df.columns) != expected:
        raise ValueError(
            f"feature-store columns mismatch:\n got {list(df.columns)}\n exp {expected}"
        )
    if df["ts_utc"].dt.tz is None:
        raise ValueError("ts_utc must be tz-aware UTC")
    for c in SATELLITE_COLS:
        if c not in df.columns:
            raise ValueError(f"satellite column {c} must always be present")


def build_city(slug: str, fires: pd.DataFrame | None = None) -> Path:
    cfg = load_city(slug)
    settings = get_settings()
    lin = LineageLog()

    station_ids = active_station_ids(slug)
    if not station_ids:
        raise RuntimeError(f"No active OpenAQ stations for {slug} (need OPENAQ_API_KEY once).")
    months = oaq.month_range(oaq.ARCHIVE_START, oaq.default_end())
    log.info("features.start", city=slug, stations=len(station_ids), months=len(months))

    base = oaq.backfill_city(station_ids, months, settings.raw_dir / slug / "openaq")
    lin.add(
        source="openaq-s3-archive",
        url=oaq.BASE_URL,
        resource_id="records/csv.gz",
        rows=len(base),
    )
    if base.empty:
        raise RuntimeError(f"OpenAQ backfill returned no rows for {slug}")

    start = f"{oaq.ARCHIVE_START[0]}-{oaq.ARCHIVE_START[1]:02d}-01"
    end = openmeteo.default_end_date()
    df = add_meteo(base, slug, start, end, lin)

    if fires is None:
        fires = firms.fetch_city_fires(cfg, start, settings.raw_dir / slug / "firms")
        lin.add(
            source="nasa-firms",
            url=firms.ARCHIVE_URL,
            resource_id=f"VIIRS:{cfg.firms_country}",
            rows=len(fires),
        )
    df = add_upwind(df, fires)
    df = add_landuse(df, cfg, lin)
    df = add_satellite(df, cfg, lin)
    df = add_ward_id(df, cfg, lin)

    df = finalize(df)
    validate(df)

    out = settings.feature_store_dir / slug / "hourly.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    lin.write(settings.feature_store_dir / slug / "lineage.json")

    log.info(
        "features.done",
        city=slug,
        rows=len(df),
        stations=df["station_id"].nunique(),
        first=str(df["ts_utc"].min()),
        last=str(df["ts_utc"].max()),
        pm25_nonnull=int(df["pm25"].notna().sum()),
        out=str(out.relative_to(repo_root())),
    )
    return out


def build_features(city: str) -> int:
    for slug in resolve_cities(city):
        build_city(slug)
    return 0


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")
