"""Pydantic content models mirroring config/schemas/*.json (owner: vayu-models).

These are the emit contract AND the content gate. ``vayu publish`` constructs them
(so it cannot emit invalid data); ``vayu gate`` re-reads emitted files and constructs
them (rejecting tampered/malformed files, acceptance 13). They enforce the cross-field
invariants JSON Schema cannot express:

- pm25_p90 >= pm25_p50 (nowcast cells/wards, forecast points)
- category == aqi.category_for_index(subindex24h)
- attribution shares sum ~= 1.0
- enforcement.ranked sorted by priority_score descending
- ci_low <= point estimate <= ci_high (interventions effects, ledger wards/totals/counterfactuals)
- lineage base_url carries no query string
- every emitted string free of HTML/control chars (via sanitize validators)

``extra="forbid"`` matches ``additionalProperties: false`` and catches poisoned extra fields.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from vayu.aqi import category_for_index
from vayu.constants import (
    AQI_CATEGORIES,
    CONFIDENCE_LEVELS,
    ENFORCEMENT_ACTIONS,
    RISK_LEVELS,
    SHARE_KEYS,
    SOURCE_LABELS,
)
from vayu.publish.sanitize import CitationUrl, CleanStr, LineageUrl, clean_scalar

# ---------------------------------------------------------------- shared types

PM_MIN, PM_MAX = 0.0, 2000.0
SUBIDX_MIN, SUBIDX_MAX = 0.0, 500.0

_CELL_ID = re.compile(r"^[a-z]+_[0-9]+_[0-9]+$")
_WARD_ID = re.compile(r"^[a-z]+_[a-z0-9]+$")
_CITY_ID = re.compile(r"^[a-z]+$")


def _validate_iso_dt(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 datetime: {value!r}") from exc
    return value


def _validate_iso_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid ISO date (YYYY-MM-DD): {value!r}") from exc
    return value


IsoDateTime = Annotated[str, AfterValidator(_validate_iso_dt)]
IsoDate = Annotated[str, AfterValidator(_validate_iso_date)]
Category = Annotated[str, AfterValidator(lambda v: v if v in AQI_CATEGORIES else _bad(v, "category"))]
Confidence = Annotated[str, AfterValidator(lambda v: v if v in CONFIDENCE_LEVELS else _bad(v, "confidence"))]
SourceLabel = Annotated[str, AfterValidator(lambda v: v if v in SOURCE_LABELS else _bad(v, "source_label"))]
RiskLevel = Annotated[str, AfterValidator(lambda v: v if v in RISK_LEVELS else _bad(v, "risk_level"))]
Action = Annotated[str, AfterValidator(lambda v: v if v in ENFORCEMENT_ACTIONS else _bad(v, "action"))]
Pm = Annotated[float, Field(ge=PM_MIN, le=PM_MAX)]
SubIndex = Annotated[float, Field(ge=SUBIDX_MIN, le=SUBIDX_MAX)]


def _bad(value, field):
    raise ValueError(f"{value!r} is not a valid {field}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def _check_p90(p50: float, p90: float) -> None:
    if p90 < p50:
        raise ValueError(f"pm25_p90 ({p90}) < pm25_p50 ({p50})")


def _check_category(subindex24h: float, category: str) -> None:
    expected = category_for_index(subindex24h)
    if category != expected:
        raise ValueError(
            f"category {category!r} != category_for_index({subindex24h}) = {expected!r}"
        )


def _check_ci(low: float, point: float, high: float, label: str) -> None:
    if not (low <= point <= high):
        raise ValueError(f"{label}: require ci_low <= point <= ci_high, got {low} <= {point} <= {high}")


# ---------------------------------------------------------------- nowcast

class GridMetaModel(_Strict):
    lat0: float
    lon0: float
    cell_deg: float = Field(gt=0)
    crs: Literal["EPSG:4326"]


class NowcastCell(_Strict):
    cell_id: str = Field(pattern=_CELL_ID.pattern)
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    pm25_p50: Pm
    pm25_p90: Pm
    subindex24h: SubIndex
    category: Category

    @model_validator(mode="after")
    def _invariants(self):
        _check_p90(self.pm25_p50, self.pm25_p90)
        _check_category(self.subindex24h, self.category)
        return self


class NowcastWard(_Strict):
    ward_id: str = Field(pattern=_WARD_ID.pattern)
    name: CleanStr = Field(min_length=1, max_length=200)
    pm25_p50: Pm
    pm25_p90: Pm
    subindex24h: SubIndex
    category: Category
    confidence: Confidence

    @model_validator(mode="after")
    def _invariants(self):
        _check_p90(self.pm25_p50, self.pm25_p90)
        _check_category(self.subindex24h, self.category)
        return self


class NowcastDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    grid_meta: GridMetaModel
    grid: list[NowcastCell]
    wards: list[NowcastWard]


# ---------------------------------------------------------------- forecast

class ForecastPoint(_Strict):
    h: Literal[24, 48, 72]
    pm25_p50: Pm
    pm25_p90: Pm
    subindex24h: SubIndex
    category: Category
    confidence: Confidence

    @model_validator(mode="after")
    def _invariants(self):
        _check_p90(self.pm25_p50, self.pm25_p90)
        _check_category(self.subindex24h, self.category)
        return self


class ForecastWard(_Strict):
    ward_id: str = Field(pattern=_WARD_ID.pattern)
    name: CleanStr = Field(min_length=1, max_length=200)
    series: list[ForecastPoint] = Field(min_length=1, max_length=3)


class ForecastDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    horizons_h: list[Literal[24, 48, 72]] = Field(min_length=1, max_length=3)
    wards: list[ForecastWard]


# ---------------------------------------------------------------- attribution

class Shares(_Strict):
    traffic: float = Field(ge=0, le=1)
    industry: float = Field(ge=0, le=1)
    biomass: float = Field(ge=0, le=1)
    dust: float = Field(ge=0, le=1)
    residential_other: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sum(self):
        total = sum(getattr(self, k) for k in SHARE_KEYS)
        if not (0.98 <= total <= 1.02):
            raise ValueError(f"attribution shares sum {total:.4f} not within [0.98, 1.02]")
        return self


class AttributionWard(_Strict):
    ward_id: str = Field(pattern=_WARD_ID.pattern)
    shares: Shares
    confidence: Confidence
    method_notes: CleanStr = Field(min_length=1, max_length=500)


class AttributionDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    wards: list[AttributionWard]


# ---------------------------------------------------------------- enforcement

class Evidence(_Strict):
    trend_72h: list[Annotated[float, Field(ge=0, le=PM_MAX)]] = Field(max_length=96)
    persistence_days: int = Field(ge=0, le=400)
    exceedance_pct: float = Field(ge=0, le=100)


class EnforcementItem(_Strict):
    ward_id: str = Field(pattern=_WARD_ID.pattern)
    source_label: SourceLabel
    confidence: Confidence
    priority_score: float = Field(ge=0, le=100)
    evidence: Evidence
    action: Action


class EnforcementDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    ranked: list[EnforcementItem]

    @model_validator(mode="after")
    def _sorted(self):
        scores = [it.priority_score for it in self.ranked]
        if scores != sorted(scores, reverse=True):
            raise ValueError("enforcement.ranked must be sorted by priority_score descending")
        return self


# ---------------------------------------------------------------- advisories

class Langs(_Strict):
    en: CleanStr = Field(min_length=1, max_length=600)
    hi: CleanStr = Field(min_length=1, max_length=600)
    regional: CleanStr | None = Field(default=None, max_length=600)


class AdvisoryItem(_Strict):
    ward_id: str = Field(pattern=_WARD_ID.pattern)
    risk_level: RiskLevel
    langs: Langs


class AdvisoriesDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    wards: list[AdvisoryItem]


# ---------------------------------------------------------------- manifest

class Centroid(_Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ManifestFiles(_Strict):
    nowcast: CleanStr | None = None
    forecast: CleanStr | None = None
    attribution: CleanStr | None = None
    enforcement: CleanStr | None = None
    advisories: CleanStr | None = None
    wards: CleanStr | None = None
    roads: CleanStr | None = None  # per-city road network geojson (vayu-data)
    fires: CleanStr | None = None  # per-city observed fire-cluster layer (vayu-data)
    replay_index: CleanStr | None = None
    interventions: CleanStr | None = None
    ledger: CleanStr | None = None
    briefs: CleanStr | None = None  # per-city agentic briefs (vayu-agents)


class CityManifest(_Strict):
    id: str = Field(pattern=_CITY_ID.pattern)
    name: CleanStr = Field(min_length=1, max_length=80)
    tier: Literal["deep", "standard", "config-only"]
    centroid: Centroid
    bbox: list[float] = Field(min_length=4, max_length=4)
    languages: list[Annotated[str, Field(pattern=r"^[a-z]{2}$")]] = Field(min_length=1, max_length=4)
    files: ManifestFiles
    fixture: bool | None = None
    generated_at: IsoDateTime | None = None


class ManifestDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    sat_numeric: bool
    cities: list[CityManifest] = Field(min_length=1)
    agentlog: CleanStr | None = None  # global agentic run log (vayu-agents); not per-city


# ---------------------------------------------------------------- replay index

class ReplayWindow(_Strict):
    start: IsoDate
    end: IsoDate


class ReplayIndexDoc(_Strict):
    city: str = Field(pattern=_CITY_ID.pattern)
    generated_at: IsoDateTime
    fixture: bool | None = None
    window: ReplayWindow
    dates: list[IsoDate] = Field(min_length=1)
    note: CleanStr | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------- interventions

class CalendarEntry(_Strict):
    stage: Literal["GRAP-I", "GRAP-II", "GRAP-III", "GRAP-IV"]
    start_utc: IsoDateTime
    end_utc: IsoDateTime | None = None
    source_url: CitationUrl = Field(max_length=500)


class SeriesPoint(_Strict):
    ts_utc: IsoDateTime
    pm25_raw: Pm
    pm25_normalized: Pm
    pm25_normalized_p90: Pm | None = None


class EffectEntry(_Strict):
    stage_transition: CleanStr = Field(min_length=1, max_length=120)
    effect_ugm3: float = Field(ge=-PM_MAX, le=PM_MAX)
    ci_low: float = Field(ge=-PM_MAX, le=PM_MAX)
    ci_high: float = Field(ge=-PM_MAX, le=PM_MAX)
    placebo_pass: bool
    n_days: int = Field(ge=0, le=400)
    method_notes: CleanStr = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _ci(self):
        _check_ci(self.ci_low, self.effect_ugm3, self.ci_high, "effect")
        return self


class InterventionsDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    calendar: list[CalendarEntry] = Field(min_length=1)
    series: list[SeriesPoint] = Field(min_length=1)
    effects: list[EffectEntry]


# ---------------------------------------------------------------- ledger

class LedgerTotals(_Strict):
    avoided_exposure_pugh: float
    avoided_deaths: float
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _ci(self):
        _check_ci(self.ci_low, self.avoided_deaths, self.ci_high, "totals.avoided_deaths")
        return self


class LedgerByStage(_Strict):
    stage_transition: CleanStr = Field(max_length=120)
    effect_ugm3: float = Field(ge=-PM_MAX, le=PM_MAX)


class LedgerWard(_Strict):
    ward_id: str = Field(pattern=_WARD_ID.pattern)
    avoided_exposure_pugh: float
    avoided_deaths: float
    ci_low: float
    ci_high: float
    effect_ugm3: float = Field(ge=-PM_MAX, le=PM_MAX)
    effect_ci_low: float = Field(ge=-PM_MAX, le=PM_MAX)
    effect_ci_high: float = Field(ge=-PM_MAX, le=PM_MAX)
    by_stage: list[LedgerByStage] | None = None

    @model_validator(mode="after")
    def _ci(self):
        _check_ci(self.ci_low, self.avoided_deaths, self.ci_high, "ward.avoided_deaths")
        _check_ci(self.effect_ci_low, self.effect_ugm3, self.effect_ci_high, "ward.effect_ugm3")
        return self


class Counterfactual(_Strict):
    scenario: CleanStr = Field(min_length=1, max_length=120)
    shift_hours: int = Field(ge=-168, le=168)
    delta_exposure: float
    delta_deaths: float
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _ci(self):
        _check_ci(self.ci_low, self.delta_deaths, self.ci_high, "counterfactual.delta_deaths")
        return self


class Citation(_Strict):
    label: CleanStr = Field(min_length=1, max_length=200)
    url: CitationUrl = Field(max_length=500)


class LedgerDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    totals: LedgerTotals
    wards: list[LedgerWard]
    counterfactuals: list[Counterfactual]
    citations: list[Citation] = Field(min_length=1)
    assumptions: list[Annotated[str, AfterValidator(clean_scalar)]] | None = None


# ---------------------------------------------------------------- receipts

class CvBucket(_Strict):
    dist_km: float = Field(ge=0)
    model_rmse: float = Field(ge=0)
    idw_rmse: float = Field(ge=0)
    n: int = Field(ge=0)


class NowcastCV(_Strict):
    baseline: CleanStr
    buckets: list[CvBucket]


class ForecastMetric(_Strict):
    rmse: float = Field(ge=0)
    mae: float = Field(ge=0)
    persistence_rmse: float = Field(ge=0)
    seasonal_naive_rmse: float = Field(ge=0)
    skill_pct: float  # may be negative (honest reporting)
    n: int = Field(ge=0)
    embargo_h: int = Field(ge=0)


class DirectionalCheck(_Strict):
    check_name: CleanStr = Field(min_length=1, max_length=160)
    expected: Annotated[str | float, AfterValidator(clean_scalar)]
    observed: Annotated[str | float, AfterValidator(clean_scalar)]
    passed: bool = Field(alias="pass")
    notes: CleanStr | None = Field(default=None, max_length=300)


class Ablation(_Strict):
    note: CleanStr | None = Field(default=None, max_length=400)
    metric: CleanStr | None = None
    with_sat: float | None = None
    without_sat: float | None = None
    delta_pct: float | None = None


class CityReceipt(_Strict):
    nowcast_cv: NowcastCV | None = None
    forecast: dict[Literal["24", "48", "72"], ForecastMetric] | None = None
    attribution_directional_checks: list[DirectionalCheck] | None = None
    ablation: Ablation | None = None
    intervention_assumptions: list[Annotated[str, AfterValidator(clean_scalar)]] | None = None


class LineageEntry(_Strict):
    source: CleanStr = Field(min_length=1, max_length=120)
    base_url: LineageUrl = Field(max_length=400)
    resource_id: CleanStr = Field(max_length=200)
    fetched_at: IsoDateTime
    rows: int = Field(ge=0)


class BreakpointRow(_Strict):
    pollutant: CleanStr
    unit: CleanStr
    category: Category
    conc_low: float
    conc_high: float
    index_low: float
    index_high: float
    extrapolated: bool


class Methodology(_Strict):
    headline_label: CleanStr | None = None
    severe_note: CleanStr | None = Field(default=None, max_length=600)
    aqi_breakpoints: list[BreakpointRow] | None = None


class MethodCitation(_Strict):
    label: CleanStr = Field(min_length=1, max_length=200)
    url: CitationUrl = Field(max_length=500)
    used_for: CleanStr | None = Field(default=None, max_length=200)


class LedgerReceipt(_Strict):
    novelty_statement: CleanStr = Field(min_length=1, max_length=1500)
    prior_art: list[Citation]
    method_citations: list[MethodCitation]


class ReceiptsDoc(_Strict):
    generated_at: IsoDateTime
    fixture: bool | None = None
    honesty_notes: list[Annotated[str, AfterValidator(clean_scalar)]]
    methodology: Methodology | None = None
    ledger: LedgerReceipt | None = None
    cities: dict[str, CityReceipt]
    lineage: list[LineageEntry]

    @field_validator("cities")
    @classmethod
    def _city_keys(cls, v):
        for key in v:
            if not _CITY_ID.match(key):
                raise ValueError(f"receipts.cities key {key!r} not a valid city slug")
        return v


# ---------------------------------------------------------------- registry

# Maps a published filename to its content model, for the file-scanning gate.
MODEL_BY_FILENAME: dict[str, type[_Strict]] = {
    "nowcast.json": NowcastDoc,
    "forecast.json": ForecastDoc,
    "attribution.json": AttributionDoc,
    "enforcement.json": EnforcementDoc,
    "advisories.json": AdvisoriesDoc,
    "manifest.json": ManifestDoc,
    "receipts.json": ReceiptsDoc,
    "interventions.json": InterventionsDoc,
    "ledger.json": LedgerDoc,
    "index.json": ReplayIndexDoc,  # replay/index.json
}


def model_for_path(path: str) -> type[_Strict] | None:
    """Content model for a published JSON path, by its basename."""
    import os

    return MODEL_BY_FILENAME.get(os.path.basename(path))


__all__ = [
    "NowcastDoc",
    "ForecastDoc",
    "AttributionDoc",
    "EnforcementDoc",
    "AdvisoriesDoc",
    "ManifestDoc",
    "ReceiptsDoc",
    "InterventionsDoc",
    "LedgerDoc",
    "ReplayIndexDoc",
    "MODEL_BY_FILENAME",
    "model_for_path",
]
