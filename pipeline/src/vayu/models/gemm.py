"""GEMM mortality (Burnett et al. 2018, PNAS). Owner: vayu-models.

Global Exposure Mortality Model hazard-ratio function:

    HR(z) = exp( theta * log(1 + z / alpha) / (1 + exp(-(z - mu) / nu)) ),   z = max(0, PM2.5 - TMREL)

with the NCD+LRI (non-communicable disease + lower respiratory infection) combined,
China-inclusive, non-age-specific parameters. The attributable fraction is AF = (HR-1)/HR.
Avoided premature deaths from a PM2.5 reduction (GRAP) are the difference in attributable
deaths between the counterfactual (no intervention, higher PM2.5) and the actual level.

All outputs are labeled MODELED ESTIMATES. Reference: Burnett et al. (2018), "Global
estimates of mortality associated with long-term exposure to outdoor fine particulate
matter", PNAS 115(38), 9592-9597, doi:10.1073/pnas.1803222115.

DOCUMENTED PARAMETERS (published on /receipts + /about-data):
- GEMM NCD+LRI (with China): theta=0.1430, alpha=1.6, mu=15.5, nu=36.8 (Burnett 2018).
- TMREL (theoretical minimum-risk exposure): 2.4 ug/m3 (Burnett 2018 counterfactual).
- India adult (25+) all-cause baseline mortality rate: 9.0 per 1000 per year (documented
  assumption; refine with ward-specific rates when available).
- India adult (25+) population fraction: 0.66 (documented; per-ward age structure not
  available at this vintage).
"""

from __future__ import annotations

import math

TMREL = 2.4
GEMM_NCD_LRI = {"theta": 0.1430, "alpha": 1.6, "mu": 15.5, "nu": 36.8}
INDIA_ADULT_MORTALITY_PER_1000 = 9.0
ADULT_FRACTION = 0.66


def hazard_ratio(pm25: float, params: dict = GEMM_NCD_LRI) -> float:
    """GEMM hazard ratio at a PM2.5 concentration (ug/m3)."""
    z = max(0.0, pm25 - TMREL)
    theta, alpha, mu, nu = params["theta"], params["alpha"], params["mu"], params["nu"]
    return math.exp(theta * math.log(1.0 + z / alpha) / (1.0 + math.exp(-(z - mu) / nu)))


def attributable_fraction(pm25: float) -> float:
    hr = hazard_ratio(pm25)
    return (hr - 1.0) / hr


def avoided_deaths(pm_actual: float, pm_counterfactual: float, population: float, *,
                   baseline_per_1000: float = INDIA_ADULT_MORTALITY_PER_1000,
                   adult_fraction: float = ADULT_FRACTION) -> float:
    """Avoided premature deaths/year from lowering PM2.5 from counterfactual to actual.

    pm_counterfactual is the (higher) no-intervention level; pm_actual the (lower) achieved
    level. Positive result = lives saved; negative if the intervention worsened air.
    """
    pop_adult = population * adult_fraction
    af_delta = attributable_fraction(pm_counterfactual) - attributable_fraction(pm_actual)
    return pop_adult * (baseline_per_1000 / 1000.0) * af_delta


def avoided_exposure_pugh(delta_ugm3: float, population: float, hours: float) -> float:
    """Person-ug/m3-hours of exposure avoided (population * concentration reduction * hours)."""
    return population * abs(delta_ugm3) * hours


__all__ = ["hazard_ratio", "attributable_fraction", "avoided_deaths", "avoided_exposure_pugh",
           "TMREL", "GEMM_NCD_LRI", "INDIA_ADULT_MORTALITY_PER_1000", "ADULT_FRACTION"]
