"""`vayu ingest` orchestrator: fetch real sources into the raw cache + lineage.

`ingest` warms every raw cache for a city (station discovery, baked wards, OpenAQ
S3 backfill, Open-Meteo per station, OSM land-use, FIRMS upwind inputs, GEE
satellite). `features` then joins those caches into the parquet. Both are
independently runnable; the fetchers are cache-aware, so reruns are incremental.
Keyed sources degrade gracefully with a clear log line when the key is absent.
"""

from __future__ import annotations

from vayu.cityconfig import load_city, resolve_cities
from vayu.ingest import firms, gee_extractor, openmeteo
from vayu.ingest import openaq_archive as oaq
from vayu.ingest.openaq_discover import discover_locations
from vayu.ingest.wards import bake_wards
from vayu.lineage import LineageLog
from vayu.logging_setup import get_logger
from vayu.settings import get_settings

log = get_logger("ingest.runner")

ALL_SOURCES = ("wards", "openaq", "openmeteo", "osm", "firms", "gee")


def _resolve_sources(sources: str) -> set[str]:
    if sources.strip().lower() == "all":
        return set(ALL_SOURCES)
    return {s.strip().lower() for s in sources.split(",") if s.strip()}


def run_ingest(city: str, sources: str = "all", start: str | None = None) -> int:
    src = _resolve_sources(sources)
    for slug in resolve_cities(city):
        _ingest_city(slug, src, start)
    return 0


def _ingest_city(slug: str, src: set[str], start: str | None) -> None:
    from vayu.features.build import active_station_ids  # avoid import cycle

    cfg = load_city(slug)
    settings = get_settings()
    lin = LineageLog()
    log.info("ingest.city.start", city=slug, sources=sorted(src))

    if "wards" in src:
        bake_wards(cfg, lin)

    base = None
    stations = None
    if "openaq" in src:
        discover_locations(cfg)  # refresh the committed seed when the key is present
        ids = active_station_ids(slug)
        months = oaq.month_range(oaq.parse_start(start), oaq.default_end())
        base = oaq.backfill_city(ids, months, settings.raw_dir / slug / "openaq")
        lin.add(
            source="openaq-s3-archive",
            url=oaq.BASE_URL,
            resource_id="records/csv.gz",
            rows=len(base),
        )
        if not base.empty:
            stations = base.groupby("station_id")[["lat", "lon"]].first().reset_index()

    if stations is not None and "openmeteo" in src:
        end = openmeteo.default_end_date()
        s = f"{oaq.parse_start(start)[0]}-{oaq.parse_start(start)[1]:02d}-01"
        rows = 0
        cache = settings.raw_dir / slug / "meteo"
        for r in stations.itertuples(index=False):
            m = openmeteo.fetch_archive_cached(
                str(r.station_id), float(r.lat), float(r.lon), s, end, cache
            )
            rows += len(m)
        lin.add(
            source="open-meteo-archive",
            url=openmeteo.ARCHIVE_URL,
            resource_id="era5:hourly",
            rows=rows,
        )

    if stations is not None and "osm" in src:
        from vayu.ingest.osm_static import build_station_landuse

        lu = build_station_landuse(
            stations, cfg.bbox_tuple, cfg.utm_epsg, settings.raw_dir / slug / "osm_landuse.parquet"
        )
        lin.add(
            source="osm-overpass",
            url="https://overpass-api.de/api/interpreter",
            resource_id="highway+building+landuse",
            rows=len(lu),
        )

    if "firms" in src:
        fdf = firms.fetch_city_fires(cfg, start, settings.raw_dir / slug / "firms")
        lin.add(
            source="nasa-firms",
            url=firms.ARCHIVE_URL,
            resource_id=f"VIIRS:{cfg.firms_country}",
            rows=len(fdf),
        )

    if stations is not None and "gee" in src:
        n = gee_extractor.backfill_satellite(cfg, stations, start, settings.raw_dir / slug / "gee")
        lin.add(source="gee", url=gee_extractor.LINEAGE_URL, resource_id="S5P+MCD19A2", rows=n)

    lin.write(settings.raw_dir / slug / "lineage.json")
    log.info("ingest.city.done", city=slug, sources=sorted(src), lineage_rows=lin.total_rows())
