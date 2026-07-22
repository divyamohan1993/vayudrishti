"""Upwind FIRMS sector (spec 5.0). Backs acceptance 10 (stubble bearing)."""

from datetime import datetime, timedelta, timezone

from vayu import upwind

UTC = timezone.utc


def test_haversine_known_distance():
    # Delhi (28.6,77.2) to a point ~88 km NW.
    d = upwind.haversine_km(28.6, 77.2, 29.2, 76.6)
    assert 85 < d < 92


def test_bearing_cardinals():
    assert abs(upwind.initial_bearing_deg(0, 0, 1, 0) - 0) < 1e-6  # due north
    assert abs(upwind.initial_bearing_deg(0, 0, 0, 1) - 90) < 1e-6  # due east


def test_angular_diff_wraps():
    assert upwind.angular_diff_deg(350, 10) == 20
    assert upwind.angular_diff_deg(10, 350) == 20
    assert upwind.angular_diff_deg(0, 180) == 180


def test_nw_stubble_in_se_out():
    # Wind FROM 315 deg (NW). NW fire within range is upwind; SE fire is not.
    assert upwind.is_upwind(28.6, 77.2, 29.2, 76.6, 315.0) is True
    assert upwind.is_upwind(28.6, 77.2, 28.1, 77.6, 315.0) is False


def test_distance_cap_excludes_far_fire():
    # Correct bearing (NW) but ~230 km away -> excluded by the 100 km cap.
    assert upwind.is_upwind(28.6, 77.2, 30.5, 75.5, 315.0) is False


def test_aggregate_trailing_window_and_sector():
    now = datetime(2025, 11, 5, 6, 0, tzinfo=UTC)
    fires = [
        {"lat": 29.2, "lon": 76.6, "frp": 12.0, "acq_utc": now - timedelta(hours=3)},  # NW, in
        {"lat": 29.0, "lon": 76.7, "frp": 8.0, "acq_utc": now - timedelta(hours=20)},  # NW, in
        {"lat": 28.1, "lon": 77.6, "frp": 50.0, "acq_utc": now - timedelta(hours=1)},  # SE, out
        {"lat": 29.2, "lon": 76.6, "frp": 99.0, "acq_utc": now - timedelta(hours=30)},  # too old
    ]
    frp, count = upwind.upwind_aggregate(28.6, 77.2, 315.0, fires, now)
    assert count == 2
    assert frp == 20.0
