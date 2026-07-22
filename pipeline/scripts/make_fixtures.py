"""Generate schema-valid, real-grounded FIXTURES for vayu-web (spec 8 fixture protocol).

Bootstrap tool (owner: vayu-models), NOT the real publish path. It writes sample data
to the REAL web/public/data/ paths with ``fixture: true`` so vayu-web can bind
immediately; ``vayu publish`` later overwrites the same paths with real model output
and drops the flag.

Real ingredients (so magnitudes/structure are honest sample data, not invented):
- Real grid origins + real ward_ids/names/centroids from vayu-data's wards.geojson.
- Real Delhi PM2.5 regimes: monsoon "now" (Open-Meteo AQ, Jul-2026, p50~40/p90~108)
  and Nov-2025 winter (OpenAQ S3 Anand Vihar ground truth, p50~158/p90~309).
- Real Delhi GRAP 2025-26 stage dates with CAQM order URLs (public record).
- Real method/prior-art citations for the Intervention Ledger.

Every document is built as a pydantic content model, so a fixture that would fail the
content gate cannot be written. Run:  uv run python scripts/make_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vayu.aqi import breakpoint_table_rows, category_for_index, sub_index
from vayu.cityconfig import load_city
from vayu.constants import ENFORCEMENT_ACTIONS, TIER_CONFIG_TO_MANIFEST
from vayu.grid import enumerate_cells, grid_meta
from vayu.publish.contentmodels import (
    AdvisoriesDoc,
    AttributionDoc,
    EnforcementDoc,
    ForecastDoc,
    InterventionsDoc,
    LedgerDoc,
    ManifestDoc,
    NowcastDoc,
    ReceiptsDoc,
    ReplayIndexDoc,
)
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.sanitize import sanitize_text

UTC = timezone.utc
NOW = datetime(2026, 7, 22, 6, 0, 0, tzinfo=UTC)
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- deterministic noise

def unit_noise(key: str) -> float:
    """Deterministic pseudo-random in [0,1) from a string key (stable fixtures)."""
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    return int(h, 16) / 0xFFFFFFFF


def signed_noise(key: str) -> float:
    return 2.0 * unit_noise(key) - 1.0


# ---------------------------------------------------------------- PM2.5 spatial field

# Real Delhi CPCB monitor coordinates (for confidence-by-station-distance).
DELHI_STATIONS = [
    (28.6468, 77.3160),  # Anand Vihar (loc 235)
    (28.6740, 77.1310),  # Punjabi Bagh (loc 50)
    (28.5632, 77.1866),  # R K Puram (loc 17)
    (28.5504, 77.2159),  # Sirifort (loc 5586)
    (28.6390, 77.1506),  # Pusa (loc 5404)
]

# Regime bases (real-grounded 24h-mean citywide level, ug/m3) and per-city hotspots.
# hotspot = (lat, lon, amplitude_ugm3, radius_km).
CITY_FIELD = {
    "delhi": {
        "base_now": 92.0,   # moderately polluted post-rain day, within real monsoon range
        "base_winter": 178.0,  # real Nov-2025 Anand Vihar mean 177
        "hotspots": [
            (28.6468, 77.3160, 55.0, 7.0),   # Anand Vihar (industrial/traffic, E)
            (28.68, 77.11, 35.0, 6.0),       # NW industrial belt
            (28.51, 77.28, 30.0, 6.0),       # Okhla (SE industrial)
        ],
        "stations": DELHI_STATIONS,
    },
    "mumbai": {
        "base_now": 58.0, "base_winter": 58.0,
        "hotspots": [(19.05, 72.90, 30.0, 5.0), (19.18, 72.95, 22.0, 5.0)],
        "stations": [(19.0596, 72.8295), (19.1550, 72.8490), (19.0176, 72.8562)],
    },
    "bengaluru": {
        "base_now": 44.0, "base_winter": 44.0,
        "hotspots": [(12.98, 77.60, 22.0, 4.0), (12.91, 77.64, 18.0, 4.0)],
        "stations": [(12.9716, 77.5946), (13.0298, 77.5679)],
    },
}


def km(lat1, lon1, lat2, lon2) -> float:
    dlat = (lat1 - lat2) * 111.0
    dlon = (lon1 - lon2) * 111.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


def pm_24h_mean(city: str, lat: float, lon: float, key: str, winter: bool) -> float:
    cfg = CITY_FIELD[city]
    base = cfg["base_winter"] if winter else cfg["base_now"]
    scale = base / cfg["base_now"]  # scale hotspots with the regime
    v = base
    for hlat, hlon, amp, radius in cfg["hotspots"]:
        d = km(lat, lon, hlat, hlon)
        v += amp * scale * math.exp(-(d * d) / (2 * radius * radius))
    v *= 1.0 + 0.13 * signed_noise(key)
    return max(4.0, v)


def confidence_for(city: str, lat: float, lon: float, key: str) -> str:
    stations = CITY_FIELD[city]["stations"]
    nearest = min(km(lat, lon, s[0], s[1]) for s in stations)
    if nearest <= 3.0:
        return "high"
    if nearest <= 9.0:
        return "med" if unit_noise(key) > 0.15 else "high"
    return "low" if unit_noise(key) > 0.3 else "med"


def cell_values(city: str, lat: float, lon: float, key: str, winter: bool) -> dict:
    mean24 = pm_24h_mean(city, lat, lon, key, winter)
    p50 = round(mean24 * (0.88 + 0.12 * unit_noise(key + "p50")), 1)
    p90 = round(p50 * (1.35 + 0.3 * unit_noise(key + "p90")), 1)
    si = sub_index("pm25", mean24)
    return {
        "pm25_p50": p50,
        "pm25_p90": max(p90, p50),
        "subindex24h": si,
        "category": category_for_index(si),
    }


# ---------------------------------------------------------------- wards loader

def load_wards(city: str) -> list[dict]:
    """Real ward_id + name + representative (lat,lon) from vayu-data's wards.geojson."""
    path = web_data_dir() / city / "wards.geojson"
    gj = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict] = []
    for feat in gj["features"]:
        props = feat.get("properties", {})
        wid = props.get("ward_id")
        if not wid:
            continue
        lat, lon = polygon_repr_point(feat.get("geometry", {}))
        out.append({"ward_id": wid, "name": sanitize_text(str(props.get("name") or wid)), "lat": lat, "lon": lon})
    return out


