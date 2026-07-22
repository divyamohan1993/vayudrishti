"""Independent resolver-receipts audit (spec 14, acceptance 18 — tightest form).

Re-reads the PUBLISHED briefs.json and re-resolves every evidence_ref + basis_ref against
the PUBLISHED artifacts, STRICTLY (no pruning): a published brief asserts resolved:true on
every ref, so every one must resolve to its stated value or the audit fails. This is the
acceptance-18 analog of the content gate: it proves the shipped file, not just the generation
path, and catches post-hoc tampering or artifact drift.

A stale briefs.json (kept from a failed run, already flagged to users) is skipped, since its
refs were verified against older artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vayu.agents import resolver
from vayu.agents.contracts import RESOLVABLE_ARTIFACTS
from vayu.agents.resolver import ResolveError, resolve, values_match


@dataclass(slots=True)
class BriefAudit:
    brief_id: str
    refs_checked: int
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(slots=True)
class CityAudit:
    city: str
    briefs_audited: int
    refs_checked: int
    failures: list[str] = field(default_factory=list)
    skipped_stale: bool = False

    @property
    def ok(self) -> bool:
        return not self.failures


def audit_brief(artifacts: dict[str, Any], brief: dict[str, Any]) -> BriefAudit:
    """Strictly re-resolve every ref of a published brief. No pruning; every ref must hold."""
    bid = str(brief.get("id", "?"))
    failures: list[str] = []
    checked = 0

    for i, ref in enumerate(brief.get("evidence_refs") or []):
        checked += 1
        artifact = ref.get("artifact")
        path = ref.get("path", "")
        if not ref.get("resolved"):
            failures.append(f"evidence_refs[{i}]: not marked resolved")
        if artifact not in artifacts:
            failures.append(f"evidence_refs[{i}]: artifact {artifact!r} not published")
            continue
        try:
            value = resolve(artifacts[artifact], path, expected_artifact=artifact)
        except ResolveError as exc:
            failures.append(f"evidence_refs[{i}]: {path!r} -> {exc}")
            continue
        if not values_match(ref.get("value"), value):
            failures.append(
                f"evidence_refs[{i}]: published {ref.get('value')!r} != resolved {value!r}"
            )

    effect = brief.get("expected_effect")
    if effect is not None:
        checked += 1
        probe = dict(effect)
        errs = resolver._ground_effect(artifacts, effect.get("basis_ref", ""), probe)
        if errs:
            failures.extend(f"expected_effect: {e}" for e in errs)
        elif not values_match(effect.get("ugm3"), probe.get("ugm3")):
            failures.append(
                f"expected_effect.ugm3 {effect.get('ugm3')!r} != re-grounded {probe.get('ugm3')!r}"
            )

    return BriefAudit(brief_id=bid, refs_checked=checked, failures=failures)


def audit_city(data_root: Path, city: str) -> CityAudit:
    """Audit the published briefs.json for one city against its published artifacts."""
    bpath = data_root / city / "briefs.json"
    if not bpath.exists():
        return CityAudit(city=city, briefs_audited=0, refs_checked=0)
    try:
        doc = json.loads(bpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CityAudit(
            city=city, briefs_audited=0, refs_checked=0, failures=[f"unreadable briefs.json: {exc}"]
        )
    if doc.get("stale"):
        return CityAudit(city=city, briefs_audited=0, refs_checked=0, skipped_stale=True)

    briefs = doc.get("briefs", [])
    artifacts = resolver.load_artifacts(data_root, city, list(RESOLVABLE_ARTIFACTS))
    failures: list[str] = []
    refs_checked = 0
    for brief in briefs:
        ba = audit_brief(artifacts, brief)
        refs_checked += ba.refs_checked
        failures.extend(f"{ba.brief_id}: {f}" for f in ba.failures)
    return CityAudit(
        city=city, briefs_audited=len(briefs), refs_checked=refs_checked, failures=failures
    )


__all__ = ["BriefAudit", "CityAudit", "audit_brief", "audit_city"]
