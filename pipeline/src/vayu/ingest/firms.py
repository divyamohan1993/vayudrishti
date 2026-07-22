"""NASA FIRMS active-fire ingest (spec 3, 5.0). VIIRS 375 m + FRP.

The live country CSV only reaches back ~7 days, so for the Feb-2025 -> now backfill
we use the FIRMS *area archive* API (free MAP_KEY), chunked to <=10 days/request.
Older dates use standard-processing (SP), the recent ~2 months use NRT. The bbox is
expanded ~1 deg so fires up to 100 km upwind of the city are captured. Times are UTC.
Missing MAP_KEY degrades gracefully to an empty frame (frp_upwind then 0).
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests

from vayu.cityconfig import CityConfig
from vayu.logging_setup import get_logger
from vayu.settings import get_settings
from vayu.timeutils import now_utc

log = get_logger("ingest.firms")

ARCHIVE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
AVAILABILITY_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv"
MAX_DAY_RANGE = 5  # FIRMS area API caps day_range at 5
BBOX_PAD_DEG = 1.0  # ~100 km, so upwind fires beyond the city bbox are captured
COLUMNS = ["lat", "lon", "frp", "acq_utc"]
SP_FALLBACK_CUTOFF = date(2026, 4, 27)


@lru_cache(maxsize=1)
def _sp_cutoff(key: str) -> date:
    """Last date covered by standard-processing (SP); newer dates need NRT."""
    try:
        resp = requests.get(f"{AVAILABILITY_URL}/{key}/all", timeout=60)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            if line.startswith("VIIRS_SNPP_SP,"):
                return date.fromisoformat(line.split(",")[2])
    except (requests.RequestException, ValueError, IndexError):
        pass
    return SP_FALLBACK_CUTOFF


def _source_for(d: date, sp_cutoff: date) -> str:
    return "VIIRS_SNPP_SP" if d <= sp_cutoff else "VIIRS_SNPP_NRT"


def _parse(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip() or csv_text.lstrip().startswith("No fire"):
        return pd.DataFrame(columns=COLUMNS)
    raw = pd.read_csv(io.StringIO(csv_text))
    if raw.empty or "latitude" not in raw.columns:
        return pd.DataFrame(columns=COLUMNS)
    t = raw["acq_time"].astype(int).astype(str).str.zfill(4)
    dt = pd.to_datetime(
        raw["acq_date"].astype(str) + t, format="%Y-%m-%d%H%M", utc=True, errors="coerce"
    )
    out = pd.DataFrame(
        {
            "lat": pd.to_numeric(raw["latitude"], errors="coerce"),
            "lon": pd.to_numeric(raw["longitude"], errors="coerce"),
            "frp": pd.to_numeric(raw.get("frp"), errors="coerce"),
            "acq_utc": dt,
        }
    )
    return out.dropna(subset=["lat", "lon", "acq_utc"]).reset_index(drop=True)


def _fetch_chunk(key: str, source: str, area: str, day_range: int, start_str: str) -> pd.DataFrame:
    url = f"{ARCHIVE_URL}/{key}/{source}/{area}/{day_range}/{start_str}"
    resp = requests.get(url, timeout=90, headers={"User-Agent": "vayu"})
    resp.raise_for_status()
    return _parse(resp.text)


def fetch_city_fires(cfg: CityConfig, start: str | None, cache_dir: Path) -> pd.DataFrame:
    key = get_settings().firms_map_key
    if not key:
        log.warning("firms.no_key", city=cfg.slug)
        return pd.DataFrame(columns=COLUMNS)

    min_lon, min_lat, max_lon, max_lat = cfg.bbox_tuple
    area = (
        f"{min_lon - BBOX_PAD_DEG},{min_lat - BBOX_PAD_DEG},"
        f"{max_lon + BBOX_PAD_DEG},{max_lat + BBOX_PAD_DEG}"
    )
    start_date = (
        datetime.fromisoformat(start).date() if start else date(2025, 2, 1)
    )
    end_date = now_utc().date()

    cache_dir.mkdir(parents=True, exist_ok=True)
    sp_cutoff = _sp_cutoff(key)
    frames: list[pd.DataFrame] = []
    cur = start_date
    while cur <= end_date:
        span = min(MAX_DAY_RANGE, (end_date - cur).days + 1)
        source = _source_for(cur, sp_cutoff)
        cache = cache_dir / f"{source}_{cur.isoformat()}_{span}.parquet"
        if cache.exists():
            frames.append(pd.read_parquet(cache))
        else:
            try:
                df = _fetch_chunk(key, source, area, span, cur.isoformat())
            except requests.RequestException as exc:
                log.warning("firms.chunk_error", start=cur.isoformat(), error=type(exc).__name__)
                df = pd.DataFrame(columns=COLUMNS)
            # Cache only finalized (older) windows; the trailing window stays live.
            if (end_date - cur).days >= MAX_DAY_RANGE:
                df.to_parquet(cache, index=False)
            frames.append(df)
        cur += timedelta(days=span)

    fires = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    fires = fires.dropna(subset=["lat", "lon", "acq_utc"]).drop_duplicates().reset_index(drop=True)
    log.info(
        "firms.done",
        city=cfg.slug,
        fires=len(fires),
        first=str(fires["acq_utc"].min()) if len(fires) else None,
        last=str(fires["acq_utc"].max()) if len(fires) else None,
    )
    return fires
