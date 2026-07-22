"""Deterministic compound-risk digest (spec 14, token frugality).

The digest is pure Python over the published artifacts. It front-loads the signals the
Situation Analyst reasons about (forecast band crossings, high enforcement priority,
available causal effects, active GRAP stage, dominant source), so the model composes
judgment instead of fishing for values via many tool round-trips. Every numeric signal
carries its canonical resolver path (built via ``make_ref``), so anything the model cites
from the digest is resolvable by construction and needs no tool call.

No network, no LLM. Fully unit-testable.
"""

from __future__ import annotations

from typing import Any

from vayu.agents import resolver
from vayu.constants import AQI_CATEGORIES

_CAT_RANK = {c: i for i, c in enumerate(AQI_CATEGORIES)}
# A candidate is "emerging risk" from this category up (Poor and worse).
_RISK_FLOOR = _CAT_RANK.get("Poor", 3)

MAX_CANDIDATES = 8


def _cat_rank(category: str | None) -> int:
    return _CAT_RANK.get(category or "", -1)


def _ref(artifacts: dict[str, Any], artifact: str, path: str, label: str) -> dict[str, Any] | None:
    """Best-effort resolvable ref; None if it does not resolve (artifact absent/shape off)."""
    try:
        return resolver.make_ref(artifacts, artifact, path, label)
    except resolver.ResolveError:
        return None


def _active_grap_stage(interventions: dict[str, Any] | None) -> dict[str, Any] | None:
    if not interventions:
        return None
    calendar = interventions.get("calendar") or []
    if not calendar:
        return None
    # Latest-starting stage is the operative one for a nowcast-time digest.
    latest = max(calendar, key=lambda e: e.get("start_utc", ""))
    return {"stage": latest.get("stage"), "start_utc": latest.get("start_utc")}


def _nowcast_by_ward(nowcast: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not nowcast:
        return {}
    return {w["ward_id"]: w for w in nowcast.get("wards", []) if "ward_id" in w}


def _enforcement_by_ward(
    enforcement: dict[str, Any] | None,
) -> dict[str, tuple[int, dict[str, Any]]]:
    if not enforcement:
        return {}
    out: dict[str, tuple[int, dict[str, Any]]] = {}
    for rank, item in enumerate(enforcement.get("ranked", [])):
        if "ward_id" in item:
            out[item["ward_id"]] = (rank, item)
    return out


def _attribution_by_ward(attribution: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not attribution:
        return {}
    return {w["ward_id"]: w for w in attribution.get("wards", []) if "ward_id" in w}


def _ledger_by_ward(ledger: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not ledger:
        return {}
    return {w["ward_id"]: w for w in ledger.get("wards", []) if "ward_id" in w}


def _dominant_share(shares: dict[str, Any]) -> tuple[str, float] | None:
    if not shares:
        return None
    key = max(shares, key=lambda k: shares.get(k, 0.0))
    return key, float(shares.get(key, 0.0))


def build_digest(artifacts: dict[str, Any], city: str) -> dict[str, Any]:
    """Compute the compound-risk digest for ``city`` from loaded published artifacts."""
    nowcast = artifacts.get("nowcast")
    forecast = artifacts.get("forecast")

    nc = _nowcast_by_ward(nowcast)
    enf = _enforcement_by_ward(artifacts.get("enforcement"))
    attr = _attribution_by_ward(artifacts.get("attribution"))
    led = _ledger_by_ward(artifacts.get("ledger"))

    candidates: list[dict[str, Any]] = []
    fwards = (forecast or {}).get("wards", []) if forecast else []
    for fw in fwards:
        ward_id = fw.get("ward_id")
        if not ward_id:
            continue
        name = fw.get("name", ward_id)
        nc_w = nc.get(ward_id)
        nc_rank = _cat_rank(nc_w.get("category")) if nc_w else -1

        fc_points: list[dict[str, Any]] = []
        worst_rank = nc_rank
        for pt in fw.get("series", []):
            h = pt.get("h")
            frank = _cat_rank(pt.get("category"))
            worst_rank = max(worst_rank, frank)
            ref = _ref(
                artifacts,
                "forecast",
                f"forecast.wards[ward_id={ward_id}].series[h={h}].pm25_p90",
                f"{h}h forecast p90, {ward_id}",
            )
            fc_points.append(
                {
                    "h": h,
                    "category": pt.get("category"),
                    "pm25_p90": pt.get("pm25_p90"),
                    "worsens": frank > nc_rank if nc_rank >= 0 else frank >= _RISK_FLOOR,
                    "ref": ref,
                }
            )

        # Only surface wards at or above the risk floor (Poor+) at nowcast or in forecast.
        if worst_rank < _RISK_FLOOR:
            continue

        entry: dict[str, Any] = {
            "ward_id": ward_id,
            "name": name,
            "nowcast": None,
            "forecast": fc_points,
            "enforcement": None,
            "attribution": None,
            "ledger": None,
        }
        if nc_w:
            entry["nowcast"] = {
                "category": nc_w.get("category"),
                "pm25_p90": nc_w.get("pm25_p90"),
                "ref": _ref(
                    artifacts,
                    "nowcast",
                    f"nowcast.wards[ward_id={ward_id}].pm25_p90",
                    f"nowcast p90, {ward_id}",
                ),
            }
        score = float(max(worst_rank - _RISK_FLOOR + 1, 0)) * 10.0

        if ward_id in enf:
            _, item = enf[ward_id]
            entry["enforcement"] = {
                "priority_score": item.get("priority_score"),
                "persistence_days": item.get("persistence_days")
                or (item.get("evidence") or {}).get("persistence_days"),
                "action": item.get("action"),
                "source_label": item.get("source_label"),
                "ref": _ref(
                    artifacts,
                    "enforcement",
                    f"enforcement.ranked[ward_id={ward_id}].priority_score",
                    f"enforcement priority, {ward_id}",
                ),
            }
            score += float(item.get("priority_score") or 0.0)

        if ward_id in attr:
            dom = _dominant_share(attr[ward_id].get("shares", {}))
            if dom:
                key, share = dom
                entry["attribution"] = {
                    "dominant": key,
                    "share": share,
                    "confidence": attr[ward_id].get("confidence"),
                    "ref": _ref(
                        artifacts,
                        "attribution",
                        f"attribution.wards[ward_id={ward_id}].shares.{key}",
                        f"dominant source share ({key}), {ward_id}",
                    ),
                }

        if ward_id in led:
            entry["ledger"] = {
                "effect_ugm3": led[ward_id].get("effect_ugm3"),
                "effect_ci_low": led[ward_id].get("effect_ci_low"),
                "effect_ci_high": led[ward_id].get("effect_ci_high"),
                "ref": _ref(
                    artifacts,
                    "ledger",
                    f"ledger.wards[ward_id={ward_id}].effect_ugm3",
                    f"ledger causal effect, {ward_id}",
                ),
            }

        entry["compound_score"] = round(score, 3)
        candidates.append(entry)

    candidates.sort(key=lambda e: e["compound_score"], reverse=True)
    candidates = candidates[:MAX_CANDIDATES]

    return {
        "city": city,
        "active_grap_stage": _active_grap_stage(artifacts.get("interventions")),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "available_artifacts": sorted(artifacts.keys()),
    }


__all__ = ["build_digest", "MAX_CANDIDATES"]
