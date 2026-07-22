"""Orchestration tests (spec 14, acceptance 18-20): the 4-role loop with a scripted fake
NIM call (zero network) covering the repair loop, the publish gate, and failure semantics
(API error -> stale-keep, warm and cold start)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from vayu.agents import nim, orchestrator
from vayu.agents.nim import ChatResult, NimError, Usage

# ---------------------------------------------------------------- scripted fake NIM


def _tool_result(name: str, args: dict[str, Any], tin: int = 100, tout: int = 60) -> ChatResult:
    return ChatResult(
        content="",
        reasoning="brief reasoning",
        tool_calls=[{"id": "call_1", "name": name, "arguments": json.dumps(args)}],
        finish_reason="tool_calls",
        usage=Usage(tin, tout),
    )


def _scripted(*results: ChatResult):
    it = iter(results)

    def call_fn(**_kwargs: Any) -> ChatResult:
        return next(it)

    return call_fn


def _raising(exc: Exception):
    def call_fn(**_kwargs: Any) -> ChatResult:
        raise exc

    return call_fn


def _drafter_brief(good_brief: dict[str, Any]) -> dict[str, Any]:
    """The drafter's submitted shape: no `resolved` on refs, no `verifier` (added downstream)."""
    b = {k: v for k, v in good_brief.items() if k != "verifier"}
    b["evidence_refs"] = [
        {k: v for k, v in r.items() if k != "resolved"} for r in good_brief["evidence_refs"]
    ]
    return b


# ---------------------------------------------------------------- repair loop


def test_repair_loop_drops_bad_brief_keeps_good(artifacts, good_brief):
    good = _drafter_brief(good_brief)
    bad = {
        **good,
        "id": "bad-1",
        "evidence_refs": [
            {
                "label": "ghost",
                "artifact": "forecast",
                "path": "forecast.wards[ward_id=ghost].series[h=24].pm25_p90",
                "value": 1.0,
            }
        ],
    }
    results = [
        _tool_result(
            "submit_situations",
            {
                "situations": [
                    {
                        "id": "s1",
                        "target_wards": ["delhi_042"],
                        "summary": "compound risk",
                        "signal_refs": [],
                    }
                ]
            },
        ),
        _tool_result(
            "submit_strategies",
            {
                "strategies": [
                    {
                        "situation_id": "s1",
                        "measure": "sprinkling",
                        "owner": "MCD",
                        "effect_refs": [],
                    }
                ]
            },
        ),
        _tool_result("submit_briefs", {"briefs": [good, bad]}),  # round 0: good kept, bad rejected
        _tool_result("submit_briefs", {"briefs": [good]}),  # repair round: only good
        _tool_result(
            "submit_verdicts",
            {"verdicts": [{"brief_id": good["id"], "passed": True, "notes": "ok"}]},
        ),
    ]
    briefs_doc, log_doc = orchestrator.generate_briefs(artifacts, "delhi", _scripted(*results))

    assert [b.id for b in briefs_doc.briefs] == [good["id"]]  # bad-1 dropped
    assert briefs_doc.briefs[0].verifier.passed is True
    assert briefs_doc.briefs[0].evidence_refs[0].value == 412.0  # ground-truthed
    assert log_doc.totals.calls == 5
    assert any(r.repairs == 1 for r in log_doc.runs)  # a repair round occurred


def test_verifier_can_reject_resolver_passing_brief(artifacts, good_brief):
    good = _drafter_brief(good_brief)
    results = [
        _tool_result(
            "submit_situations",
            {
                "situations": [
                    {"id": "s1", "target_wards": ["delhi_042"], "summary": "x", "signal_refs": []}
                ]
            },
        ),
        _tool_result(
            "submit_strategies",
            {
                "strategies": [
                    {"situation_id": "s1", "measure": "m", "owner": "MCD", "effect_refs": []}
                ]
            },
        ),
        _tool_result("submit_briefs", {"briefs": [good]}),
        _tool_result(
            "submit_verdicts",
            {"verdicts": [{"brief_id": good["id"], "passed": False, "notes": "overreaches"}]},
        ),
    ]
    briefs_doc, _ = orchestrator.generate_briefs(artifacts, "delhi", _scripted(*results))
    assert briefs_doc.briefs == []  # adversarial verifier removed it


