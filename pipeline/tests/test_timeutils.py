"""IST<->UTC conversion and calendar features (spec 5.0 boundary test)."""

from datetime import datetime, timezone

from vayu import timeutils


def test_ist_midnight_maps_to_prior_day_1830_utc():
    # The frozen boundary case: IST 00:00 -> 18:30 UTC on the previous day.
    utc = timeutils.ist_naive_to_utc(datetime(2025, 2, 1, 0, 0, 0))
    assert timeutils.utc_iso_z(utc) == "2025-01-31T18:30:00Z"


def test_no_dst_offset_is_constant_across_seasons():
    winter = timeutils.ist_naive_to_utc(datetime(2025, 1, 15, 12, 0, 0))
    summer = timeutils.ist_naive_to_utc(datetime(2025, 6, 15, 12, 0, 0))
    # 12:00 IST is always 06:30 UTC; India has no daylight saving.
    assert winter.strftime("%H:%M") == "06:30"
    assert summer.strftime("%H:%M") == "06:30"


def test_ist_naive_to_utc_rejects_aware():
    aware = datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)
    try:
        timeutils.ist_naive_to_utc(aware)
    except ValueError:
        return
    raise AssertionError("expected ValueError for tz-aware input")


def test_parse_offset_iso_matches_openaq_archive():
    # OpenAQ archive datetime for an Indian station: +05:30 offset.
    dt = timeutils.parse_iso_to_utc("2025-02-01T01:00:00+05:30")
    assert timeutils.utc_iso_z(dt) == "2025-01-31T19:30:00Z"


def test_parse_iso_with_z():
    dt = timeutils.parse_iso_to_utc("2025-02-01T05:30:00Z")
    assert timeutils.utc_iso_z(dt) == "2025-02-01T05:30:00Z"


def test_calendar_features_use_ist_local_time():
    # 2025-11-15 18:30 UTC == 2025-11-16 00:00 IST -> hour 0, next day.
    ts = datetime(2025, 11, 15, 18, 30, tzinfo=timezone.utc)
    f = timeutils.calendar_features(ts)
    assert f["hour_ist"] == 0
    assert f["month_ist"] == 11
    # 2025-11-16 is a Sunday.
    assert f["dow_ist"] == 6
    assert f["is_weekend"] == 1
