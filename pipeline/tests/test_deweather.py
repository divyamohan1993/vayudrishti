"""Deweathering (Grange & Carslaw 2019) tests on a synthetic weather-driven series."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vayu.models.deweather import normalise, train_deweather


def make_weather_driven(days: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2025-11-01", periods=days * 24, freq="h", tz="UTC")
    n = len(ts)
    wind = rng.uniform(0.5, 6.0, n)
    # slowly declining emission trend + STRONG wind ventilation effect + noise
    trend = 160 - 0.04 * np.arange(n) / 24.0
    pm = np.maximum(5.0, trend + 220.0 / (wind + 0.5) - 45.0 + rng.normal(0, 10, n))
    return pd.DataFrame({
        "ts_utc": ts, "pm25": pm, "wind_speed_10m": wind,
        "wind_dir_10m": rng.uniform(0, 360, n), "temp_2m": rng.uniform(10, 25, n),
        "rh_2m": rng.uniform(30, 90, n), "precip_mm": 0.0, "blh_m": rng.uniform(200, 1200, n),
    })


def test_normalise_reduces_weather_signal():
    df = make_weather_driven()
    model = train_deweather(df, rounds=120)
    norm = normalise(df, model, n_samples=80)
    raw_corr = abs(np.corrcoef(df["pm25"], df["wind_speed_10m"])[0, 1])
    norm_corr = abs(np.corrcoef(norm, df["wind_speed_10m"])[0, 1])
    # The weather-normalized series should correlate less with wind than the raw series.
    assert norm_corr < raw_corr
    assert np.isfinite(norm).all()
    assert (norm >= 0).all()
    assert norm.shape == (len(df),)


def test_normalise_preserves_level_roughly():
    df = make_weather_driven()
    model = train_deweather(df, rounds=120)
    norm = normalise(df, model, n_samples=80)
    # Normalization removes weather variance, not the overall pollution level.
    assert abs(np.mean(norm) - np.mean(df["pm25"])) < 0.4 * np.mean(df["pm25"])
