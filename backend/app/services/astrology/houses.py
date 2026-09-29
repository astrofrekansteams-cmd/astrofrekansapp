"""Chart angles and house systems.

Angles come from spherical trigonometry on the Right Ascension of the
Midheaven (RAMC). Placidus cusps come from the classic trisection of the
diurnal and nocturnal semi-arcs, solved iteratively.

References: Jean Meeus, *Astronomical Algorithms* (ch. 12-13) for sidereal
time and coordinate conversion; the standard Placidus derivation for the
intermediate cusps.

Placidus (and Koch) are undefined inside the polar circles. Above
|latitude| = 66 degrees the engine falls back to Whole Sign and reports which
system it actually used, instead of returning silently wrong cusps.
"""

from __future__ import annotations

import math

from app.domain.astrology import ChartAngles, HousePosition, normalize_degrees
from app.domain.enums import HouseSystem

OBLIQUITY_J2000 = 23.4392911
PLACIDUS_LATITUDE_LIMIT = 66.0


def obliquity_of_ecliptic(julian_centuries: float) -> float:
    """Mean obliquity of the ecliptic in degrees (Meeus 22.2)."""
    t = julian_centuries
    return 23.43929111 - (46.8150 * t + 0.00059 * t**2 - 0.001813 * t**3) / 3600.0


def _ra_to_ecliptic_longitude(ra_degrees: float, obliquity: float) -> float:
    """Ecliptic longitude of the ecliptic point whose RA is ``ra_degrees``."""
    ra = math.radians(normalize_degrees(ra_degrees))
    eps = math.radians(obliquity)
    return normalize_degrees(
        math.degrees(math.atan2(math.sin(ra), math.cos(ra) * math.cos(eps)))
    )


def _declination_of_ecliptic_point(longitude: float, obliquity: float) -> float:
    """Declination of a point on the ecliptic, in degrees."""
    return math.degrees(
        math.asin(math.sin(math.radians(obliquity)) * math.sin(math.radians(longitude)))
    )


def midheaven_longitude(ramc_degrees: float, obliquity: float) -> float:
    """The MC is simply the ecliptic point culminating at the RAMC."""
    return _ra_to_ecliptic_longitude(ramc_degrees, obliquity)


def ascendant_longitude(ramc_degrees: float, latitude: float, obliquity: float) -> float:
    """Ecliptic longitude of the Ascendant.

    Sanity checks baked into the tests: at the equator with RAMC = 0 the
    Ascendant is 0 Cancer (90 degrees); it moves later in Cancer as latitude
    increases.
    """
    ramc = math.radians(normalize_degrees(ramc_degrees))
    eps = math.radians(obliquity)
    phi = math.radians(max(-89.9, min(89.9, latitude)))

    y = math.cos(ramc)
    x = -(math.sin(ramc) * math.cos(eps) + math.tan(phi) * math.sin(eps))
    return normalize_degrees(math.degrees(math.atan2(y, x)))


def compute_angles(
    ramc_degrees: float, latitude: float, obliquity: float = OBLIQUITY_J2000
) -> ChartAngles:
    return ChartAngles(
        ascendant=ascendant_longitude(ramc_degrees, latitude, obliquity),
        midheaven=midheaven_longitude(ramc_degrees, obliquity),
    )


def _semi_arc(declination: float, latitude: float) -> tuple[float, float]:
    """Diurnal and nocturnal semi-arcs (degrees) of a point.

    ``acos`` is clamped so circumpolar points degrade gracefully instead of
    raising.
    """
    value = -math.tan(math.radians(latitude)) * math.tan(math.radians(declination))
    value = max(-1.0, min(1.0, value))
    diurnal = math.degrees(math.acos(value))
    return diurnal, 180.0 - diurnal


