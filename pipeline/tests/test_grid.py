"""Grid conventions (spec 5.0)."""

from vayu import grid


def test_origin_floors_to_cell():
    # min corner (76.847, 28.406) floors to (76.84, 28.40).
    bbox = (76.847, 28.406, 77.35, 28.88)
    lat0, lon0 = grid.grid_origin(bbox)
    assert (lat0, lon0) == (28.40, 76.84)


def test_origin_stable_on_exact_multiple():
    # Exact multiples of 0.01 must not drop a cell through FP error.
    bbox = (77.00, 28.60, 77.50, 28.90)
    lat0, lon0 = grid.grid_origin(bbox)
    assert (lat0, lon0) == (28.60, 77.00)


def test_cell_index_and_id():
    lat0, lon0 = 28.40, 76.84
    row, col = grid.cell_index(28.6139, 77.2090, lat0, lon0)
    assert (row, col) == (21, 36)
    assert grid.cell_id("delhi", row, col) == "delhi_21_36"
    assert grid.latlon_to_cell_id("delhi", 28.6139, 77.2090, lat0, lon0) == "delhi_21_36"


def test_cell_center_is_cell_midpoint():
    clat, clon = grid.cell_center(0, 0, 28.40, 76.84)
    assert clat == 28.405
    assert clon == 76.845


def test_grid_meta_counts_cover_bbox():
    bbox = (76.84, 28.40, 77.35, 28.88)
    meta = grid.grid_meta(bbox)
    assert meta.cell_deg == 0.01
    assert meta.crs == "EPSG:4326"
    # (28.88-28.40)/0.01 = 48 -> +1 = 49 rows; (77.35-76.84)/0.01 = 51 -> 52 cols.
    assert meta.n_rows == 49
    assert meta.n_cols == 52
    assert meta.as_dict() == {"lat0": 28.40, "lon0": 76.84, "cell_deg": 0.01, "crs": "EPSG:4326"}


def test_enumerate_cells_matches_meta_product():
    bbox = (77.00, 12.90, 77.10, 13.00)
    meta = grid.grid_meta(bbox)
    cells = grid.enumerate_cells(bbox)
    assert len(cells) == meta.n_rows * meta.n_cols
    # Max corner point lands inside the last enumerated cell.
    row, col = grid.cell_index(13.00, 77.10, meta.lat0, meta.lon0)
    assert (row, col) == (meta.n_rows - 1, meta.n_cols - 1)
