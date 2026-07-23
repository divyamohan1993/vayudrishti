"""Forecast publish: real ward-level 24/48/72h forecast.json (spec 5.2). Owner: vayu-models.

Trains the per-horizon LightGBM quantile models on the station-derived ward-hourly series,
then forecasts EVERY ward from a recent history built by IDW-ing station PM2.5 to the ward
centroid (so wards without a monitor are gap-filled, same philosophy as the nowcast). Target-
hour meteo comes from the real Open-Meteo forecast endpoint (zero-auth, past_days covers the
recent-past targets since the archive parquet lags real time). Emitted via the content model;
gate-valid, fixture flag dropped.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd
from shapely.geometry import shape

from vayu.aqi import category_for_index, sub_index
from vayu.cityconfig import load_city
from vayu.logging_setup import get_logger
from vayu.models.baseline_idw import idw_predict
from vayu.models.forecast import HORIZONS, build_ward_hourly, train_forecast
from vayu.models.run import load_feature_store
from vayu.publish.contentmodels import ForecastDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.sanitize import sanitize_text
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("forecast_pub")
_CONF = {24: "high", 48: "med", 72: "low"}


def _ward_centroids(city: str) -> dict[str, tuple[float, float, str]]:
    feats = json.loads((web_data_dir() / city / "wards.geojson").read_text(encoding="utf-8"))["features"]
    out = {}
    for f in feats:
        try:
            c = shape(f["geometry"]).representative_point()
            p = f["properties"]
            out[p["ward_id"]] = (c.y, c.x, sanitize_text(str(p.get("name") or p["ward_id"])))
        except Exception:  # pragma: no cover
            continue
    return out


def _latest_covered(df: pd.DataFrame, min_stations: int = 2) -> pd.Timestamp:
    """Latest hour with at least ``min_stations`` PM2.5 observations (live data can lag,
    especially for sparse-network cities), so lag0 anchors on a well-covered hour."""
    counts = df.dropna(subset=["pm25"]).groupby("ts_utc")["station_id"].nunique()
    ok = counts[counts >= min_stations]
    return ok.index.max() if len(ok) else df["ts_utc"].max()


def _recent_history(df: pd.DataFrame, origin, centroids: dict, hours: int = 26) -> dict[str, dict]:
    ids = list(centroids)
    clat = np.array([centroids[w][0] for w in ids])
    clon = np.array([centroids[w][1] for w in ids])
    hist: dict[str, dict] = {w: {} for w in ids}
    for off in range(hours):
        t = origin - pd.Timedelta(hours=off)
        cur = df[df["ts_utc"] == t].dropna(subset=["pm25"])
        if len(cur) >= 1:  # single-station IDW is a uniform fill; still a valid anchor
            vals = idw_predict(cur["lat"].to_numpy(), cur["lon"].to_numpy(), cur["pm25"].to_numpy(), clat, clon)
            for i, w in enumerate(ids):
                hist[w][off] = float(vals[i])
    return hist


def _openmeteo(lat: float, lon: float) -> pd.DataFrame:
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&hourly=wind_speed_10m,boundary_layer_height,relative_humidity_2m,precipitation,temperature_2m"
           "&wind_speed_unit=ms&past_days=7&forecast_days=2&timezone=UTC")
    last: Exception | None = None
    for attempt in range(5):  # backoff on Open-Meteo rate limits / transient 503s
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.load(r)["hourly"]
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    else:
        raise last  # exhausted retries
    return pd.DataFrame({
        "ts_utc": pd.to_datetime(d["time"], utc=True),
        "wind_speed_10m": d["wind_speed_10m"], "blh_m": d["boundary_layer_height"],
        "rh_2m": d["relative_humidity_2m"], "precip_mm": d["precipitation"], "temp_2m": d["temperature_2m"],
    }).set_index("ts_utc")


def _row(h_off: dict, origin, horizon: int, meteo: pd.DataFrame, frp: float) -> dict:
    def lag(o):
        return h_off.get(o, np.nan)
    vals = [lag(i) for i in range(24)]
    tgt = origin + pd.Timedelta(hours=horizon)
    m = meteo.reindex([tgt]).iloc[0] if tgt in meteo.index else meteo.iloc[-1]
    local = tgt.tz_convert("Asia/Kolkata")
    return {
        "lag0": lag(0), "lag1": lag(1), "lag3": lag(3), "lag6": lag(6), "lag12": lag(12), "lag24": lag(24),
        "roll24": float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan,
        "trend6": (lag(0) - lag(6)) if np.isfinite(lag(0)) and np.isfinite(lag(6)) else np.nan,
        "wind_speed_10m_tgt": float(m["wind_speed_10m"]), "blh_m_tgt": float(m["blh_m"]),
        "rh_2m_tgt": float(m["rh_2m"]), "precip_mm_tgt": float(m["precip_mm"]), "temp_2m_tgt": float(m["temp_2m"]),
        "frp_upwind": frp,
        "hour_sin": np.sin(2 * np.pi * local.hour / 24.0), "hour_cos": np.cos(2 * np.pi * local.hour / 24.0),
        "doy_sin": np.sin(2 * np.pi * local.dayofyear / 365.0), "doy_cos": np.cos(2 * np.pi * local.dayofyear / 365.0),
    }


def build(city: str = "delhi", *, train_df: pd.DataFrame | None = None, origin=None,
          archive_meteo: bool = False, models=None) -> ForecastDoc:
    """Real ward forecast from ``origin`` (default: latest). ``train_df`` overrides the
    training set for out-of-fold replay; ``archive_meteo`` takes target-hour meteo from the
    parquet (historical replay targets) instead of the Open-Meteo forecast endpoint;
    ``models`` reuses pre-trained per-horizon models (replay trains once, predicts many dates)."""
    df = load_feature_store(city)
    origin = origin if origin is not None else _latest_covered(df)
    gen = utc_iso_z(now_utc())
    cfg = load_city(city)
    log.info("forecast_pub.start", city=city, origin=str(origin))

    if models is None:
        wh = build_ward_hourly(train_df if train_df is not None else df)
        models = {h: train_forecast(wh, h) for h in HORIZONS}
    centroids = _ward_centroids(city)
    hist = _recent_history(df, origin, centroids)
    if archive_meteo:
        meteo = df.groupby("ts_utc")[["wind_speed_10m", "blh_m", "rh_2m", "precip_mm", "temp_2m"]].mean()
    else:
        meteo = _openmeteo(cfg.centroid[0], cfg.centroid[1])
    cur = df[df["ts_utc"] == origin]
    frp = float(cur["frp_upwind"].mean()) if cur["frp_upwind"].notna().any() else 0.0

    wards = []
    for ward_id, (_lat, _lon, name) in centroids.items():
        h_off = hist.get(ward_id, {})
        if not any(np.isfinite(v) for v in h_off.values()):
            continue  # no recent history at all for this ward
        series = []
        for horizon in HORIZONS:
            feat = _row(h_off, origin, horizon, meteo, frp)
            p50, p90 = models[horizon].predict(pd.DataFrame([feat]))
            v50 = float(p50[0])
            si = sub_index("pm25", v50) or 0
            series.append({
                "h": horizon, "pm25_p50": round(v50, 1), "pm25_p90": round(float(max(p90[0], v50)), 1),
                "subindex24h": si, "category": category_for_index(si), "confidence": _CONF[horizon],
            })
        wards.append({"ward_id": ward_id, "name": name, "series": series})

    doc = ForecastDoc(generated_at=gen, horizons_h=list(HORIZONS), wards=wards)
    log.info("forecast_pub.built", city=city, wards=len(wards))
    return doc


def publish(city: str = "delhi") -> int:
    emit_model(build(city), f"{city}/forecast.json")
    log.info("forecast_pub.published", city=city, path=f"{city}/forecast.json")
    return 0


__all__ = ["build", "publish"]
