"""Resolver-receipts audit tests (spec 14, acceptance 18): re-resolving a PUBLISHED
briefs.json against published artifacts, strictly (tamper + drift caught, stale skipped)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vayu.agents import audit


def _write_briefs(
    data_root: Path, city: str, briefs: list[dict[str, Any]], *, stale: bool = False
) -> None:
    doc: dict[str, Any] = {"generated_at": "2025-11-08T06:00:00Z", "model": "m", "briefs": briefs}
    if stale:
        doc["stale"] = True
    (data_root / city / "briefs.json").write_text(json.dumps(doc), encoding="utf-8")


def test_audit_passes_on_valid_published_briefs(data_root, good_brief):
    _write_briefs(data_root, "delhi", [good_brief])
    r = audit.audit_city(data_root, "delhi")
    assert r.ok, r.failures
    assert r.briefs_audited == 1
    assert r.refs_checked >= 4  # 3 evidence_refs + the expected_effect basis


def test_audit_catches_tampered_value(data_root, good_brief):
    good_brief["evidence_refs"][0]["value"] = 999.0  # someone edited the published file
    _write_briefs(data_root, "delhi", [good_brief])
    r = audit.audit_city(data_root, "delhi")
    assert not r.ok
    assert any("999" in f for f in r.failures)


def test_audit_catches_unresolvable_path(data_root, good_brief):
    good_brief["evidence_refs"][0]["path"] = "forecast.wards[ward_id=ghost].series[h=24].pm25_p90"
    _write_briefs(data_root, "delhi", [good_brief])
    r = audit.audit_city(data_root, "delhi")
    assert not r.ok
    assert any("ghost" in f for f in r.failures)


def test_audit_catches_effect_drift(data_root, good_brief):
    good_brief["expected_effect"]["ugm3"] = -5.0  # no longer matches the ledger row (-18)
    _write_briefs(data_root, "delhi", [good_brief])
    r = audit.audit_city(data_root, "delhi")
    assert not r.ok
    assert any("expected_effect" in f for f in r.failures)


def test_audit_skips_stale(data_root, good_brief):
    good_brief["evidence_refs"][0]["value"] = 999.0  # would fail a strict audit
    _write_briefs(data_root, "delhi", [good_brief], stale=True)
    r = audit.audit_city(data_root, "delhi")
    assert r.ok and r.skipped_stale  # stale files are not strictly audited


def test_audit_missing_file_is_ok(data_root):
    r = audit.audit_city(data_root, "mumbai")  # no mumbai/briefs.json
    assert r.ok and r.briefs_audited == 0
