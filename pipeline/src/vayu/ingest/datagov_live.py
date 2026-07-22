"""data.gov.in CPCB live-snapshot poller (spec 3). Free key.

Polls the CPCB real-time resource, converts the naive-IST ``last_update`` to UTC,
and maps each station to its canonical OpenAQ location id by nearest-coordinate
match against the discovery seed (populating station_match). Output is
archive-shaped so it concatenates onto the archive/live tail.

data.gov.in is frequently slow/unavailable; this degrades gracefully to an empty
frame (with a clear log line) on timeout or missing key, and OpenAQ v3 live remains
the primary current-data path. The API key rides in the query string, so lineage
stores the base URL + resource id only (spec 7).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests

from vayu import upwind
from vayu.ingest.openaq_archive import POLLUTANTS
from vayu.ingest.openaq_discover import load_seed
from vayu.logging_setup import get_logger
from vayu.settings import get_settings
from vayu.timeutils import ist_naive_to_utc

log = get_logger("ingest.datagov_live")

RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
MATCH_KM = 1.0  # a data.gov.in station maps to an OpenAQ id within ~1 km

# data.gov.in pollutant_id -> our column.
PARAM_MAP = {
    "PM2.5": "pm25", "PM10": "pm10", "NO2": "no2",
    "SO2": "so2", "OZONE": "o3", "CO": "co",
}


def _nearest_openaq_id(lat: float, lon: float, seed: list[dict]) -> str | None:
    best_id, best_km = None, MATCH_KM
    for s in seed:
        km = upwind.haversine_km(lat, lon, s["lat"], s["lon"])
        if km < best_km:
            best_id, best_km = str(s["location_id"]), km
    return best_id


def _parse_ist(value: str) -> datetime | None:
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return ist_naive_to_utc(datetime.strptime(value.strip(), fmt))
        except (ValueError, AttributeError):
            continue
    return None


def fetch_datagov(
    city_slug: str, bbox: tuple[float, float, float, float], *, timeout: int = 90, retries: int = 2
) -> pd.DataFrame:
    """Live CPCB readings for a city, archive-shaped. Empty on key-absent/timeout."""
    key = get_settings().datagov_api_key
    empty = pd.DataFrame(columns=["ts_utc", "station_id", "lat", "lon", *POLLUTANTS])
    if not key:
        log.warning("datagov.no_key", city=city_slug)
        return empty

    records = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                BASE_URL,
                params={"api-key": key, "format": "json", "limit": 5000},
                timeout=timeout,
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])
            break
        except requests.RequestException as exc:
            log.warning("datagov.error", city=city_slug, attempt=attempt, error=type(exc).__name__)
    if not records:
        return empty

    seed = load_seed(city_slug)
    min_lon, min_lat, max_lon, max_lat = bbox
    rows: list[dict] = []
    for rec in records:
        try:
            lat = float(rec.get("latitude"))
            lon = float(rec.get("longitude"))
        except (TypeError, ValueError):
            continue
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue
        param = PARAM_MAP.get(str(rec.get("pollutant_id", "")).upper())
        if param is None:
            continue
        value = rec.get("pollutant_avg") or rec.get("avg_value")
        ts = _parse_ist(str(rec.get("last_update", "")))
        station_id = _nearest_openaq_id(lat, lon, seed)
        if value in (None, "NA", "") or ts is None or station_id is None:
            continue
        rows.append(
            {
                "ts_utc": pd.Timestamp(ts).floor("h"),
                "station_id": station_id,
                "lat": lat,
                "lon": lon,
                "parameter": param,
                "value": pd.to_numeric(value, errors="coerce"),
            }
        )

    if not rows:
        log.info("datagov.empty", city=city_slug)
        return empty
    raw = pd.DataFrame(rows).dropna(subset=["value"])
    wide = raw.pivot_table(
        index=["ts_utc", "station_id", "lat", "lon"], columns="parameter", values="value"
    ).reset_index()
    for p in POLLUTANTS:
        if p not in wide.columns:
            wide[p] = pd.NA
    wide = wide[["ts_utc", "station_id", "lat", "lon", *POLLUTANTS]]
    log.info("datagov.done", city=city_slug, rows=len(wide), stations=wide["station_id"].nunique())
    return wide
