"""OSM land-use features via Overpass (spec 3, 5.1). Zero-auth.

Computed in the city's projected UTM CRS (never degrees, spec 5.0):
- road_density: vehicular road length per km^2 within a 500 m buffer.
- builtup_frac: building-footprint area fraction within the 500 m buffer.
- industrial_dist_km: distance to the nearest OSM industrial land-use.

A citywide road fetch (Delhi ~170k ways) is too heavy for one Overpass request,
so we fetch roads+buildings for a *chunk* of points at once (union of around
clauses) and compute each point's features locally. This is a handful of requests
per city instead of one-per-station. Results cache per city; a chunk that fails
Overpass degrades to NaN (unknown), distinct from a genuine zero, and never blocks
the parquet. Full-geometry OGR is avoided (Smart App Control blocks GDAL here).
"""

from __future__ import annotations

import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point, Polygon

from vayu.logging_setup import get_logger

log = get_logger("ingest.osm_static")

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
ROAD_CLASSES = "motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street"
BUFFER_M = 500.0
BUFFER_AREA_KM2 = 3.141592653589793 * (BUFFER_M / 1000.0) ** 2
CHUNK_SIZE = 4  # small union queries keep Overpass under its 504 threshold


def overpass_query(query: str, *, retries: int = 5, timeout: int = 180) -> dict | None:
    """POST an Overpass query with backoff across endpoints; None on total failure."""
    delay = 4.0
    for attempt in range(retries):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            resp = requests.post(
                endpoint, data={"data": query}, timeout=timeout, headers={"User-Agent": "vayu"}
            )
            if resp.status_code == 200:
                return resp.json()
            log.warning("osm.overpass_status", status=resp.status_code, attempt=attempt)
        except requests.RequestException as exc:
            log.warning("osm.overpass_error", error=type(exc).__name__, attempt=attempt)
        time.sleep(delay)
        delay *= 2
    return None


def _parse_ways(elements: list[dict]) -> tuple[list, list]:
    roads, blds = [], []
    for el in elements:
        tags = el.get("tags", {})
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if "building" in tags:
            if len(coords) >= 3:
                ring = coords if coords[0] == coords[-1] else coords + [coords[0]]
                try:
                    poly = Polygon(ring)
                    if poly.is_valid or poly.buffer(0).is_valid:
                        blds.append(poly if poly.is_valid else poly.buffer(0))
                except Exception:  # noqa: BLE001 - skip degenerate footprints
                    continue
        elif "highway" in tags and len(coords) >= 2:
            roads.append(LineString(coords))
    return roads, blds


def _fetch_ways_near(chunk: pd.DataFrame) -> tuple[list, list, bool]:
    clauses = []
    for r in chunk.itertuples(index=False):
        clauses.append(f'way[highway~"{ROAD_CLASSES}"](around:{int(BUFFER_M)},{r.lat},{r.lon});')
        clauses.append(f"way[building](around:{int(BUFFER_M)},{r.lat},{r.lon});")
    query = f"[out:json][timeout:180];({''.join(clauses)});out geom;"
    data = overpass_query(query)
    if data is None:
        return [], [], False
    roads, blds = _parse_ways(data.get("elements", []))
    return roads, blds, True


def fetch_industrial(bbox: tuple[float, float, float, float], utm_epsg: int) -> gpd.GeoSeries:
    """Citywide industrial land-use polygons, projected. Empty on failure."""
    min_lon, min_lat, max_lon, max_lat = bbox
    query = (
        f"[out:json][timeout:120];"
        f"way[landuse=industrial]({min_lat},{min_lon},{max_lat},{max_lon});out geom;"
    )
    data = overpass_query(query, timeout=120)
    if data is None:
        return gpd.GeoSeries([], crs=utm_epsg)
    _, polys = _parse_ways(
        [{**e, "tags": {"building": "yes"}} for e in data.get("elements", [])]
    )
    if not polys:
        return gpd.GeoSeries([], crs=utm_epsg)
    return gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(utm_epsg)


MAJOR_ROAD_CLASSES = "motorway|trunk|primary"
ROAD_SIMPLIFY_DEG = 0.0002  # ~22 m; thin orientation lines only
ROAD_COORD_DECIMALS = 5


