"""Attribution CPF + directional-validation tests (spec 5.3, acceptance 10)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vayu.models.attribution import (
    confidence_for_shares,
    cpf,
    directional_checks,
    peak_bearing,
    ward_shares,
)
from vayu.publish.contentmodels import Shares


def make_station_df(bearing_hot: float = 315.0, n: int = 2400, sid: str = "s1", seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    wind_dir = rng.uniform(0, 360, n)
    dtheta = np.abs((wind_dir - bearing_hot + 180) % 360 - 180)
    boost = np.where(dtheta < 30, 160.0, 0.0)  # high PM when wind FROM the hot bearing
    pm25 = 80 + boost + rng.normal(0, 20, n)
    return pd.DataFrame({"station_id": sid, "wind_dir_10m": wind_dir, "pm25": pm25})


class TestCpf:
    def test_peaks_at_injected_bearing(self):
        df = make_station_df(bearing_hot=315.0)
        vals = cpf(df["wind_dir_10m"].to_numpy(), df["pm25"].to_numpy())
        pk = peak_bearing(vals)
        assert pk is not None
        # peak within one 30-degree sector of the injected NW source bearing
        assert min(abs(pk - 315.0), 360 - abs(pk - 315.0)) <= 30.0

    def test_all_nan_when_empty(self):
        vals = cpf(np.array([]), np.array([]))
        assert np.all(np.isnan(vals))
        assert peak_bearing(vals) is None


class TestDirectionalChecks:
    def test_nw_stubble_check_passes_in_season(self):
        df = pd.concat([make_station_df(315.0, sid="s1", seed=1),
                        make_station_df(300.0, sid="s2", seed=2)], ignore_index=True)
        checks = directional_checks(df, in_stubble_season=True)
        nw = [c for c in checks if "NW stubble" in c["check_name"]]
        assert nw and nw[0]["pass"] is True

    def test_off_season_skips_nw_check(self):
        df = make_station_df(315.0)
        checks = directional_checks(df, in_stubble_season=False)
        assert not any("NW stubble" in c["check_name"] for c in checks)


class TestWardShares:
    def test_shares_sum_to_one_and_gate_valid(self):
        shares = ward_shares(road_density=0.6, builtup_frac=0.7, industrial_dist_km=1.5,
                             frp_upwind=120.0, cpf_nw=0.5, cpf_industrial=0.2)
        assert abs(sum(shares.values()) - 1.0) <= 0.02
        assert all(0.0 <= v <= 1.0 for v in shares.values())
        Shares(**shares)  # must satisfy the content-gate model (sum ~1)

    def test_confidence_tiers(self):
        assert confidence_for_shares({"traffic": 0.5, "industry": 0.2, "biomass": 0.1,
                                      "dust": 0.1, "residential_other": 0.1}) == "high"
