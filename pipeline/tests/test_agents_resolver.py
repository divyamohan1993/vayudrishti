"""Resolver unit tests (spec 14, acceptance 18): grammar, resolution, tolerance,
ground-truth overwrite, and brief verification (resolve / mismatch / unresolvable)."""

from __future__ import annotations

import pytest

from vayu.agents import resolver
from vayu.agents.resolver import ResolveError

# ---------------------------------------------------------------- path grammar


def test_parse_key_index_predicate():
    steps = resolver.parse_path("forecast.wards[ward_id=delhi_042].series[h=24].pm25_p90")
    assert steps[0] == ("key", "forecast")
    assert ("pred", "ward_id", "delhi_042") in steps
    assert ("pred", "h", "24") in steps
    assert steps[-1] == ("key", "pm25_p90")


def test_parse_numeric_index():
    assert ("index", 0) in resolver.parse_path("enforcement.ranked[0].priority_score")


@pytest.mark.parametrize("bad", ["", "  ", "forecast.wards[]", "a[b]", "a[[0]]", "a[=v]"])
def test_parse_rejects_malformed(bad):
    with pytest.raises(ResolveError):
        resolver.parse_path(bad)


def test_parse_rejects_unterminated_bracket():
    with pytest.raises(ResolveError):
        resolver.parse_path("a[0")


def test_parse_rejects_too_many_steps():
    with pytest.raises(ResolveError):
        resolver.parse_path(".".join(f"k{i}" for i in range(40)))


# ---------------------------------------------------------------- resolve


def test_resolve_predicate_and_index(artifacts):
    assert (
        resolver.resolve(
            artifacts["forecast"],
            "forecast.wards[ward_id=delhi_042].series[h=24].pm25_p90",
            "forecast",
        )
        == 412.0
    )
    assert (
        resolver.resolve(
            artifacts["enforcement"], "enforcement.ranked[0].priority_score", "enforcement"
        )
        == 88.0
    )


def test_resolve_nested_dict_keys(artifacts):
    assert (
        resolver.resolve(
            artifacts["receipts"], "receipts.cities.delhi.forecast.24.skill_pct", "receipts"
        )
        == 23.6
    )


def test_resolve_predicate_value_with_spaces(artifacts):
    assert (
        resolver.resolve(
            artifacts["interventions"],
            "interventions.effects[stage_transition=GRAP-II to GRAP-III].effect_ugm3",
            "interventions",
        )
        == -18.0
    )


def test_resolve_artifact_mismatch(artifacts):
    with pytest.raises(ResolveError):
        resolver.resolve(
            artifacts["forecast"],
            "forecast.wards[ward_id=delhi_042].series[h=24].pm25_p90",
            "nowcast",
        )


def test_resolve_missing_key_and_predicate(artifacts):
    with pytest.raises(ResolveError):
        resolver.resolve(
            artifacts["nowcast"], "nowcast.wards[ward_id=delhi_999].pm25_p90", "nowcast"
        )
    with pytest.raises(ResolveError):
        resolver.resolve(artifacts["nowcast"], "nowcast.wards[ward_id=delhi_042].nope", "nowcast")


def test_resolve_container_rejected(artifacts):
    # Resolving to the shares object (a dict) must fail: a ref names a scalar.
    with pytest.raises(ResolveError):
        resolver.resolve(
            artifacts["attribution"], "attribution.wards[ward_id=delhi_042].shares", "attribution"
        )


# ---------------------------------------------------------------- values_match


def test_values_match_tolerance():
    assert resolver.values_match(412.0, 412.3)  # rounding within rtol
    assert not resolver.values_match(412.0, 480.0)  # fabricated
    assert resolver.values_match(0.55, 0.55)
    assert not resolver.values_match(0.55, 0.20)  # share fabrication caught by atol
    assert resolver.values_match("NW", "NW")
    assert not resolver.values_match("NW", "SE")


def test_values_match_bool_not_coerced():
    assert resolver.values_match(True, True)
    assert not resolver.values_match(True, 1)  # bool vs int handled distinctly


# ---------------------------------------------------------------- make_ref (tools path)


def test_make_ref_resolvable_by_construction(artifacts):
    ref = resolver.make_ref(
        artifacts, "ledger", "ledger.wards[ward_id=delhi_042].effect_ugm3", "effect"
    )
    assert ref == {
        "label": "effect",
        "artifact": "ledger",
        "path": "ledger.wards[ward_id=delhi_042].effect_ugm3",
        "value": -18.0,
        "resolved": True,
    }


def test_make_ref_unresolvable_raises(artifacts):
    with pytest.raises(ResolveError):
        resolver.make_ref(artifacts, "ledger", "ledger.wards[ward_id=nope].effect_ugm3", "x")


# ---------------------------------------------------------------- verify_brief