def polygon_repr_point(geom: dict) -> tuple[float, float]:
    """Mean of exterior-ring vertices (Polygon or first MultiPolygon part)."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return (0.0, 0.0)
    ring = coords[0] if gtype == "Polygon" else coords[0][0]
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return (round(sum(lats) / len(lats), 5), round(sum(lons) / len(lons), 5))


# ---------------------------------------------------------------- builders

def build_nowcast(city: str, wards: list[dict], winter: bool = False) -> NowcastDoc:
    meta = grid_meta(load_city(city).bbox_tuple)
    grid = []
    for row, col, clat, clon in enumerate_cells(load_city(city).bbox_tuple):
        key = f"{city}_{row}_{col}"
        v = cell_values(city, clat, clon, key, winter)
        grid.append({"cell_id": key, "row": row, "col": col, **v})
    ward_rows = []
    for w in wards:
        key = f"{w['ward_id']}_nc"
        v = cell_values(city, w["lat"], w["lon"], key, winter)
        ward_rows.append({
            "ward_id": w["ward_id"], "name": w["name"], **v,
            "confidence": confidence_for(city, w["lat"], w["lon"], key),
        })
    return NowcastDoc(
        generated_at=NOW_ISO, fixture=True,
        grid_meta={"lat0": meta.lat0, "lon0": meta.lon0, "cell_deg": meta.cell_deg, "crs": meta.crs},
        grid=grid, wards=ward_rows,
    )


def build_forecast(city: str, wards: list[dict], winter: bool = False) -> ForecastDoc:
    ward_rows = []
    for w in wards:
        series = []
        for h in (24, 48, 72):
            key = f"{w['ward_id']}_f{h}"
            # forecast drifts up slightly with horizon + widening uncertainty
            mean24 = pm_24h_mean(city, w["lat"], w["lon"], key, winter) * (1.0 + 0.04 * (h // 24))
            p50 = round(mean24 * 0.95, 1)
            p90 = round(p50 * (1.4 + 0.06 * (h // 24) + 0.2 * unit_noise(key)), 1)
            si = sub_index("pm25", mean24)
            conf = ("high", "med", "low")[h // 24 - 1]
            series.append({
                "h": h, "pm25_p50": p50, "pm25_p90": max(p90, p50),
                "subindex24h": si, "category": category_for_index(si), "confidence": conf,
            })
        ward_rows.append({"ward_id": w["ward_id"], "name": w["name"], "series": series})
    return ForecastDoc(generated_at=NOW_ISO, fixture=True, horizons_h=[24, 48, 72], wards=ward_rows)


_SHARE_PROFILES = [
    # (traffic, industry, biomass, dust, residential_other) archetypes
    (0.34, 0.14, 0.08, 0.30, 0.14),  # traffic corridor
    (0.18, 0.40, 0.10, 0.20, 0.12),  # industrial
    (0.16, 0.12, 0.34, 0.22, 0.16),  # biomass-influenced (NW)
    (0.20, 0.14, 0.10, 0.42, 0.14),  # dust-heavy
]


def build_attribution(city: str, wards: list[dict]) -> AttributionDoc:
    rows = []
    for w in wards:
        prof = _SHARE_PROFILES[int(unit_noise(w["ward_id"] + "prof") * len(_SHARE_PROFILES)) % len(_SHARE_PROFILES)]
        jitter = [max(0.02, p * (1 + 0.15 * signed_noise(w["ward_id"] + str(i)))) for i, p in enumerate(prof)]
        total = sum(jitter)
        shares = {k: round(v / total, 3) for k, v in zip(
            ("traffic", "industry", "biomass", "dust", "residential_other"), jitter)}
        # fix rounding drift onto the largest share
        drift = round(1.0 - sum(shares.values()), 3)
        kmax = max(shares, key=lambda k: shares[k])
        shares[kmax] = round(shares[kmax] + drift, 3)
        dom = max(shares, key=lambda k: shares[k])
        conf = "high" if shares[dom] > 0.38 else ("med" if shares[dom] > 0.30 else "low")
        note = sanitize_text(
            f"CPF wind-sector peak + land-use heuristic; dominant {dom} ({int(shares[dom]*100)}%). "
            "Labeled estimate, not measured emissions."
        )
        rows.append({"ward_id": w["ward_id"], "shares": shares, "confidence": conf, "method_notes": note})
    return AttributionDoc(generated_at=NOW_ISO, fixture=True, wards=rows)


_ACTION_BY_SOURCE = {
    "dust": "deploy_water_sprinkling",
    "traffic": "reroute_divert_heavy_traffic",
    "industry": "inspect_industrial_emissions",
    "biomass": "ban_open_biomass_burning",
    "residential_other": "issue_public_health_advisory",
    "mixed": "issue_public_health_advisory",
}


def build_enforcement(city: str, wards: list[dict], winter: bool = False) -> EnforcementDoc:
    items = []
    for w in wards:
        key = f"{w['ward_id']}_enf"
        mean24 = pm_24h_mean(city, w["lat"], w["lon"], key, winter)
        si = sub_index("pm25", mean24)
        persistence = int(2 + unit_noise(key + "p") * 20)
        exceed = round(min(100.0, max(0.0, (si - 100) / 4.0 + 20 * unit_noise(key + "e"))), 1)
        # trend: last 24 pseudo-hours around the mean
        trend = [round(max(4.0, mean24 * (0.8 + 0.4 * unit_noise(f"{key}t{i}"))), 1) for i in range(24)]
        prof_idx = int(unit_noise(w["ward_id"] + "prof") * len(_SHARE_PROFILES)) % len(_SHARE_PROFILES)
        source = ("traffic", "industry", "biomass", "dust")[prof_idx]
        priority = round(min(100.0, 0.15 * si + 1.5 * persistence + 0.3 * exceed), 1)
        conf = "high" if priority > 55 else ("med" if priority > 30 else "low")
        items.append({
            "ward_id": w["ward_id"], "source_label": source, "confidence": conf,
            "priority_score": priority,
            "evidence": {"trend_72h": trend, "persistence_days": persistence, "exceedance_pct": exceed},
            "action": _ACTION_BY_SOURCE.get(source, "monitor_no_action"),
        })
    items.sort(key=lambda it: it["priority_score"], reverse=True)
    return EnforcementDoc(generated_at=NOW_ISO, fixture=True, ranked=items)


_RISK_TEXT = {
    "low": {
        "en": "Air quality is acceptable. Sensitive groups should watch for symptoms.",
        "hi": "Vayu gunavatta theek hai. Sanvedansheel logon ko lakshanon par dhyan dena chahiye.",
    },
    "moderate": {
        "en": "Moderate pollution. Limit prolonged outdoor exertion if you have heart or lung conditions.",
        "hi": "Madhyam pradushan. Hriday ya phephde ki bimari ho to lambe samay tak bahar shram na karein.",
    },
    "high": {
        "en": "High pollution. Avoid outdoor activity, keep windows shut, use a mask outdoors.",
        "hi": "Uchch pradushan. Bahar ki gatividhi se bachein, khidkiyan band rakhein, bahar mask pahnein.",
    },
    "severe": {
        "en": "Severe pollution. Stay indoors, run air purifiers, protect children and the elderly.",
        "hi": "Gambhir pradushan. Ghar ke andar rahein, air purifier chalayein, bachchon aur budhon ko bachayein.",
    },
}
_RISK_MR = {
    "low": "Havechi gunvatta theek aahe. Samvedansheel vyaktinni lakshanankade laksh dyave.",
    "moderate": "Madhyam pradushan. Hriday kinva phupphusachya samasya asalyas bahup shram taala.",
    "high": "Uchch pradushan. Bahercha vyayam taala, khidkya band theva, bahar mask vapara.",
    "severe": "Gambhir pradushan. Gharat raha, air purifier vapara, lahan mule ani vruddhanna japa.",
}


def risk_from_subindex(si: int) -> str:
    if si <= 100:
        return "low"
    if si <= 200:
        return "moderate"
    if si <= 300:
        return "high"
    return "severe"


def build_advisories(city: str, wards: list[dict], winter: bool = False) -> AdvisoriesDoc:
    regional = load_city(city).languages.regional
    rows = []
    for w in wards:
        key = f"{w['ward_id']}_adv"
        mean24 = pm_24h_mean(city, w["lat"], w["lon"], key, winter)
        si = sub_index("pm25", mean24)
        risk = risk_from_subindex(si)
        langs = {"en": sanitize_text(_RISK_TEXT[risk]["en"]), "hi": sanitize_text(_RISK_TEXT[risk]["hi"])}
        if regional == "mr":
            langs["regional"] = sanitize_text(_RISK_MR[risk])
        rows.append({"ward_id": w["ward_id"], "risk_level": risk, "langs": langs})
    return AdvisoriesDoc(generated_at=NOW_ISO, fixture=True, wards=rows)


# ---------------------------------------------------------------- Intervention Ledger

CAQM = "https://caqm.nic.in/WriteReadData/LINKS"
GRAP_CALENDAR = [
    ("GRAP-I", "2025-10-14 08:00", "2025-11-11 00:00", f"{CAQM}/grap-stage-1-14102025.pdf"),
    ("GRAP-II", "2025-10-19 08:00", "2025-11-11 00:00", f"{CAQM}/grap-stage-2-19102025.pdf"),
    ("GRAP-III", "2025-11-11 08:00", "2025-11-26 00:00", f"{CAQM}/grap-stage-3-invocation-11112025.pdf"),
    ("GRAP-IV", "2025-12-13 09:00", "2025-12-24 21:00", f"{CAQM}/grap-stage-4-invocation-13122025.pdf"),
    ("GRAP-IV", "2026-01-16 08:00", "2026-01-20 12:00", f"{CAQM}/grap-stage-4-invocation-16012026.pdf"),
]
IST = timezone(timedelta(hours=5, minutes=30))


def _ist_to_utc_iso(s: str) -> str:
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    return iso(dt)


def build_interventions() -> InterventionsDoc:
    calendar = [
        {"stage": stg, "start_utc": _ist_to_utc_iso(start),
         "end_utc": (_ist_to_utc_iso(end) if end else None), "source_url": url}
        for stg, start, end, url in GRAP_CALENDAR
    ]
    # Daily ribbon series over the GRAP window: raw (weather-noisy) vs normalized (deweathered).
    series = []
    start = datetime(2025, 11, 1, tzinfo=UTC)
    grap_starts = [datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=IST).astimezone(UTC)
                   for _, s, _, _ in GRAP_CALENDAR]
    for d in range(92):
        day = start + timedelta(days=d)
        # seasonal baseline peaks mid-winter, plus response dips after each GRAP start
        seasonal = 150 + 70 * math.exp(-((d - 40) ** 2) / (2 * 26 ** 2))
        dip = 0.0
        for gs in grap_starts:
            days_since = (day - gs).total_seconds() / 86400.0
            if 0 <= days_since <= 12:
                dip += 22 * math.exp(-days_since / 6.0)
        normalized = max(20.0, seasonal - dip)
        weather = 40 * signed_noise(f"wx{d}") + 18 * math.sin(d / 3.0)
        raw = max(15.0, normalized + weather)
        series.append({
            "ts_utc": iso(day),
            "pm25_raw": round(raw, 1),
            "pm25_normalized": round(normalized, 1),
            "pm25_normalized_p90": round(normalized * 1.35, 1),
        })
    # Event-study effects per stage transition (weather-normalized), block-bootstrap CI.
    effects = [
        {"stage_transition": "GRAP-III invoked (2025-11-11)", "effect_ugm3": -18.4,
         "ci_low": -29.1, "ci_high": -7.9, "placebo_pass": True, "n_days": 14,
         "method_notes": sanitize_text("Event-study on deweathered series; placebo vs matched high-PM non-intervention days passed; block-bootstrap 1000x.")},
        {"stage_transition": "GRAP-IV invoked (2025-12-13)", "effect_ugm3": -31.7,
         "ci_low": -47.2, "ci_high": -15.9, "placebo_pass": True, "n_days": 11,
         "method_notes": sanitize_text("Strongest detected effect; placebo passed; block-bootstrap CI.")},
        {"stage_transition": "GRAP-IV invoked (2026-01-16)", "effect_ugm3": -6.1,
         "ci_low": -17.8, "ci_high": 6.4, "placebo_pass": False, "n_days": 4,
         "method_notes": sanitize_text("CI straddles 0 and placebo failed: no detectable effect (accountability finding), short window.")},
    ]
    return InterventionsDoc(generated_at=NOW_ISO, fixture=True, calendar=calendar, series=series, effects=effects)


LEDGER_CITATIONS = [
    {"label": "Grange & Carslaw 2019, meteorological normalisation, Sci. Total Environ.",
     "url": "https://doi.org/10.1016/j.scitotenv.2018.10.344"},
    {"label": "Burnett et al. 2018, GEMM exposure-response, PNAS",
     "url": "https://doi.org/10.1073/pnas.1803222115"},
    {"label": "CPCB National Air Quality Index methodology",
     "url": "https://cpcb.nic.in/national-air-quality-index/"},
]
LEDGER_ASSUMPTIONS = [
    "Single-winter scope (2025-26); no multi-season generalization.",
    "GEMM hazard ratios applied to adult (25+) population; India adult fraction ~0.66 (documented).",
    "Weather normalization removes meteorological confounding but not co-emitted-source confounding.",
    "Counterfactual timing assumes the same emission response shifted in time; not a re-simulation of chemistry.",
]


def build_ledger(wards: list[dict]) -> LedgerDoc:
    ward_rows = []
    tot_exp = 0.0
    tot_deaths = 0.0
    for w in wards:
        key = f"{w['ward_id']}_led"
        # effect stronger in NW/E (stubble + industry) — proxy by hotspot proximity
        base_effect = -8.0 - 22.0 * unit_noise(key + "eff")
        eff = round(base_effect, 1)
        eff_lo = round(eff - (4 + 8 * unit_noise(key + "lo")), 1)
        eff_hi = round(min(-0.5, eff + (3 + 6 * unit_noise(key + "hi"))), 1)
        # avoided exposure (person-ug/m3-hours) and deaths scale with |effect| and a pop proxy
        pop_proxy = 8000 + 90000 * unit_noise(key + "pop")
        avoided_exp = round(abs(eff) * pop_proxy * 24 * 30 / 1e6, 2)  # scaled units
        deaths = round(abs(eff) * pop_proxy * 8.5e-7, 3)
        d_lo = round(deaths * 0.55, 3)
        d_hi = round(deaths * 1.7, 3)
        tot_exp += avoided_exp
        tot_deaths += deaths
        ward_rows.append({
            "ward_id": w["ward_id"], "avoided_exposure_pugh": avoided_exp,
            "avoided_deaths": deaths, "ci_low": d_lo, "ci_high": d_hi,
            "effect_ugm3": eff, "effect_ci_low": min(eff_lo, eff), "effect_ci_high": max(eff_hi, eff),
        })
    totals = {
        "avoided_exposure_pugh": round(tot_exp, 1),
        "avoided_deaths": round(tot_deaths, 1),
        "ci_low": round(tot_deaths * 0.7, 1),   # combined CI narrower than naive sum
        "ci_high": round(tot_deaths * 1.4, 1),
    }
    counterfactuals = [
        {"scenario": "Stage III 72h earlier", "shift_hours": -72, "delta_exposure": round(tot_exp * 0.22, 1),
         "delta_deaths": round(tot_deaths * 0.20, 2), "ci_low": round(tot_deaths * 0.10, 2), "ci_high": round(tot_deaths * 0.33, 2)},
        {"scenario": "Stage III 48h earlier", "shift_hours": -48, "delta_exposure": round(tot_exp * 0.15, 1),
         "delta_deaths": round(tot_deaths * 0.13, 2), "ci_low": round(tot_deaths * 0.06, 2), "ci_high": round(tot_deaths * 0.22, 2)},
        {"scenario": "Stage III 24h earlier", "shift_hours": -24, "delta_exposure": round(tot_exp * 0.07, 1),
         "delta_deaths": round(tot_deaths * 0.06, 2), "ci_low": round(tot_deaths * 0.02, 2), "ci_high": round(tot_deaths * 0.11, 2)},
    ]
    return LedgerDoc(
        generated_at=NOW_ISO, fixture=True, totals=totals, wards=ward_rows,
        counterfactuals=counterfactuals, citations=LEDGER_CITATIONS, assumptions=LEDGER_ASSUMPTIONS,
    )


# ---------------------------------------------------------------- replay (Nov-2025)

REPLAY_DATES = ["2025-11-08", "2025-11-11", "2025-11-14", "2025-11-19", "2025-11-24"]


def build_replay(city: str, wards: list[dict]) -> tuple[ReplayIndexDoc, list[tuple[str, NowcastDoc, ForecastDoc]]]:
    days = []
    for d in REPLAY_DATES:
        nc = build_nowcast(city, wards, winter=True)
        fc = build_forecast(city, wards, winter=True)
        gen = f"{d}T06:00:00Z"
        nc = nc.model_copy(update={"generated_at": gen})
        fc = fc.model_copy(update={"generated_at": gen})
        days.append((d, nc, fc))
    index = ReplayIndexDoc(
        city=city, generated_at=NOW_ISO, fixture=True,
        window={"start": REPLAY_DATES[0], "end": REPLAY_DATES[-1]}, dates=REPLAY_DATES,
        note=sanitize_text("Out-of-fold predictions only; embargo at least horizon plus 168h. Nov-2025 held-out test window."),
    )
    return index, days


# ---------------------------------------------------------------- manifest + receipts

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


def build_manifest(cities: dict[str, dict]) -> ManifestDoc:
    entries = []
    for slug, info in cities.items():
        cfg = load_city(slug)
        tier = TIER_CONFIG_TO_MANIFEST.get(cfg.tier, cfg.tier)
        langs = list(dict.fromkeys(cfg.languages.primary + ([cfg.languages.regional] if cfg.languages.regional else [])))
        entries.append({
            "id": slug, "name": cfg.name, "tier": tier,
            "centroid": {"lat": cfg.centroid[0], "lon": cfg.centroid[1]},
            "bbox": list(cfg.bbox), "languages": langs,
            "files": info["files"], "fixture": True, "generated_at": NOW_ISO,
        })
    return ManifestDoc(generated_at=NOW_ISO, fixture=True, sat_numeric=False, cities=entries)


def build_receipts() -> ReceiptsDoc:
    delhi = {
        "nowcast_cv": {
            "baseline": "IDW",
            "buckets": [
                {"dist_km": 1.0, "model_rmse": 12.4, "idw_rmse": 15.1, "n": 640},
                {"dist_km": 2.0, "model_rmse": 16.9, "idw_rmse": 22.7, "n": 512},
                {"dist_km": 3.0, "model_rmse": 21.2, "idw_rmse": 31.4, "n": 388},
                {"dist_km": 5.0, "model_rmse": 27.8, "idw_rmse": 44.9, "n": 274},
            ],
        },
        "forecast": {
            "24": {"rmse": 34.1, "mae": 24.8, "persistence_rmse": 41.0, "seasonal_naive_rmse": 58.3, "skill_pct": 16.8, "n": 2100, "embargo_h": 192},
            "48": {"rmse": 45.6, "mae": 33.9, "persistence_rmse": 47.1, "seasonal_naive_rmse": 60.2, "skill_pct": 3.2, "n": 2040, "embargo_h": 216},
            "72": {"rmse": 53.9, "mae": 40.7, "persistence_rmse": 52.2, "seasonal_naive_rmse": 61.5, "skill_pct": -3.3, "n": 1980, "embargo_h": 240},
        },
        "attribution_directional_checks": [
            {"check_name": "NW stubble bearing in season", "expected": "300-330 deg (NW)", "observed": "315 deg", "pass": True,
             "notes": sanitize_text("CPF high-PM bearing aligns with Punjab/Haryana stubble belt in Nov.")},
            {"check_name": "Anand Vihar industrial/traffic sector", "expected": "E-SE named industrial area", "observed": "ESE peak", "pass": True},
        ],
        "ablation": {"note": sanitize_text("With vs without GEE numeric satellite features (S5P NO2 + MAIAC AOD)."),
                     "metric": "nowcast RMSE (ug/m3)", "with_sat": 21.2, "without_sat": 23.9, "delta_pct": -11.3},
        "intervention_assumptions": LEDGER_ASSUMPTIONS,
    }
    methodology = {
        "headline_label": "PM2.5 sub-index (24h)",
        "severe_note": sanitize_text(
            "CPCB defines no upper concentration for the Severe band. VayuDrishti continues the "
            "Very Poor slope so the sub-index reaches 500 at 380 ug/m3 for PM2.5, then caps at 500. "
            "Raw PM2.5 is always shown alongside."),
        "aqi_breakpoints": breakpoint_table_rows(),
    }
    honesty = [
        "Fixtures are sample data (fixture=true); real numbers replace them at handoff.",
        "Single-winter training window (Feb-2025 onward); no multi-season generalization claims.",
        "48h/72h forecast skill reported honestly; 72h skill may be at or below 0 versus persistence.",
        "Attribution is a labeled estimate (CPF + heuristics), never measured emissions.",
        "Intervention effects with CI spanning 0 are reported as null accountability findings.",
    ]
    lineage = [
        {"source": "OpenAQ S3 archive (CPCB hourly)", "base_url": "https://openaq-data-archive.s3.amazonaws.com",
         "resource_id": "records/csv.gz/locationid=235", "fetched_at": NOW_ISO, "rows": 445},
        {"source": "Open-Meteo Air Quality", "base_url": "https://air-quality-api.open-meteo.com/v1/air-quality",
         "resource_id": "delhi-centroid", "fetched_at": NOW_ISO, "rows": 576},
        {"source": "CAQM GRAP orders (public record)", "base_url": "https://caqm.nic.in/WriteReadData/LINKS",
         "resource_id": "grap-2025-26-orders", "fetched_at": NOW_ISO, "rows": 5},
    ]
    return ReceiptsDoc(
        generated_at=NOW_ISO, fixture=True, honesty_notes=honesty, methodology=methodology,
        ledger={"novelty_statement": sanitize_text(NOVELTY), "prior_art": PRIOR_ART, "method_citations": METHOD_CITATIONS},
        cities={"delhi": delhi}, lineage=lineage,
    )


# ---------------------------------------------------------------- driver

def main() -> int:
    root = web_data_dir()
    written: list[str] = []

    delhi_wards = load_wards("delhi")
    mumbai_wards = load_wards("mumbai")
    blr_wards = load_wards("bengaluru")

    # Delhi = deep (all surfaces)
    emit_model(build_nowcast("delhi", delhi_wards), "delhi/nowcast.json"); written.append("delhi/nowcast.json")
    emit_model(build_forecast("delhi", delhi_wards), "delhi/forecast.json"); written.append("delhi/forecast.json")
    emit_model(build_attribution("delhi", delhi_wards), "delhi/attribution.json"); written.append("delhi/attribution.json")
    emit_model(build_enforcement("delhi", delhi_wards), "delhi/enforcement.json"); written.append("delhi/enforcement.json")
    emit_model(build_advisories("delhi", delhi_wards), "delhi/advisories.json"); written.append("delhi/advisories.json")
    emit_model(build_interventions(), "delhi/interventions.json"); written.append("delhi/interventions.json")
    emit_model(build_ledger(delhi_wards), "delhi/ledger.json"); written.append("delhi/ledger.json")
    r_index, r_days = build_replay("delhi", delhi_wards)
    emit_model(r_index, "delhi/replay/index.json"); written.append("delhi/replay/index.json")
    for d, nc, fc in r_days:
        emit_model(nc, f"delhi/replay/{d}/nowcast.json")
        emit_model(fc, f"delhi/replay/{d}/forecast.json")
        written.append(f"delhi/replay/{d}/*")

    # Mumbai = standard (nowcast + forecast + advisories)
    emit_model(build_nowcast("mumbai", mumbai_wards), "mumbai/nowcast.json"); written.append("mumbai/nowcast.json")
    emit_model(build_forecast("mumbai", mumbai_wards), "mumbai/forecast.json"); written.append("mumbai/forecast.json")
    emit_model(build_advisories("mumbai", mumbai_wards), "mumbai/advisories.json"); written.append("mumbai/advisories.json")

    # Bengaluru = config-only (nowcast + forecast + advisories, live)
    emit_model(build_nowcast("bengaluru", blr_wards), "bengaluru/nowcast.json"); written.append("bengaluru/nowcast.json")
    emit_model(build_forecast("bengaluru", blr_wards), "bengaluru/forecast.json"); written.append("bengaluru/forecast.json")
    emit_model(build_advisories("bengaluru", blr_wards), "bengaluru/advisories.json"); written.append("bengaluru/advisories.json")

    # Global manifest + receipts
    cities = {
        "delhi": {"files": {
            "nowcast": "delhi/nowcast.json", "forecast": "delhi/forecast.json",
            "attribution": "delhi/attribution.json", "enforcement": "delhi/enforcement.json",
            "advisories": "delhi/advisories.json", "wards": "delhi/wards.geojson",
            "replay_index": "delhi/replay/index.json", "interventions": "delhi/interventions.json",
            "ledger": "delhi/ledger.json"}},
        "mumbai": {"files": {
            "nowcast": "mumbai/nowcast.json", "forecast": "mumbai/forecast.json",
            "advisories": "mumbai/advisories.json", "wards": "mumbai/wards.geojson"}},
        "bengaluru": {"files": {
            "nowcast": "bengaluru/nowcast.json", "forecast": "bengaluru/forecast.json",
            "advisories": "bengaluru/advisories.json", "wards": "bengaluru/wards.geojson"}},
    }
    emit_model(build_manifest(cities), "manifest.json"); written.append("manifest.json")
    emit_model(build_receipts(), "receipts.json"); written.append("receipts.json")

    print(f"Wrote {len(written)} fixture artifacts under {root}:")
    for w in written:
        print("  ", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
