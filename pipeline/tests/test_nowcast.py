"""Nowcast model + LOSO CV pipeline tests on a synthetic feature-store frame.

The synthetic frame matches vayu-data's frozen 27-column parquet schema (spec 8) so the
model code is exercised end-to-end now; real acceptance-3 numbers come when the real
Delhi feature store lands. These tests assert the pipeline runs and returns well-formed
structure (finite RMSEs, quantile ordering, LOSO buckets), not a specific skill value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vayu.models.features import add_calendar, add_wind_vector, build_station_frame
from vayu.models.nowcast import NowcastModel, loso_cv

STATIONS = {
    "s1": (28.65, 77.31), "s2": (28.57, 77.19), "s3": (28.68, 77.13),
    "s4": (28.55, 77.22), "s5": (28.61, 77.28), "s6": (28.50, 77.10),
}


def make_synthetic_frame(days: int = 5, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-11-01", periods=days * 24, freq="h", tz="UTC")
    rows = []
    for sid, (lat, lon) in STATIONS.items():
        spatial = (lat - 28.4) * 200 + (lon - 76.83) * 60  # smooth field -> IDW is informative
        for t in ts:
            hour = t.tz_convert("Asia/Kolkata").hour
            diurnal = 30 * np.sin(2 * np.pi * (hour - 6) / 24.0)
            wind = float(rng.uniform(0.5, 5.0))
            pm25 = max(6.0, 90 + spatial + diurnal - 8 * wind + rng.normal(0, 8))
            rows.append({
                "ts_utc": t, "station_id": sid, "lat": lat, "lon": lon,
                "pm25": pm25, "pm10": pm25 * 1.8, "no2": rng.uniform(20, 80),
                "so2": rng.uniform(5, 30), "o3": rng.uniform(10, 60), "co": rng.uniform(0.5, 2.0),
                "wind_speed_10m": wind, "wind_dir_10m": float(rng.uniform(0, 360)),
                "temp_2m": rng.uniform(12, 28), "rh_2m": rng.uniform(30, 90),
                "precip_mm": 0.0, "blh_m": rng.uniform(200, 1200),
                "s5p_no2": rng.uniform(1e-5, 8e-5) if rng.random() > 0.3 else np.nan,
                "s5p_so2": np.nan, "s5p_co": rng.uniform(0.02, 0.05), "s5p_aai": rng.uniform(-1, 3),
                "aod550": rng.uniform(0.2, 1.5) if rng.random() > 0.2 else np.nan,
                "frp_upwind": rng.uniform(0, 200), "fire_count_upwind": int(rng.integers(0, 20)),
                "road_density": rng.uniform(0, 1), "builtup_frac": rng.uniform(0, 1),
                "industrial_dist_km": rng.uniform(0.2, 12), "ward_id": f"delhi_{hash(sid) % 290:03d}",
            })
    return pd.DataFrame(rows)


class TestFeatures:
    def test_wind_vector_magnitude(self):
        df = pd.DataFrame({"wind_speed_10m": [10.0], "wind_dir_10m": [0.0]})
        out = add_wind_vector(df)
        # Wind FROM north -> blows toward south -> v negative, u ~ 0.
        assert abs(out["wind_u"].iloc[0]) < 1e-9
        assert out["wind_v"].iloc[0] < 0

    def test_calendar_ist(self):
        df = pd.DataFrame({"ts_utc": pd.to_datetime(["2025-11-01T00:00:00Z"])})
        out = add_calendar(df)
        assert {"hour_sin", "hour_cos", "doy_sin", "doy_cos", "is_weekend"} <= set(out.columns)

    def test_station_frame_has_spatial(self):
        frame = build_station_frame(make_synthetic_frame(days=2))
        assert {"idw_pm25", "nearest_dist_km", "station_count"} <= set(frame.columns)
        assert frame["idw_pm25"].notna().any()


class TestNowcastModel:
    def test_fit_predict_quantile_ordering(self):
        frame = build_station_frame(make_synthetic_frame(days=3))
        model = NowcastModel.fit(frame)
        p50, p90 = model.predict(frame)
        assert p50.shape == (len(frame),)
        assert (p90 >= p50 - 1e-6).all()  # quantile ordering (gate invariant)
        assert (p50 >= 0).all()


class TestLosoCv:
    def test_returns_wellformed_curve(self):
        result = loso_cv(make_synthetic_frame(days=5))
        assert result["baseline"] == "IDW"
        assert result["buckets"], "expected non-empty LOSO buckets"
        for b in result["buckets"]:
            assert {"dist_km", "model_rmse", "idw_rmse", "n"} == set(b)
            assert np.isfinite(b["model_rmse"]) and b["model_rmse"] > 0
            assert np.isfinite(b["idw_rmse"]) and b["idw_rmse"] > 0
            assert b["n"] > 0
        assert np.isfinite(result["overall"]["model_rmse"])

    def test_model_competitive_on_smooth_field(self):
        # On a smooth spatial field with feature signal, the fusion model should be at
        # least roughly competitive with IDW overall (not a strict acceptance-3 assertion,
        # which needs real data, but a sanity floor).
        result = loso_cv(make_synthetic_frame(days=6, seed=3))
        o = result["overall"]
        assert o["model_rmse"] <= o["idw_rmse"] * 1.6
