"""Digest + tools tests (spec 14): compound-risk selection, resolvable refs by
construction, and clean degradation on missing artifacts."""

from __future__ import annotations

from vayu.agents import digest, resolver, tools

# ---------------------------------------------------------------- digest


def test_digest_surfaces_risk_wards_only(artifacts):
    d = digest.build_digest(artifacts, "delhi")
    ids = [c["ward_id"] for c in d["candidates"]]
    assert "delhi_042" in ids  # Severe at 24h
    assert "delhi_007" in ids  # Poor
    assert "delhi_001" not in ids  # Moderate -> below risk floor
    # Highest compound score first (delhi_042 has band crossing + priority 88).
    assert d["candidates"][0]["ward_id"] == "delhi_042"


def test_digest_active_grap_stage(artifacts):
    d = digest.build_digest(artifacts, "delhi")
    assert d["active_grap_stage"]["stage"] == "GRAP-III"  # latest-starting


def test_digest_refs_resolve_by_construction(artifacts):
    d = digest.build_digest(artifacts, "delhi")
    top = d["candidates"][0]
    # Every ref the digest attached must resolve against the same artifacts.
    for ref in top["forecast"]:
        assert ref["ref"] is not None
        assert (
            resolver.resolve(
                artifacts[ref["ref"]["artifact"]], ref["ref"]["path"], ref["ref"]["artifact"]
            )
            == ref["ref"]["value"]
        )
    for key in ("nowcast", "enforcement", "attribution", "ledger"):
        r = top[key] and top[key].get("ref")
        if r:
            assert (
                resolver.resolve(artifacts[r["artifact"]], r["path"], r["artifact"]) == r["value"]
            )


def test_digest_partial_artifacts_no_crash():
    d = digest.build_digest(
        {
            "forecast": {
                "wards": [
                    {
                        "ward_id": "delhi_042",
                        "name": "AV",
                        "series": [{"h": 24, "pm25_p90": 400.0, "category": "Severe"}],
                    }
                ]
            }
        },
        "delhi",
    )
    assert d["candidates"][0]["ward_id"] == "delhi_042"
    assert d["candidates"][0]["nowcast"] is None  # nowcast absent
    assert d["active_grap_stage"] is None


# ---------------------------------------------------------------- tools


def test_tool_get_forecast_refs_resolve(artifacts):
    ctx = tools.ToolContext(artifacts=artifacts, city="delhi")
    out = tools.execute(ctx, "get_forecast", {"ward_id": "delhi_042", "horizon": 24})
    assert out["available"] and out["series"][0]["pm25_p90"] == 412.0
    for ref in out["refs"]:
        assert (
            resolver.resolve(artifacts[ref["artifact"]], ref["path"], ref["artifact"])
            == ref["value"]
        )


def test_tool_get_enforcement_and_ledger(artifacts):
    ctx = tools.ToolContext(artifacts=artifacts, city="delhi")
    enf = tools.execute(ctx, "get_enforcement", {})
    assert enf["ranked"][0]["ward_id"] == "delhi_042"
    led = tools.execute(ctx, "get_ledger", {"ward_id": "delhi_042"})
    assert led["effect_ugm3"] == -18.0


def test_tool_missing_artifact_degrades():
    ctx = tools.ToolContext(artifacts={}, city="delhi")
    assert tools.execute(ctx, "get_nowcast", {})["available"] is False
    assert tools.execute(ctx, "get_fires_upwind", {})["available"] is False  # no fires artifact


def test_tool_unknown_and_bad_args_never_raise(artifacts):
    ctx = tools.ToolContext(artifacts=artifacts, city="delhi")
    assert "error" in tools.execute(ctx, "nope", {})
    assert "error" in tools.execute(ctx, "get_forecast", {"bogus": 1})  # missing required ward_id


def test_all_eight_tools_registered():
    assert set(tools.TOOL_NAMES) == {
        "get_nowcast",
        "get_forecast",
        "get_attribution",
        "get_enforcement",
        "get_ledger",
        "get_interventions",
        "get_receipts",
        "get_fires_upwind",
    }
    assert len(tools.TOOL_SCHEMAS) == 8
