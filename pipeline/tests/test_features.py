"""Feature-store assembly: schema conformance + batch upwind (network-free)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from vayu.features import build

UTC = UTC


def _minimal_df():
    ts = pd.date_range("2025-11-05", periods=3, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": list(ts) * 1,
            "station_id": ["235", "235", "235"],
            "lat": [28.6, 28.6, 28.6],
            "lon": [77.2, 77.2, 77.2],
            "pm25": [210.0, 180.5, np.nan],
            "wind_dir_10m": [315.0, 315.0, np.nan],
        }
    )


def test_feature_columns_match_schema_count():
    cols = build.feature_columns()
    assert len(cols) == 27
    assert cols[0] == "ts_utc"
    assert cols[-1] == "ward_id"
    for c in ["s5p_no2", "aod550", "frp_upwind", "fire_count_upwind", "industrial_dist_km"]:
        assert c in cols


def test_finalize_produces_full_schema_with_dtypes():
    out = build.finalize(_minimal_df())
    assert list(out.columns) == build.feature_columns()
    # tz-aware UTC timestamp (pandas may use us or ns resolution; both are valid).
    assert out["ts_utc"].dt.tz is not None
    assert str(out["ts_utc"].dt.tz) == "UTC"
    assert str(out["station_id"].dtype) == "string"
    assert str(out["ward_id"].dtype) == "string"
    assert out["fire_count_upwind"].dtype == np.int64
    assert out["s5p_no2"].dtype == np.float64  # present, NaN
    assert out["s5p_no2"].isna().all()
    build.validate(out)


def test_add_upwind_nw_stubble_counts_only_upwind_fires():
    now = datetime(2025, 11, 5, 2, 0, tzinfo=UTC)
    df = pd.DataFrame(
        {
            "ts_utc": [now],
            "station_id": ["235"],
            "lat": [28.6],
            "lon": [77.2],
            "wind_dir_10m": [315.0],  # wind FROM NW
        }
    )
    fires = pd.DataFrame(
        {
            "lat": [29.2, 28.1],  # NW (in sector), SE (out)
            "lon": [76.6, 77.6],
            "frp": [15.0, 40.0],
            "acq_utc": pd.to_datetime(
                [now - timedelta(hours=2), now - timedelta(hours=2)], utc=True
            ),
        }
    )
    out = build.add_upwind(df, fires)
    assert out["fire_count_upwind"].iloc[0] == 1
    assert out["frp_upwind"].iloc[0] == 15.0


def test_add_upwind_handles_object_dtype_fires():
    # Empty FIRMS chunks can upcast lat/lon to object; add_upwind must still work.
    now = datetime(2025, 11, 5, 2, 0, tzinfo=UTC)
    df = pd.DataFrame(
        {"ts_utc": [now], "station_id": ["235"], "lat": [28.6], "lon": [77.2],
         "wind_dir_10m": [315.0]}
    )
    fires = pd.DataFrame(
        {"lat": [29.2], "lon": [76.6], "frp": [15.0],
         "acq_utc": pd.to_datetime([now - timedelta(hours=2)], utc=True)}
    ).astype({"lat": "object", "lon": "object"})
    out = build.add_upwind(df, fires)
    assert out["fire_count_upwind"].iloc[0] == 1
    assert out["frp_upwind"].iloc[0] == 15.0


def test_add_upwind_empty_fires_is_zero():
    df = pd.DataFrame(
        {"ts_utc": [datetime(2025, 11, 5, tzinfo=UTC)], "station_id": ["1"],
         "lat": [28.6], "lon": [77.2], "wind_dir_10m": [315.0]}
    )
    out = build.add_upwind(df, None)
    assert out["frp_upwind"].iloc[0] == 0.0
    assert out["fire_count_upwind"].iloc[0] == 0
