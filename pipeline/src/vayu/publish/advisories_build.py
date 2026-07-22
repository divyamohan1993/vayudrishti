"""Advisories publish: real per-ward citizen advisories (spec 5.5). Owner: vayu-models.

Publish-time templates (LLM-authored at build, runtime LLM-free) selected by ward risk, which
is driven by the real nowcast sub-index. Plain text only, sanitized. en + hi always; regional
(Mumbai mr) when the city config declares it. Emitted via the content model; gate-valid.
"""

from __future__ import annotations

import json

from vayu.cityconfig import load_city
from vayu.logging_setup import get_logger
from vayu.publish.contentmodels import AdvisoriesDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.publish.sanitize import sanitize_text
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("advisories_pub")

_TEXT = {
    "low": {
        "en": "Air quality is acceptable. Sensitive groups should watch for symptoms.",
        "hi": "Vayu gunavatta theek hai. Sanvedansheel logon ko lakshanon par dhyan dena chahiye.",
        "mr": "Havechi gunvatta theek aahe. Samvedansheel vyaktinni lakshanankade laksh dyave.",
    },
    "moderate": {
        "en": "Moderate pollution. Limit prolonged outdoor exertion if you have heart or lung conditions.",
        "hi": "Madhyam pradushan. Hriday ya phephde ki bimari ho to lambe samay tak bahar shram na karein.",
        "mr": "Madhyam pradushan. Hriday kinva phupphusachya samasya asalyas bahup shram taala.",
    },
    "high": {
        "en": "High pollution. Avoid outdoor activity, keep windows shut, use a mask outdoors.",
        "hi": "Uchch pradushan. Bahar ki gatividhi se bachein, khidkiyan band rakhein, bahar mask pahnein.",
        "mr": "Uchch pradushan. Bahercha vyayam taala, khidkya band theva, bahar mask vapara.",
    },
    "severe": {
        "en": "Severe pollution. Stay indoors, run air purifiers, protect children and the elderly.",
        "hi": "Gambhir pradushan. Ghar ke andar rahein, air purifier chalayein, bachchon aur budhon ko bachayein.",
        "mr": "Gambhir pradushan. Gharat raha, air purifier vapara, lahan mule ani vruddhanna japa.",
    },
}


def _risk(subindex: float) -> str:
    if subindex <= 100:
        return "low"
    if subindex <= 200:
        return "moderate"
    if subindex <= 300:
        return "high"
    return "severe"


def build(city: str = "delhi") -> AdvisoriesDoc:
    gen = utc_iso_z(now_utc())
    regional = load_city(city).languages.regional
    nowcast = json.loads((web_data_dir() / city / "nowcast.json").read_text(encoding="utf-8"))

    rows = []
    for w in nowcast["wards"]:
        risk = _risk(float(w["subindex24h"]))
        langs = {"en": sanitize_text(_TEXT[risk]["en"]), "hi": sanitize_text(_TEXT[risk]["hi"])}
        if regional and regional in _TEXT[risk]:
            langs["regional"] = sanitize_text(_TEXT[risk][regional])
        rows.append({"ward_id": w["ward_id"], "risk_level": risk, "langs": langs})

    doc = AdvisoriesDoc(generated_at=gen, wards=rows)
    log.info("advisories_pub.built", city=city, wards=len(rows))
    return doc


def publish(city: str = "delhi") -> int:
    emit_model(build(city), f"{city}/advisories.json")
    log.info("advisories_pub.published", city=city, path=f"{city}/advisories.json")
    return 0


__all__ = ["build", "publish"]