def emit_roads_geojson(
    bbox: tuple[float, float, float, float], out_path: Path
) -> int:
    """Publish a thin major-road roads.geojson for map orientation (spec vayu-web).

    Motorway/trunk/primary/secondary only, city bbox, simplified + 5dp rounded.
    Returns the number of road features written (0 if Overpass fails; file untouched).
    """
    import json

    from shapely.geometry import mapping

    min_lon, min_lat, max_lon, max_lat = bbox
    query = (
        f"[out:json][timeout:180];"
        f'way[highway~"^({MAJOR_ROAD_CLASSES})$"]({min_lat},{min_lon},{max_lat},{max_lon});'
        f"out geom;"
    )
    data = overpass_query(query, timeout=180)
    if data is None:
        log.warning("osm.roads_fetch_failed", bbox=bbox)
        return 0

    def _round(obj):
        if isinstance(obj, float):
            return round(obj, ROAD_COORD_DECIMALS)
        if isinstance(obj, (list, tuple)):
            return [_round(x) for x in obj]
        return obj

    features = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(coords) < 2:
            continue
        geom = LineString(coords).simplify(ROAD_SIMPLIFY_DEG, preserve_topology=False)
        if geom.is_empty:
            continue
        props = {"class": tags.get("highway")}
        if tags.get("name"):
            props["name"] = tags["name"]
        gj = mapping(geom)
        gj["coordinates"] = _round(gj["coordinates"])
        features.append({"type": "Feature", "properties": props, "geometry": gj})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")),
        encoding="utf-8",
    )
    log.info(
        "osm.roads_emit",
        features=len(features),
        size_kb=round(out_path.stat().st_size / 1024, 1),
        out=str(out_path.name),
    )
    return len(features)


def _chunks(df: pd.DataFrame, size: int):
    for i in range(0, len(df), size):
        yield df.iloc[i : i + size]


def build_station_landuse(
    stations: pd.DataFrame,
    bbox: tuple[float, float, float, float],
    utm_epsg: int,
    cache_path: Path,
    *,
    chunk_size: int = CHUNK_SIZE,
) -> pd.DataFrame:
    """Per-station [station_id, road_density, builtup_frac, industrial_dist_km].

    ``stations`` needs columns station_id, lat, lon. Cached per city; already-cached
    stations are skipped so reruns and the cron stay cheap (land-use is static).
    """
    empty = pd.DataFrame(
        columns=["station_id", "road_density", "builtup_frac", "industrial_dist_km"]
    )
    cached = pd.read_parquet(cache_path) if cache_path.exists() else empty
    done = set(cached["station_id"].astype(str))
    todo = stations[~stations["station_id"].astype(str).isin(done)].reset_index(drop=True)
    if todo.empty:
        return cached.drop_duplicates("station_id", keep="last").reset_index(drop=True)

    industrial = fetch_industrial(bbox, utm_epsg)
    rows = []
    for chunk in _chunks(todo, chunk_size):
        roads, blds, ok = _fetch_ways_near(chunk)
        roads_gdf = gpd.GeoSeries(roads, crs="EPSG:4326").to_crs(utm_epsg) if roads else None
        blds_gdf = gpd.GeoSeries(blds, crs="EPSG:4326").to_crs(utm_epsg) if blds else None
        pts = gpd.GeoSeries(
            [Point(r.lon, r.lat) for r in chunk.itertuples(index=False)], crs="EPSG:4326"
        ).to_crs(utm_epsg)
        for pt, r in zip(pts, chunk.itertuples(index=False), strict=False):
            buf = pt.buffer(BUFFER_M)
            if not ok:
                rd = bf = float("nan")
            else:
                rd = (
                    round(roads_gdf.intersection(buf).length.sum() / 1000.0 / BUFFER_AREA_KM2, 4)
                    if roads_gdf is not None
                    else 0.0
                )
                bf = (
                    round(min(1.0, blds_gdf.intersection(buf).area.sum() / buf.area), 4)
                    if blds_gdf is not None
                    else 0.0
                )
            dist = (
                round(industrial.distance(pt).min() / 1000.0, 4)
                if len(industrial)
                else float("nan")
            )
            rows.append(
                {
                    "station_id": str(r.station_id),
                    "road_density": rd,
                    "builtup_frac": bf,
                    "industrial_dist_km": dist,
                }
            )

    out = pd.concat([cached, pd.DataFrame(rows)], ignore_index=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache_path, index=False)
    log.info("osm.station_landuse", stations=len(out), newly_fetched=len(rows))
    return out.drop_duplicates("station_id", keep="last").reset_index(drop=True)
