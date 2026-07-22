"""Time conventions (spec 5.0, FROZEN).

- Storage is UTC ISO-8601 with a trailing ``Z``.
- CPCB / data.gov.in timestamps are naive IST and are converted at ingest.
- OpenAQ archive timestamps already carry an explicit offset (+05:30 for India).
- ALL calendar/diurnal features come from ``Asia/Kolkata`` local time.

India observes no DST, so the IST offset is a constant +05:30.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def ist_naive_to_utc(dt: datetime) -> datetime:
    """Localize a naive IST timestamp and return it as tz-aware UTC.

    Used for data.gov.in / CPCB snapshots, which report local clock time with no
    offset. Raises if given an already tz-aware datetime (caller confusion).
    """
    if dt.tzinfo is not None:
        raise ValueError("ist_naive_to_utc expects a naive datetime; got tz-aware")
    return dt.replace(tzinfo=IST).astimezone(UTC)


def to_utc(dt: datetime, *, assume: ZoneInfo = IST) -> datetime:
    """Return ``dt`` as tz-aware UTC.

    tz-aware inputs are converted; naive inputs are assumed to be in ``assume``
    (IST by default) then converted.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=assume)
    return dt.astimezone(UTC)


def parse_iso_to_utc(value: str) -> datetime:
    """Parse an ISO-8601 string (with or without offset) to tz-aware UTC.

    Accepts a trailing ``Z``. Offset-bearing strings (OpenAQ archive) convert
    directly; naive strings are treated as IST.
    """
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    return to_utc(dt)


def utc_iso_z(dt: datetime) -> str:
    """Format a datetime as UTC ISO-8601 with a trailing ``Z`` (storage form)."""
    dt = to_utc(dt) if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def calendar_features(ts_utc: datetime) -> dict[str, float | int]:
    """Diurnal/seasonal features derived from Asia/Kolkata local time (spec 5.1).

    ``ts_utc`` may be naive (assumed UTC) or tz-aware. Returns hour, day-of-week,
    month, day-of-year, weekend flag, and cyclical sin/cos encodings.
    """
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=UTC)
    local = ts_utc.astimezone(IST)
    hour = local.hour
    dow = local.weekday()  # Monday=0
    doy = local.timetuple().tm_yday
    return {
        "hour_ist": hour,
        "dow_ist": dow,
        "month_ist": local.month,
        "doy_ist": doy,
        "is_weekend": int(dow >= 5),
        "hour_sin": math.sin(2 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2 * math.pi * hour / 24.0),
        "doy_sin": math.sin(2 * math.pi * doy / 365.0),
        "doy_cos": math.cos(2 * math.pi * doy / 365.0),
    }
