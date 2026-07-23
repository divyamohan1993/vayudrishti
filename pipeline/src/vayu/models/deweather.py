"""Meteorological normalisation / deweathering (Grange & Carslaw 2019). Owner: vayu-models.

Trains a gradient-boosted model of PM2.5 on meteorological + temporal features, then
"normalises" by repeatedly resampling ONLY the meteorological inputs from the observed
distribution while holding each timestamp's temporal features fixed, and averaging the
predictions. The result is a weather-neutral PM2.5 series: the emission/trend signal with
meteorological variability removed. This is what lets the Intervention-Ledger event-study
attribute a change to policy (GRAP) rather than to the weather ("it rained, not the ban").

Reference: Grange, S.K. & Carslaw, D.C. (2019), "Using meteorological normalisation to
detect interventions in air quality time series", Sci. Total Environ. 653, 578-588,
doi:10.1016/j.scitotenv.2018.10.344.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from vayu.models.features import add_calendar, add_wind_vector

METEO_COLS = ["wind_u", "wind_v", "wind_speed_10m", "temp_2m", "rh_2m", "precip_mm", "blh_m"]
TIME_COLS = ["hour_sin", "hour_cos", "doy_sin", "doy_cos", "is_weekend", "trend_days"]
_FEATURES = METEO_COLS + TIME_COLS
_DW_PARAMS = {"objective": "regression", "verbose": -1, "num_leaves": 63, "min_data_in_leaf": 40,
              "learning_rate": 0.05, "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1}


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = add_wind_vector(df)
    df = add_calendar(df)
    ts = pd.to_datetime(df["ts_utc"], utc=True)
    # Long-term trend term (days since first observation) so normalisation keeps the trend.
    df = df.copy()
    df["trend_days"] = (ts.astype("int64") / 1e9 / 86400.0)
    df["trend_days"] -= df["trend_days"].min()
    return df


def train_deweather(df: pd.DataFrame, *, target: str = "pm25", rounds: int = 300) -> lgb.Booster:
    prepped = _prep(df).dropna(subset=[target])
    x = prepped[_FEATURES]
    y = prepped[target].to_numpy(float)
    return lgb.train(_DW_PARAMS, lgb.Dataset(x, label=y, free_raw_data=False), num_boost_round=rounds)


def normalise(df: pd.DataFrame, model: lgb.Booster, *, n_samples: int = 300, seed: int = 0) -> np.ndarray:
    """Weather-normalised PM2.5 per row: resample meteo from the pool, hold time fixed, average."""
    prepped = _prep(df)
    base = prepped[_FEATURES].to_numpy(float)
    pool = prepped[METEO_COLS].to_numpy(float)
    meteo_idx = [_FEATURES.index(c) for c in METEO_COLS]
    rng = np.random.default_rng(seed)
    n = len(prepped)
    acc = np.zeros(n)
    for _ in range(n_samples):
        sample = base.copy()
        sample[:, meteo_idx] = pool[rng.integers(0, n, n)]
        acc += model.predict(sample)
    return np.clip(acc / n_samples, 0, None)


def city_normalised_daily(parquet_df: pd.DataFrame, *, n_samples: int = 300, rounds: int = 300,
                          seed: int = 0) -> pd.DataFrame:
    """City-level daily raw vs weather-normalised PM2.5 for the interventions ribbon.

    Aggregates the station parquet to a city-hourly mean (PM2.5 + meteo), deweathers that
    series, and returns daily means. Labeled a city-mean series (spec 13 ribbon).
    """
    cols = ["pm25", *[c for c in ("wind_speed_10m", "wind_dir_10m", "temp_2m", "rh_2m",
                                  "precip_mm", "blh_m") if c in parquet_df.columns]]
    hourly = parquet_df.groupby("ts_utc", as_index=False)[cols].mean()
    model = train_deweather(hourly, rounds=rounds)
    hourly = hourly.copy()
    hourly["pm25_normalized"] = normalise(hourly, model, n_samples=n_samples, seed=seed)
    ts = pd.to_datetime(hourly["ts_utc"], utc=True)
    hourly["date"] = ts.dt.tz_convert("Asia/Kolkata").dt.date
    daily = hourly.groupby("date").agg(pm25_raw=("pm25", "mean"),
                                       pm25_normalized=("pm25_normalized", "mean")).reset_index()
    # Drop days with no valid raw PM2.5 (splice edges / live-layer hours with all-NaN
    # station values): a gap in the ribbon is honest; a fabricated value is not.
    return daily.dropna(subset=["pm25_raw", "pm25_normalized"]).reset_index(drop=True)


def normalised_station_frame(parquet_df: pd.DataFrame, *, n_samples: int = 200, rounds: int = 250,
                             seed: int = 0) -> pd.DataFrame:
    """Per-station weather-normalised PM2.5 (for per-ward event-study aggregation)."""
    out = []
    for _sid, g in parquet_df.groupby("station_id"):
        g = g.sort_values("ts_utc")
        if g["pm25"].notna().sum() < 200:
            continue
        model = train_deweather(g, rounds=rounds)
        gg = g.copy()
        gg["pm25_normalized"] = normalise(g, model, n_samples=n_samples, seed=seed)
        out.append(gg[["ts_utc", "station_id", "ward_id", "pm25", "pm25_normalized"]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=["ts_utc", "station_id", "ward_id", "pm25", "pm25_normalized"])


__all__ = ["train_deweather", "normalise", "city_normalised_daily", "normalised_station_frame",
           "METEO_COLS", "TIME_COLS"]
