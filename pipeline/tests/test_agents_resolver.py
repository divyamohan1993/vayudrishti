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


def test_verify_good_brief_overwrites_ground_truth(artifacts, good_brief):
    good_brief["evidence_refs"][0]["value"] = 999.0  # model asserted wrong-but-close? no, far off
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok is False  # 999 vs 412 is a fabrication -> rejected
    assert any("!= resolved" in e for e in res.errors)


def test_verify_good_brief_passes_and_grounds(artifacts, good_brief):
    res = resolver.verify_brief(artifacts, good_brief)
    assert res.ok, res.errors
    # Values overwritten with resolved ground truth.
    assert res.brief["evidence_refs"][0]["value"] == 412.0
    assert res.brief["expected_effect"]["ugm3"] == -18.0


def test_verify_unresolvable_ref_rejected(artifacts, good_brief):
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
    assert not res.ok
    assert any("ghost" in e for e in res.errors)


def test_verify_basis_ref_mismatch_rejected(artifacts, good_brief):
    good_brief["expected_effect"]["ugm3"] = -18.0
    good_brief["expected_effect"]["ci_low"] = -50.0
    good_brief["expected_effect"]["basis_ref"] = (
        "ledger.wards[ward_id=delhi_042].avoided_deaths"  # resolves to 14.0, != -18
    )
    res = resolver.verify_brief(artifacts, good_brief)
    assert not res.ok
    assert any("basis" in e for e in res.errors)


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
    assert any("not published" in e for e in res.errors)


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
