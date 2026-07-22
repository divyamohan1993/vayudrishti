"""Content-model tests (spec 14): BriefsDoc / AgentLogDoc accept valid docs and reject
invariant / sanitization / enum violations (the emit contract + gate)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vayu.agents.contracts import AgentLogDoc, BriefsDoc


def _doc(good_brief):
    return {
        "generated_at": "2025-11-08T06:00:00Z",
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "briefs": [good_brief],
    }


def test_briefsdoc_accepts_valid(good_brief):
    doc = BriefsDoc.model_validate(_doc(good_brief))
    assert doc.briefs[0].id == "delhi-2025-11-08-nw-stubble-01"


def test_briefsdoc_null_effect_and_no_action_code(good_brief):
    good_brief["expected_effect"] = None
    good_brief["action_code"] = None
    BriefsDoc.model_validate(_doc(good_brief))


def test_cold_start_empty_stale_envelope():
    BriefsDoc.model_validate(
        {"generated_at": "2025-11-08T06:00:00Z", "model": "m", "stale": True, "briefs": []}
    )


def test_reject_ci_out_of_order(good_brief):
    good_brief["expected_effect"] = {
        "ugm3": -18.0,
        "ci_low": -6.0,
        "ci_high": -31.0,
        "basis_ref": "ledger.wards[ward_id=delhi_042].effect_ugm3",
    }
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_trigger_window_reversed(good_brief):
    good_brief["trigger_window"] = {
        "start_utc": "2025-11-10T12:00:00Z",
        "end_utc": "2025-11-08T12:00:00Z",
    }
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_bad_action_code(good_brief):
    good_brief["action_code"] = "nuke_the_site"
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_html_in_strings(good_brief):
    good_brief["headline"] = "Severe <script>alert(1)</script> risk"
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_think_leak_in_situation(good_brief):
    # A </think> leak carries angle brackets -> rejected by the CleanStr sanitizer gate.
    good_brief["situation"] = "reasoning</think> the answer is"
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_empty_evidence_refs(good_brief):
    good_brief["evidence_refs"] = []
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_unresolved_flag_false(good_brief):
    good_brief["evidence_refs"][0]["resolved"] = False
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_bad_ward_id_pattern(good_brief):
    good_brief["target_wards"] = ["Delhi 042"]
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


def test_reject_extra_field(good_brief):
    good_brief["surprise"] = 1
    with pytest.raises(ValidationError):
        BriefsDoc.model_validate(_doc(good_brief))


# ---------------------------------------------------------------- agentlog


def test_agentlogdoc_valid():
    AgentLogDoc.model_validate(
        {
            "generated_at": "2025-11-08T06:00:00Z",
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "runs": [
                {
                    "role": "situation_analyst",
                    "city": "delhi",
                    "model": "m",
                    "reasoning_budget": 8192,
                    "tokens_in": 1200,
                    "tokens_out": 900,
                    "duration_ms": 4200,
                    "repairs": 0,
                },
            ],
            "totals": {"tokens_in": 1200, "tokens_out": 900, "total": 2100, "calls": 1},
        }
    )


def test_agentlog_rejects_bad_role():
    with pytest.raises(ValidationError):
        AgentLogDoc.model_validate(
            {
                "generated_at": "2025-11-08T06:00:00Z",
                "model": "m",
                "runs": [
                    {
                        "role": "overlord",
                        "model": "m",
                        "reasoning_budget": 1,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "duration_ms": 0,
                    }
                ],
            }
        )


def test_agentlog_with_audit_block():
    AgentLogDoc.model_validate(
        {
            "generated_at": "2025-11-08T06:00:00Z",
            "model": "m",
            "runs": [],
            "audit": {
                "passed": True,
                "briefs_audited": 3,
                "refs_checked": 30,
                "audited_at": "2025-11-08T06:00:00Z",
            },
        }
    )


def test_agentlog_rejects_incomplete_audit_block():
    with pytest.raises(ValidationError):
        AgentLogDoc.model_validate(
            {
                "generated_at": "2025-11-08T06:00:00Z",
                "model": "m",
                "runs": [],
                "audit": {"passed": True},  # missing briefs_audited / refs_checked / audited_at
            }
        )