def _placidus_cusp(
    *, house: int, ramc_degrees: float, latitude: float, obliquity: float
) -> float:
    """Intermediate Placidus cusp (11, 12, 2 or 3).

    Trisection of the semi-arcs:

    * cusp 11: RA = RAMC + 1/3 of the diurnal semi-arc
    * cusp 12: RA = RAMC + 2/3 of the diurnal semi-arc
    * cusp 2 : RA = RAMC + 180 - 2/3 of the nocturnal semi-arc
    * cusp 3 : RA = RAMC + 180 - 1/3 of the nocturnal semi-arc

    The semi-arc depends on the declination of the cusp itself, so the
    equation is solved by fixed-point iteration (converges in a few steps
    outside the polar circles).
    """
    offsets = {11: 30.0, 12: 60.0, 2: 120.0, 3: 150.0}
    ra = normalize_degrees(ramc_degrees + offsets[house])

    for _ in range(60):
        longitude = _ra_to_ecliptic_longitude(ra, obliquity)
        declination = _declination_of_ecliptic_point(longitude, obliquity)
        diurnal, nocturnal = _semi_arc(declination, latitude)

        if house == 11:
            candidate = ramc_degrees + diurnal / 3.0
        elif house == 12:
            candidate = ramc_degrees + 2.0 * diurnal / 3.0
        elif house == 2:
            candidate = ramc_degrees + 180.0 - 2.0 * nocturnal / 3.0
        else:  # house 3
            candidate = ramc_degrees + 180.0 - nocturnal / 3.0

        candidate = normalize_degrees(candidate)
        if abs(signed_delta(candidate, ra)) < 1e-9:
            ra = candidate
            break
        ra = candidate

    return _ra_to_ecliptic_longitude(ra, obliquity)


def signed_delta(a: float, b: float) -> float:
    diff = (a - b) % 360.0
    return diff - 360.0 if diff > 180.0 else diff


def compute_houses(
    *,
    system: HouseSystem,
    ramc_degrees: float,
    latitude: float,
    angles: ChartAngles,
    obliquity: float = OBLIQUITY_J2000,
) -> tuple[list[HousePosition], HouseSystem]:
    """Twelve cusps plus the system actually used."""
    effective = system
    if system in (HouseSystem.PLACIDUS, HouseSystem.KOCH) and abs(latitude) >= (
        PLACIDUS_LATITUDE_LIMIT
    ):
        effective = HouseSystem.WHOLE_SIGN

    if effective == HouseSystem.WHOLE_SIGN:
        start = float(int(angles.ascendant // 30) * 30)
        cusps = [normalize_degrees(start + 30.0 * index) for index in range(12)]
    elif effective == HouseSystem.EQUAL:
        cusps = [
            normalize_degrees(angles.ascendant + 30.0 * index) for index in range(12)
        ]
    else:
        # Koch is not implemented yet; it falls back to Placidus geometry.
        eleven = _placidus_cusp(
            house=11, ramc_degrees=ramc_degrees, latitude=latitude, obliquity=obliquity
        )
        twelve = _placidus_cusp(
            house=12, ramc_degrees=ramc_degrees, latitude=latitude, obliquity=obliquity
        )
        two = _placidus_cusp(
            house=2, ramc_degrees=ramc_degrees, latitude=latitude, obliquity=obliquity
        )
        three = _placidus_cusp(
            house=3, ramc_degrees=ramc_degrees, latitude=latitude, obliquity=obliquity
        )
        cusps = [
            angles.ascendant,  # 1
            two,  # 2
            three,  # 3
            angles.imum_coeli,  # 4
            normalize_degrees(eleven + 180.0),  # 5 (opposite 11)
            normalize_degrees(twelve + 180.0),  # 6 (opposite 12)
            angles.descendant,  # 7
            normalize_degrees(two + 180.0),  # 8
            normalize_degrees(three + 180.0),  # 9
            angles.midheaven,  # 10
            eleven,  # 11
            twelve,  # 12
        ]
        effective = HouseSystem.PLACIDUS

    return (
        [
            HousePosition(number=index + 1, cusp_longitude=cusp)
            for index, cusp in enumerate(cusps)
        ],
        effective,
    )


def house_of(longitude: float, houses: list[HousePosition]) -> int | None:
    """Which house a longitude falls in, honouring wrap-around cusps."""
    if not houses:
        return None
    ordered = sorted(houses, key=lambda house: house.number)
    for index, house in enumerate(ordered):
        start = house.cusp_longitude
        end = ordered[(index + 1) % 12].cusp_longitude
        span = (end - start) % 360.0
        offset = (longitude - start) % 360.0
        if span > 0 and offset < span:
            return house.number
    return None
