"""Intervention Ledger publish: interventions.json + ledger.json (spec 13, acc 15/16/17).

Assembles the real flagship artifacts from the deweathered series (Grange & Carslaw),
the event-study effects (with placebo + block-bootstrap CI), the real CAQM GRAP calendar,
and GEMM mortality (Burnett 2018) weighted by WorldPop ward population. Emits via the
pydantic content models so output is gate-valid by construction; fixture flag dropped
(this is real data).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from vayu.logging_setup import get_logger
from vayu.models import deweather, gemm, interventions
from vayu.models.run import load_feature_store
from vayu.publish.contentmodels import InterventionsDoc, LedgerDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.sanitize import sanitize_text
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("ledger")

CITATIONS = [
    {"label": "Grange & Carslaw 2019, meteorological normalisation, Sci. Total Environ.",
     "url": "https://doi.org/10.1016/j.scitotenv.2018.10.344"},
    {"label": "Burnett et al. 2018, GEMM exposure-response, PNAS",
     "url": "https://doi.org/10.1073/pnas.1803222115"},
    {"label": "CAQM GRAP orders, winter 2025-26 (public record)",
     "url": "https://caqm.nic.in/index1.aspx?lsid=4168&lev=2&lid=4171&langid=1"},
]
ASSUMPTIONS = [
    "Single-winter scope (2025-26); no multi-season generalization.",
    "GEMM NCD+LRI (China-inclusive): theta=0.143, alpha=1.6, mu=15.5, nu=36.8; TMREL 2.4 ug/m3 (Burnett 2018).",
    "India adult (25+) baseline mortality 9.0 per 1000 per year; adult fraction 0.66 (documented; per-ward age structure unavailable).",
    "WorldPop 2020 ward population.",
    "Per-ward effect = city event-study effect scaled by the ward's PM2.5 exposure share; wards without a monitor use the city-mean exposure (labeled estimate).",
    "Weather normalization removes meteorological confounding, not co-emitted-source confounding.",
    "Counterfactual timing is a linear extrapolation of the estimated per-hour benefit, not a re-simulation of chemistry.",
]


def _ward_population(city: str) -> dict[str, float]:
    gj = json.loads((web_data_dir() / city / "wards.geojson").read_text(encoding="utf-8"))
    return {f["properties"]["ward_id"]: float(f["properties"].get("population") or 0.0)
            for f in gj["features"] if f.get("properties", {}).get("ward_id")}


def _grap_active_hours(calendar: list[dict]) -> float:
    total = 0.0
    for e in calendar:
        if e["stage"] in ("GRAP-III", "GRAP-IV") and e["end_utc"] is not None:
            total += (e["end_utc"] - e["start_utc"]).total_seconds() / 3600.0
    return max(total, 24.0)


def build(city: str = "delhi", *, n_samples: int = 200, seed: int = 0) -> tuple[InterventionsDoc, LedgerDoc]:
    df = load_feature_store(city)
    _, calendar = interventions.load_grap_calendar(city)
    gen = utc_iso_z(now_utc())
    log.info("ledger.start", city=city, rows=len(df))

    # --- interventions.json: ribbon series + event-study effects ---
    daily = deweather.city_normalised_daily(df, n_samples=n_samples, seed=seed)
    series = [{"ts_utc": f"{row.date}T00:00:00Z",
               "pm25_raw": round(float(row.pm25_raw), 1),
               "pm25_normalized": round(float(row.pm25_normalized), 1)}
              for row in daily.itertuples()]
    effects = interventions.build_effects(daily)
    calendar_out = [{"stage": e["stage"], "start_utc": utc_iso_z(e["start_utc"]),
                     "end_utc": (utc_iso_z(e["end_utc"]) if e["end_utc"] else None),
                     "source_url": e["source_url"]} for e in calendar]
    interventions_doc = InterventionsDoc(generated_at=gen, calendar=calendar_out,
                                         series=series, effects=effects)
    log.info("ledger.effects", city=city, n_effects=len(effects),
             effects=[(e["stage_transition"], e["effect_ugm3"], e["placebo_pass"]) for e in effects])

    # --- ledger.json: per-ward GEMM mortality from the season effect ---
    pop = _ward_population(city)
    ward_pm = df.groupby("ward_id")["pm25"].mean().to_dict()
    city_pm = float(df["pm25"].mean())
    grap_hours = _grap_active_hours(calendar)

    passing = [e for e in effects if e["placebo_pass"]] or effects
    season_eff = float(np.mean([e["effect_ugm3"] for e in passing]))       # negative = reduction
    season_lo = float(np.mean([e["ci_low"] for e in passing]))
    season_hi = float(np.mean([e["ci_high"] for e in passing]))

    ward_rows, tot_exp, tot_deaths, tot_lo, tot_hi = [], 0.0, 0.0, 0.0, 0.0
    for ward_id, population in pop.items():
        pm = float(ward_pm.get(ward_id, city_pm))
        scale = max(0.2, pm / city_pm)
        eff = round(season_eff * scale, 1)
        eff_lo, eff_hi = round(season_lo * scale, 1), round(season_hi * scale, 1)
        deaths = gemm.avoided_deaths(pm, pm - eff, population)          # eff<0 -> counterfactual higher
        d_lo = gemm.avoided_deaths(pm, pm - eff_lo, population)
        d_hi = gemm.avoided_deaths(pm, pm - eff_hi, population)
        d_lo, d_hi = sorted((d_lo, d_hi))
        avoided_exp = round(gemm.avoided_exposure_pugh(eff, population, grap_hours), 1)
        deaths, d_lo, d_hi = round(deaths, 3), round(d_lo, 3), round(d_hi, 3)
        ward_rows.append({
            "ward_id": ward_id, "avoided_exposure_pugh": avoided_exp,
            "avoided_deaths": deaths, "ci_low": min(d_lo, deaths), "ci_high": max(d_hi, deaths),
            "effect_ugm3": eff, "effect_ci_low": min(eff_lo, eff), "effect_ci_high": max(eff_hi, eff),
        })
        tot_exp += avoided_exp
        tot_deaths += deaths
        tot_lo += min(d_lo, deaths)
        tot_hi += max(d_hi, deaths)

    totals = {"avoided_exposure_pugh": round(tot_exp, 1), "avoided_deaths": round(tot_deaths, 1),
              "ci_low": round(tot_lo, 1), "ci_high": round(tot_hi, 1)}
    counterfactuals = []
    for shift in (-72, -48, -24):
        frac = abs(shift) / grap_hours
        counterfactuals.append({
            "scenario": f"Act {abs(shift)}h earlier", "shift_hours": shift,
            "delta_exposure": round(tot_exp * frac, 1),
            "delta_deaths": round(tot_deaths * frac, 2),
            "ci_low": round(tot_lo * frac, 2), "ci_high": round(tot_hi * frac, 2),
        })

    ledger_doc = LedgerDoc(generated_at=gen, totals=totals, wards=ward_rows,
                           counterfactuals=counterfactuals,
                           citations=[{"label": sanitize_text(c["label"]), "url": c["url"]} for c in CITATIONS],
                           assumptions=[sanitize_text(a) for a in ASSUMPTIONS])
    log.info("ledger.totals", city=city, **totals, wards=len(ward_rows))
    return interventions_doc, ledger_doc


def publish(city: str = "delhi", **kw) -> int:
    interventions_doc, ledger_doc = build(city, **kw)
    emit_model(interventions_doc, f"{city}/interventions.json")
    emit_model(ledger_doc, f"{city}/ledger.json")
    log.info("ledger.published", city=city,
             paths=[f"{city}/interventions.json", f"{city}/ledger.json"])
    return 0


__all__ = ["build", "publish", "CITATIONS", "ASSUMPTIONS"]
