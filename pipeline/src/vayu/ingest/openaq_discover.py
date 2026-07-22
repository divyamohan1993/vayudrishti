"""Discover OpenAQ station locations within a city bbox (spec 3, 5.0).

OpenAQ v1/v2 are gone (410) and the S3 archive is keyed by location id only, so
there is no zero-auth way to find which locations sit in a city. We use the free
OpenAQ v3 locations API (key from .env) once to build a committed, verified seed
at ``config/cities/{city}.openaq.json``; the S3 backfill then runs fully
anonymously against those ids. Without the key we fall back to that committed
seed and log a clear degrade line.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from vayu.cityconfig import CityConfig
from vayu.logging_setup import get_logger
from vayu.settings import get_settings, repo_root

log = get_logger("ingest.openaq_discover")

V3_LOCATIONS = "https://api.openaq.org/v3/locations"
POLLUTANTS = {"pm25", "pm10", "no2", "so2", "o3", "co"}


def seed_path(city_slug: str) -> Path:
    return repo_root() / "config" / "cities" / f"{city_slug}.openaq.json"


def _fetch_page(bbox: tuple[float, float, float, float], page: int, key: str) -> dict:
    params = {
        "bbox": ",".join(str(round(v, 5)) for v in bbox),
        "limit": 1000,
        "page": page,
    }
    resp = requests.get(
        V3_LOCATIONS,
        params=params,
        headers={"X-API-Key": key, "User-Agent": "vayu"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def discover_locations(city: CityConfig, *, write_seed: bool = True) -> list[dict]:
    """Query OpenAQ v3 for stations in the city bbox; write a committed seed.

    Returns a list of ``{location_id, name, lat, lon, parameters, first, last}``.
    Falls back to the committed seed when the key is absent.
    """
    settings = get_settings()
    seed = seed_path(city.slug)

    if not settings.openaq_api_key:
        cached = _read_seed(seed)
        log.warning(
            "openaq_discover.no_key",
            city=city.slug,
            fallback_seed=str(seed.name),
            cached_locations=len(cached),
        )
        return cached

    results: list[dict] = []
    page = 1
    while True:
        payload = _fetch_page(city.bbox_tuple, page, settings.openaq_api_key)
        rows = payload.get("results", [])
        for loc in rows:
            coords = loc.get("coordinates") or {}
            lat, lon = coords.get("latitude"), coords.get("longitude")
            if lat is None or lon is None:
                continue
            params = sorted(
                {
                    (s.get("parameter") or {}).get("name")
                    for s in (loc.get("sensors") or [])
                    if (s.get("parameter") or {}).get("name")
                }
            )
            if not (set(params) & POLLUTANTS):
                continue
            results.append(
                {
                    "location_id": loc["id"],
                    "name": loc.get("name") or f"loc-{loc['id']}",
                    "lat": lat,
                    "lon": lon,
                    "parameters": [p for p in params if p in POLLUTANTS],
                    "first": (loc.get("datetimeFirst") or {}).get("utc"),
                    "last": (loc.get("datetimeLast") or {}).get("utc"),
                }
            )
        if len(rows) < 1000:
            break
        page += 1

    results.sort(key=lambda r: r["location_id"])
    log.info("openaq_discover.done", city=city.slug, locations=len(results))
    if write_seed:
        seed.parent.mkdir(parents=True, exist_ok=True)
        seed.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def _read_seed(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_seed(city_slug: str) -> list[dict]:
    """Read the committed OpenAQ seed for a city (used by the S3 backfill)."""
    return _read_seed(seed_path(city_slug))
