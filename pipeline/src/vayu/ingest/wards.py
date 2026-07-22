"""Ward ingest + bake (spec 5.0, 8). Source: Datameet municipal spatial data.

Downloads the real ward polygons once, bakes ``ward_id`` per the frozen
convention, trims to the published property set, lightly simplifies and rounds
coordinates for payload/git size, and writes ``web/public/data/{city}/wards.geojson``.
Population (WorldPop via GEE) is added by a later step; it is an optional property.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from vayu.cityconfig import CityConfig
from vayu.geo import assign_ward_ids, read_geojson
from vayu.lineage import LineageLog
from vayu.logging_setup import get_logger
from vayu.settings import get_settings, repo_root

log = get_logger("ingest.wards")

SIMPLIFY_TOLERANCE_DEG = 0.0001  # ~11 m; invisible at city zoom
COORD_DECIMALS = 5  # ~1 m


def _resolve_local(city: CityConfig) -> Path:
    lp = city.wards.local_path or f"data/raw/{city.slug}/wards_source.geojson"
    p = Path(lp)
    return p if p.is_absolute() else repo_root() / p


def download_wards(city: CityConfig) -> Path:
    """Ensure the source ward geojson is cached locally; download if missing."""
    dest = _resolve_local(city)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    if not city.wards.url:
        raise FileNotFoundError(f"No cached wards and no url for {city.slug}: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("wards.download", city=city.slug, source=city.wards.source)
    resp = requests.get(city.wards.url, timeout=120, headers={"User-Agent": "vayu"})
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def _round_coords(obj):
    if isinstance(obj, (int, float)):
        return round(obj, COORD_DECIMALS)
    if isinstance(obj, list):
        return [_round_coords(x) for x in obj]
    return obj


def bake_wards(city: CityConfig, lineage: LineageLog | None = None) -> Path:
    """Bake and publish wards.geojson for a city. Returns the output path."""
    src = download_wards(city)
    gdf = read_geojson(src)
    n_source = len(gdf)
    baked = assign_ward_ids(
        gdf,
        city.slug,
        city.wards.ward_id_field,
        numeric=city.wards.ward_id_numeric,
        name_field=city.wards.name_field,
    )
    baked = baked[["ward_id", "name", "ward_code", "geometry"]].copy()
    baked["geometry"] = baked["geometry"].simplify(
        SIMPLIFY_TOLERANCE_DEG, preserve_topology=True
    )

    fc = json.loads(baked.to_json())
    for feat in fc["features"]:
        feat["geometry"]["coordinates"] = _round_coords(feat["geometry"]["coordinates"])
        feat.pop("id", None)
    fc = {"type": "FeatureCollection", "features": fc["features"]}

    out = get_settings().resolved_web_data_dir / city.slug / "wards.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")

    log.info(
        "wards.bake",
        city=city.slug,
        wards=len(baked),
        source_features=n_source,
        out=str(out.relative_to(repo_root())),
        size_kb=round(out.stat().st_size / 1024, 1),
    )
    if lineage is not None:
        lineage.add(
            source="datameet-wards",
            url=city.wards.url or str(src),
            resource_id=f"{city.wards.source}:{Path(src).name}",
            rows=len(baked),
        )
    return out


def add_ward_population(city: CityConfig, year: int = 2020) -> int:
    """Add WorldPop population per ward into the published wards.geojson (spec 13).

    Reads the baked wards.geojson, sums WorldPop 100m population per polygon via GEE,
    writes it back as an optional `population` property. Returns wards populated (0 if
    GEE is off; the geometry file is left untouched in that case).
    """
    from vayu.ingest.gee_extractor import ward_population

    out = get_settings().resolved_web_data_dir / city.slug / "wards.geojson"
    fc = json.loads(out.read_text(encoding="utf-8"))
    pops = ward_population(fc, year=year)
    if not pops:
        log.warning("wards.population_skip", city=city.slug)
        return 0
    for feat in fc["features"]:
        wid = feat["properties"].get("ward_id")
        feat["properties"]["population"] = pops.get(wid)
    out.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    covered = sum(1 for f in fc["features"] if f["properties"].get("population") is not None)
    log.info("wards.population", city=city.slug, populated=covered, year=year)
    return covered
