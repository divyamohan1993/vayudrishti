"""Read-only, deterministic tools over published artifacts (spec 14).

Eight tools (get_nowcast/forecast/attribution/enforcement/ledger/interventions/receipts/
fires_upwind) offered to the roles for drill-down beyond the digest. No network. Every
numeric a tool returns carries its canonical resolver path (via ``make_ref``), so a ref the
model copies from a tool result is resolvable by construction.

A tool for a missing artifact returns ``{"available": false, ...}`` rather than raising, so a
partial publish never crashes a role. ``get_fires_upwind`` degrades this way until an upwind
fire summary is published (no fires artifact exists in the spec 8 contract yet).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vayu.agents import resolver

_MAX_ITEMS = 12


@dataclass(slots=True)
class ToolContext:
    artifacts: dict[str, Any]
    city: str


def _ref(ctx: ToolContext, artifact: str, path: str, label: str) -> dict[str, Any] | None:
    try:
        return resolver.make_ref(ctx.artifacts, artifact, path, label)
    except resolver.ResolveError:
        return None


def _missing(artifact: str) -> dict[str, Any]:
    return {"available": False, "artifact": artifact, "note": f"{artifact} not published"}


# ---------------------------------------------------------------- handlers


def get_nowcast(ctx: ToolContext, ward_id: str | None = None) -> dict[str, Any]:
    nc = ctx.artifacts.get("nowcast")
    if not nc:
        return _missing("nowcast")
    wards = nc.get("wards", [])
    if ward_id:
        w = next((x for x in wards if x.get("ward_id") == ward_id), None)
        if not w:
            return {"available": True, "found": False, "ward_id": ward_id}
        return {
            "available": True,
            "ward": {
                k: w.get(k)
                for k in (
                    "ward_id",
                    "name",
                    "pm25_p50",
                    "pm25_p90",
                    "subindex24h",
                    "category",
                    "confidence",
                )
            },
            "refs": [
                r
                for r in [
                    _ref(
                        ctx,
                        "nowcast",
                        f"nowcast.wards[ward_id={ward_id}].pm25_p90",
                        f"nowcast p90, {ward_id}",
                    ),
                    _ref(
                        ctx,
                        "nowcast",
                        f"nowcast.wards[ward_id={ward_id}].subindex24h",
                        f"nowcast subindex24h, {ward_id}",
                    ),
                ]
                if r
            ],
        }
    top = sorted(wards, key=lambda w: w.get("pm25_p90", 0), reverse=True)[:_MAX_ITEMS]
    return {
        "available": True,
        "wards": [
            {
                "ward_id": w.get("ward_id"),
                "pm25_p90": w.get("pm25_p90"),
                "category": w.get("category"),
            }
            for w in top
        ],
    }


def get_forecast(ctx: ToolContext, ward_id: str, horizon: int | None = None) -> dict[str, Any]:
    fc = ctx.artifacts.get("forecast")
    if not fc:
        return _missing("forecast")
    w = next((x for x in fc.get("wards", []) if x.get("ward_id") == ward_id), None)
    if not w:
        return {"available": True, "found": False, "ward_id": ward_id}
    series = w.get("series", [])
    if horizon is not None:
        series = [p for p in series if p.get("h") == horizon]
    refs = []
    for p in series:
        r = _ref(
            ctx,
            "forecast",
            f"forecast.wards[ward_id={ward_id}].series[h={p.get('h')}].pm25_p90",
            f"{p.get('h')}h forecast p90, {ward_id}",
        )
        if r:
            refs.append(r)
    return {
        "available": True,
        "ward_id": ward_id,
        "series": [
            {
                k: p.get(k)
                for k in ("h", "pm25_p50", "pm25_p90", "subindex24h", "category", "confidence")
            }
            for p in series
        ],
        "refs": refs,
    }


def get_attribution(ctx: ToolContext, ward_id: str) -> dict[str, Any]:
    at = ctx.artifacts.get("attribution")
    if not at:
        return _missing("attribution")
    w = next((x for x in at.get("wards", []) if x.get("ward_id") == ward_id), None)
    if not w:
        return {"available": True, "found": False, "ward_id": ward_id}
    shares = w.get("shares", {})
    refs = [
        r
        for r in (
            _ref(
                ctx,
                "attribution",
                f"attribution.wards[ward_id={ward_id}].shares.{k}",
                f"{k} share, {ward_id}",
            )
            for k in shares
        )
        if r
    ]
    return {
        "available": True,
        "ward_id": ward_id,
        "shares": shares,
        "confidence": w.get("confidence"),
        "method_notes": w.get("method_notes"),
        "refs": refs,
    }


def get_enforcement(ctx: ToolContext, top: int | None = None) -> dict[str, Any]:
    en = ctx.artifacts.get("enforcement")
    if not en:
        return _missing("enforcement")
    ranked = en.get("ranked", [])[: (top or _MAX_ITEMS)]
    items = []
    for it in ranked:
        wid = it.get("ward_id")
        items.append(
            {
                "ward_id": wid,
                "priority_score": it.get("priority_score"),
                "source_label": it.get("source_label"),
                "confidence": it.get("confidence"),
                "action": it.get("action"),
                "evidence": it.get("evidence"),
                "refs": [
                    r
                    for r in [
                        _ref(
                            ctx,
                            "enforcement",
                            f"enforcement.ranked[ward_id={wid}].priority_score",
                            f"priority, {wid}",
                        ),
                        _ref(
                            ctx,
                            "enforcement",
                            f"enforcement.ranked[ward_id={wid}].evidence.exceedance_pct",
                            f"exceedance %, {wid}",
                        ),
                    ]
                    if r
                ],
            }
        )
    return {"available": True, "ranked": items}


def get_ledger(ctx: ToolContext, ward_id: str | None = None) -> dict[str, Any]:
    ld = ctx.artifacts.get("ledger")
    if not ld:
        return _missing("ledger")
    if ward_id:
        w = next((x for x in ld.get("wards", []) if x.get("ward_id") == ward_id), None)
        if not w:
            return {"available": True, "found": False, "ward_id": ward_id}
        return {
            "available": True,
            "ward_id": ward_id,
            "effect_ugm3": w.get("effect_ugm3"),
            "effect_ci_low": w.get("effect_ci_low"),
            "effect_ci_high": w.get("effect_ci_high"),
            "avoided_deaths": w.get("avoided_deaths"),
            "refs": [
                r
                for r in [
                    _ref(
                        ctx,
                        "ledger",
                        f"ledger.wards[ward_id={ward_id}].effect_ugm3",
                        f"causal effect, {ward_id}",
                    ),
                    _ref(
                        ctx,
                        "ledger",
                        f"ledger.wards[ward_id={ward_id}].avoided_deaths",
                        f"avoided deaths, {ward_id}",
                    ),
                ]
                if r
            ],
        }
    counterfactuals = ld.get("counterfactuals", [])[:_MAX_ITEMS]
    return {"available": True, "totals": ld.get("totals"), "counterfactuals": counterfactuals}


def get_interventions(ctx: ToolContext) -> dict[str, Any]:
    iv = ctx.artifacts.get("interventions")
    if not iv:
        return _missing("interventions")
    effects = iv.get("effects", [])[:_MAX_ITEMS]
    refs = [
        r
        for r in (
            _ref(
                ctx,
                "interventions",
                f"interventions.effects[stage_transition={e.get('stage_transition')}].effect_ugm3",
                f"effect, {e.get('stage_transition')}",
            )
            for e in effects
        )
        if r
    ]
    return {"available": True, "calendar": iv.get("calendar", []), "effects": effects, "refs": refs}


def get_receipts(ctx: ToolContext, city: str | None = None) -> dict[str, Any]:
    rc = ctx.artifacts.get("receipts")
    if not rc:
        return _missing("receipts")
    city = city or ctx.city
    city_r = (rc.get("cities") or {}).get(city)
    if not city_r:
        return {"available": True, "found": False, "city": city}
    forecast = city_r.get("forecast") or {}
    refs = [
        r
        for r in (
            _ref(
                ctx,
                "receipts",
                f"receipts.cities.{city}.forecast.{h}.skill_pct",
                f"{h}h skill %, {city}",
            )
            for h in forecast
        )
        if r
    ]
    return {
        "available": True,
        "city": city,
        "forecast": forecast,
        "attribution_directional_checks": city_r.get("attribution_directional_checks"),
        "refs": refs,
    }


def get_fires_upwind(ctx: ToolContext, ward_id: str | None = None) -> dict[str, Any]:
    # No upwind-fire artifact is published in the spec 8 contract yet. Degrade cleanly;
    # fires inform qualitative reasoning only until a citable summary is published.
    fires = ctx.artifacts.get("fires")
    if not fires:
        return {
            "available": False,
            "artifact": "fires",
            "note": "upwind fire summary not published; treat fire context as qualitative only",
        }
    wards = fires.get("wards", [])
    if ward_id:
        w = next((x for x in wards if x.get("ward_id") == ward_id), None)
        return {"available": True, "ward": w, "found": bool(w)}
    return {"available": True, "wards": wards[:_MAX_ITEMS]}


# ---------------------------------------------------------------- registry + schemas

_W = {"ward_id": {"type": "string", "description": "ward_id, e.g. delhi_042"}}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_nowcast",
            "description": "Nowcast for a ward, or the top wards by PM2.5 p90.",
            "parameters": {"type": "object", "properties": _W},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "Forecast series (24/48/72h) for a ward.",
            "parameters": {
                "type": "object",
                "properties": {**_W, "horizon": {"type": "integer", "enum": [24, 48, 72]}},
                "required": ["ward_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attribution",
            "description": "Source-apportionment shares for a ward.",
            "parameters": {"type": "object", "properties": _W, "required": ["ward_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_enforcement",
            "description": "Ranked enforcement queue (measured signals).",
            "parameters": {"type": "object", "properties": {"top": {"type": "integer"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ledger",
            "description": "Ledger causal effects for a ward, or totals + counterfactuals.",
            "parameters": {"type": "object", "properties": _W},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_interventions",
            "description": "GRAP calendar + weather-normalized stage effects.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_receipts",
            "description": "Validation receipts: forecast skill + attribution directional checks.",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fires_upwind",
            "description": "Upwind FIRMS fire context for a ward (qualitative only).",
            "parameters": {"type": "object", "properties": _W},
        },
    },
]

_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_nowcast": get_nowcast,
    "get_forecast": get_forecast,
    "get_attribution": get_attribution,
    "get_enforcement": get_enforcement,
    "get_ledger": get_ledger,
    "get_interventions": get_interventions,
    "get_receipts": get_receipts,
    "get_fires_upwind": get_fires_upwind,
}

TOOL_NAMES: tuple[str, ...] = tuple(_HANDLERS)


def execute(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call. Unknown tool or bad args return an error dict, never raise."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        return handler(ctx, **(arguments or {}))
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - tools must never crash a role
        return {"error": f"{name} failed: {type(exc).__name__}"}


__all__ = ["ToolContext", "TOOL_SCHEMAS", "TOOL_NAMES", "execute"]
