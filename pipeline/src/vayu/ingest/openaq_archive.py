"""OpenAQ S3 archive backfill (spec 3). Anonymous, unsigned S3 access.

Downloads real CPCB hourly history (Feb-2025 -> now) for a city's discovered
stations, resamples the sub-hourly raw records to hourly UTC means, and caches
one parquet per (station, month) so reruns are incremental: finished months are
read from disk, only the current/live month is refetched.

Resampling happens AFTER UTC conversion and is floor-labeled to the hour, so it
aligns with Open-Meteo's UTC hourly stamps (e.g. 03:45:00+05:30 -> 22:00Z).
"""

from __future__ import annotations

import gzip
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
from botocore import UNSIGNED
from botocore.client import Config

from vayu.logging_setup import get_logger
from vayu.timeutils import now_utc

log = get_logger("ingest.openaq_archive")

BUCKET = "openaq-data-archive"
BASE_URL = f"https://{BUCKET}.s3.amazonaws.com/"
POLLUTANTS = ["pm25", "pm10", "no2", "so2", "o3", "co"]
ARCHIVE_START = (2025, 2)  # spec backfill window start


def _client():
    # UNSIGNED = anonymous (the --no-sign-request equivalent). Thread-safe.
    return boto3.client(
        "s3", config=Config(signature_version=UNSIGNED, max_pool_connections=64)
    )


def month_range(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    (sy, sm), (ey, em) = start, end
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _list_month_keys(client, location_id: int, year: int, month: int) -> list[str]:
    prefix = f"records/csv.gz/locationid={location_id}/year={year}/month={month:02d}/"
    keys: list[str] = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def _fetch_csv(client, key: str) -> pd.DataFrame:
    body = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    text = gzip.decompress(body)
    return pd.read_csv(io.BytesIO(text))


def _to_hourly(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw[raw["parameter"].isin(POLLUTANTS)].copy()
    if raw.empty:
        return pd.DataFrame(columns=["ts_utc", "station_id", "lat", "lon", *POLLUTANTS])
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw.loc[raw["value"] < 0, "value"] = pd.NA  # CPCB invalid-data sentinel
    raw["ts_utc"] = pd.to_datetime(raw["datetime"], utc=True).dt.floor("h")
    grouped = (
        raw.groupby(["location_id", "ts_utc", "parameter"], observed=True)["value"]
        .mean()
        .reset_index()
    )
    wide = grouped.pivot_table(
        index=["location_id", "ts_utc"], columns="parameter", values="value"
    ).reset_index()
    coords = raw.groupby("location_id")[["lat", "lon"]].first().reset_index()
    wide = wide.merge(coords, on="location_id")
    wide = wide.rename(columns={"location_id": "station_id"})
    wide["station_id"] = wide["station_id"].astype(str)
    for p in POLLUTANTS:
        if p not in wide.columns:
            wide[p] = pd.NA
    return wide[["ts_utc", "station_id", "lat", "lon", *POLLUTANTS]]


def _is_current_month(year: int, month: int) -> bool:
    now = now_utc()
    return (year, month) == (now.year, now.month)


def backfill_station_month(
    client, location_id: int, year: int, month: int, cache_dir: Path
) -> pd.DataFrame | None:
    cache = cache_dir / f"loc{location_id}_{year}{month:02d}.parquet"
    if cache.exists() and not _is_current_month(year, month):
        return pd.read_parquet(cache)
    keys = _list_month_keys(client, location_id, year, month)
    if not keys:
        return None
    dfs = [_fetch_csv(client, k) for k in keys]
    if not dfs:
        return None
    hourly = _to_hourly(pd.concat(dfs, ignore_index=True))
    if not _is_current_month(year, month):  # keep the live month refetchable
        cache.parent.mkdir(parents=True, exist_ok=True)
        hourly.to_parquet(cache, index=False)
    return hourly


def backfill_city(
    location_ids: list[int],
    months: list[tuple[int, int]],
    cache_dir: Path,
    *,
    max_workers: int = 24,
) -> pd.DataFrame:
    """Backfill all stations x months into an hourly DataFrame (cached per part).

    Station-months run concurrently on a shared thread-safe (UNSIGNED) client; each
    worker lists its month then fetches that month's day-files. Cached months are
    read from disk, so reruns skip finished work.
    """
    client = _client()
    cache_dir.mkdir(parents=True, exist_ok=True)
    tasks = [(loc, y, m) for loc in location_ids for (y, m) in months]

    def _work(task: tuple[int, int, int]) -> pd.DataFrame | None:
        loc, year, month = task
        try:
            return backfill_station_month(client, loc, year, month, cache_dir)
        except Exception as exc:  # noqa: BLE001 - one bad month must not kill the backfill
            log.warning(
                "openaq_archive.month_error",
                loc=loc,
                ym=f"{year}-{month:02d}",
                error=type(exc).__name__,
            )
            return None

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for df in pool.map(_work, tasks):
            if df is not None and not df.empty:
                frames.append(df)
    if not frames:
        log.warning("openaq_archive.empty", locations=len(location_ids), months=len(months))
        return pd.DataFrame(columns=["ts_utc", "station_id", "lat", "lon", *POLLUTANTS])
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["station_id", "ts_utc"]).reset_index(drop=True)
    log.info(
        "openaq_archive.done",
        locations=len(location_ids),
        station_months=len(frames),
        rows=len(out),
        first=str(out["ts_utc"].min()),
        last=str(out["ts_utc"].max()),
    )
    return out


def default_end() -> tuple[int, int]:
    now = now_utc()
    return (now.year, now.month)


def parse_start(start: str | None) -> tuple[int, int]:
    if not start:
        return ARCHIVE_START
    dt = datetime.fromisoformat(start)
    return (dt.year, dt.month)
