"""Pydantic content models for briefs.json + agentlog.json (spec 14, owner: vayu-agents).

These mirror ``config/schemas/briefs.schema.json`` and ``agentlog.schema.json`` and
ARE the emit contract AND the content gate for the agentic layer:

- The briefs command constructs :class:`BriefsDoc` before writing, so it cannot emit
  schema/range/sanitization/invariant-invalid data.
- vayu-models' file-scanning gate registers these in ``MODEL_BY_FILENAME`` so a tampered
  or malformed published file is rejected (acceptance 13 discipline, extended to briefs).

They enforce cross-field invariants JSON Schema cannot express:
- trigger_window.start_utc <= end_utc
- expected_effect: ci_low <= ugm3 <= ci_high (when present)
- evidence_refs non-empty and every ref.resolved is True (only verified refs publish)
- every emitted string free of HTML / control chars (via sanitize validators)

Resolvability of ``path`` / ``basis_ref`` against sibling artifacts is a SEPARATE,
authoritative check (``vayu.agents.resolver.verify_brief``); it needs the whole published
tree and so is not a per-file pydantic invariant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from vayu.constants import ENFORCEMENT_ACTIONS
from vayu.publish.sanitize import CleanStr

# Artifacts an evidence ref may resolve into (numeric-bearing published files).
RESOLVABLE_ARTIFACTS: tuple[str, ...] = (
    "nowcast",
    "forecast",
    "attribution",
    "enforcement",
    "ledger",
    "interventions",
    "receipts",
)

AGENT_ROLES: tuple[str, ...] = (
    "situation_analyst",
    "causal_strategist",
    "action_drafter",
    "adversarial_verifier",
)

# Brief categories (spec 14/15). "action" is the default compound-risk brief; the others
# are the Depth-Pack types that land after the core loop (same verifier discipline).
BRIEF_TYPES: tuple[str, ...] = ("action", "trigger-watch", "plume-alert", "data-quality")

_WARD_ID = r"^[a-z]+_[a-z0-9]+$"
_BRIEF_ID = r"^[a-z0-9][a-z0-9-]{1,63}$"
_LANG = r"^[a-z]{2}$"
_CITY_ID = r"^[a-z]+$"


def _iso_dt(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 datetime: {value!r}") from exc
    return value


def _action_code(value: str) -> str:
    if value not in ENFORCEMENT_ACTIONS:
        raise ValueError(f"{value!r} is not a valid enforcement action code")
    return value


def _artifact(value: str) -> str:
    if value not in RESOLVABLE_ARTIFACTS:
        raise ValueError(f"{value!r} is not a resolvable artifact")
    return value


def _role(value: str) -> str:
    if value not in AGENT_ROLES:
        raise ValueError(f"{value!r} is not a valid agent role")
    return value


def _brief_type(value: str) -> str:
    if value not in BRIEF_TYPES:
        raise ValueError(f"{value!r} is not a valid brief_type")
    return value


IsoDateTime = Annotated[str, AfterValidator(_iso_dt)]
ActionCode = Annotated[str, AfterValidator(_action_code)]
Artifact = Annotated[str, AfterValidator(_artifact)]
Role = Annotated[str, AfterValidator(_role)]
BriefType = Annotated[str, AfterValidator(_brief_type)]

# A resolved value may be a number, string, boolean, or null. bool precedes int so a
# JSON boolean is not coerced to 0/1.
RefValue = bool | int | float | str | None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------------------------------------------------------------- briefs


class TriggerWindow(_Strict):
    start_utc: IsoDateTime
    end_utc: IsoDateTime

    @model_validator(mode="after")
    def _order(self):
        start = datetime.fromisoformat(self.start_utc.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.end_utc.replace("Z", "+00:00"))
        if end < start:
            raise ValueError(f"trigger_window end_utc {self.end_utc} < start_utc {self.start_utc}")
        return self


class ExpectedEffect(_Strict):
    ugm3: float
    ci_low: float
    ci_high: float
    basis_ref: CleanStr = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _ci(self):
        if not (self.ci_low <= self.ugm3 <= self.ci_high):
            raise ValueError(
                f"expected_effect: require ci_low <= ugm3 <= ci_high, got "
                f"{self.ci_low} <= {self.ugm3} <= {self.ci_high}"
            )
        return self


class EvidenceRef(_Strict):
    label: CleanStr = Field(min_length=1, max_length=200)
    artifact: Artifact
    path: CleanStr = Field(min_length=1, max_length=300)
    value: RefValue
    resolved: Literal[True]


class LedgerRef(_Strict):
    stage_transition: CleanStr | None = Field(default=None, min_length=1, max_length=120)
    scenario: CleanStr | None = Field(default=None, min_length=1, max_length=120)


class Verifier(_Strict):
    passed: bool
    notes: CleanStr = Field(default="", max_length=500)


class Brief(_Strict):
    id: str = Field(pattern=_BRIEF_ID)
    brief_type: BriefType | None = None
    headline: CleanStr = Field(min_length=1, max_length=160)
    situation: CleanStr = Field(min_length=1, max_length=1000)
    action: CleanStr = Field(min_length=1, max_length=600)
    action_code: ActionCode | None = None
    target_wards: list[Annotated[str, Field(pattern=_WARD_ID)]] = Field(min_length=1, max_length=60)
    trigger_window: TriggerWindow
    expected_effect: ExpectedEffect | None
    owner: CleanStr = Field(min_length=1, max_length=120)
    advisory_langs: list[Annotated[str, Field(pattern=_LANG)]] = Field(min_length=1, max_length=4)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)
    ledger_ref: LedgerRef | None = None
    verifier: Verifier


class BriefsDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    stale: bool | None = None
    model: CleanStr = Field(min_length=1, max_length=120)
    briefs: list[Brief]


# ---------------------------------------------------------------- agentlog


class AgentRun(_Strict):
    role: Role
    city: str | None = Field(default=None, pattern=_CITY_ID)
    model: CleanStr = Field(min_length=1, max_length=120)
    reasoning_budget: int = Field(ge=0, le=65536)
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    repairs: int | None = Field(default=None, ge=0, le=2)


class AgentTotals(_Strict):
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    total: int = Field(ge=0)
    calls: int = Field(ge=0)


class AuditStamp(_Strict):
    """Published resolver-receipts result (acceptance 18 as DATA, not a client-side claim).
    Set by the generation self-audit right after briefs are written."""

    passed: bool
    briefs_audited: int = Field(ge=0)
    refs_checked: int = Field(ge=0)
    audited_at: IsoDateTime


class AgentLogDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    stale: bool | None = None
    model: CleanStr = Field(min_length=1, max_length=120)
    runs: list[AgentRun]
    totals: AgentTotals | None = None
    audit: AuditStamp | None = None


__all__ = [
    "RESOLVABLE_ARTIFACTS",
    "AGENT_ROLES",
    "TriggerWindow",
    "ExpectedEffect",
    "EvidenceRef",
    "LedgerRef",
    "Verifier",
    "Brief",
    "BriefsDoc",
    "AgentRun",
    "AgentTotals",
    "AgentLogDoc",
]
