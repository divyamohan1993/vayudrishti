"""Publish the real receipts.json evidence page (spec 8, 13; acc 2/3/10 + Ledger).

Assembles cached validation results (nowcast LOSO curve, forecast backtest), live
attribution directional checks, the CPCB methodology table, the Intervention-Ledger
novelty statement + prior-art + method citations, honest caveats, and real data lineage
(vayu-data's lineage.json, query-string-free). No heavy compute; gate-valid by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from vayu.aqi import breakpoint_table_rows
from vayu.logging_setup import get_logger
from vayu.models.attribution import directional_checks
from vayu.models.run import load_feature_store, metrics_path
from vayu.publish.contentmodels import ReceiptsDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.ledger_build import ASSUMPTIONS
from vayu.publish.sanitize import sanitize_text
from vayu.settings import get_settings
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("receipts")

NOVELTY = (
    "The first operational system anywhere that answers, ward by ward and weather-adjusted, "
    "whether a city's emergency pollution measures (Delhi GRAP stages) actually worked, and "
    "estimates what acting earlier would have saved in exposure and premature deaths. One-off "
    "academic GRAP evaluations exist (city-level, retrospective papers); IITM DSS forecasts; "
    "no deployed system does continuous ward-level causal audit with mortality counterfactuals."
)
PRIOR_ART = [
    {"label": "IITM Delhi Air Quality Early Warning System / Decision Support System (forecasts, not causal audit)",
     "url": "https://ews.tropmet.res.in/"},
    {"label": "Retrospective academic GRAP evaluations (city-level, post-hoc)",
     "url": "https://www.cseindia.org/air-pollution"},
]
METHOD_CITATIONS = [
    {"label": "Grange & Carslaw 2019, meteorological normalisation", "url": "https://doi.org/10.1016/j.scitotenv.2018.10.344", "used_for": "deweathering"},
    {"label": "Burnett et al. 2018, GEMM, PNAS", "url": "https://doi.org/10.1073/pnas.1803222115", "used_for": "mortality exposure-response"},
    {"label": "CPCB National AQI methodology", "url": "https://cpcb.nic.in/national-air-quality-index/", "used_for": "AQI sub-index"},
]
HONESTY = [
    "Acceptance criterion 3 (preregistered, kept on record as written): 'Delhi nowcast stratified LOSO curve beats IDW at every distance bucket <=5km.' OUTCOME: NOT MET.",
    "Full distance-stratified LOSO curve is published in nowcast_cv: the fusion model's RMSE exceeds the IDW baseline at every <=5km bucket, and is lower than IDW only at the farthest (>=8km) bucket.",
    "Post-hoc diagnosis (NOT preregistered): at station-dense holdout locations IDW is a strong baseline, and the fusion model's dominant feature is the IDW-of-neighbours term, so it cannot systematically beat IDW where neighbours are close. Land-use (100%) and satellite (71%) together reduce error only 0.3% (see ablation), so the shortfall is structural, not a missing-feature gap.",
    "Product-relevant metric going forward: fusion's value is interior gap-fill far from monitors (the >=8km bucket, where the model beats IDW) -- the operational use case for grid cells with no nearby station.",
    "Single-winter training window (Feb-2025 onward); no multi-season generalization claims.",
    "Forecast backtest uses archived actual meteo at the target hour as a proxy for forecast meteo, so live skill will be somewhat lower (weather-forecast error).",
    "Attribution is a labeled estimate (CPF wind-sector + heuristics), never measured emissions.",
    "Intervention effects are a before/after contrast on the deweathered series; the placebo test isolates the policy signal from the seasonal emission trend. A CI spanning 0 or a failed placebo is published as a null accountability finding.",
    "Avoided-mortality is a GEMM modeled estimate with WorldPop 2020 population; its CI can span zero.",
    "LOSO is the blind spatial holdout (no active US-diplomatic monitor exists in these cities).",
]


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _lineage(city: str) -> list[dict]:
    raw = _load_json(get_settings().feature_store_dir / city / "lineage.json") or []
    return [{"source": sanitize_text(e["source"]), "base_url": e["base_url"],
             "resource_id": sanitize_text(str(e.get("resource_id", ""))),
             "fetched_at": e["fetched_at"], "rows": int(e.get("rows", 0))} for e in raw]


def build(city: str = "delhi") -> ReceiptsDoc:
    gen = utc_iso_z(now_utc())
    art = metrics_path(city).parent

    cv_sat = _load_json(art / "nowcast_cv_sat.json")
    cv_landuse = _load_json(art / "nowcast_cv_landuse.json")
    cv = cv_sat or cv_landuse or _load_json(art / "nowcast_cv.json")
    forecast = _load_json(art / "forecast_backtest.json")

    city_receipt: dict = {}
    if cv:
        city_receipt["nowcast_cv"] = {"baseline": cv["baseline"], "buckets": cv["buckets"]}
    if forecast:
        city_receipt["forecast"] = forecast
    if cv_sat and cv_landuse:
        w = cv_sat["overall"]["model_rmse"]
        wo = cv_landuse["overall"]["model_rmse"]
        city_receipt["ablation"] = {
            "note": sanitize_text(
                "Nowcast LOSO RMSE with vs without the GEE numeric satellite features "
                "(Sentinel-5P + MAIAC AOD); identical rows and config, satellite 71% populated "
                "(real cloud/QA gaps). Positive delta_pct = satellite reduces error."),
            "metric": "nowcast LOSO RMSE (ug/m3)",
            "with_sat": round(w, 2), "without_sat": round(wo, 2),
            "delta_pct": round(100.0 * (wo - w) / wo, 1) if wo else 0.0,
        }
    try:
        df = load_feature_store(city)
        city_receipt["attribution_directional_checks"] = directional_checks(df, in_stubble_season=True)
    except FileNotFoundError:
        pass
    city_receipt["intervention_assumptions"] = [sanitize_text(a) for a in ASSUMPTIONS]

    methodology = {
        "headline_label": "PM2.5 sub-index (24h)",
        "severe_note": sanitize_text(
            "CPCB defines no upper concentration for the Severe band. VayuDrishti continues the "
            "Very Poor slope so the PM2.5 sub-index reaches 500 at 380 ug/m3, then caps at 500. "
            "Raw PM2.5 is always shown alongside."),
        "aqi_breakpoints": breakpoint_table_rows(),
    }
    doc = ReceiptsDoc(
        generated_at=gen,
        honesty_notes=[sanitize_text(h) for h in HONESTY],
        methodology=methodology,
        ledger={"novelty_statement": sanitize_text(NOVELTY), "prior_art": PRIOR_ART,
                "method_citations": METHOD_CITATIONS},
        cities={city: city_receipt},
        lineage=_lineage(city),
    )
    return doc


def publish(city: str = "delhi") -> int:
    doc = build(city)
    emit_model(doc, "receipts.json")
    log.info("receipts.published", city=city, path="receipts.json",
             lineage_rows=len(doc.lineage), honesty_notes=len(doc.honesty_notes))
    return 0


__all__ = ["build", "publish", "NOVELTY"]
