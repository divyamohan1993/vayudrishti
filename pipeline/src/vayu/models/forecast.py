"""Ward-level 24/48/72h forecast + rolling-origin backtest (spec 5.2, acceptance 2).

Walk-forward by construction: features at an origin use only data at or before the
origin (recent lags, trend, ward diurnal state) plus origin-time forecast meteo for the
target hour. The backtest holds out a test window separated from training by an embargo
of >= horizon + 168h (vayu-data's max feature lag), evaluates over many rolling origins,
and scores skill honestly against persistence AND a diurnal-climatology seasonal-naive.
A negative skill is a valid published number.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from vayu.models.metrics import mae, rmse, skill_pct

HORIZONS = (24, 48, 72)
MAX_FEATURE_LAG_H = 168  # vayu-data: satellite 7-day medians are the largest backward window
_MET = ["wind_speed_10m", "blh_m", "rh_2m", "precip_mm", "temp_2m"]
_LGB = {"objective": "quantile", "verbose": -1, "num_leaves": 31, "min_data_in_leaf": 30,
        "learning_rate": 0.05, "feature_fraction": 0.85}
_ROUNDS = 200


def embargo_for(horizon: int) -> int:
    """Embargo hours between train end and test origin: horizon + max feature lag."""
    return horizon + MAX_FEATURE_LAG_H


def build_ward_hourly(parquet_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the station parquet to a ward-hourly frame (mean over stations in a ward)."""
    cols = ["pm25", *[c for c in _MET if c in parquet_df.columns],
            *(["frp_upwind"] if "frp_upwind" in parquet_df.columns else [])]
    grp = (parquet_df.groupby(["ward_id", "ts_utc"], as_index=False)[cols].mean())
    return grp.sort_values(["ward_id", "ts_utc"]).reset_index(drop=True)


def _supervised_for_ward(g: pd.DataFrame, horizon: int, hour_clim: dict[int, float]) -> pd.DataFrame:
    """Origin-aligned supervised rows for one ward at one horizon."""
    g = g.set_index("ts_utc").sort_index().asfreq("h")
    pm = g["pm25"]
    tgt_index = g.index + pd.Timedelta(hours=horizon)
    feat = pd.DataFrame(index=g.index)
    feat["lag0"] = pm
    for lag in (1, 3, 6, 12, 24):
        feat[f"lag{lag}"] = pm.shift(lag)
    feat["roll24"] = pm.rolling(24, min_periods=6).mean()
    feat["trend6"] = pm - pm.shift(6)
    for m in _MET:
        if m in g.columns:
            feat[f"{m}_tgt"] = g[m].shift(-horizon)  # origin-time forecast meteo for target hour
    if "frp_upwind" in g.columns:
        feat["frp_upwind"] = g["frp_upwind"]
    tgt_hour = tgt_index.tz_convert("Asia/Kolkata").hour
    tgt_doy = tgt_index.tz_convert("Asia/Kolkata").dayofyear
    feat["hour_sin"] = np.sin(2 * np.pi * tgt_hour / 24.0)
    feat["hour_cos"] = np.cos(2 * np.pi * tgt_hour / 24.0)
    feat["doy_sin"] = np.sin(2 * np.pi * tgt_doy / 365.0)
    feat["doy_cos"] = np.cos(2 * np.pi * tgt_doy / 365.0)
    feat["y"] = pm.shift(-horizon)
    feat["persistence"] = pm  # lag0 = value at origin
    feat["seasonal_naive"] = [hour_clim.get(int(h), np.nan) for h in tgt_hour]
    feat["origin"] = g.index
    return feat.reset_index(drop=True)


def _hour_climatology(ward_hourly: pd.DataFrame) -> dict[int, float]:
    local_hour = pd.to_datetime(ward_hourly["ts_utc"], utc=True).dt.tz_convert("Asia/Kolkata").dt.hour
    return ward_hourly.assign(_h=local_hour.to_numpy()).groupby("_h")["pm25"].mean().to_dict()


