"""Nowcast publish: real nowcast.json grid + wards via grid_features (spec 5.1). Owner: vayu-models.

Trains the LightGBM quantile fusion model on the station parquet, predicts p50/p90 at every
grid cell (vayu-data's build_grid_features) and rolls up to wards (shapely point-in-polygon).
The headline subindex24h is the CPCB PM2.5 sub-index of the trailing-24h mean (IDW of station
24h means), a distinct quantity from the current-hour p50. Emitted via the content model so it
is gate-valid; fixture flag dropped.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from vayu.aqi import category_for_index, sub_index
from vayu.cityconfig import load_city
from vayu.features.grid_features import build_grid_features
from vayu.grid import grid_meta
from vayu.logging_setup import get_logger
from vayu.models.baseline_idw import haversine_km, idw_predict
from vayu.models.features import TARGET, add_calendar, add_wind_vector, build_station_frame, feature_matrix
from vayu.models.nowcast import NowcastModel, train_quantile
from vayu.models.run import load_feature_store
from vayu.publish.contentmodels import NowcastDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.sanitize import sanitize_text
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("nowcast_pub")
CONF_HIGH_KM, CONF_MED_KM = 3.0, 9.0


def _train(df: pd.DataFrame, *, max_rows: int = 120_000, rounds: int = 150) -> NowcastModel:
    d = df
    if len(d) > max_rows:
        ts = np.sort(d["ts_utc"].unique())
        stride = max(1, int(np.ceil(len(d) / max_rows)))
        d = d[d["ts_utc"].isin(set(ts[::stride].tolist()))]
    frame = build_station_frame(d)
    x, y = feature_matrix(frame), frame[TARGET].to_numpy(float)
    return NowcastModel(p50=train_quantile(x, y, 0.5, rounds=rounds),
                        p90=train_quantile(x, y, 0.9, rounds=rounds))


def _station_24h(df: pd.DataFrame, ts) -> pd.DataFrame:
    recent = df[(df["ts_utc"] > ts - pd.Timedelta(hours=24)) & (df["ts_utc"] <= ts)]
    return (recent.dropna(subset=["pm25"]).groupby("station_id")
            .agg(lat=("lat", "first"), lon=("lon", "first"), m=("pm25", "mean")).reset_index())


def _cell_features(gf: pd.DataFrame, df: pd.DataFrame, ts) -> pd.DataFrame:
    gf = add_wind_vector(gf)
    gf = gf.assign(ts_utc=ts)
    gf = add_calendar(gf)
    gf["s5p_no2_isnan"] = gf["s5p_no2"].isna().astype(int)
    gf["aod550_isnan"] = gf["aod550"].isna().astype(int)
    cur = df[df["ts_utc"] == ts].dropna(subset=["pm25"])
    lat, lon = gf["lat"].to_numpy(), gf["lon"].to_numpy()
    if len(cur) >= 2:
        clat, clon, cval = cur["lat"].to_numpy(), cur["lon"].to_numpy(), cur["pm25"].to_numpy()
        gf["idw_pm25"] = idw_predict(clat, clon, cval, lat, lon)
        gf["nearest_dist_km"] = [float(np.min(haversine_km(clat, clon, la, lo))) for la, lo in zip(lat, lon)]
        gf["station_count"] = len(cur)
    else:
        gf["idw_pm25"] = np.nan
        gf["nearest_dist_km"] = np.nan
        gf["station_count"] = 0
    return gf


def _confidence(dist_km: float) -> str:
    if not np.isfinite(dist_km) or dist_km > CONF_MED_KM:
        return "low"
    return "high" if dist_km <= CONF_HIGH_KM else "med"


def build(city: str = "delhi") -> NowcastDoc:
    df = load_feature_store(city)
    ts = df["ts_utc"].max()
    cfg = load_city(city)
    gen = utc_iso_z(now_utc())
    log.info("nowcast_pub.start", city=city, ts=str(ts), rows=len(df))

    model = _train(df)
    gf = build_grid_features(city, ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts)
    gf = _cell_features(gf, df, ts)
    p50, p90 = model.predict(gf)

    s24 = _station_24h(df, ts)
    lat, lon = gf["lat"].to_numpy(), gf["lon"].to_numpy()
    if len(s24) >= 1:
        cell_24h = idw_predict(s24["lat"].to_numpy(), s24["lon"].to_numpy(), s24["m"].to_numpy(), lat, lon)
    else:
        cell_24h = p50.copy()
    cell_24h = np.where(np.isnan(cell_24h), p50, cell_24h)

    meta = grid_meta(cfg.bbox_tuple)
    grid = []
    for i in range(len(gf)):
        si = sub_index("pm25", float(cell_24h[i])) or 0
        grid.append({
            "cell_id": gf["cell_id"].iat[i], "row": int(gf["row"].iat[i]), "col": int(gf["col"].iat[i]),
            "pm25_p50": round(float(p50[i]), 1), "pm25_p90": round(float(max(p90[i], p50[i])), 1),
            "subindex24h": si, "category": category_for_index(si),
        })

    wards = _ward_rollup(city, gf, p50, p90, cell_24h)
    doc = NowcastDoc(generated_at=gen,
                     grid_meta={"lat0": meta.lat0, "lon0": meta.lon0, "cell_deg": meta.cell_deg, "crs": meta.crs},
                     grid=grid, wards=wards)
    log.info("nowcast_pub.built", city=city, cells=len(grid), wards=len(wards))
    return doc


def _ward_rollup(city: str, gf: pd.DataFrame, p50, p90, cell_24h) -> list[dict]:
    features = json.loads((web_data_dir() / city / "wards.geojson").read_text(encoding="utf-8"))["features"]
    geoms, meta = [], []
    for f in features:
        try:
            geoms.append(shape(f["geometry"]))
            meta.append((f["properties"]["ward_id"], sanitize_text(str(f["properties"].get("name") or f["properties"]["ward_id"]))))
        except Exception:  # pragma: no cover
            continue
    tree = STRtree(geoms)
    lat, lon = gf["lat"].to_numpy(), gf["lon"].to_numpy()
    nearest = gf["nearest_dist_km"].to_numpy()
    bucket: dict[int, list[int]] = {}
    for ci in range(len(gf)):
        pt = Point(float(lon[ci]), float(lat[ci]))
        for gi in tree.query(pt):
            if geoms[gi].contains(pt):
                bucket.setdefault(gi, []).append(ci)
                break
    rows = []
    for gi, cells in bucket.items():
        ward_id, name = meta[gi]
        idx = np.array(cells)
        si = sub_index("pm25", float(np.nanmean(cell_24h[idx]))) or 0
        nd = float(np.nanmin(nearest[idx])) if np.isfinite(nearest[idx]).any() else float("nan")
        rows.append({
            "ward_id": ward_id, "name": name,
            "pm25_p50": round(float(np.mean(p50[idx])), 1),
            "pm25_p90": round(float(max(np.mean(p90[idx]), np.mean(p50[idx]))), 1),
            "subindex24h": si, "category": category_for_index(si), "confidence": _confidence(nd),
        })
    return rows


def publish(city: str = "delhi") -> int:
    emit_model(build(city), f"{city}/nowcast.json")
    log.info("nowcast_pub.published", city=city, path=f"{city}/nowcast.json")
    return 0


__all__ = ["build", "publish"]
