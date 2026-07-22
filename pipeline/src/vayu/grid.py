"""Grid conventions (spec 5.0, FROZEN). Owner: vayu-data.

- CRS EPSG:4326, square cells of ``CELL_DEG`` = 0.01 deg ("approx 1 km").
- Origin = city bbox SW corner floored to 0.01 deg.
- ``cell_id = "{city}_{row}_{col}"`` with ``row = floor((lat - lat0) / 0.01)`` and
  ``col = floor((lon - lon0) / 0.01)``.
- ``nowcast.json`` carries ``grid_meta = {lat0, lon0, cell_deg, crs}``.

Floors use a rounded quotient so exact multiples of 0.01 do not fall into the
lower cell through floating-point error.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

CELL_DEG = 0.01
CRS = "EPSG:4326"

# Bounding box order matches config: (min_lon, min_lat, max_lon, max_lat).
BBox = tuple[float, float, float, float]


def _floor_units(value: float, cell: float = CELL_DEG) -> int:
    """floor(value / cell) robust to FP error at exact cell boundaries."""
    return math.floor(round(value / cell, 6))


def grid_origin(bbox: BBox, cell: float = CELL_DEG) -> tuple[float, float]:
    """SW origin (lat0, lon0): bbox SW corner floored to the cell size."""
    min_lon, min_lat, _max_lon, _max_lat = bbox
    lat0 = _floor_units(min_lat, cell) * cell
    lon0 = _floor_units(min_lon, cell) * cell
    return (round(lat0, 6), round(lon0, 6))


def cell_index(
    lat: float, lon: float, lat0: float, lon0: float, cell: float = CELL_DEG
) -> tuple[int, int]:
    """(row, col) for a point, row from latitude, col from longitude."""
    row = _floor_units(lat - lat0, cell)
    col = _floor_units(lon - lon0, cell)
    return (row, col)


def cell_id(city: str, row: int, col: int) -> str:
    return f"{city}_{row}_{col}"


def latlon_to_cell_id(
    city: str, lat: float, lon: float, lat0: float, lon0: float, cell: float = CELL_DEG
) -> str:
    row, col = cell_index(lat, lon, lat0, lon0, cell)
    return cell_id(city, row, col)


def cell_center(
    row: int, col: int, lat0: float, lon0: float, cell: float = CELL_DEG
) -> tuple[float, float]:
    """Center (lat, lon) of a cell."""
    return (round(lat0 + (row + 0.5) * cell, 6), round(lon0 + (col + 0.5) * cell, 6))


@dataclass(frozen=True)
class GridMeta:
    lat0: float
    lon0: float
    cell_deg: float
    crs: str
    n_rows: int
    n_cols: int

    def as_dict(self) -> dict:
        # grid_meta published to nowcast.json (spec 8): lat0, lon0, cell_deg, crs.
        return {
            "lat0": self.lat0,
            "lon0": self.lon0,
            "cell_deg": self.cell_deg,
            "crs": self.crs,
        }


def grid_meta(bbox: BBox, cell: float = CELL_DEG) -> GridMeta:
    """Full grid description for a city bbox, including row/col counts."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lat0, lon0 = grid_origin(bbox, cell)
    n_rows = _floor_units(max_lat - lat0, cell) + 1
    n_cols = _floor_units(max_lon - lon0, cell) + 1
    return GridMeta(lat0=lat0, lon0=lon0, cell_deg=cell, crs=CRS, n_rows=n_rows, n_cols=n_cols)


def enumerate_cells(bbox: BBox, cell: float = CELL_DEG) -> list[tuple[int, int, float, float]]:
    """All (row, col, center_lat, center_lon) tuples covering the bbox."""
    meta = grid_meta(bbox, cell)
    out: list[tuple[int, int, float, float]] = []
    for row in range(meta.n_rows):
        for col in range(meta.n_cols):
            clat, clon = cell_center(row, col, meta.lat0, meta.lon0, cell)
            out.append((row, col, clat, clon))
    return out