FEATURE_COLS = (["lag0", "lag1", "lag3", "lag6", "lag12", "lag24", "roll24", "trend6"]
                + [f"{m}_tgt" for m in _MET] + ["frp_upwind", "hour_sin", "hour_cos", "doy_sin", "doy_cos"])


def _matrix(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({c: (df[c] if c in df.columns else np.nan) for c in FEATURE_COLS})


@dataclass
class ForecastModel:
    horizon: int
    p50: lgb.Booster
    p90: lgb.Booster

    def predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = _matrix(df)
        p50 = np.clip(self.p50.predict(x), 0, None)
        p90 = np.maximum(np.clip(self.p90.predict(x), 0, None), p50)
        return p50, p90


def _build_supervised(ward_hourly: pd.DataFrame, horizon: int) -> pd.DataFrame:
    clim = _hour_climatology(ward_hourly)
    parts = [_supervised_for_ward(g, horizon, clim) for _, g in ward_hourly.groupby("ward_id")]
    sup = pd.concat(parts, ignore_index=True)
    return sup.dropna(subset=["y", "lag0", "lag24"]).reset_index(drop=True)


def train_forecast(ward_hourly: pd.DataFrame, horizon: int) -> ForecastModel:
    sup = _build_supervised(ward_hourly, horizon)
    x, y = _matrix(sup), sup["y"].to_numpy(float)
    d = lgb.Dataset(x, label=y, free_raw_data=False)
    p50 = lgb.train({**_LGB, "alpha": 0.5}, d, num_boost_round=_ROUNDS)
    p90 = lgb.train({**_LGB, "alpha": 0.9}, d, num_boost_round=_ROUNDS)
    return ForecastModel(horizon=horizon, p50=p50, p90=p90)


def rolling_origin_backtest(ward_hourly: pd.DataFrame, horizon: int, *, test_frac: float = 0.3) -> dict:
    """Train before an embargo gap, evaluate over rolling origins in the held-out window."""
    sup = _build_supervised(ward_hourly, horizon)
    if sup.empty:
        return _empty_metrics(horizon)
    origins = np.sort(sup["origin"].unique())
    embargo = pd.Timedelta(hours=embargo_for(horizon))
    split = origins[int(len(origins) * (1 - test_frac))]
    train_end = split - embargo
    train = sup[sup["origin"] <= train_end]
    test = sup[sup["origin"] >= split]
    if len(train) < 100 or len(test) < 20:
        return _empty_metrics(horizon, n=len(test))
    x, y = _matrix(train), train["y"].to_numpy(float)
    booster = lgb.train({**_LGB, "alpha": 0.5}, lgb.Dataset(x, label=y, free_raw_data=False),
                        num_boost_round=_ROUNDS)
    yt = test["y"].to_numpy(float)
    ym = np.clip(booster.predict(_matrix(test)), 0, None)
    r_model = rmse(yt, ym)
    r_pers = rmse(yt, test["persistence"].to_numpy(float))
    r_seas = rmse(yt, test["seasonal_naive"].to_numpy(float))
    return {
        "rmse": round(r_model, 2), "mae": round(mae(yt, ym), 2),
        "persistence_rmse": round(r_pers, 2), "seasonal_naive_rmse": round(r_seas, 2),
        "skill_pct": skill_pct(r_model, r_pers), "n": int(yt.size), "embargo_h": embargo_for(horizon),
    }


def _empty_metrics(horizon: int, n: int = 0) -> dict:
    return {"rmse": 0.0, "mae": 0.0, "persistence_rmse": 0.0, "seasonal_naive_rmse": 0.0,
            "skill_pct": 0.0, "n": n, "embargo_h": embargo_for(horizon)}


def backtest_all(ward_hourly: pd.DataFrame) -> dict[str, dict]:
    return {str(h): rolling_origin_backtest(ward_hourly, h) for h in HORIZONS}


__all__ = ["HORIZONS", "embargo_for", "build_ward_hourly", "train_forecast",
           "rolling_origin_backtest", "backtest_all", "ForecastModel", "MAX_FEATURE_LAG_H"]
