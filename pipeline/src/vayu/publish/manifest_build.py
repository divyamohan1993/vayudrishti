"""Publish the real manifest.json (spec 8). Owner: vayu-models.

Assembles the global entry index from actual published file state: per-city file keys for
whatever exists on disk (incl. vayu-data's roads/fires geojson and vayu-agents' briefs),
per-city fixture flag = true iff any of that city's model JSONs still carries fixture:true,
and the global agentlog path. No model compute; gate-valid by construction. This is the
manifest half of the publish-orchestration flip.
"""

from __future__ import annotations

import json

from vayu.cityconfig import all_slugs, load_city
from vayu.constants import TIER_CONFIG_TO_MANIFEST
from vayu.logging_setup import get_logger
from vayu.publish.contentmodels import ManifestDoc
from vayu.publish.emit import emit_model, web_data_dir
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("manifest")

# key -> relative filename under {city}/. Included only when present on disk.
_PER_CITY = {
    "nowcast": "nowcast.json", "forecast": "forecast.json", "attribution": "attribution.json",
    "enforcement": "enforcement.json", "advisories": "advisories.json", "wards": "wards.geojson",
    "roads": "roads.geojson", "fires": "fires.json", "replay_index": "replay/index.json",
    "interventions": "interventions.json", "ledger": "ledger.json", "briefs": "briefs.json",
}
# Cities with the GEE numeric satellite path active (Delhi backfilled; others land-use only).
_SAT_CITIES = {"delhi"}


def _is_fixture(path) -> bool:
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("fixture"))
    except (OSError, json.JSONDecodeError):
        return False  # geojson / unreadable -> no fixture flag


def build() -> ManifestDoc:
    root = web_data_dir()
    gen = utc_iso_z(now_utc())
    entries, any_fixture = [], False
    for slug in all_slugs():
        cfg = load_city(slug)
        files, city_fixture = {}, False
        for key, fname in _PER_CITY.items():
            path = root / slug / fname
            if path.exists():
                files[key] = f"{slug}/{fname}"
                if fname.endswith(".json") and _is_fixture(path):
                    city_fixture = True
        langs = list(dict.fromkeys(cfg.languages.primary
                                   + ([cfg.languages.regional] if cfg.languages.regional else [])))
        entry = {
            "id": slug, "name": cfg.name,
            "tier": TIER_CONFIG_TO_MANIFEST.get(cfg.tier, cfg.tier),
            "centroid": {"lat": cfg.centroid[0], "lon": cfg.centroid[1]},
            "bbox": list(cfg.bbox), "languages": langs, "files": files, "generated_at": gen,
        }
        if city_fixture:
            entry["fixture"] = True
            any_fixture = True
        entries.append(entry)

    kwargs = {
        "generated_at": gen,
        "sat_numeric": any(s in _SAT_CITIES for s in all_slugs()),
        "cities": entries,
    }
    if (root / "agentlog.json").exists():
        kwargs["agentlog"] = "agentlog.json"
    if any_fixture:
        kwargs["fixture"] = True
    return ManifestDoc(**kwargs)


def publish() -> int:
    doc = build()
    emit_model(doc, "manifest.json")
    log.info("manifest.published", cities=len(doc.cities), sat_numeric=doc.sat_numeric,
             fixture=bool(doc.fixture))
    return 0


__all__ = ["build", "publish"]
