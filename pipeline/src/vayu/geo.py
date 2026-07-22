"""Ward-id baking, station matching, and projected-CRS helpers (spec 5.0).

ward_id convention: ``"{city}_{zeropad3(index)}"``. For cities whose native ward
field is numeric (Delhi wards, BBMP ward numbers) the index IS that number. For
cities whose native field is a code, not an integer (Mumbai BMC wards are lettered
A, B, F/N, H/E, ...), we synthesize a stable integer index by sorting the native
codes deterministically, and keep the native value in ``ward_code``. This is the
spec 5.0 clarification agreed with vayu-models and vayu-web.

Every consumer joins on ``ward_id``; nobody re-derives it. Stations/cells outside
all ward polygons get ``"{city}_unassigned"`` and are kept, not dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape


def read_geojson(path: str | Path) -> gpd.GeoDataFrame:
    """Read a GeoJSON into a GeoDataFrame without GDAL/pyogrio.

    This environment's Application Control policy blocks pyogrio's native GDAL
    extension, so we parse GeoJSON with json + shapely instead. EPSG:4326 assumed.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    feats = data.get("features", [])
    geoms = [shape(f["geometry"]) for f in feats]
    props = [f.get("properties", {}) or {} for f in feats]
    return gpd.GeoDataFrame(props, geometry=geoms, crs="EPSG:4326")


def bake_ward_id(city: str, index: int) -> str:
    return f"{city}_{int(index):03d}"


def unassigned_ward_id(city: str) -> str:
    return f"{city}_unassigned"


def assign_ward_ids(
    gdf: gpd.GeoDataFrame,
    city: str,
    id_field: str,
    *,
    numeric: bool = True,
    name_field: str | None = None,
) -> gpd.GeoDataFrame:
    """Return a copy with baked ``ward_id``, native ``ward_code``, and ``name``.

    Numeric ids map straight through zeropad3. Non-numeric codes get a stable
    integer index assigned by lexicographic sort of the native code.
    """
    out = gdf.copy()

    def _s(v) -> str | None:
        """Null-safe string coercion (real ward data has occasional gaps)."""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return str(v)

    id_vals = [_s(v) for v in out[id_field].tolist()]
    name_vals = (
        [_s(v) for v in out[name_field].tolist()]
        if (name_field and name_field in out.columns)
        else [None] * len(out)
    )

    if numeric:
        if any(v is None for v in id_vals):
            raise ValueError(
                f"{city}: numeric ward id field '{id_field}' has null values; "
                "set ward_id_numeric: false or clean the source."
            )
        codes = id_vals
        indices = [int(float(v)) for v in codes]
    else:
        # Fill a missing native code deterministically (name, then positional) so
        # every real polygon still gets a stable id, then sort codes to 1..N.
        codes = [
            idv if idv is not None else (nm if nm is not None else f"row{i:04d}")
            for i, (idv, nm) in enumerate(zip(id_vals, name_vals, strict=False))
        ]
        ordered = sorted(set(codes))
        code_to_idx = {c: i + 1 for i, c in enumerate(ordered)}
        indices = [code_to_idx[c] for c in codes]

    out["ward_code"] = codes
    out["ward_id"] = [bake_ward_id(city, i) for i in indices]
    out["name"] = [
        nm if nm is not None else f"Ward {c}"
        for nm, c in zip(name_vals, codes, strict=False)
    ]

    if out["ward_id"].duplicated().any():
        dupes = out.loc[out["ward_id"].duplicated(keep=False), "ward_id"].unique()
        raise ValueError(f"Duplicate ward_id after bake for {city}: {list(dupes)[:5]}")
    return out


def resolve_station_id(name: str, station_match: dict[str, int]) -> str | None:
    """Canonical station_id (OpenAQ location id as string) for a data.gov.in name."""
    loc = station_match.get(name)
    return None if loc is None else str(loc)


def to_utm(gdf: gpd.GeoDataFrame, epsg: int) -> gpd.GeoDataFrame:
    """Reproject to the city's UTM CRS for distance/buffer work (never degrees)."""
    return gdf.to_crs(epsg=epsg)


def assign_points_to_wards(
    points: gpd.GeoDataFrame, wards: gpd.GeoDataFrame, city: str
) -> pd.Series:
    """ward_id for each point via polygon containment; outside => unassigned.

    Both inputs must be EPSG:4326. Returns a Series aligned to ``points.index``.
    """
    if "ward_id" not in wards.columns:
        raise ValueError("wards GeoDataFrame must carry baked 'ward_id'")
    joined = gpd.sjoin(
        points[["geometry"]], wards[["ward_id", "geometry"]], how="left", predicate="within"
    )
    # sjoin can duplicate a point that lands on a shared boundary; keep first.
    joined = joined[~joined.index.duplicated(keep="first")]
    return joined["ward_id"].reindex(points.index).fillna(unassigned_ward_id(city))
