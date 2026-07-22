"""Intervention event-study tests (spec 13, acceptance 15) on synthetic normalized series."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vayu.models.interventions import (
    block_bootstrap_ci,
    event_effect,
    load_grap_calendar,
    placebo_test,
)


def make_daily_with_step(drop_date: str = "2025-11-11", drop: float = -25.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-10-15", "2025-12-20", freq="D")
    base = 180.0 + rng.normal(0, 7, len(dates))
    dd = pd.Timestamp(drop_date)
    norm = base + np.where(dates >= dd, drop, 0.0)
    return pd.DataFrame({"date": dates.date, "pm25_normalized": norm})


class TestEventStudy:
    def test_detects_step_drop(self):
        daily = make_daily_with_step(drop=-25.0)
        eff = event_effect(daily, pd.Timestamp("2025-11-11"))
        assert eff < -10.0  # recovers roughly the injected -25 reduction

    def test_placebo_passes_for_real_drop(self):
        daily = make_daily_with_step(drop=-25.0)
        passed, pct = placebo_test(daily, pd.Timestamp("2025-11-11"), [pd.Timestamp("2025-11-11")])
        assert passed
        assert 0.0 <= pct <= 1.0

    def test_placebo_fails_for_no_effect(self):
        daily = make_daily_with_step(drop=0.0)  # no real intervention effect
        passed, _ = placebo_test(daily, pd.Timestamp("2025-11-11"), [pd.Timestamp("2025-11-11")])
        assert passed is False

    def test_bootstrap_ci_brackets_effect(self):
        daily = make_daily_with_step(drop=-25.0)
        lo, hi = block_bootstrap_ci(daily, pd.Timestamp("2025-11-11"))
        assert np.isfinite(lo) and np.isfinite(hi)
        assert lo <= hi


class TestRealCalendar:
    def test_parses_committed_grap_yaml(self):
        meta, entries = load_grap_calendar("delhi")
        assert meta["city"] == "delhi"
        assert len(entries) >= 4
        assert all(e["source_url"].startswith("http") for e in entries)
        assert any(e["stage"] == "GRAP-IV" for e in entries)
        # every entry has a real UTC start
        assert all(e["start_utc"] is not None for e in entries)
