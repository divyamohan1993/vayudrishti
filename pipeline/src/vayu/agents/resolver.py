"""Deterministic evidence resolver (spec 14, acceptance 18) — the authoritative gate.

ONE ``resolve()`` code path is used in both directions:
- Tools build a ref by resolving a path against a loaded artifact, so any ref a tool
  emits is resolvable BY CONSTRUCTION (``make_ref``).
- The verifier re-resolves each ref the model returns and checks its asserted value
  against the artifact's own ground-truth value (``verify_brief``).

Grammar (a deliberately tiny, constrained dotted-path — LLM output is untrusted, so it
gets no general query language):

    path      := ROOT ('.' KEY | '[' SELECTOR ']')*
    ROOT/KEY  := [A-Za-z0-9_]+                 # ROOT must equal the ref's `artifact`
    SELECTOR  := DIGITS                         # list index, e.g. [0]
               | FIELD '=' VALUE                # first list item where item[FIELD]==VALUE
    FIELD     := [A-Za-z0-9_]+
    VALUE     := any run of chars except ']'    # compared numerically if both parse, else as text

Examples:
    forecast.wards[ward_id=delhi_042].series[h=24].pm25_p90
    ledger.wards[ward_id=delhi_042].effect_ugm3
    enforcement.ranked[0].priority_score
    attribution.wards[ward_id=delhi_042].shares.traffic
    receipts.cities.delhi.forecast.24.skill_pct   (receipts is global)

A ref MUST resolve to a scalar (number / string / bool / null); resolving to an object
or array is rejected. The pipeline OVERWRITES the model's asserted value with the resolved
one, so a published value is always the artifact's own; the numeric tolerance is purely a
hallucination tripwire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Numeric hallucination tripwire. Generous enough for rounding, tight enough to catch a
# fabricated figure. The published value is the resolved ground truth regardless.
ATOL = 0.05
RTOL = 0.02

# Defensive caps on untrusted paths.
_MAX_PATH_LEN = 300
_MAX_STEPS = 16

Scalar = bool | int | float | str | None


class ResolveError(ValueError):
    """A path did not resolve against the given artifact."""


# ---------------------------------------------------------------- path grammar


def _read_ident(path: str, i: int) -> tuple[str, int]:
    j = i
    n = len(path)
    while j < n and (path[j].isalnum() or path[j] == "_"):
        j += 1
    return path[i:j], j


def _selector_step(inner: str) -> tuple:
    inner = inner.strip()
    if inner == "":
        raise ResolveError("empty [] selector")
    if inner.isdigit():
        return ("index", int(inner))
    if "=" in inner:
        field_name, value = inner.split("=", 1)
        field_name = field_name.strip()
        if not field_name or not all(c.isalnum() or c == "_" for c in field_name):
            raise ResolveError(f"bad predicate field {field_name!r}")
        return ("pred", field_name, value)
    raise ResolveError(f"unsupported selector {inner!r} (only [index] or [field=value])")


def parse_path(path: str) -> list[tuple]:
    """Parse a dotted-path into steps. Raises :class:`ResolveError` on any invalid token."""
    if not isinstance(path, str) or not path:
        raise ResolveError("path must be a non-empty string")
    if len(path) > _MAX_PATH_LEN:
        raise ResolveError("path too long")
    steps: list[tuple] = []
    i, n = 0, len(path)
    while i < n:
        ch = path[i]
        if ch == ".":
            i += 1
            continue
        if ch == "[":
            end = path.find("]", i)
            if end == -1:
                raise ResolveError("unterminated '['")
            steps.append(_selector_step(path[i + 1 : end]))
            i = end + 1
            continue
        ident, j = _read_ident(path, i)
        if j == i:
            raise ResolveError(f"unexpected character {ch!r} at index {i}")
        steps.append(("key", ident))
        i = j
        if len(steps) > _MAX_STEPS:
            raise ResolveError("path has too many steps")
    if not steps:
        raise ResolveError("empty path")
    return steps


def _eq(actual: Any, value: str) -> bool:
    if isinstance(actual, bool):
        return str(actual).lower() == value.strip().lower()
    if isinstance(actual, (int, float)):
        try:
            return float(actual) == float(value)
        except ValueError:
            return False
    return str(actual) == value


def _walk(root: Any, steps: list[tuple]) -> Any:
    cur = root
    for step in steps:
        kind = step[0]
        if kind == "key":
            if not isinstance(cur, dict) or step[1] not in cur:
                raise ResolveError(f"key {step[1]!r} not found")
            cur = cur[step[1]]
        elif kind == "index":
            if not isinstance(cur, list) or not (0 <= step[1] < len(cur)):
                raise ResolveError(f"index [{step[1]}] out of range")
            cur = cur[step[1]]
        elif kind == "pred":
            if not isinstance(cur, list):
                raise ResolveError(f"predicate [{step[1]}=...] applied to non-list")
            field_name, value = step[1], step[2]
            match = next(
                (
                    it
                    for it in cur
                    if isinstance(it, dict) and field_name in it and _eq(it[field_name], value)
                ),
                None,
            )
            if match is None:
                raise ResolveError(f"no list item where {field_name}={value!r}")
            cur = match
        else:  # pragma: no cover - parse_path never emits other kinds
            raise ResolveError(f"unknown step {step!r}")
    return cur


def resolve(root_obj: Any, path: str, expected_artifact: str | None = None) -> Scalar:
    """Resolve ``path`` against ``root_obj`` (the artifact's parsed JSON) to a scalar.

    The path's first token is the artifact name; if ``expected_artifact`` is given it must
    match. Resolving to a dict/list is an error (a ref must name a concrete value).
    """
    steps = parse_path(path)
    if steps[0][0] != "key":
        raise ResolveError("path must start with the artifact name")
    root_name = steps[0][1]
    if expected_artifact is not None and root_name != expected_artifact:
        raise ResolveError(f"path root {root_name!r} != artifact {expected_artifact!r}")
    value = _walk(root_obj, steps[1:])
    if isinstance(value, (dict, list)):
        raise ResolveError("path resolves to a container, not a scalar value")
    return value


def values_match(claimed: Any, resolved: Any, atol: float = ATOL, rtol: float = RTOL) -> bool:
    """Hallucination tripwire: does the model's asserted value match the resolved one?

    A boolean matches only another boolean of equal value (``true`` never matches ``1``),
    so a type-confused assertion is caught rather than coerced away.
    """
    c_bool, r_bool = isinstance(claimed, bool), isinstance(resolved, bool)
    if c_bool or r_bool:
        return c_bool and r_bool and claimed == resolved
    if isinstance(claimed, (int, float)) and isinstance(resolved, (int, float)):
        return abs(float(claimed) - float(resolved)) <= max(atol, rtol * abs(float(resolved)))
    return str(claimed) == str(resolved)


# ---------------------------------------------------------------- artifact loading

# Global (not per-city) published artifacts.
_GLOBAL_ARTIFACTS = {"receipts"}


def artifact_path(data_root: Path, city: str, artifact: str) -> Path:
    if artifact in _GLOBAL_ARTIFACTS:
        return data_root / f"{artifact}.json"
    return data_root / city / f"{artifact}.json"


def load_artifacts(data_root: Path, city: str, artifacts: list[str]) -> dict[str, Any]:
    """Load the requested published artifacts for a city. Missing files are omitted (the
    resolver then reports refs into them as unresolvable, which drops the brief)."""
    out: dict[str, Any] = {}
    for name in artifacts:
        p = artifact_path(data_root, city, name)
        if p.exists():
            try:
                out[name] = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return out


def make_ref(artifacts: dict[str, Any], artifact: str, path: str, label: str) -> dict[str, Any]:
    """Build a resolvable evidence ref from a tool. Raises if the path does not resolve to a
    scalar, so a tool can never hand the model an unresolvable ref."""
    if artifact not in artifacts:
        raise ResolveError(f"artifact {artifact!r} not loaded")
    value = resolve(artifacts[artifact], path, expected_artifact=artifact)
    return {"label": label, "artifact": artifact, "path": path, "value": value, "resolved": True}


# ---------------------------------------------------------------- brief verification


@dataclass(slots=True)
class BriefVerification:
    ok: bool
    brief: dict[str, Any]
    errors: list[str] = field(default_factory=list)


def _infer_artifact(path: str) -> str:
    return parse_path(path)[0][1]


def verify_brief(artifacts: dict[str, Any], brief: dict[str, Any]) -> BriefVerification:
    """Resolve every evidence_ref (and basis_ref) of one brief against the loaded artifacts.

    On success returns the brief with each ref/effect value overwritten by the resolved
    ground truth. On any unresolvable or mismatched ref returns ok=False with reasons.
    """
    import copy

    out = copy.deepcopy(brief)
    errors: list[str] = []

    refs = out.get("evidence_refs") or []
    if not refs:
        errors.append("brief has no evidence_refs")
    for idx, ref in enumerate(refs):
        artifact = ref.get("artifact")
        path = ref.get("path", "")
        if artifact not in artifacts:
            errors.append(f"evidence_refs[{idx}]: artifact {artifact!r} not published")
            continue
        try:
            resolved = resolve(artifacts[artifact], path, expected_artifact=artifact)
        except ResolveError as exc:
            errors.append(f"evidence_refs[{idx}]: {path!r} -> {exc}")
            continue
        if not values_match(ref.get("value"), resolved):
            errors.append(
                f"evidence_refs[{idx}]: asserted {ref.get('value')!r} != resolved {resolved!r}"
            )
            continue
        ref["value"] = resolved  # publish ground truth
        ref["resolved"] = True

    effect = out.get("expected_effect")
    if effect is not None:
        basis = effect.get("basis_ref", "")
        try:
            art = _infer_artifact(basis)
        except ResolveError as exc:
            errors.append(f"expected_effect.basis_ref: unparseable ({exc})")
            art = None
        if art is not None:
            if art not in artifacts:
                errors.append(f"expected_effect.basis_ref: artifact {art!r} not published")
            else:
                try:
                    resolved = resolve(artifacts[art], basis, expected_artifact=art)
                except ResolveError as exc:
                    errors.append(f"expected_effect.basis_ref: {basis!r} -> {exc}")
                else:
                    if not isinstance(resolved, (int, float)) or isinstance(resolved, bool):
                        errors.append("expected_effect.basis_ref must resolve to a number")
                    elif not values_match(effect.get("ugm3"), resolved):
                        errors.append(
                            f"expected_effect.ugm3 {effect.get('ugm3')!r} != basis {resolved!r}"
                        )
                    else:
                        effect["ugm3"] = float(resolved)  # ground truth

    return BriefVerification(ok=not errors, brief=out, errors=errors)


@dataclass(slots=True)
class DocVerification:
    kept: list[dict[str, Any]]
    dropped: list[tuple[dict[str, Any], list[str]]]


def verify_briefs(artifacts: dict[str, Any], briefs: list[dict[str, Any]]) -> DocVerification:
    """Verify a list of briefs; return survivors (ground-truthed) and drops (with reasons)."""
    kept: list[dict[str, Any]] = []
    dropped: list[tuple[dict[str, Any], list[str]]] = []
    for brief in briefs:
        res = verify_brief(artifacts, brief)
        if res.ok:
            kept.append(res.brief)
        else:
            dropped.append((brief, res.errors))
    return DocVerification(kept=kept, dropped=dropped)


__all__ = [
    "ResolveError",
    "ATOL",
    "RTOL",
    "parse_path",
    "resolve",
    "values_match",
    "artifact_path",
    "load_artifacts",
    "make_ref",
    "verify_brief",
    "verify_briefs",
    "BriefVerification",
    "DocVerification",
]
