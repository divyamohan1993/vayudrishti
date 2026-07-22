"""Training + validation runner (owner: vayu-models).

Loads vayu-data's feature-store parquet and produces the real acceptance-2/3 numbers:
nowcast LOSO CV degradation curve (vs IDW) and the forecast rolling-origin backtest
(skill vs persistence + seasonal-naive). Metrics are cached for the publish step to fold
into receipts.json. Runs the moment `data/feature-store/{city}/hourly.parquet` exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from vayu.logging_setup import get_logger
from vayu.models.forecast import backtest_all, build_ward_hourly
from vayu.models.nowcast import loso_cv
from vayu.settings import get_settings

log = get_logger("train")


def feature_store_path(city: str) -> Path:
    return get_settings().feature_store_dir / city / "hourly.parquet"


def metrics_path(city: str) -> Path:
    return get_settings().resolved_data_dir / "artifacts" / city / "metrics.json"


def load_feature_store(city: str) -> pd.DataFrame:
    path = feature_store_path(city)
    if not path.exists():
        raise FileNotFoundError(f"No feature store at {path}. Run `vayu features --city {city}` first.")
    return pd.read_parquet(path)


def validate_city(city: str) -> dict:
    """Run nowcast LOSO CV + forecast backtest, log honestly, cache metrics."""
    df = load_feature_store(city)
    log.info("train.loaded", city=city, rows=len(df), stations=df["station_id"].nunique())

    cv = loso_cv(df)
    log.info("train.nowcast_cv", city=city, overall=cv["overall"])
    for b in cv["buckets"]:
        beats = b["model_rmse"] < b["idw_rmse"]
        log.info("train.cv_bucket", city=city, dist_km=b["dist_km"],
                 model_rmse=b["model_rmse"], idw_rmse=b["idw_rmse"], beats_idw=beats, n=b["n"])

    ward_hourly = build_ward_hourly(df)
    forecast = backtest_all(ward_hourly)
    for h, m in forecast.items():
        log.info("train.forecast_backtest", city=city, horizon=h, skill_pct=m["skill_pct"],
                 rmse=m["rmse"], persistence_rmse=m["persistence_rmse"], n=m["n"], embargo_h=m["embargo_h"])

    metrics = {"nowcast_cv": cv, "forecast": forecast}
    out = metrics_path(city)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    log.info("train.metrics_cached", city=city, path=str(out))
    return metrics


def train_city(city: str) -> int:
    try:
        validate_city(city)
        return 0
    except FileNotFoundError as exc:
        log.error("train.no_feature_store", city=city, detail=str(exc))
        return 1


__all__ = ["validate_city", "train_city", "load_feature_store", "feature_store_path", "metrics_path"]
