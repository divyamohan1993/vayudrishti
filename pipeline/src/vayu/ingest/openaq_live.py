"""OpenAQ v3 live-latest ingest (spec 3, "live latest" path). Free key.

Fetches each station's most recent measurements from the v3 `/latest` endpoint and
shapes them exactly like the archive hourly table, so live rows concatenate onto
the archive tail (dedup on station_id+ts_utc, live preferred). This closes the
~4-day ERA5/archive lag so the nowcast anchor is current. Missing key degrades
gracefully to an empty frame; the sensor_id -> pollutant map comes from the
committed discovery seed.
"""

from __future__ import annotations

import pandas as pd
import requests

from vayu.ingest.openaq_archive import POLLUTANTS
from vayu.ingest.openaq_discover import load_seed
from vayu.logging_setup import get_logger
from vayu.settings import get_settings

log = get_logger("ingest.openaq_live")

V3_LATEST = "https://api.openaq.org/v3/locations/{loc}/latest"
LINEAGE_URL = "https://api.openaq.org/v3/locations"


def fetch_live(city_slug: str, location_ids: list[int]) -> pd.DataFrame:
    """Latest hourly readings for the given stations as a wide archive-shaped frame."""
    key = get_settings().openaq_api_key
    empty = pd.DataFrame(columns=["ts_utc", "station_id", "lat", "lon", *POLLUTANTS])
    if not key:
        log.warning("openaq_live.no_key", city=city_slug)
        return empty

    seed = {s["location_id"]: s for s in load_seed(city_slug)}
    records: list[dict] = []
    for loc in location_ids:
        info = seed.get(loc)
        if not info or not info.get("sensors"):
            continue
        smap = info["sensors"]
        try:
            resp = requests.get(
                V3_LATEST.format(loc=loc), headers={"X-API-Key": key}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("openaq_live.error", loc=loc, error=type(exc).__name__)
            continue
        for item in resp.json().get("results", []):
            param = smap.get(str(item.get("sensorsId")))
            if param not in POLLUTANTS:
                continue
            dt = (item.get("datetime") or {}).get("utc")
            val = item.get("value")
            if dt is None or val is None:
                continue
            records.append(
                {
                    "ts_utc": pd.Timestamp(dt).floor("h"),
                    "station_id": str(loc),
                    "lat": float(info["lat"]),
                    "lon": float(info["lon"]),
                    "parameter": param,
                    "value": float(val),
                }
            )

    if not records:
        log.info("openaq_live.empty", city=city_slug)
        return empty

    raw = pd.DataFrame(records)
    wide = raw.pivot_table(
        index=["ts_utc", "station_id", "lat", "lon"], columns="parameter", values="value"
    ).reset_index()
    for p in POLLUTANTS:
        if p not in wide.columns:
            wide[p] = pd.NA
    wide = wide[["ts_utc", "station_id", "lat", "lon", *POLLUTANTS]]
    log.info(
        "openaq_live.done",
        city=city_slug,
        rows=len(wide),
        latest=str(wide["ts_utc"].max()),
    )
    return wide
