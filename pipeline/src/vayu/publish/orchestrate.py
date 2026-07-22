"""Full publish orchestration (acceptance 1). Owner: vayu-models.

`vayu publish --city X` runs every producer the city's tier warrants, in dependency order,
then re-gates the result. Deep (Delhi): nowcast, forecast, attribution, enforcement,
advisories, interventions+ledger, replay. Standard/config-only (Mumbai, Bengaluru): nowcast,
forecast, advisories. Global receipts (Delhi-validated) + manifest close every run. Producers
construct pydantic content models, so nothing invalid reaches disk; the final gate is defence
in depth. Receipts read the cached `vayu train` metrics (validation runs on its own cadence).
"""

from __future__ import annotations

from vayu.cityconfig import load_city, resolve_cities
from vayu.logging_setup import get_logger
from vayu.publish import (
    advisories_build,
    attribution_build,
    enforcement_build,
    forecast_build,
    ledger_build,
    manifest_build,
    nowcast_build,
    receipts_build,
    replay_build,
)
from vayu.publish.gate import run_gate

log = get_logger("publish")


def publish_city(city: str) -> None:
    """Publish one city's surfaces in dependency order (advisories after nowcast;
    enforcement after attribution)."""
    tier = load_city(city).tier
    log.info("publish.city.start", city=city, tier=tier)
    nowcast_build.publish(city)
    forecast_build.publish(city)
    if tier == "deep":
        attribution_build.publish(city)      # before enforcement (source label)
        enforcement_build.publish(city)
    advisories_build.publish(city)           # after nowcast (risk)
    if tier == "deep":
        ledger_build.publish(city)           # interventions.json + ledger.json
        replay_build.publish(city)           # Nov-2025 out-of-fold
    log.info("publish.city.done", city=city)


def run(city_arg: str) -> int:
    cities = resolve_cities(city_arg)
    for city in cities:
        publish_city(city)
    # Global surfaces: receipts (Delhi-validated deep city) + manifest index.
    if "delhi" in cities:
        receipts_build.publish("delhi")
    manifest_build.publish()
    rc = run_gate(city="all", data_root=None)
    log.info("publish.complete", cities=cities, gate_ok=(rc == 0))
    return rc


__all__ = ["publish_city", "run"]
