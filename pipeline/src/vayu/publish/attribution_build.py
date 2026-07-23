"""Attribution publish: real per-ward source shares (spec 5.3). Owner: vayu-models.

CPF wind-sector analysis per station (which bearings deliver high-percentile PM2.5) mapped
to each ward via its nearest station, combined with the ward's land-use proxies through the
attribution engine's share heuristic. LABELED ESTIMATE, never measured emissions. Emitted via
the content model; gate-valid, fixture flag dropped.
"""

from __future__ import annotations

import json

import numpy as np
from shapely.geometry import shape

from vayu.logging_setup import get_logger
from vayu.models.attribution import (
    INDUSTRIAL_BEARINGS,
    NW_STUBBLE_RANGE,
    confidence_for_shares,
    cpf,
    sector_centers,
    ward_shares,
)
from vayu.models.baseline_idw import haversine_km
from vayu.models.run import load_feature_store
from vayu.publish.contentmodels import AttributionDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.sanitize import sanitize_text
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("attribution_pub")


def _ward_points(city: str):
    feats = json.loads((web_data_dir() / city / "wards.geojson").read_text(encoding="utf-8"))["features"]
    for f in feats:
        try:
            c = shape(f["geometry"]).representative_point()
            yield f["properties"]["ward_id"], c.y, c.x
        except Exception:  # pragma: no cover
            continue


def _sector_mean(cpf_vec: np.ndarray, lo: float, hi: float) -> float:
    centers = sector_centers()
    if lo <= hi:
        mask = (centers >= lo) & (centers <= hi)
    else:
        mask = (centers >= lo) | (centers <= hi)
    vals = cpf_vec[mask]
    vals = vals[~np.isnan(vals)]
    return float(vals.mean()) if vals.size else 0.0


def build(city: str = "delhi") -> AttributionDoc:
    df = load_feature_store(city)
    gen = utc_iso_z(now_utc())
    log.info("attribution_pub.start", city=city)

    # Station CPF + coordinates + land-use (median per station).
    scpf, slat, slon, sid_order, sland = {}, [], [], [], {}
    for sid, g in df.groupby("station_id"):
        scpf[sid] = cpf(g["wind_dir_10m"].to_numpy(), g["pm25"].to_numpy())
        slat.append(float(g["lat"].median()))
        slon.append(float(g["lon"].median()))
        sid_order.append(sid)
        sland[sid] = (float(g["road_density"].median()), float(g["builtup_frac"].median()),
                      float(g["industrial_dist_km"].median()), float(g["frp_upwind"].mean()))
    slat, slon = np.array(slat), np.array(slon)
    ind_lo, ind_hi = next(iter(INDUSTRIAL_BEARINGS.values()))

    rows = []
    for ward_id, lat, lon in _ward_points(city):
        nsid = sid_order[int(np.argmin(haversine_km(slat, slon, lat, lon)))]
        cpf_vec = scpf[nsid]
        cpf_nw = _sector_mean(cpf_vec, *NW_STUBBLE_RANGE)
        cpf_ind = _sector_mean(cpf_vec, ind_lo, ind_hi)
        road, builtup, indust, frp = sland[nsid]
        shares = ward_shares(road, builtup, indust, frp, cpf_nw, cpf_ind)
        dom = max(shares, key=lambda k: shares[k])
        rows.append({
            "ward_id": ward_id, "shares": shares, "confidence": confidence_for_shares(shares),
            "method_notes": sanitize_text(
                f"CPF wind-sector peak (nearest station) + land-use heuristic; dominant {dom} "
                f"({int(shares[dom] * 100)}%). Labeled estimate, not measured emissions."),
        })

    doc = AttributionDoc(generated_at=gen, wards=rows)
    log.info("attribution_pub.built", city=city, wards=len(rows))
    return doc


def publish(city: str = "delhi") -> int:
    emit_model(build(city), f"{city}/attribution.json")
    log.info("attribution_pub.published", city=city, path=f"{city}/attribution.json")
    return 0


__all__ = ["build", "publish"]
