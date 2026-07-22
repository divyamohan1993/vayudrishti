"""Single source of truth for category strings and controlled vocabularies (spec 5.0).

Every emitted category, confidence tier, risk level, source label, and enforcement
action comes from here. vayu-web mirrors these verbatim in its display-label maps,
``config/schemas/*.json`` enumerate the same literals, and the pydantic content gate
validates emitted strings against them. Changing a literal here is a contract change:
edit the schema and SendMessage consumers in the same commit (spec 8).
"""

from __future__ import annotations

# CPCB National AQI categories, ascending severity. FROZEN, byte-identical everywhere.
AQI_CATEGORIES: tuple[str, ...] = (
    "Good",
    "Satisfactory",
    "Moderate",
    "Poor",
    "Very Poor",
    "Severe",
)

# Confidence tier (spec 5.0), used identically across nowcast/forecast/attribution/enforcement.
CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "med", "low")

# Attribution / enforcement dominant-source labels ("mixed" = no single dominant source).
SOURCE_LABELS: tuple[str, ...] = (
    "traffic",
    "industry",
    "biomass",
    "dust",
    "residential_other",
    "mixed",
)

# Attribution share keys (must sum ~1.0). Excludes "mixed", which is a dominant label only.
SHARE_KEYS: tuple[str, ...] = (
    "traffic",
    "industry",
    "biomass",
    "dust",
    "residential_other",
)

# Advisory risk levels (spec 5.5), ascending severity.
RISK_LEVELS: tuple[str, ...] = ("low", "moderate", "high", "severe")

# Enforcement action taxonomy (spec 5.4, FIXED). These are i18n keys, not display text;
# vayu-web owns the en/hi/mr labels. Ordered roughly by dominant source they map to.
ENFORCEMENT_ACTIONS: tuple[str, ...] = (
    "deploy_water_sprinkling",
    "halt_construction_dust",
    "intensify_mechanized_sweeping",
    "reroute_divert_heavy_traffic",
    "inspect_industrial_emissions",
    "ban_open_biomass_burning",
    "issue_public_health_advisory",
    "monitor_no_action",
)

# City tiers. Config uses "config_only" (underscore); the web manifest uses the
# hyphenated "config-only". Map at publish time (see publish.manifest).
TIER_CONFIG_TO_MANIFEST: dict[str, str] = {
    "deep": "deep",
    "standard": "standard",
    "config_only": "config-only",
    "config-only": "config-only",
}

__all__ = [
    "AQI_CATEGORIES",
    "CONFIDENCE_LEVELS",
    "SOURCE_LABELS",
    "SHARE_KEYS",
    "RISK_LEVELS",
    "ENFORCEMENT_ACTIONS",
    "TIER_CONFIG_TO_MANIFEST",
]
