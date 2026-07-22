"""Google Earth Engine satellite extractor (spec 3, 5.1). Service-account, headless.

Numeric satellite features per station point (grid cells later), daily cadence
broadcast to hours by the feature builder:
- Sentinel-5P TROPOMI: NO2, SO2, CO, aerosol index (OFFL L3).
- MODIS MAIAC AOD 550 nm (MCD19A2 granules).

The service account is live (GEE_SERVICE_ACCOUNT_JSON_PATH + GEE_PROJECT). If the
key is absent or EE init fails, this degrades gracefully: satellite parquet
columns stay present but NaN, and manifest.sat_numeric is false. Never blocks.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from vayu.cityconfig import CityConfig
from vayu.logging_setup import get_logger
from vayu.settings import get_settings, repo_root
from vayu.timeutils import now_utc

log = get_logger("ingest.gee")

LINEAGE_URL = "https://earthengine.googleapis.com"

# (collection id, band, output column, scale factor)
S5P_PRODUCTS = [
    ("COPERNICUS/S5P/OFFL/L3_NO2", "tropospheric_NO2_column_number_density", "s5p_no2", 1.0),
    ("COPERNICUS/S5P/OFFL/L3_SO2", "SO2_column_number_density", "s5p_so2", 1.0),
    ("COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density", "s5p_co", 1.0),
    ("COPERNICUS/S5P/OFFL/L3_AER_AI", "absorbing_aerosol_index", "s5p_aai", 1.0),
]
MODIS_AOD = ("MODIS/061/MCD19A2_GRANULES", "Optical_Depth_055", "aod550", 0.001)
SAT_COLS = ["s5p_no2", "s5p_so2", "s5p_co", "s5p_aai", "aod550"]


def _resolve_key_path(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else repo_root() / raw


@lru_cache(maxsize=1)
def init_ee() -> bool:
    """Initialize EE with the service account. Returns False (logged) on any failure."""
    settings = get_settings()
    try:
        import ee  # lazy: keep EE optional at import time
    except Exception as exc:  # noqa: BLE001
        log.warning("gee.import_failed", error=str(exc)[:120])
        return False
    try:
        if settings.gee_service_account_json_path:
            key_file = _resolve_key_path(settings.gee_service_account_json_path)
            if not key_file.exists():
                log.warning("gee.key_missing", path=str(key_file.name))
                return False
            data = json.loads(key_file.read_text(encoding="utf-8"))
            email = settings.gee_service_account_email or data["client_email"]
            creds = ee.ServiceAccountCredentials(email, key_file=str(key_file))
        elif settings.gee_service_account_json:
            raw = settings.gee_service_account_json
            try:
                raw = base64.b64decode(raw).decode("utf-8")
            except Exception:  # noqa: BLE001 - already raw JSON
                pass
            data = json.loads(raw)
            email = settings.gee_service_account_email or data["client_email"]
            creds = ee.ServiceAccountCredentials(email, key_data=raw)
        else:
            log.warning("gee.no_credentials")
            return False
        ee.Initialize(creds, project=settings.gee_project)
        log.info("gee.init_ok", project=settings.gee_project)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("gee.init_failed", error=str(exc)[:160])
        return False


def _point_series(ee_mod, coll_id, band, scale_factor, point, start, end):
    """Daily band values at a point as {date: value}."""
    coll = (
        ee_mod.ImageCollection(coll_id)
        .select(band)
        .filterDate(start, end)
        .filterBounds(point)
    )
    region = coll.getRegion(point, 1113).getInfo()
    if not region or len(region) < 2:
        return {}
    header = region[0]
    ti, vi = header.index("time"), header.index(band)
    out: dict[str, float] = {}
    for row in region[1:]:
        val = row[vi]
        if val is None:
            continue
        day = pd.to_datetime(row[ti], unit="ms", utc=True).strftime("%Y-%m-%d")
        out.setdefault(day, []).append(val * scale_factor)  # type: ignore[arg-type]
    return {d: sum(v) / len(v) for d, v in out.items()}


def backfill_satellite(
    cfg: CityConfig, stations: pd.DataFrame, start: str | None, cache_dir: Path
) -> int:
    """Per-city daily satellite parquet [date, station_id, <SAT_COLS>]. 0 if EE off."""
    if not init_ee():
        log.warning("gee.skip", city=cfg.slug, reason="ee_unavailable")
        return 0
    import ee

    start = start or "2025-02-01"
    end = now_utc().strftime("%Y-%m-%d")
    cache = cache_dir / "satellite_daily.parquet"
    cache_dir.mkdir(parents=True, exist_ok=True)
    done = set()
    if cache.exists():
        prev = pd.read_parquet(cache)
        done = set(prev["station_id"].astype(str))
    else:
        prev = pd.DataFrame(columns=["date", "station_id", *SAT_COLS])

    rows: list[dict] = []
    for r in stations.itertuples(index=False):
        sid = str(r.station_id)
        if sid in done:
            continue
        point = ee.Geometry.Point([float(r.lon), float(r.lat)])
        per_day: dict[str, dict] = {}
        for coll_id, band, col, sf in [*S5P_PRODUCTS, MODIS_AOD]:
            try:
                series = _point_series(ee, coll_id, band, sf, point, start, end)
            except Exception as exc:  # noqa: BLE001
                log.warning("gee.series_error", station=sid, product=col, error=str(exc)[:100])
                series = {}
            for day, val in series.items():
                per_day.setdefault(day, {})[col] = val
        for day, vals in per_day.items():
            rows.append({"date": day, "station_id": sid, **vals})
        log.info("gee.station_done", city=cfg.slug, station=sid, days=len(per_day))

    if not rows:
        return int(len(prev))
    out = pd.concat([prev, pd.DataFrame(rows)], ignore_index=True)
    for c in SAT_COLS:
        if c not in out.columns:
            out[c] = pd.NA
    out.to_parquet(cache, index=False)
    log.info("gee.done", city=cfg.slug, rows=len(out), new_rows=len(rows))
    return len(out)


def load_satellite_daily(cache_dir: Path) -> pd.DataFrame:
    cache = cache_dir / "satellite_daily.parquet"
    if not cache.exists():
        return pd.DataFrame(columns=["date", "station_id", *SAT_COLS])
    return pd.read_parquet(cache)


WORLDPOP_COLLECTION = "WorldPop/GP/100m/pop"


def ward_population(wards_geojson: dict, year: int = 2020) -> dict[str, float]:
    """Sum WorldPop 100m population per ward polygon via GEE. {} if EE off.

    Returns {ward_id: population}. Vintage = ``year`` (documented on /about-data).
    """
    if not init_ee():
        log.warning("gee.worldpop_skip", reason="ee_unavailable")
        return {}
    import ee

    try:
        pop = (
            ee.ImageCollection(WORLDPOP_COLLECTION)
            .filter(ee.Filter.eq("year", year))
            .filter(ee.Filter.eq("country", "IND"))
            .mosaic()
        )
        feats = [
            ee.Feature(ee.Geometry(f["geometry"]), {"ward_id": f["properties"]["ward_id"]})
            for f in wards_geojson["features"]
        ]
        fc = ee.FeatureCollection(feats)
        reduced = pop.reduceRegions(
            collection=fc, reducer=ee.Reducer.sum(), scale=100
        ).getInfo()
        out: dict[str, float] = {}
        for f in reduced["features"]:
            props = f["properties"]
            val = props.get("sum")
            if val is not None:
                out[props["ward_id"]] = round(float(val), 1)
        log.info("gee.worldpop_done", wards=len(out), year=year)
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("gee.worldpop_error", error=str(exc)[:160])
        return {}