def test_empty_situations_yields_no_briefs_no_crash(artifacts):
    results = [_tool_result("submit_situations", {"situations": []})]
    briefs_doc, log_doc = orchestrator.generate_briefs(artifacts, "delhi", _scripted(*results))
    assert briefs_doc.briefs == []
    assert briefs_doc.fixture is True  # propagated from fixture artifacts
    assert log_doc.totals.calls == 1


def test_call_budget_trips(artifacts, good_brief):
    # A fake that always drills (never submits) burns calls; the budget must stop it.
    def always_drill(**_kwargs):
        return ChatResult(
            content="",
            reasoning="",
            tool_calls=[{"id": "c", "name": "get_nowcast", "arguments": "{}"}],
            finish_reason="tool_calls",
            usage=Usage(1, 1),
        )

    with pytest.raises(NimError):
        orchestrator.generate_briefs(artifacts, "delhi", always_drill, max_calls=2)


# ---------------------------------------------------------------- publish gate


def test_gate_catches_think_leak_and_key(tmp_path):
    from vayu.commands import briefs as cmd

    with pytest.raises(NimError):
        cmd._gate("reasoning </think> answer", Path("briefs.json"))
    with pytest.raises(NimError):
        cmd._gate("key is nvapi-secret123", Path("briefs.json"))
    cmd._gate("clean action brief", Path("briefs.json"))  # no raise


def test_write_json_refuses_poisoned_doc(tmp_path):
    from vayu.commands import briefs as cmd

    out = tmp_path / "briefs.json"
    with pytest.raises(NimError):
        cmd._write_json(out, {"headline": "leak <think>secret</think>"})
    assert not out.exists()  # nothing written


def test_write_json_keeps_required_null_prunes_optional(tmp_path):
    from vayu.commands import briefs as cmd

    out = tmp_path / "briefs.json"
    cmd._write_json(out, {"expected_effect": None, "action_code": None, "briefs": []})
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "expected_effect" in doc  # required-nullable kept
    assert "action_code" not in doc  # optional-None pruned


# ---------------------------------------------------------------- failure semantics


def _run_briefs(monkeypatch, data_root: Path, *, key: str | None, chat_raises: bool):
    from vayu.commands import briefs as cmd

    monkeypatch.setattr(cmd, "get_settings", lambda: SimpleNamespace(nvidia_api_key=key))
    if chat_raises:
        monkeypatch.setattr(nim, "chat", _raising(NimError("simulated outage")))
    args = argparse.Namespace(city="delhi", data_dir=str(data_root), max_calls=None)
    return cmd.run(args)


def test_api_error_keeps_previous_stale(monkeypatch, data_root):
    prev = {"generated_at": "2025-11-01T00:00:00Z", "model": "m", "briefs": [], "marker": "kept"}
    (data_root / "delhi" / "briefs.json").write_text(json.dumps(prev), encoding="utf-8")

    rc = _run_briefs(monkeypatch, data_root, key="nvapi-fake-key-for-test-000000", chat_raises=True)

    assert rc == 0  # NEVER fails the publish pipeline
    doc = json.loads((data_root / "delhi" / "briefs.json").read_text(encoding="utf-8"))
    assert doc["stale"] is True
    assert doc["generated_at"] == "2025-11-01T00:00:00Z"  # previous preserved
    assert doc["marker"] == "kept"


def test_cold_start_emits_empty_stale_envelope(monkeypatch, data_root):
    assert not (data_root / "delhi" / "briefs.json").exists()

    rc = _run_briefs(monkeypatch, data_root, key="nvapi-fake-key-for-test-000000", chat_raises=True)

    assert rc == 0
    from vayu.agents.contracts import BriefsDoc

    doc = json.loads((data_root / "delhi" / "briefs.json").read_text(encoding="utf-8"))
    assert doc["stale"] is True and doc["briefs"] == []
    BriefsDoc.model_validate(doc)  # the stale envelope is itself schema-valid
    # agentlog is written stale too.
    log = json.loads((data_root / "agentlog.json").read_text(encoding="utf-8"))
    assert log["stale"] is True and log["runs"] == []


def test_missing_key_is_a_clean_stale_keep(monkeypatch, data_root):
    rc = _run_briefs(monkeypatch, data_root, key=None, chat_raises=False)
    assert rc == 0
    doc = json.loads((data_root / "delhi" / "briefs.json").read_text(encoding="utf-8"))
    assert doc["stale"] is True
