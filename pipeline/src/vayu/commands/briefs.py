"""`vayu briefs` — build verified Action Briefs from published artifacts (spec 14).

Runs AFTER ``vayu publish`` (it reasons over the just-published per-city JSONs). Failure
semantics are absolute (acceptance 19): any NIM failure, missing key, or unexpected error
keeps the previous briefs.json (marked stale) or emits a minimal stale envelope on cold
start, logs a warning, and returns 0. It NEVER aborts the publish pipeline.

Every emitted file passes an independent publish gate (acceptance 20): the serialized JSON
is grepped for ``</think>`` leakage and NVIDIA key material before it is written.
"""

from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path
from typing import Any

from vayu.agents import nim, resolver
from vayu.agents.contracts import RESOLVABLE_ARTIFACTS
from vayu.agents.nim import NIM_MODEL_ID, THINK_LEAK, NimError
from vayu.logging_setup import get_logger
from vayu.settings import get_settings
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("vayu.briefs")

CITIES = ("delhi", "mumbai", "bengaluru")
# Key material must never reach a published file (acceptance 20).
_KEY_LEAK = "nvapi-"
# Required-and-nullable fields whose null value must be kept (not pruned).
_KEEP_NULL = {"expected_effect", "value"}


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "briefs",
        help="Build verified, evidence-cited Action Briefs (Nemotron agentic layer, spec 14).",
    )
    p.add_argument("--city", required=True, help="delhi | mumbai | bengaluru | all")
    p.add_argument(
        "--data-dir", default=None, help="Override web/public/data root (default from settings)."
    )
    p.add_argument("--max-calls", type=int, default=None, help="Hard NIM call ceiling per city.")
    p.add_argument(
        "--audit",
        action="store_true",
        help="Do not generate: re-resolve every ref in the PUBLISHED briefs.json against the "
        "published artifacts (acceptance 18). Exit 1 if any published ref fails.",
    )
    p.set_defaults(func=run)


