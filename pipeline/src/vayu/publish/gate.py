"""File-scanning content gate (spec 6/7; acceptance 13). Owner: vayu-models.

Pure-local: reads JSON files off disk and validates each against its pydantic content
model (schema shape + numeric ranges + string sanitization + cross-field invariants +
lineage no-query-string). No network, no secrets. Returns a report; the CLI turns a
non-empty error list into a non-zero exit so CI fails on malformed publish output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from vayu.logging_setup import get_logger
from vayu.publish.contentmodels import MODEL_BY_FILENAME, ManifestDoc, model_for_path
from vayu.publish.emit import web_data_dir

log = get_logger("gate")


def _register_external_models() -> None:
    """Best-effort registration of teammate-owned content models (the agentic layer).

    Non-fatal by design: an absent or broken external contract leaves those files
    unvalidated (the owner self-verifies before emit) but never crashes the gate. Keeps
    the gate pure-local -- vayu.agents.contracts imports only pydantic + our own modules.
    """
    try:
        from vayu.agents.contracts import AgentLogDoc, BriefsDoc

        MODEL_BY_FILENAME.setdefault("briefs.json", BriefsDoc)  # per-city
        MODEL_BY_FILENAME.setdefault("agentlog.json", AgentLogDoc)  # global
    except Exception as exc:  # pragma: no cover - defensive
        log.debug("gate.external_models_unavailable", detail=str(exc))


@dataclass
class GateReport:
    checked: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _validate_file(path: Path, report: GateReport) -> None:
    key = str(path)
    if key in report.checked:
        return
    model = model_for_path(key)
    if model is None:
        return  # not a model-owned JSON (e.g. wards.geojson is vayu-data's); skip
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"{path}: unreadable/invalid JSON: {exc}")
        return
    try:
        model.model_validate(data)
        report.checked.append(key)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"])
            report.errors.append(f"{path}: {loc or '<root>'}: {err['msg']}")


def _scan_known_json(root: Path, report: GateReport) -> int:
    found = 0
    for path in sorted(root.rglob("*.json")):
        if model_for_path(str(path)) is not None:
            _validate_file(path, report)
            found += 1
    return found


def gate_city(city: str, data_root: Path, report: GateReport) -> None:
    """Validate every known JSON present under {data_root}/{city} plus shared globals.

    Presence-based (does not require a full file set), so a poisoned dir with only a
    bad file still trips the gate.
    """
    city_dir = data_root / city
    found = _scan_known_json(city_dir, report) if city_dir.exists() else 0
    for name in ("manifest.json", "receipts.json"):
        gpath = data_root / name
        if gpath.exists():
            _validate_file(gpath, report)
    if found == 0 and not city_dir.exists():
        report.errors.append(f"gate --city {city}: no directory {city_dir}")
    elif found == 0:
        report.errors.append(f"gate --city {city}: no known JSON files under {city_dir}")


def gate_all(data_root: Path, report: GateReport) -> None:
    """Validate manifest + receipts + every known JSON, and enforce manifest completeness."""
    manifest_path = data_root / "manifest.json"
    if not manifest_path.exists():
        report.errors.append(f"gate --all: missing manifest.json in {data_root}")
        return
    _scan_known_json(data_root, report)
    # Completeness: every model-owned file the manifest declares must exist.
    try:
        manifest = ManifestDoc.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
    except (ValidationError, json.JSONDecodeError):
        return  # already recorded by _validate_file
    for city in manifest.cities:
        for key, rel in city.files.model_dump(exclude_none=True).items():
            if not rel.endswith(".json") or model_for_path(rel) is None:
                continue  # wards.geojson etc. are validated elsewhere
            if not (data_root / rel).exists():
                report.errors.append(f"gate --all: {city.id}.files.{key} declared but missing: {rel}")


def run_gate(*, city: str, data_root: str | None) -> int:
    root = Path(data_root) if data_root else web_data_dir()
    if not root.exists():
        log.error("gate.data_root_missing", data_root=str(root))
        return 1
    _register_external_models()
    report = GateReport()
    if city == "all":
        gate_all(root, report)
    else:
        gate_city(city, root, report)
    if report.ok:
        log.info("gate.pass", checked=len(report.checked), data_root=str(root))
        return 0
    for err in report.errors:
        log.error("gate.reject", detail=err)
    log.error("gate.fail", errors=len(report.errors), checked=len(report.checked))
    return 1


__all__ = ["GateReport", "gate_city", "gate_all", "run_gate"]
