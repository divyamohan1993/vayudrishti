"""Enforcement publish: real ward queue ranked by MEASURED signals (spec 5.4). Owner: vayu-models.

Ranks wards by exceedance persistence x recent level x population vulnerability, computed from
IDW-to-centroid PM2.5 history. Attribution is a confidence-tagged LABEL on the card (read from
attribution.json), not a rank multiplier. Action comes from the fixed taxonomy. Emitted via the
content model; gate-valid, fixture flag dropped.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from shapely.geometry import shape

from vayu.aqi import sub_index
from vayu.logging_setup import get_logger
from vayu.models.baseline_idw import idw_predict
from vayu.models.run import load_feature_store
from vayu.publish.contentmodels import EnforcementDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("enforcement_pub")

NAAQS_PM25_24H = 60.0  # India NAAQS 24-hour PM2.5 standard (ug/m3)
WINDOW_H = 168         # 7 days for persistence/exceedance
_ACTION = {
    "dust": "deploy_water_sprinkling", "traffic": "reroute_divert_heavy_traffic",
    "industry": "inspect_industrial_emissions", "biomass": "ban_open_biomass_burning",
    "residential_other": "issue_public_health_advisory", "mixed": "issue_public_health_advisory",
}


def _wards(city: str):
    feats = json.loads((web_data_dir() / city / "wards.geojson").read_text(encoding="utf-8"))["features"]
    for f in feats:
        try:
            c = shape(f["geometry"]).representative_point()
            yield f["properties"]["ward_id"], c.y, c.x, float(f["properties"].get("population") or 0.0)
        except Exception:  # pragma: no cover
            continue


def _source_labels(city: str) -> dict[str, str]:
    path = web_data_dir() / city / "attribution.json"
    if not path.exists():
        return {}
    out = {}
    for w in json.loads(path.read_text(encoding="utf-8")).get("wards", []):
        shares = w["shares"]
        dom = max(shares, key=lambda k: shares[k])
        out[w["ward_id"]] = dom if shares[dom] > 0.3 else "mixed"
    return out


def build(city: str = "delhi") -> EnforcementDoc:
    df = load_feature_store(city)
    gen = utc_iso_z(now_utc())
    origin = df["ts_utc"].max()
    labels = _source_labels(city)
    ward_list = list(_wards(city))
    ids = [w[0] for w in ward_list]
    clat = np.array([w[1] for w in ward_list])
    clon = np.array([w[2] for w in ward_list])
    pops = np.array([w[3] for w in ward_list])
    max_pop = float(pops.max()) or 1.0

    # IDW station PM2.5 to ward centroids over the trailing window.
    series = {w: [] for w in ids}
    for off in range(WINDOW_H):
        cur = df[df["ts_utc"] == origin - pd.Timedelta(hours=off)].dropna(subset=["pm25"])
        if len(cur) >= 2:
            vals = idw_predict(cur["lat"].to_numpy(), cur["lon"].to_numpy(), cur["pm25"].to_numpy(), clat, clon)
            for i, w in enumerate(ids):
                series[w].append(float(vals[i]))

    items = []
    for i, w in enumerate(ids):
        s = np.array(series[w][::-1])  # chronological
        if s.size < 24:
            continue
        recent = s[-24:]
        recent_mean = float(np.nanmean(recent))
        exceedance_pct = round(100.0 * float(np.mean(s > NAAQS_PM25_24H)), 1)
        daily = [np.nanmean(s[max(0, len(s) - (d + 1) * 24):len(s) - d * 24]) for d in range(len(s) // 24)]
        persistence_days = int(sum(1 for dm in daily if dm > NAAQS_PM25_24H))
        vuln = float(pops[i]) / max_pop
        si = sub_index("pm25", recent_mean) or 0
        score = 0.10 * si + 3.0 * persistence_days + 0.25 * exceedance_pct + 25.0 * vuln
        priority = round(float(np.clip(score, 0, 100)), 1)
        conf = "high" if priority > 55 else ("med" if priority > 30 else "low")
        label = labels.get(w, "mixed")
        trend = [round(float(x), 1) for x in s[-72:]]
        items.append({
            "ward_id": w, "source_label": label, "confidence": conf, "priority_score": priority,
            "evidence": {"trend_72h": trend, "persistence_days": persistence_days, "exceedance_pct": exceedance_pct},
            "action": _ACTION.get(label, "monitor_no_action"),
        })

    items.sort(key=lambda it: it["priority_score"], reverse=True)
    doc = EnforcementDoc(generated_at=gen, ranked=items)
    log.info("enforcement_pub.built", city=city, wards=len(items),
             top=[(it["ward_id"], it["priority_score"]) for it in items[:3]])
    return doc


def publish(city: str = "delhi") -> int:
    emit_model(build(city), f"{city}/enforcement.json")
    log.info("enforcement_pub.published", city=city, path=f"{city}/enforcement.json")
    return 0


__all__ = ["build", "publish"]
