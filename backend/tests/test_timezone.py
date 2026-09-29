"""Timezone and DST handling.

A one-hour error in the birth instant moves the Ascendant by about 15 degrees,
so these cases are as load-bearing as the ephemeris itself.
"""

from __future__ import annotations

from datetime import date, time

import pytest

from app.core.exceptions import ValidationFailed
from app.domain.astrology import BirthData
from app.domain.enums import HouseSystem
from app.services.timezone.service import (
    is_valid_timezone,
    timezone_for_coordinates,
    to_utc,
    utc_offset_hours,
)


def test_coordinates_resolve_to_iana_zones():
    assert timezone_for_coordinates(41.0082, 28.9784) == "Europe/Istanbul"
    assert timezone_for_coordinates(40.7128, -74.0060) == "America/New_York"
    assert timezone_for_coordinates(-33.8688, 151.2093) == "Australia/Sydney"


def test_istanbul_had_summer_time_in_1992():
    """Turkey observed DST in 1992 (UTC+3 in May) and froze at UTC+3 in 2016."""
    summer_1992 = to_utc(date(1992, 5, 14), time(14, 30), "Europe/Istanbul")
    winter_1992 = to_utc(date(1992, 1, 14), time(14, 30), "Europe/Istanbul")

    assert summer_1992.hour == 11  # UTC+3
    assert winter_1992.hour == 12  # UTC+2

    assert utc_offset_hours(date(1992, 5, 14), time(14, 30), "Europe/Istanbul") == 3.0
    assert utc_offset_hours(date(1992, 1, 14), time(14, 30), "Europe/Istanbul") == 2.0
    # Permanent UTC+3 since September 2016.
    assert utc_offset_hours(date(2026, 1, 14), time(14, 30), "Europe/Istanbul") == 3.0


def test_us_daylight_saving_transition():
    standard = to_utc(date(2026, 1, 15), time(12, 0), "America/New_York")
    daylight = to_utc(date(2026, 7, 15), time(12, 0), "America/New_York")
    assert standard.hour == 17  # UTC-5
    assert daylight.hour == 16  # UTC-4


def test_time_inside_a_dst_gap_is_shifted_forward():
    """2026-03-08 02:30 never existed in New York; it must not silently pass."""
    resolved = to_utc(date(2026, 3, 8), time(2, 30), "America/New_York")
    # 03:30 EDT == 07:30 UTC
    assert resolved.hour == 7
    assert resolved.minute == 30


def test_ambiguous_time_resolves_to_the_first_occurrence():
    """2026-11-01 01:30 happens twice; birth records mean the first one."""
    resolved = to_utc(date(2026, 11, 1), time(1, 30), "America/New_York")
    assert resolved.hour == 5  # EDT (-4), not EST (-5)


def test_unknown_timezone_is_rejected():
    assert not is_valid_timezone("Mars/Olympus_Mons")
    with pytest.raises(ValidationFailed):
        to_utc(date(2000, 1, 1), time(12, 0), "Mars/Olympus_Mons")


def test_birth_data_keeps_local_and_utc_separate():
    birth = BirthData(
        birth_date=date(1992, 5, 14),
        birth_time=time(14, 30),
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        house_system=HouseSystem.PLACIDUS,
    )
    assert birth.local_datetime.hour == 14
    assert birth.utc_datetime.hour == 11
    assert birth.utc_offset_hours == 3.0
    assert birth.can_compute_houses


def test_unknown_birth_time_falls_back_to_noon_without_houses():
    birth = BirthData(
        birth_date=date(1992, 5, 14),
        birth_time=None,
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
    )
    assert birth.local_datetime.hour == 12
    assert not birth.time_known
    assert not birth.can_compute_houses
