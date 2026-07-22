"""CPCB AQI methodology tests (spec 5.0). Anchors from CPCB's own worked example."""

from __future__ import annotations

import math

import pytest

from vayu.aqi import (
    HEADLINE_LABEL,
    category_for_index,
    full_aqi,
    headline_subindex,
    sub_index,
    trailing_24h_mean,
)
from vayu.constants import AQI_CATEGORIES


class TestPm25Anchors:
    """CPCB documented example: PM2.5 sub-index = 51 at 31, 75 at 45, 100 at 60."""

    def test_cpcb_worked_example(self):
        assert sub_index("pm25", 31) == 51
        assert sub_index("pm25", 45) == 75
        assert sub_index("pm25", 60) == 100

    def test_band_endpoints(self):
        assert sub_index("pm25", 0) == 0
        assert sub_index("pm25", 30) == 50
        assert sub_index("pm25", 61) == 101
        assert sub_index("pm25", 90) == 200
        assert sub_index("pm25", 91) == 201
        assert sub_index("pm25", 120) == 300
        assert sub_index("pm25", 121) == 301
        assert sub_index("pm25", 250) == 400

    def test_severe_band_extrapolation_and_cap(self):
        # Documented VayuDrishti convention: index 500 reached at 380 ug/m3, then caps.
        assert sub_index("pm25", 380) == 500
        assert sub_index("pm25", 500) == 500
        assert sub_index("pm25", 900) == 500
        # Just inside Severe stays near 401, not jumping to 500.
        assert 401 <= sub_index("pm25", 260) <= 410

    def test_inter_band_gap_clamps_to_floor(self):
        # CPCB leaves a 1-unit gap (30 < c < 31); clamp to the band floor (51).
        assert sub_index("pm25", 30.5) == 51


class TestMissingAndInvalid:
    def test_none(self):
        assert sub_index("pm25", None) is None

    def test_nan(self):
        assert sub_index("pm25", float("nan")) is None

    def test_negative(self):
        assert sub_index("pm25", -5) is None

    def test_unknown_pollutant(self):
        with pytest.raises(KeyError):
            sub_index("radon", 10)


class TestOtherPollutants:
    def test_pm10_anchors(self):
        assert sub_index("pm10", 50) == 50
        assert sub_index("pm10", 100) == 100
        assert sub_index("pm10", 250) == 200
        assert sub_index("pm10", 430) == 400

    def test_no2_anchors(self):
        assert sub_index("no2", 40) == 50
        assert sub_index("no2", 80) == 100

    def test_co_uses_mg(self):
        assert sub_index("co", 1.0) == 50
        assert sub_index("co", 2.0) == 100


class TestCategories:
    def test_boundaries(self):
        assert category_for_index(50) == "Good"
        assert category_for_index(51) == "Satisfactory"
        assert category_for_index(100) == "Satisfactory"
        assert category_for_index(101) == "Moderate"
        assert category_for_index(200) == "Moderate"
        assert category_for_index(201) == "Poor"
        assert category_for_index(300) == "Poor"
        assert category_for_index(301) == "Very Poor"
        assert category_for_index(400) == "Very Poor"
        assert category_for_index(401) == "Severe"
        assert category_for_index(500) == "Severe"

    def test_categories_are_from_constants(self):
        for _, name in [(0, "Good"), (500, "Severe")]:
            pass
        assert set(AQI_CATEGORIES) == {
            "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe",
        }

    def test_missing(self):
        assert category_for_index(None) is None
        assert category_for_index(float("nan")) is None


class TestTrailing24hMean:
    def test_requires_16_valid(self):
        assert trailing_24h_mean([100.0] * 15) is None
        assert trailing_24h_mean([100.0] * 16) == 100.0

    def test_drops_missing(self):
        vals = [100.0] * 16 + [None, float("nan")]
        assert trailing_24h_mean(vals) == 100.0

    def test_uses_last_24(self):
        vals = [0.0] * 10 + [200.0] * 24
        assert trailing_24h_mean(vals) == 200.0


class TestHeadline:
    def test_label_and_shape(self):
        h = headline_subindex(45)
        assert h == {"subindex24h": 75, "category": "Satisfactory", "label": HEADLINE_LABEL}
        assert HEADLINE_LABEL == "PM2.5 sub-index (24h)"

    def test_missing(self):
        assert headline_subindex(None) is None


class TestFullAqi:
    def test_needs_three_pollutants(self):
        assert full_aqi({"pm25": 100, "no2": 50}) is None

    def test_needs_a_pm_species(self):
        # Three pollutants but no PM -> not eligible.
        assert full_aqi({"no2": 50, "so2": 50, "co": 1.0}) is None

    def test_worst_subindex_wins(self):
        out = full_aqi({"pm25": 250, "pm10": 100, "no2": 50})
        assert out is not None
        assert out["dominant_pollutant"] == "pm25"
        assert out["aqi"] == 400
        assert out["category"] == "Very Poor"

    def test_pm10_can_dominate(self):
        out = full_aqi({"pm25": 40, "pm10": 430, "no2": 50})
        assert out["dominant_pollutant"] == "pm10"
        assert out["aqi"] == 400
