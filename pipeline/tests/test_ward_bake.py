"""ward_id baking + point-in-polygon assignment (spec 5.0)."""

import geopandas as gpd
from shapely.geometry import Point, box

from vayu import geo


def _wards(id_field, ids, geoms):
    return gpd.GeoDataFrame({id_field: ids, "geometry": geoms}, crs="EPSG:4326")


def test_numeric_ward_ids_zeropad3():
    gdf = _wards("ward_no", [5, 12, 250], [box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)])
    out = geo.assign_ward_ids(gdf, "delhi", "ward_no", numeric=True)
    assert list(out["ward_id"]) == ["delhi_005", "delhi_012", "delhi_250"]
    assert list(out["ward_code"]) == ["5", "12", "250"]


def test_lettered_ward_ids_get_stable_synthesized_index():
    # Mumbai BMC lettered wards: deterministic sort -> 1..N, native kept as ward_code.
    codes = ["F/N", "A", "F/S", "B"]
    geoms = [box(i, 0, i + 1, 1) for i in range(4)]
    gdf = _wards("ward", codes, geoms)
    out = geo.assign_ward_ids(gdf, "mumbai", "ward", numeric=False)
    by_code = dict(zip(out["ward_code"], out["ward_id"], strict=False))
    # sorted(["A","B","F/N","F/S"]) -> A=1, B=2, F/N=3, F/S=4
    assert by_code == {
        "A": "mumbai_001",
        "B": "mumbai_002",
        "F/N": "mumbai_003",
        "F/S": "mumbai_004",
    }


def test_lettered_index_is_deterministic_across_input_order():
    codes_a = ["F/N", "A", "F/S", "B"]
    codes_b = ["B", "F/S", "A", "F/N"]
    geoms = [box(i, 0, i + 1, 1) for i in range(4)]
    out_a = geo.assign_ward_ids(_wards("w", codes_a, geoms), "mumbai", "w", numeric=False)
    out_b = geo.assign_ward_ids(_wards("w", codes_b, geoms), "mumbai", "w", numeric=False)
    assert dict(zip(out_a["ward_code"], out_a["ward_id"], strict=False)) == dict(
        zip(out_b["ward_code"], out_b["ward_id"], strict=False)
    )


def test_points_outside_polygons_are_unassigned_not_dropped():
    wards = _wards("ward_no", [1, 2], [box(0, 0, 1, 1), box(2, 0, 3, 1)])
    wards = geo.assign_ward_ids(wards, "delhi", "ward_no", numeric=True)
    pts = gpd.GeoDataFrame(
        {"station_id": ["s1", "s2"], "geometry": [Point(0.5, 0.5), Point(5, 5)]},
        crs="EPSG:4326",
    )
    ids = geo.assign_points_to_wards(pts, wards, "delhi")
    assert ids.iloc[0] == "delhi_001"
    assert ids.iloc[1] == "delhi_unassigned"
    assert len(ids) == 2  # nothing dropped
