"""Shared fixtures for the agentic-layer tests (spec 14). Schema-valid sample artifacts
for one city (delhi) plus a matching verified brief. No API, no network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_GEN = "2025-11-08T06:00:00Z"


def _nowcast() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "grid_meta": {"lat0": 28.4, "lon0": 76.8, "cell_deg": 0.01, "crs": "EPSG:4326"},
        "grid": [
            {
                "cell_id": "delhi_10_12",
                "row": 10,
                "col": 12,
                "pm25_p50": 175.0,
                "pm25_p90": 235.0,
                "subindex24h": 320.0,
                "category": "Very Poor",
            }
        ],
        "wards": [
            {
                "ward_id": "delhi_042",
                "name": "Anand Vihar",
                "pm25_p50": 180.0,
                "pm25_p90": 240.0,
                "subindex24h": 330.0,
                "category": "Very Poor",
                "confidence": "high",
            },
            {
                "ward_id": "delhi_007",
                "name": "Rohini",
                "pm25_p50": 95.0,
                "pm25_p90": 135.0,
                "subindex24h": 250.0,
                "category": "Poor",
                "confidence": "med",
            },
            {
                "ward_id": "delhi_001",
                "name": "Lodhi Estate",
                "pm25_p50": 45.0,
                "pm25_p90": 70.0,
                "subindex24h": 120.0,
                "category": "Moderate",
                "confidence": "high",
            },
        ],
    }


def _forecast() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "horizons_h": [24, 48, 72],
        "wards": [
            {
                "ward_id": "delhi_042",
                "name": "Anand Vihar",
                "series": [
                    {
                        "h": 24,
                        "pm25_p50": 210.0,
                        "pm25_p90": 412.0,
                        "subindex24h": 430.0,
                        "category": "Severe",
                        "confidence": "med",
                    },
                    {
                        "h": 48,
                        "pm25_p50": 190.0,
                        "pm25_p90": 300.0,
                        "subindex24h": 360.0,
                        "category": "Very Poor",
                        "confidence": "low",
                    },
                    {
                        "h": 72,
                        "pm25_p50": 150.0,
                        "pm25_p90": 240.0,
                        "subindex24h": 330.0,
                        "category": "Very Poor",
                        "confidence": "low",
                    },
                ],
            },
            {
                "ward_id": "delhi_007",
                "name": "Rohini",
                "series": [
                    {
                        "h": 24,
                        "pm25_p50": 110.0,
                        "pm25_p90": 170.0,
                        "subindex24h": 280.0,
                        "category": "Poor",
                        "confidence": "med",
                    },
                ],
            },
            {
                "ward_id": "delhi_001",
                "name": "Lodhi Estate",
                "series": [
                    {
                        "h": 24,
                        "pm25_p50": 48.0,
                        "pm25_p90": 80.0,
                        "subindex24h": 140.0,
                        "category": "Moderate",
                        "confidence": "high",
                    },
                ],
            },
        ],
    }


def _attribution() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "wards": [
            {
                "ward_id": "delhi_042",
                "shares": {
                    "traffic": 0.15,
                    "industry": 0.10,
                    "biomass": 0.55,
                    "dust": 0.10,
                    "residential_other": 0.10,
                },
                "confidence": "med",
                "method_notes": "CPF wind-sector analysis, NW bearing peak.",
            },
            {
                "ward_id": "delhi_007",
                "shares": {
                    "traffic": 0.40,
                    "industry": 0.20,
                    "biomass": 0.15,
                    "dust": 0.15,
                    "residential_other": 0.10,
                },
                "confidence": "low",
                "method_notes": "Mixed urban sources.",
            },
        ],
    }


def _enforcement() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "ranked": [
            {
                "ward_id": "delhi_042",
                "source_label": "biomass",
                "confidence": "high",
                "priority_score": 88.0,
                "evidence": {
                    "trend_72h": [200.0, 260.0, 330.0],
                    "persistence_days": 6,
                    "exceedance_pct": 92.0,
                },
                "action": "ban_open_biomass_burning",
            },
            {
                "ward_id": "delhi_007",
                "source_label": "traffic",
                "confidence": "med",
                "priority_score": 61.0,
                "evidence": {
                    "trend_72h": [150.0, 160.0, 170.0],
                    "persistence_days": 3,
                    "exceedance_pct": 74.0,
                },
                "action": "reroute_divert_heavy_traffic",
            },
        ],
    }


def _ledger() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "totals": {
            "avoided_exposure_pugh": 12000.0,
            "avoided_deaths": 120.0,
            "ci_low": 60.0,
            "ci_high": 190.0,
        },
        "wards": [
            {
                "ward_id": "delhi_042",
                "avoided_exposure_pugh": 1400.0,
                "avoided_deaths": 14.0,
                "ci_low": 6.0,
                "ci_high": 23.0,
                "effect_ugm3": -18.0,
                "effect_ci_low": -31.0,
                "effect_ci_high": -6.0,
            },
        ],
        "counterfactuals": [
            {
                "scenario": "Stage III 48h earlier",
                "shift_hours": -48,
                "delta_exposure": 900.0,
                "delta_deaths": 9.0,
                "ci_low": 3.0,
                "ci_high": 16.0,
            }
        ],
        "citations": [
            {
                "label": "CAQM GRAP order, 2025-11-07",
                "url": "https://caqm.example.gov.in/orders/2025-11-07",
            }
        ],
    }


def _interventions() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "calendar": [
            {
                "stage": "GRAP-II",
                "start_utc": "2025-11-01T00:00:00Z",
                "end_utc": "2025-11-07T00:00:00Z",
                "source_url": "https://caqm.example.gov.in/orders/grap2",
            },
            {
                "stage": "GRAP-III",
                "start_utc": "2025-11-07T00:00:00Z",
                "end_utc": None,
                "source_url": "https://caqm.example.gov.in/orders/grap3",
            },
        ],
        "series": [
            {"ts_utc": "2025-11-07T00:00:00Z", "pm25_raw": 320.0, "pm25_normalized": 300.0},
            {"ts_utc": "2025-11-08T00:00:00Z", "pm25_raw": 290.0, "pm25_normalized": 282.0},
        ],
        "effects": [
            {
                "stage_transition": "GRAP-II to GRAP-III",
                "effect_ugm3": -18.0,
                "ci_low": -31.0,
                "ci_high": -6.0,
                "placebo_pass": True,
                "n_days": 5,
                "method_notes": "Event-study on weather-normalized series, block-bootstrap CI.",
            }
        ],
    }


def _receipts() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "fixture": True,
        "honesty_notes": [
            "Single-winter training window (Feb 2025 to now); no multi-season claims."
        ],
        "cities": {
            "delhi": {
                "forecast": {
                    "24": {
                        "rmse": 42.0,
                        "mae": 31.0,
                        "persistence_rmse": 55.0,
                        "seasonal_naive_rmse": 60.0,
                        "skill_pct": 23.6,
                        "n": 90,
                        "embargo_h": 96,
                    }
                },
                "attribution_directional_checks": [
                    {
                        "check_name": "NW stubble bearing in season",
                        "expected": "NW",
                        "observed": "NW",
                        "pass": True,
                    }
                ],
            }
        },
        "lineage": [
            {
                "source": "OpenAQ S3 archive",
                "base_url": "https://openaq-data-archive.s3.amazonaws.com",
                "resource_id": "cpcb-hourly",
                "fetched_at": _GEN,
                "rows": 120000,
            }
        ],
    }


def _fires() -> dict[str, Any]:
    return {
        "generated_at": _GEN,
        "trailing_hours": 72,
        "source": "NASA FIRMS VIIRS S-NPP",
        "clusters": [
            {
                "cluster_id": "delhi_fc0",
                "centroid": [28.90, 77.10],
                "frp_total": 128.4,
                "fire_count": 22,
                "distance_km": 38.2,
                "bearing_deg": 315.0,
            },
            {
                "cluster_id": "delhi_fc1",
                "centroid": [28.72, 76.88],
                "frp_total": 44.1,
                "fire_count": 7,
                "distance_km": 61.5,
                "bearing_deg": 302.4,
            },
        ],
    }


@pytest.fixture
def artifacts() -> dict[str, Any]:
    """Loaded published artifacts for delhi (as the resolver/digest/tools receive them)."""
    return {
        "nowcast": _nowcast(),
        "forecast": _forecast(),
        "attribution": _attribution(),
        "enforcement": _enforcement(),
        "ledger": _ledger(),
        "interventions": _interventions(),
        "receipts": _receipts(),
        "fires": _fires(),
    }


@pytest.fixture
def data_root(tmp_path: Path, artifacts: dict[str, Any]) -> Path:
    """A web/public/data-style tree on disk: per-city files + global receipts."""
    city_dir = tmp_path / "delhi"
    city_dir.mkdir(parents=True)
    for name in (
        "nowcast",
        "forecast",
        "attribution",
        "enforcement",
        "ledger",
        "interventions",
        "fires",
    ):
        (city_dir / f"{name}.json").write_text(json.dumps(artifacts[name]), encoding="utf-8")
    (tmp_path / "receipts.json").write_text(json.dumps(artifacts["receipts"]), encoding="utf-8")
    return tmp_path


@pytest.fixture
def good_brief() -> dict[str, Any]:
    """A brief whose refs resolve against the `artifacts` fixture."""
    return {
        "id": "delhi-2025-11-08-nw-stubble-01",
        "headline": "Northwest wards cross into Severe with upwind biomass dominant",
        "situation": (
            "Forecast p90 jumps into Severe at 24h in Anand Vihar while attribution shows "
            "biomass as the dominant source and enforcement persistence is high."
        ),
        "action": (
            "Pre-position water sprinkling on Anand Vihar arterials and enforce the "
            "open-biomass-burning ban for 48h."
        ),
        "action_code": "ban_open_biomass_burning",
        "target_wards": ["delhi_042"],
        "trigger_window": {"start_utc": "2025-11-08T12:00:00Z", "end_utc": "2025-11-10T12:00:00Z"},
        "expected_effect": {
            "ugm3": -18.0,
            "ci_low": -31.0,
            "ci_high": -6.0,
            "basis_ref": "ledger.wards[ward_id=delhi_042].effect_ugm3",
        },
        "owner": "MCD",
        "advisory_langs": ["en", "hi"],
        "evidence_refs": [
            {
                "label": "24h forecast p90, delhi_042",
                "artifact": "forecast",
                "path": "forecast.wards[ward_id=delhi_042].series[h=24].pm25_p90",
                "value": 412.0,
                "resolved": True,
            },
            {
                "label": "biomass share, delhi_042",
                "artifact": "attribution",
                "path": "attribution.wards[ward_id=delhi_042].shares.biomass",
                "value": 0.55,
                "resolved": True,
            },
            {
                "label": "enforcement priority, delhi_042",
                "artifact": "enforcement",
                "path": "enforcement.ranked[ward_id=delhi_042].priority_score",
                "value": 88.0,
                "resolved": True,
            },
        ],
        "ledger_ref": {"stage_transition": "GRAP-II to GRAP-III"},
        "verifier": {"passed": True, "notes": ""},
    }