def _prune(obj: Any, *, key: str | None = None) -> Any:
    """Drop None values (absent == default) EXCEPT required-nullable fields, recursively."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if v is None and k not in _KEEP_NULL:
                continue
            out[k] = _prune(v, key=k)
        return out
    if isinstance(obj, list):
        return [_prune(v) for v in obj]
    return obj


def _gate(text: str, path: Path) -> None:
    """Refuse to publish a file carrying a </think> trace or key material (acceptance 20)."""
    if THINK_LEAK.search(text):
        raise NimError(f"</think> leak detected in {path.name}; refusing to publish")
    if _KEY_LEAK in text:
        raise NimError(f"key material detected in {path.name}; refusing to publish")


def _write_json(path: Path, doc: Any) -> None:
    payload = _prune(doc)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _gate(text, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _briefs_path(data_root: Path, city: str) -> Path:
    return data_root / city / "briefs.json"


def _agentlog_path(data_root: Path) -> Path:
    return data_root / "agentlog.json"


def _read_prev(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _keep_stale_briefs(data_root: Path, city: str) -> None:
    """Preserve the previous briefs (stale), or emit a minimal stale envelope on cold start."""
    path = _briefs_path(data_root, city)
    prev = _read_prev(path)
    if prev is not None:
        prev["stale"] = True
        doc = prev
    else:
        doc = {
            "generated_at": utc_iso_z(now_utc()),
            "model": NIM_MODEL_ID,
            "stale": True,
            "briefs": [],
        }
    try:
        _write_json(path, doc)
        log.warning("briefs_stale_kept", city=city, had_previous=prev is not None)
    except NimError as exc:
        # A poisoned previous file: do not propagate it. Overwrite with a clean stale envelope.
        clean = {
            "generated_at": utc_iso_z(now_utc()),
            "model": NIM_MODEL_ID,
            "stale": True,
            "briefs": [],
        }
        _write_json(path, clean)
        log.warning("briefs_stale_reset", city=city, reason=str(exc))


def _resolve_cities(arg: str) -> list[str]:
    return list(CITIES) if arg == "all" else [arg]


def _run_audit(data_root: Path, cities: list[str]) -> int:
    """Re-resolve every ref in each published briefs.json; print a report, exit 1 on any fail."""
    from vayu.agents.audit import audit_city

    results = [audit_city(data_root, c) for c in cities]
    for r in results:
        if r.ok:
            log.info(
                "audit_ok",
                city=r.city,
                briefs=r.briefs_audited,
                refs=r.refs_checked,
                skipped_stale=r.skipped_stale,
            )
        else:
            log.error("audit_failed", city=r.city, failures=r.failures)
    summary = {
        "audit": "resolver-receipts",
        "audited_at": utc_iso_z(now_utc()),
        "passed": all(r.ok for r in results),
        "total_briefs": sum(r.briefs_audited for r in results),
        "total_refs_checked": sum(r.refs_checked for r in results),
        "cities": [
            {
                "city": r.city,
                "briefs_audited": r.briefs_audited,
                "refs_checked": r.refs_checked,
                "passed": r.ok,
                "skipped_stale": r.skipped_stale,
                **({"failures": r.failures} if r.failures else {}),
            }
            for r in results
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def _briefs_fixture(data_root: Path, city: str) -> bool:
    doc = _read_prev(_briefs_path(data_root, city))
    return bool(doc and doc.get("fixture"))


def _assemble_agentlog(
    prev_log: dict[str, Any],
    processed: set[str],
    all_runs: list[dict[str, Any]],
    audits: list[Any],
    fixture: bool,
    gen_at: str,
) -> dict[str, Any]:
    """Merge this run's per-city traces into ``prev_log``, replacing ONLY the cities processed
    this run so a per-city run never clobbers other cities. The audit stamp and fixture flag
    span ALL published cities (``audits`` is over every city)."""
    kept = [r for r in (prev_log.get("runs") or []) if r.get("city") not in processed]
    runs = kept + all_runs
    ti = sum(r["tokens_in"] for r in runs)
    to = sum(r["tokens_out"] for r in runs)
    doc: dict[str, Any] = {
        "generated_at": gen_at,
        "model": NIM_MODEL_ID,
        "runs": runs,
        "totals": {"tokens_in": ti, "tokens_out": to, "total": ti + to, "calls": len(runs)},
    }
    if fixture:
        doc["fixture"] = True
    if not runs:
        doc["stale"] = True
    if any(a.briefs_audited for a in audits) or runs:
        doc["audit"] = {
            "passed": all(a.ok for a in audits),
            "briefs_audited": sum(a.briefs_audited for a in audits),
            "refs_checked": sum(a.refs_checked for a in audits),
            "audited_at": gen_at,
        }
    return doc


def run(args: argparse.Namespace) -> int:
    from vayu.agents.orchestrator import MAX_CALLS, generate_briefs

    settings = get_settings()
    data_root = Path(args.data_dir) if args.data_dir else settings.resolved_web_data_dir

    if getattr(args, "audit", False):
        return _run_audit(data_root, _resolve_cities(args.city))

    max_calls = args.max_calls or MAX_CALLS
    key = settings.nvidia_api_key

    all_runs: list[dict[str, Any]] = []
    client = None
    cities = _resolve_cities(args.city)

    for city in cities:
        try:
            if not key:
                raise NimError("NVIDIA_API_KEY absent; agentic layer disabled")
            artifacts = resolver.load_artifacts(data_root, city, list(RESOLVABLE_ARTIFACTS))
            if not artifacts.get("forecast"):
                log.info("briefs_skip_no_forecast", city=city)
                _keep_stale_briefs(data_root, city)
                continue
            if client is None:
                client = nim.build_client(key)
            call_fn = functools.partial(nim.chat, client)
            briefs_doc, log_doc = generate_briefs(
                artifacts, city, call_fn, model=NIM_MODEL_ID, max_calls=max_calls
            )
            _write_json(_briefs_path(data_root, city), briefs_doc.model_dump())
            all_runs.extend(r.model_dump() for r in log_doc.runs)
            log.info(
                "briefs_published",
                city=city,
                n_briefs=len(briefs_doc.briefs),
                calls=log_doc.totals.calls if log_doc.totals else None,
                tokens=log_doc.totals.total if log_doc.totals else None,
            )
        except NimError as exc:
            log.warning("briefs_nim_failure", city=city, error=str(exc))
            _keep_stale_briefs(data_root, city)
        except Exception as exc:  # noqa: BLE001 - agent layer must never fail publish
            log.warning("briefs_unexpected_error", city=city, error=f"{type(exc).__name__}: {exc}")
            _keep_stale_briefs(data_root, city)

    # Global agentlog: MERGE this run's per-city traces into the prior file (a per-city run must
    # not clobber other cities), then self-audit ALL published cities so the stamp + fixture flag
    # span the whole set, not just the cities processed this run.
    from vayu.agents.audit import audit_city

    gen_at = utc_iso_z(now_utc())
    audits = [audit_city(data_root, c) for c in CITIES]
    fixture = any(_briefs_fixture(data_root, c) for c in CITIES)
    prev_log = _read_prev(_agentlog_path(data_root)) or {}
    agentlog = _assemble_agentlog(prev_log, set(cities), all_runs, audits, fixture, gen_at)
    try:
        _write_json(_agentlog_path(data_root), agentlog)
    except NimError as exc:
        log.warning("agentlog_gate_failed", error=str(exc))

    return 0
