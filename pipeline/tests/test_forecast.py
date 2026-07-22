"""Forecast + rolling-origin backtest tests on a synthetic ward-hourly frame.

Exercises the acceptance-2 engine (embargo = horizon + 168h, vs persistence and
seasonal-naive) end-to-end. Real skill numbers come with vayu-data's Delhi parquet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vayu.models.forecast import (
    HORIZONS,
    ForecastModel,
    backtest_all,
    build_ward_hourly,
    embargo_for,
    rolling_origin_backtest,
    train_forecast,
)


def make_ward_hourly(days: int = 45, wards: int = 4, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-10-10", periods=days * 24, freq="h", tz="UTC")
    rows = []
    for w in range(wards):
        wid = f"delhi_{w:03d}"
        base = 110 + 25 * w
        level = base
        for t in ts:
            hour = t.tz_convert("Asia/Kolkata").hour
            diurnal = 25 * np.sin(2 * np.pi * (hour - 6) / 24.0)
            level = 0.85 * level + 0.15 * base + rng.normal(0, 6)  # autocorrelation
            pm = max(6.0, level + diurnal + rng.normal(0, 8))
            rows.append({
                "ward_id": wid, "ts_utc": t, "pm25": pm,
                "wind_speed_10m": float(rng.uniform(0.5, 5)), "blh_m": float(rng.uniform(200, 1200)),
                "rh_2m": float(rng.uniform(30, 90)), "precip_mm": 0.0, "temp_2m": float(rng.uniform(12, 28)),
                "frp_upwind": float(rng.uniform(0, 150)),
            })
    return pd.DataFrame(rows)


class TestWardHourly:
    def test_aggregates_stations_in_ward(self):
        stations = pd.DataFrame({
            "ward_id": ["delhi_001", "delhi_001", "delhi_002"],
            "ts_utc": pd.to_datetime(["2025-11-01T00:00:00Z"] * 3, utc=True),
            "pm25": [100.0, 200.0, 50.0],
            "wind_speed_10m": [1.0, 1.0, 1.0], "blh_m": [500.0, 500.0, 500.0],
            "rh_2m": [50.0, 50.0, 50.0], "precip_mm": [0.0, 0.0, 0.0],
            "temp_2m": [20.0, 20.0, 20.0], "frp_upwind": [10.0, 10.0, 10.0],
        })
        wh = build_ward_hourly(stations)
        row = wh[wh["ward_id"] == "delhi_001"].iloc[0]
        assert abs(row["pm25"] - 150.0) < 1e-6  # mean of the two stations


class TestEmbargo:
    def test_embargo_is_horizon_plus_168(self):
        assert embargo_for(24) == 192
        assert embargo_for(48) == 216
        assert embargo_for(72) == 240


class TestBacktest:
    def test_backtest_structure(self):
        wh = make_ward_hourly(days=45)
        m = rolling_origin_backtest(wh, 24)
        assert set(m) == {"rmse", "mae", "persistence_rmse", "seasonal_naive_rmse",
                          "skill_pct", "n", "embargo_h"}
        assert m["embargo_h"] == 192
        assert m["n"] > 0
        assert m["rmse"] > 0 and m["persistence_rmse"] > 0
        assert np.isfinite(m["skill_pct"])  # may be negative — honest

    def test_backtest_all_horizons(self):
        wh = make_ward_hourly(days=45)
        allm = backtest_all(wh)
        assert set(allm) == {"24", "48", "72"}
        for h in HORIZONS:
            assert allm[str(h)]["embargo_h"] == embargo_for(h)

    def test_seasonal_naive_distinct_from_persistence(self):
        # Diurnal-climatology seasonal-naive must differ from persistence (spec 5.2).
        wh = make_ward_hourly(days=45)
        m = rolling_origin_backtest(wh, 48)
        assert m["seasonal_naive_rmse"] != m["persistence_rmse"]


class TestForecastModel:
    def test_train_predict_quantile_ordering(self):
        wh = make_ward_hourly(days=30)
        model = train_forecast(wh, 24)
        assert isinstance(model, ForecastModel)
        # predict on a small supervised slice
        from vayu.models.forecast import _build_supervised  # noqa: PLC0415
        sup = _build_supervised(wh, 24).head(50)
        p50, p90 = model.predict(sup)
        assert (p90 >= p50 - 1e-6).all()
        assert (p50 >= 0).all()
