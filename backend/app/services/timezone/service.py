"""Timezone resolution for birth data.

Birth charts live or die on this: a one hour error moves the Ascendant by
roughly 15 degrees. Rules:

* the IANA zone is resolved from the birth *coordinates* (offline lookup),
* the local birth datetime is interpreted with that zone, which applies the
  historical DST rules of the birth year (``zoneinfo`` ships the full tzdata
  history),
* everything is stored and computed in UTC.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timezonefinder import TimezoneFinder

from app.core.exceptions import ValidationFailed


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    # The lookup table is ~40 MB in memory; one instance per process.
    return TimezoneFinder(in_memory=True)


def timezone_for_coordinates(latitude: float, longitude: float) -> str | None:
    """IANA zone name for a coordinate pair, or ``None`` over open water."""
    return _finder().timezone_at(lat=latitude, lng=longitude)


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def to_utc(local_date: date, local_time: time | None, timezone_name: str) -> datetime:
    """Local birth date/time -> UTC instant, DST aware.

    Times that fall inside a DST gap (the clock skipped them) are shifted
    forward by the gap; ambiguous times (clock repeated) resolve to the first,
    pre-transition occurrence, which matches how birth certificates are read.
    """
    if not is_valid_timezone(timezone_name):
        raise ValidationFailed(
            "Unknown timezone.", details={"timezone": timezone_name}
        )
    zone = ZoneInfo(timezone_name)
    naive = datetime.combine(local_date, local_time or time(12, 0))
    aware = naive.replace(tzinfo=zone, fold=0)

    # Detect a non-existent local time: re-deriving the local time from the
    # UTC instant gives a different wall clock.
    round_trip = aware.astimezone(ZoneInfo("UTC")).astimezone(zone)
    if round_trip.replace(tzinfo=None) != naive:
        aware = (naive + timedelta(hours=1)).replace(tzinfo=zone, fold=0)

    return aware.astimezone(ZoneInfo("UTC"))


def utc_offset_hours(local_date: date, local_time: time | None, timezone_name: str) -> float:
    zone = ZoneInfo(timezone_name)
    moment = datetime.combine(local_date, local_time or time(12, 0), tzinfo=zone)
    offset = moment.utcoffset()
    return 0.0 if offset is None else offset.total_seconds() / 3600.0