def test_verify_prunes_mismatched_ref_keeps_brief(artifacts, good_brief):
    good_brief["evidence_refs"][0]["value"] = 999.0  # fabricated value -> pruned, not fatal
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok  # brief survives on its two other good refs
    assert len(res.brief["evidence_refs"]) == 2  # the fabricated ref was dropped
    assert any("!= resolved" in p for p in res.pruned)


def test_verify_good_brief_passes_and_grounds(artifacts, good_brief):
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok, res.errors
    # Values overwritten with resolved ground truth.
    assert res.brief["evidence_refs"][0]["value"] == 412.0
    assert res.brief["expected_effect"]["ugm3"] == -18.0


def test_verify_prunes_unresolvable_ref_keeps_brief(artifacts, good_brief):
    good_brief["evidence_refs"].append(
        {
            "label": "bogus",
            "artifact": "forecast",
            "path": "forecast.wards[ward_id=ghost].series[h=24].pm25_p90",
            "value": 1.0,
            "resolved": True,
        }
    )
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok  # the three real refs remain
    assert len(res.brief["evidence_refs"]) == 3
    assert any("ghost" in p for p in res.pruned)


def test_verify_all_refs_bad_fails(artifacts, good_brief):
    for ref in good_brief["evidence_refs"]:
        ref["artifact"] = "forecast"
        ref["path"] = "forecast.wards[ward_id=ghost].series[h=24].pm25_p90"
    res = resolver.verify_brief(artifacts, good_brief)
    assert not res.ok  # nothing resolvable left
    assert any("no resolvable" in e for e in res.errors)


def test_verify_basis_ref_mismatch_rejected(artifacts, good_brief):
    good_brief["expected_effect"]["ugm3"] = -18.0
    good_brief["expected_effect"]["ci_low"] = -50.0
    good_brief["expected_effect"]["basis_ref"] = (
        "ledger.wards[ward_id=delhi_042].avoided_deaths"  # resolves to 14.0, != -18
    )
    res = resolver.verify_brief(artifacts, good_brief)
    assert not res.ok
    assert any("basis" in e for e in res.errors)


def test_verify_grounds_ci_from_basis_row(artifacts, good_brief):
    # The drafter asserts an ungrounded CI; the resolver overwrites it from the ledger row so no
    # CI number is ever left unverified (basis_ref points at effect_ugm3, CI comes from siblings).
    good_brief["expected_effect"]["ci_low"] = -22.0
    good_brief["expected_effect"]["ci_high"] = -14.0
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok, res.errors
    assert res.brief["expected_effect"]["ugm3"] == -18.0
    assert res.brief["expected_effect"]["ci_low"] == -31.0   # grounded from effect_ci_low
    assert res.brief["expected_effect"]["ci_high"] == -6.0   # grounded from effect_ci_high


def test_verify_basis_ref_as_effect_row(artifacts, good_brief):
    good_brief["expected_effect"]["basis_ref"] = "ledger.wards[ward_id=delhi_042]"
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok, res.errors
    assert res.brief["expected_effect"]["ugm3"] == -18.0
    assert res.brief["expected_effect"]["ci_low"] == -31.0


def test_verify_keeps_valid_ledger_ref(artifacts, good_brief):
    good_brief["ledger_ref"] = {"stage_transition": "GRAP-II to GRAP-III"}  # real
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.brief["ledger_ref"] == {"stage_transition": "GRAP-II to GRAP-III"}


def test_verify_drops_garbage_ledger_ref(artifacts, good_brief):
    good_brief["ledger_ref"] = {"scenario": "ban_open_biomass_burning), "}  # not a real scenario
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok  # brief still valid
    assert "ledger_ref" not in res.brief  # garbage linkage dropped


def test_verify_briefs_partitions_kept_and_dropped(artifacts, good_brief):
    bad = dict(good_brief)
    bad = {
        **good_brief,
        "id": "bad-1",
        "evidence_refs": [
            {
                "label": "x",
                "artifact": "nowcast",
                "path": "nowcast.wards[ward_id=ghost].pm25_p90",
                "value": 1.0,
                "resolved": True,
            }
        ],
    }
    out = resolver.verify_briefs(artifacts, [good_brief, bad])
    assert [b["id"] for b in out.kept] == ["delhi-2025-11-08-nw-stubble-01"]
    assert out.dropped and out.dropped[0][0]["id"] == "bad-1"


def test_missing_artifact_makes_ref_unresolvable(good_brief):
    res = resolver.verify_brief({}, good_brief)  # no artifacts loaded
    assert not res.ok
    assert any("no resolvable" in e for e in res.errors)
    assert any("not published" in p for p in res.pruned)


# ---------------------------------------------------------------- disk loading


def test_load_artifacts_from_disk(data_root):
    loaded = resolver.load_artifacts(
        data_root, "delhi", ["nowcast", "forecast", "receipts", "missing"]
    )
    assert set(loaded) == {"nowcast", "forecast", "receipts"}  # missing omitted
    assert (
        resolver.resolve(loaded["receipts"], "receipts.cities.delhi.forecast.24.n", "receipts")
        == 90
    )
