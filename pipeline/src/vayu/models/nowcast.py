"""Nowcast fusion: LightGBM quantile p50/p90 + LOSO CV (spec 5.1, acceptance 3).

Trains gradient-boosted quantile regressors on station rows and validates with
Leave-One-Station-Out cross-validation, stratified by each held-out station's distance
to its nearest retained station, producing a degradation curve against the IDW baseline.
Acceptance 3: the model beats IDW at every distance bucket <= 5 km.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from vayu.models.baseline_idw import haversine_km
from vayu.models.features import TARGET, build_station_frame, feature_matrix
from vayu.models.metrics import rmse

_LGB_PARAMS = {
    "objective": "quantile",
    "verbose": -1,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
}
_NUM_ROUNDS = 250
# Distance-to-nearest-retained-station bucket upper edges (km). <=5 km checked by acceptance 3.
CV_BUCKET_EDGES = (1.5, 3.0, 5.0, 8.0, float("inf"))


def train_quantile(x: pd.DataFrame, y: np.ndarray, alpha: float, rounds: int = _NUM_ROUNDS) -> lgb.Booster:
    params = {**_LGB_PARAMS, "alpha": alpha}
    dataset = lgb.Dataset(x, label=y, free_raw_data=False)
    return lgb.train(params, dataset, num_boost_round=rounds)


@dataclass
class NowcastModel:
    p50: lgb.Booster
    p90: lgb.Booster

    @classmethod
    def fit(cls, station_frame: pd.DataFrame) -> NowcastModel:
        x = feature_matrix(station_frame)
        y = station_frame[TARGET].to_numpy(float)
        return cls(p50=train_quantile(x, y, 0.5), p90=train_quantile(x, y, 0.9))

    def predict(self, feature_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = feature_matrix(feature_df)
        p50 = np.clip(self.p50.predict(x), 0, None)
        p90 = np.clip(self.p90.predict(x), 0, None)
        p90 = np.maximum(p90, p50)  # enforce quantile ordering (gate invariant)
        return p50, p90


def _station_coords(frame: pd.DataFrame) -> dict[str, tuple[float, float]]:
    coords: dict[str, tuple[float, float]] = {}
    for sid, grp in frame.groupby("station_id"):
        coords[sid] = (float(grp["lat"].median()), float(grp["lon"].median()))
    return coords


def loso_cv(parquet_df: pd.DataFrame, *, max_rows: int = 180_000, cv_rounds: int = 150,
           max_folds: int | None = None) -> dict:
    """Leave-One-Station-Out CV, stratified by distance-to-nearest-retained-station.

    Returns {"baseline": "IDW", "buckets": [{dist_km, model_rmse, idw_rmse, n}], "overall": {...}}.
    Uses the precomputed leave-self-out ``idw_pm25`` column as the IDW baseline prediction.
    For tractability on the full feature store, whole timestamps are subsampled to about
    ``max_rows`` (every retained hour keeps its complete station field, so the spatial
    fusion signal is intact). ``max_folds`` evaluates a representative subset of held-out
    stations while STILL training on all others (spatial density preserved); the estimate
    stays on real data.
    """
    df = parquet_df
    if len(df) > max_rows:
        ts = np.sort(df["ts_utc"].unique())
        stride = max(1, int(np.ceil(len(df) / max_rows)))
        keep = set(ts[::stride].tolist())
        df = df[df["ts_utc"].isin(keep)]
    frame = build_station_frame(df)
    stations = sorted(frame["station_id"].unique())
    coords = _station_coords(frame)
    eval_stations = stations
    if max_folds and len(stations) > max_folds:
        step = max(1, len(stations) // max_folds)
        eval_stations = stations[::step][:max_folds]
    per_station: list[dict] = []

    for held in eval_stations:
        train = frame[frame["station_id"] != held]
        test = frame[frame["station_id"] == held]
        if len(train) < 50 or test.empty:
            continue
        # distance from held-out station to nearest retained station
        hlat, hlon = coords[held]
        others = [coords[s] for s in stations if s != held]
        if not others:
            continue
        d_near = float(np.min([haversine_km(o[0], o[1], hlat, hlon) for o in others]))
        model = train_quantile(feature_matrix(train), train[TARGET].to_numpy(float), 0.5, rounds=cv_rounds)
        y_true = test[TARGET].to_numpy(float)
        y_model = np.clip(model.predict(feature_matrix(test)), 0, None)
        y_idw = test["idw_pm25"].to_numpy(float)
        per_station.append({"station": held, "d_near": d_near,
                            "y": y_true, "model": y_model, "idw": y_idw, "n": len(test)})

    buckets = _bucketize(per_station)
    all_y = np.concatenate([p["y"] for p in per_station]) if per_station else np.array([])
    all_m = np.concatenate([p["model"] for p in per_station]) if per_station else np.array([])
    all_i = np.concatenate([p["idw"] for p in per_station]) if per_station else np.array([])
    overall = {"model_rmse": round(rmse(all_y, all_m), 2), "idw_rmse": round(rmse(all_y, all_i), 2),
               "n": int(all_y.size), "stations": len(per_station)}
    return {"baseline": "IDW", "buckets": buckets, "overall": overall}


def _bucketize(per_station: list[dict]) -> list[dict]:
    buckets = []
    lower = 0.0
    for edge in CV_BUCKET_EDGES:
        members = [p for p in per_station if lower <= p["d_near"] < edge]
        if members:
            y = np.concatenate([m["y"] for m in members])
            ym = np.concatenate([m["model"] for m in members])
            yi = np.concatenate([m["idw"] for m in members])
            buckets.append({
                "dist_km": (edge if np.isfinite(edge) else round(max(m["d_near"] for m in members), 1)),
                "model_rmse": round(rmse(y, ym), 2),
                "idw_rmse": round(rmse(y, yi), 2),
                "n": int(y.size),
            })
        lower = edge
    return buckets


__all__ = ["NowcastModel", "train_quantile", "loso_cv", "CV_BUCKET_EDGES"]
